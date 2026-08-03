"""Offline title extraction from the PDF itself.

Two independent attempts, in order of trustworthiness:

* ``title_from_metadata`` reads the document's ``/Title`` entry. Cheap and correct
  whenever the LaTeX toolchain filled it in, which is most of the time.
* ``title_from_layout`` falls back to typography: the title is the first block of
  noticeably-larger-than-body text near the top of page one.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

# Shorter than this and it is a section marker, a drop cap, or a journal banner.
MIN_TITLE_CHARS = 10

# Title text must be at least this much larger than body text to count.
SIZE_RATIO = 1.15

# Words are grouped into a line if their baselines fall within this many points.
LINE_TOLERANCE_PT = 3.0

# Minimum horizontal gap, in points, that counts as a word space. ``extract_words``
# splits a run wherever the font size changes as well as wherever there is a gap, so a
# small-caps title emits "T" and "HE" as separate words that must be rejoined. Measured
# across the sample corpus, attribute-only splits gap by under 1pt while genuine spaces
# gap by 4pt or more, so the threshold sits comfortably between the two.
SPACE_GAP_PT = 2.0

# Titles live at the top of the page; figure captions further down do not qualify.
TOP_FRACTION = 0.45

# /Title values that are placeholders rather than real titles.
_JUNK_TITLE_RE = re.compile(
    r"^\s*(untitled|unknown|microsoft word.*|.*\.(pdf|dvi|tex|ps|doc|docx))\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _Line:
    top: float
    size: float
    text: str


def title_from_metadata(path: Path) -> str | None:
    """Return the PDF's ``/Title`` if it looks like a real title."""
    try:
        with pdfplumber.open(path) as pdf:
            raw = pdf.metadata.get("Title")
    except Exception:
        return None
    return _clean_candidate(raw)


def title_from_layout(path: Path) -> str | None:
    """Infer the title from font sizes on the first page."""
    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                return None
            page = pdf.pages[0]
            lines = _page_lines(page)
            page_height = page.height
    except Exception:
        return None

    if not lines:
        return None

    body_size = statistics.median(line.size for line in lines)
    threshold = body_size * SIZE_RATIO
    cutoff = page_height * TOP_FRACTION

    block = _first_large_block(lines, threshold, cutoff)
    return _clean_candidate(" ".join(line.text for line in block))


def _page_lines(page: pdfplumber.page.Page) -> list[_Line]:
    """Group page words into lines, each tagged with its dominant font size.

    Two details make this work on real LaTeX output:

    * Words are clustered by *baseline*, not by ``top``. In a small-caps title the full
      capitals are set larger than the small capitals, so their tops differ by several
      points while their baselines agree to well under a point. Grouping on ``top``
      splits one visual line into two and yields ``"T D H : T M L"`` followed by
      ``"HE RAGON ATCHLING ..."``.
    * The dominant size is weighted by character count rather than taken as the maximum,
      so a single oversized drop-cap cannot outvote the rest of the line and reduce the
      whole title to ``"M"``.
    """
    words = page.extract_words(extra_attrs=["size"])
    if not words:
        return []

    lines: list[_Line] = []
    for group in _cluster_by_baseline(words):
        group = sorted(group, key=lambda w: w["x0"])
        weights: Counter[float] = Counter()
        for word in group:
            weights[round(word["size"], 1)] += len(word["text"])
        lines.append(
            _Line(
                top=min(w["top"] for w in group),
                size=weights.most_common(1)[0][0],
                text=_join_words(group),
            )
        )
    return lines


def _cluster_by_baseline(words: list[dict]) -> list[list[dict]]:
    """Group words into visual lines by their baselines.

    Sequential clustering rather than bucketing by floor division, which would split a
    line whenever its words straddle a bucket boundary.
    """
    groups: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (w["bottom"], w["x0"])):
        if groups and word["bottom"] - groups[-1][-1]["bottom"] <= LINE_TOLERANCE_PT:
            groups[-1].append(word)
        else:
            groups.append([word])
    return groups


def _join_words(group: list[dict]) -> str:
    """Join a line's words, inserting a space only where the layout has a real gap."""
    parts = [group[0]["text"]]
    for previous, word in zip(group, group[1:]):
        if word["x0"] - previous["x1"] > SPACE_GAP_PT:
            parts.append(" ")
        parts.append(word["text"])
    return "".join(parts)


def _first_large_block(
    lines: list[_Line], threshold: float, cutoff: float
) -> list[_Line]:
    """Return the first contiguous run of above-threshold lines in the page header.

    Contiguity is what rejoins a title wrapped across two or three lines; requiring the
    run to start above ``cutoff`` is what keeps an oversized figure caption or section
    heading from being mistaken for one.
    """
    block: list[_Line] = []
    for index, line in enumerate(lines):
        if line.size < threshold:
            if block:
                break
            continue
        if not block and line.top > cutoff:
            continue
        if block and lines[index - 1] is not block[-1]:
            break
        block.append(line)
    return block


def _clean_candidate(raw: str | None) -> str | None:
    """Normalise whitespace and reject values that are not plausible titles."""
    if not raw:
        return None
    text = re.sub(r"\s+", " ", raw).strip()
    if len(text) < MIN_TITLE_CHARS or _JUNK_TITLE_RE.match(text):
        return None
    return text
