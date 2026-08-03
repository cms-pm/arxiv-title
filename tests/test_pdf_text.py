"""Extraction tests against the real sample corpus in ``artifacts/``."""

from pathlib import Path

import pytest

from arxiv_title.sources.pdf_text import title_from_layout, title_from_metadata

ARTIFACTS = Path(__file__).resolve().parent.parent / "artifacts"

pytestmark = pytest.mark.skipif(
    not ARTIFACTS.is_dir(), reason="sample corpus not present"
)

# Expected titles, verified against the arXiv API.
EXPECTED = {
    "2101.05536v1": "Scaling Equilibrium Propagation to Deep ConvNets",
    "2207.00708v1": "Parameter efficient dendritic-tree neurons outperform perceptrons",
    "2509.26507v1": "Dragon Hatchling",
    "2511.18424v1": "CrossJEPA",
    "2605.08135v1": "Dendritic Neural Networks with Equilibrium Propagation",
    "2606.24851v3": "Real vs. Complex Spectral Bases for Neural Operators",
    "2606.30789v2": "Predictable GRPO: A Closed-Form Model of Training Dynamics",
    "2606.30930v1": "SGD at the Edge of Stability",
    "2606.32026v1": "AdaJEPA: An Adaptive Latent World Model",
    "2607.00286v1": "Self-Organized Learning in Oscillatory Neural Networks",
}

# These four are set in LaTeX small caps or with an enlarged leading capital. A
# largest-glyph rule reduces them to a single character; the weighted-dominant-size and
# baseline-clustering rules are what make them work.
SMALL_CAPS_CASES = ["2605.08135v1", "2606.30930v1", "2511.18424v1", "2606.30789v2"]


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_layout_extraction_matches_expected_title(stem):
    title = title_from_layout(ARTIFACTS / f"{stem}.pdf")
    assert title is not None
    assert EXPECTED[stem].lower() in title.lower()


@pytest.mark.parametrize("stem", SMALL_CAPS_CASES)
def test_small_caps_titles_are_not_truncated_to_one_glyph(stem):
    title = title_from_layout(ARTIFACTS / f"{stem}.pdf")
    assert title is not None and len(title) > 20


def test_layout_inserts_spaces_between_words():
    title = title_from_layout(ARTIFACTS / "2606.32026v1.pdf")
    assert title == "AdaJEPA: An Adaptive Latent World Model"


def test_layout_rejoins_small_caps_runs_without_spurious_spaces():
    # "T" + "HE" are separate words only because their font sizes differ.
    title = title_from_layout(ARTIFACTS / "2509.26507v1.pdf")
    assert title.upper().startswith("THE DRAGON HATCHLING")


def test_metadata_covers_most_of_the_corpus():
    found = {
        stem: title_from_metadata(ARTIFACTS / f"{stem}.pdf") for stem in EXPECTED
    }
    # 2101.05536v1 ships an empty /Title; the rest are populated.
    assert found["2101.05536v1"] is None
    assert all(v for k, v in found.items() if k != "2101.05536v1")


def test_metadata_is_none_for_missing_file(tmp_path):
    assert title_from_metadata(tmp_path / "nope.pdf") is None


def test_layout_is_none_for_unreadable_file(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf")
    assert title_from_layout(broken) is None
