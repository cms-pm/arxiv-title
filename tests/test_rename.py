from pathlib import Path

from arxiv_title.rename import apply_renames, plan_renames
from arxiv_title.resolve import Resolution, Source, collect_pdfs


def _res(tmp_path: Path, arxiv_id: str, title: str | None, **kw) -> Resolution:
    path = tmp_path / f"{arxiv_id}.pdf"
    path.touch()
    return Resolution(
        path=path, arxiv_id=arxiv_id, title=title, source=Source.API, **kw
    )


def test_plan_builds_prefixed_destination(tmp_path):
    plans = plan_renames([_res(tmp_path, "2101.05536v1", "How Frogs Croak")])
    assert plans[0].destination.name == "2101.05536v1_how_frogs_croak.pdf"


def test_unresolved_resolution_is_skipped(tmp_path):
    res = _res(tmp_path, "2101.05536v1", None, error="no title found")
    plans = plan_renames([res])
    assert plans[0].destination is None
    assert plans[0].skipped == "no title found"


def test_identical_titles_do_not_collapse_onto_one_name(tmp_path):
    plans = plan_renames(
        [
            _res(tmp_path, "2101.05536v1", "Same Title Here"),
            _res(tmp_path, "2101.05537v1", "Same Title Here"),
        ]
    )
    names = [p.destination.name for p in plans]
    assert len(set(names)) == 2


def test_collision_with_preexisting_file_gets_suffix(tmp_path):
    (tmp_path / "2101.05536v1_how_frogs_croak.pdf").touch()
    plans = plan_renames([_res(tmp_path, "2101.05536v1", "How Frogs Croak")])
    assert plans[0].destination.name == "2101.05536v1_how_frogs_croak_2.pdf"


def test_rerun_is_a_noop(tmp_path):
    source = tmp_path / "2101.05536v1.pdf"
    source.write_bytes(b"x")
    apply_renames(plan_renames([_res(tmp_path, "2101.05536v1", "How Frogs Croak")]))

    renamed = tmp_path / "2101.05536v1_how_frogs_croak.pdf"
    assert renamed.exists() and not source.exists()

    # Second pass over the already-renamed file must not move or duplicate it.
    again = Resolution(
        path=renamed,
        arxiv_id="2101.05536v1",
        title="How Frogs Croak",
        source=Source.API,
    )
    plans = plan_renames([again])
    assert plans[0].is_noop
    assert apply_renames(plans) == []
    assert [p.name for p in tmp_path.iterdir()] == [renamed.name]


def test_apply_preserves_contents(tmp_path):
    source = tmp_path / "2101.05536v1.pdf"
    source.write_bytes(b"payload")
    res = Resolution(
        path=source, arxiv_id="2101.05536v1", title="How Frogs Croak", source=Source.API
    )
    applied = apply_renames(plan_renames([res]))
    assert len(applied) == 1
    assert applied[0].destination.read_bytes() == b"payload"


def test_no_id_prefix(tmp_path):
    plans = plan_renames(
        [_res(tmp_path, "2101.05536v1", "How Frogs Croak")], id_prefix=False
    )
    assert plans[0].destination.name == "how_frogs_croak.pdf"


def test_collect_pdfs_filters_directory_but_keeps_explicit_files(tmp_path):
    (tmp_path / "2101.05536v1.pdf").touch()
    (tmp_path / "notes.pdf").touch()
    (tmp_path / "readme.txt").touch()
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "2207.00708v1.pdf").touch()

    shallow = collect_pdfs([tmp_path])
    assert [p.name for p in shallow] == ["2101.05536v1.pdf"]

    deep = collect_pdfs([tmp_path], recursive=True)
    assert [p.name for p in deep] == ["2101.05536v1.pdf", "2207.00708v1.pdf"]

    # An explicitly named file is kept even if it does not match, so the user gets a
    # clear per-file error rather than silence.
    explicit = collect_pdfs([tmp_path / "notes.pdf"])
    assert [p.name for p in explicit] == ["notes.pdf"]


def test_source_confidence():
    assert Source.API.is_confident
    assert Source.METADATA.is_confident
    assert not Source.LAYOUT.is_confident
