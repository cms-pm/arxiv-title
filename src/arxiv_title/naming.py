"""arXiv identifier recognition and title -> filename slugging."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# Post-2007 identifiers: 2101.05536, 2101.05536v1. The 4-digit YYMM is followed by a
# 4- or 5-digit sequence number (arXiv widened it to 5 in 2015).
MODERN_RE = re.compile(r"(?P<id>\d{4}\.\d{4,5})(?P<ver>v\d+)?", re.ASCII)

# Pre-2007 identifiers: math.GT/0309136, hep-th/9901001. The slash cannot appear in a
# filename, so accept the underscore form these get saved as locally.
LEGACY_RE = re.compile(
    r"(?P<archive>[a-z-]+(?:\.[A-Z]{2})?)[_/](?P<num>\d{7})(?P<ver>v\d+)?"
)

# Longest filename we will produce. The POSIX limit is 255 bytes; leaving headroom means
# a downstream copy that appends " (1)" or a sync suffix still fits.
MAX_FILENAME_BYTES = 200

# LaTeX fragments that survive into arXiv metadata often enough to be worth stripping.
_LATEX_COMMAND_RE = re.compile(r"\\[a-zA-Z]+\s*")
_MATH_RE = re.compile(r"\$[^$]*\$")


def parse_arxiv_id(stem: str) -> str | None:
    """Return the arXiv ID (with version, if present) at the start of ``stem``.

    Anchored at the start so that an already-renamed file such as
    ``2101.05536v1_scaling_equilibrium_propagation.pdf`` still resolves to its ID,
    which is what makes a second run idempotent. A digit sequence buried in the middle
    of an unrelated filename is deliberately not matched.
    """
    for pattern in (MODERN_RE, LEGACY_RE):
        match = pattern.match(stem)
        if match:
            return match.group(0)
    return None


def strip_version(arxiv_id: str) -> str:
    """``2101.05536v1`` -> ``2101.05536``. The API keys results by the bare ID."""
    return re.sub(r"v\d+$", "", arxiv_id)


def slugify(title: str, max_bytes: int = MAX_FILENAME_BYTES) -> str:
    """Turn a paper title into a lowercase underscore-separated filename component."""
    text = _MATH_RE.sub(" ", title)
    text = _LATEX_COMMAND_RE.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ")

    # Atom <title> values are hard-wrapped with newlines and indentation.
    text = re.sub(r"\s+", " ", text).strip()

    # Fold accents so "Schrödinger" -> "schrodinger" rather than losing the character.
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")

    return _truncate_at_word(text, max_bytes)


def _truncate_at_word(slug: str, max_bytes: int) -> str:
    """Cut ``slug`` to ``max_bytes``, preferring an underscore boundary."""
    if len(slug.encode()) <= max_bytes:
        return slug
    cut = slug.encode()[:max_bytes].decode(errors="ignore")
    if "_" in cut:
        cut = cut.rsplit("_", 1)[0]
    return cut.strip("_")


def target_name(
    arxiv_id: str, title: str, *, id_prefix: bool = True, suffix: str = ".pdf"
) -> str:
    """Build the destination filename for a paper."""
    slug = slugify(title, MAX_FILENAME_BYTES - len(arxiv_id) - len(suffix) - 1)
    if not slug:
        raise ValueError(f"title produced an empty slug: {title!r}")
    if id_prefix:
        return f"{arxiv_id}_{slug}{suffix}"
    return f"{slug}{suffix}"


def is_arxiv_pdf(path: Path) -> bool:
    """True if ``path`` is a PDF whose name starts with an arXiv identifier."""
    return path.suffix.lower() == ".pdf" and parse_arxiv_id(path.stem) is not None
