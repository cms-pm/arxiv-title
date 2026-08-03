"""Extraction tests against the committed PDF fixtures in ``tests/pdf/``.

These three papers are checked in so the suite is self-contained on a fresh clone. The
wider ``artifacts/`` corpus is gitignored and not required here.
"""

from pathlib import Path

import pytest

from arxiv_title.sources.pdf_text import title_from_layout, title_from_metadata

FIXTURES = Path(__file__).resolve().parent / "pdf"

# Titles verified against the arXiv API.
EXPECTED = {
    "2606.30789v2": "Predictable GRPO: A Closed-Form Model of Training Dynamics",
    "2606.31137v1": (
        "A Bayesian Filtering Approach for Learning Lagrangian Dynamics "
        "from Noisy Measurements"
    ),
    "2607.22653v1": (
        "Do Language Models Converge to Themselves? "
        "Recursive Self-Refinement as Textual Relaxation"
    ),
}

# 2606.30789v2 sets its title with an enlarged leading capital. Under a largest-glyph
# rule the extracted title collapsed to "G"; it is the regression guard for both the
# character-count-weighted size rule and baseline clustering.
SMALL_CAPS_CASE = "2606.30789v2"


def fixture(stem: str) -> Path:
    return FIXTURES / f"{stem}.pdf"


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_layout_extraction_matches_canonical_title(stem):
    assert title_from_layout(fixture(stem)) == EXPECTED[stem]


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_metadata_extraction_matches_canonical_title(stem):
    assert title_from_metadata(fixture(stem)) == EXPECTED[stem]


def test_small_caps_title_is_not_truncated_to_one_glyph():
    title = title_from_layout(fixture(SMALL_CAPS_CASE))
    assert title is not None and len(title) > 20


def test_layout_inserts_spaces_between_words():
    # Guards the gap threshold in the other direction: too small a threshold and the
    # words run together as "PredictableGRPO:AClosed-FormModel...".
    title = title_from_layout(fixture(SMALL_CAPS_CASE))
    assert " " in title
    assert "PredictableGRPO" not in title


def test_layout_rejoins_titles_wrapped_across_lines():
    # This title spans more than one line in the PDF and must come back as one string.
    title = title_from_layout(fixture("2606.31137v1"))
    assert title.startswith("A Bayesian Filtering Approach")
    assert title.endswith("from Noisy Measurements")
    assert "\n" not in title


def test_metadata_is_none_for_missing_file(tmp_path):
    assert title_from_metadata(tmp_path / "nope.pdf") is None


def test_layout_is_none_for_unreadable_file(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    assert title_from_layout(broken) is None
