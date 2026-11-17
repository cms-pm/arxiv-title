"""Markdown conversion: command shape, skipping, and failure reporting."""

from __future__ import annotations

import subprocess

import pytest

from arxiv_title import convert as convert_mod
from arxiv_title.convert import (
    Conversion,
    convert,
    convert_all,
    markdown_path,
    plan_conversions,
)


class FakeRun:
    """Stand-in for subprocess.run that records the argv it was handed."""

    def __init__(self, returncode=0, stderr="", write=True):
        self.returncode = returncode
        self.stderr = stderr
        self.write = write
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if self.write:
            # argv is [markitdown, src, "-o", dest]
            open(argv[3], "w").write("# hello\n")
        return subprocess.CompletedProcess(argv, self.returncode, "", self.stderr)


def test_markdown_path_swaps_the_suffix(tmp_path):
    assert markdown_path(tmp_path / "2101.05536v1_a_paper.pdf").name == (
        "2101.05536v1_a_paper.md"
    )


def test_invokes_markitdown_with_input_and_output(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    fake = FakeRun()
    monkeypatch.setattr(subprocess, "run", fake)

    result = convert(Conversion(pdf, markdown_path(pdf)))

    assert result.ok and result.error is None
    assert fake.calls == [["markitdown", str(pdf), "-o", str(tmp_path / "paper.md")]]
    assert (tmp_path / "paper.md").read_text() == "# hello\n"


def test_existing_markdown_is_skipped_unless_overwriting(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    (tmp_path / "paper.md").write_text("prior")
    fake = FakeRun()
    monkeypatch.setattr(subprocess, "run", fake)

    convert_all(plan_conversions([pdf]))
    assert fake.calls == []
    assert (tmp_path / "paper.md").read_text() == "prior"

    convert_all(plan_conversions([pdf], overwrite=True))
    assert len(fake.calls) == 1


def test_nonzero_exit_reports_the_last_stderr_line(tmp_path, monkeypatch):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    fake = FakeRun(returncode=1, stderr="Traceback...\nUnsupportedFormatException\n")
    monkeypatch.setattr(subprocess, "run", fake)

    result = convert(Conversion(pdf, markdown_path(pdf)))

    assert not result.ok
    assert result.error == "UnsupportedFormatException"


def test_silent_failure_is_caught(tmp_path, monkeypatch):
    """A zero exit that produced no file must not be reported as success."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(subprocess, "run", FakeRun(write=False))

    result = convert(Conversion(pdf, markdown_path(pdf)))

    assert not result.ok
    assert result.error == "markitdown wrote no output file"


@pytest.mark.parametrize(
    "raised, expected",
    [
        (FileNotFoundError(), "markitdown not found on PATH"),
        (subprocess.TimeoutExpired("markitdown", 300), "timed out after 300s"),
    ],
)
def test_missing_binary_and_timeout_degrade_to_an_error(
    tmp_path, monkeypatch, raised, expected
):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    def boom(*args, **kwargs):
        raise raised

    monkeypatch.setattr(subprocess, "run", boom)

    result = convert(Conversion(pdf, markdown_path(pdf)))

    assert not result.ok
    assert result.error == expected


def test_availability_follows_which(monkeypatch):
    monkeypatch.setattr(convert_mod.shutil, "which", lambda name: None)
    assert not convert_mod.markitdown_available()
    monkeypatch.setattr(convert_mod.shutil, "which", lambda name: "/usr/bin/markitdown")
    assert convert_mod.markitdown_available()
