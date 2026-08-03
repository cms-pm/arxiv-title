from pathlib import Path

import pytest

from arxiv_title.naming import (
    is_arxiv_pdf,
    parse_arxiv_id,
    slugify,
    strip_version,
    target_name,
)


@pytest.mark.parametrize(
    "stem, expected",
    [
        ("2101.05536v1", "2101.05536v1"),
        ("2101.05536", "2101.05536"),
        ("2606.30789v12", "2606.30789v12"),
        ("0704.0001", "0704.0001"),
        ("hep-th_9901001", "hep-th_9901001"),
        ("math.GT_0309136v2", "math.GT_0309136v2"),
        # Already renamed: the ID prefix must still be recoverable so reruns are no-ops.
        ("2101.05536v1_scaling_equilibrium_propagation", "2101.05536v1"),
        ("notes", None),
        ("meeting-2024", None),
        # Not anchored at the start: a stray number mid-filename is not an ID.
        ("scan_of_2101.05536", None),
    ],
)
def test_parse_arxiv_id(stem, expected):
    assert parse_arxiv_id(stem) == expected


def test_strip_version():
    assert strip_version("2101.05536v1") == "2101.05536"
    assert strip_version("2101.05536") == "2101.05536"


@pytest.mark.parametrize(
    "title, expected",
    [
        ("How frogs create their own reality", "how_frogs_create_their_own_reality"),
        ("AdaJEPA: An Adaptive Latent World Model", "adajepa_an_adaptive_latent_world_model"),
        # Accents are folded, not dropped.
        ("Schrödinger Operators", "schrodinger_operators"),
        ("The Role of Green's Function", "the_role_of_green_s_function"),
        # Atom titles arrive hard-wrapped across lines.
        ("Real vs. Complex\n  Spectral Bases", "real_vs_complex_spectral_bases"),
        # LaTeX residue in metadata.
        ("Bounds on $\\alpha$ for \\emph{Deep} Nets", "bounds_on_for_deep_nets"),
        ("Trailing footnote marker ∗", "trailing_footnote_marker"),
    ],
)
def test_slugify(title, expected):
    assert slugify(title) == expected


def test_slugify_truncates_at_word_boundary():
    slug = slugify("alpha beta gamma delta epsilon", max_bytes=16)
    assert len(slug) <= 16
    assert not slug.endswith("_")
    # Cut on a separator rather than mid-word.
    assert slug == "alpha_beta"


def test_target_name_with_and_without_prefix():
    assert target_name("2101.05536v1", "How Frogs Create Their Own Reality") == (
        "2101.05536v1_how_frogs_create_their_own_reality.pdf"
    )
    assert target_name(
        "2101.05536v1", "How Frogs Create Their Own Reality", id_prefix=False
    ) == "how_frogs_create_their_own_reality.pdf"


def test_target_name_stays_within_filename_limit():
    name = target_name("2101.05536v1", "word " * 200)
    assert len(name.encode()) <= 200


def test_target_name_rejects_empty_slug():
    with pytest.raises(ValueError):
        target_name("2101.05536v1", "$$$")


def test_is_arxiv_pdf():
    assert is_arxiv_pdf(Path("2101.05536v1.pdf"))
    assert is_arxiv_pdf(Path("/a/b/2101.05536v1.PDF"))
    assert not is_arxiv_pdf(Path("2101.05536v1.txt"))
    assert not is_arxiv_pdf(Path("notes.pdf"))
