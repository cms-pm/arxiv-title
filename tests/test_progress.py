"""Spinner: animates on a terminal, degrades to plain lines elsewhere."""

from __future__ import annotations

import io
import os
import time

from arxiv_title import progress
from arxiv_title.convert import Conversion, convert_all
from arxiv_title.progress import Spinner


class FakeTTY(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_non_terminal_gets_one_plain_line_and_no_control_codes():
    stream = io.StringIO()
    spinner = Spinner(stream)

    spinner.start("[1/2] converting paper.pdf")
    spinner.stop()

    assert stream.getvalue() == "  [1/2] converting paper.pdf ...\n"


def test_terminal_animates_then_erases_its_line(monkeypatch):
    monkeypatch.setattr(progress, "INTERVAL_SECONDS", 0.01)
    stream = FakeTTY()
    spinner = Spinner(stream)

    spinner.start("[1/2] converting paper.pdf")
    time.sleep(0.08)
    spinner.stop()

    output = stream.getvalue()
    assert "[1/2] converting paper.pdf 0s" in output
    assert len({f for f in progress.FRAMES if f in output}) > 1  # it advanced
    assert output.endswith("\r\x1b[K")
    assert "\n" not in output


def test_long_labels_are_trimmed_so_the_line_never_wraps(monkeypatch):
    monkeypatch.setattr(
        progress.shutil, "get_terminal_size", lambda: os.terminal_size((40, 24))
    )
    spinner = Spinner(FakeTTY())
    spinner._label = "converting " + "a_very_long_paper_title_" * 10 + ".pdf"

    line = spinner._render(0)

    assert len(line) < 40
    assert "…" in line


def test_stop_is_safe_when_never_started():
    stream = FakeTTY()
    Spinner(stream).stop()
    assert stream.getvalue() == ""


def test_convert_all_calls_hooks_around_each_unskipped_file(tmp_path, monkeypatch):
    done_pdf, todo_pdf = tmp_path / "done.pdf", tmp_path / "todo.pdf"
    conversions = [
        Conversion(done_pdf, done_pdf.with_suffix(".md"), skipped="markdown already exists"),
        Conversion(todo_pdf, todo_pdf.with_suffix(".md")),
    ]
    monkeypatch.setattr(
        "arxiv_title.convert.convert", lambda c: setattr(c, "ok", not c.skipped) or c
    )
    events = []

    convert_all(
        conversions,
        on_start=lambda c: events.append(("start", c.source.name)),
        on_done=lambda c: events.append(("done", c.source.name)),
    )

    assert events == [("done", "done.pdf"), ("start", "todo.pdf"), ("done", "todo.pdf")]
