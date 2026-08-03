"""Canonical titles from the arXiv Atom API.

This is the most reliable source by a wide margin: the filename *is* the identifier, so
no text extraction is involved and the title comes back exactly as arXiv records it.
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable

import httpx

from ..naming import strip_version

API_URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"

# arXiv accepts up to 100 ids per id_list query, and asks for a 3s gap between calls.
BATCH_SIZE = 100
BATCH_DELAY_SECONDS = 3.0
TIMEOUT_SECONDS = 20.0


class ArxivAPIError(RuntimeError):
    """The API could not be reached or returned something unparseable."""


def fetch_titles(
    ids: Iterable[str], *, client: httpx.Client | None = None
) -> dict[str, str]:
    """Look up titles for ``ids``, keyed by version-stripped arXiv ID.

    IDs the API does not know are simply absent from the result, letting the caller
    fall back to a PDF-derived title. Network failures raise :class:`ArxivAPIError`.
    """
    bare_ids = list(dict.fromkeys(strip_version(i) for i in ids))
    if not bare_ids:
        return {}

    titles: dict[str, str] = {}
    owns_client = client is None
    client = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=True)
    try:
        batches = [
            bare_ids[i : i + BATCH_SIZE] for i in range(0, len(bare_ids), BATCH_SIZE)
        ]
        for index, batch in enumerate(batches):
            if index:
                time.sleep(BATCH_DELAY_SECONDS)
            titles.update(_fetch_batch(client, batch))
    finally:
        if owns_client:
            client.close()
    return titles


def _fetch_batch(client: httpx.Client, batch: list[str]) -> dict[str, str]:
    params = {"id_list": ",".join(batch), "max_results": str(len(batch))}
    try:
        response = client.get(API_URL, params=params)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ArxivAPIError(f"arXiv API request failed: {exc}") from exc
    return parse_feed(response.text)


def parse_feed(xml_text: str) -> dict[str, str]:
    """Extract ``{bare_id: title}`` from an arXiv Atom feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ArxivAPIError(f"could not parse arXiv API response: {exc}") from exc

    titles: dict[str, str] = {}
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = (entry.findtext(f"{ATOM}id") or "").strip()
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        if not entry_id or not title:
            continue
        # A lookup miss comes back as an entry whose id points at the api/errors doc
        # and whose title is literally "Error". Skip it so the caller falls through.
        if "api/errors" in entry_id or title == "Error":
            continue
        bare = strip_version(entry_id.rstrip("/").rsplit("/", 1)[-1])
        titles[bare] = title
    return titles
