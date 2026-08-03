"""Layered title resolution: arXiv API, then PDF metadata, then page layout."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .naming import parse_arxiv_id, strip_version
from .sources import pdf_text
from .sources.arxiv_api import ArxivAPIError, fetch_titles


class Source(str, Enum):
    API = "api"
    METADATA = "metadata"
    LAYOUT = "layout"

    @property
    def is_confident(self) -> bool:
        """Layout-derived titles are guesses and need confirmation before renaming."""
        return self is not Source.LAYOUT


@dataclass
class Resolution:
    path: Path
    arxiv_id: str
    title: str | None = None
    source: Source | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.title is not None

    @property
    def is_confident(self) -> bool:
        return self.source is not None and self.source.is_confident


def resolve_titles(
    paths: Iterable[Path], *, use_api: bool = True
) -> tuple[list[Resolution], str | None]:
    """Resolve a title for each path.

    Returns the resolutions alongside a warning describing why the API layer was
    skipped, if it was. The API lookup is issued once for the whole batch rather than
    per file, so a directory of a hundred papers costs a single request.
    """
    resolutions = [_new_resolution(path) for path in paths]
    pending = [r for r in resolutions if r.error is None]

    api_titles: dict[str, str] = {}
    warning: str | None = None
    if use_api and pending:
        try:
            api_titles = fetch_titles(r.arxiv_id for r in pending)
        except ArxivAPIError as exc:
            warning = f"{exc} — falling back to PDF extraction"

    for resolution in pending:
        _fill(resolution, api_titles)
    return resolutions, warning


def _new_resolution(path: Path) -> Resolution:
    arxiv_id = parse_arxiv_id(path.stem)
    if arxiv_id is None:
        return Resolution(path=path, arxiv_id="", error="filename is not an arXiv ID")
    if not path.is_file():
        return Resolution(path=path, arxiv_id=arxiv_id, error="not a file")
    return Resolution(path=path, arxiv_id=arxiv_id)


def _fill(resolution: Resolution, api_titles: dict[str, str]) -> None:
    title = api_titles.get(strip_version(resolution.arxiv_id))
    if title:
        resolution.title, resolution.source = title, Source.API
        return

    for source, extract in (
        (Source.METADATA, pdf_text.title_from_metadata),
        (Source.LAYOUT, pdf_text.title_from_layout),
    ):
        title = extract(resolution.path)
        if title:
            resolution.title, resolution.source = title, source
            return

    resolution.error = "no title found in API, PDF metadata, or page layout"


def collect_pdfs(paths: Sequence[Path], *, recursive: bool = False) -> list[Path]:
    """Expand CLI arguments into a sorted list of candidate PDFs.

    Explicit file arguments are kept as given so the user gets a clear error for a file
    they named directly; directory scans keep only arXiv-shaped PDFs.
    """
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            found.extend(
                p
                for p in sorted(path.glob(pattern))
                if p.is_file() and parse_arxiv_id(p.stem)
            )
        else:
            found.append(path)
    return list(dict.fromkeys(found))
