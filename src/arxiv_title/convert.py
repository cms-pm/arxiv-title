"""Optional Markdown conversion of renamed PDFs via the `markitdown` CLI."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

MARKITDOWN = "markitdown"
TIMEOUT_SECONDS = 300.0


@dataclass
class Conversion:
    source: Path
    destination: Path
    ok: bool = False
    skipped: str | None = None
    error: str | None = None


def markitdown_available() -> bool:
    return shutil.which(MARKITDOWN) is not None


def markdown_path(pdf: Path) -> Path:
    return pdf.with_suffix(".md")


def plan_conversions(pdfs: list[Path], *, overwrite: bool = False) -> list[Conversion]:
    """Pair each PDF with its `.md` target, marking ones already converted."""
    conversions = []
    for pdf in pdfs:
        destination = markdown_path(pdf)
        skipped = None
        if destination.exists() and not overwrite:
            skipped = "markdown already exists"
        conversions.append(Conversion(pdf, destination, skipped=skipped))
    return conversions


def convert(conversion: Conversion) -> Conversion:
    """Run `markitdown <pdf> -o <md>` for one file, recording the outcome."""
    if conversion.skipped:
        return conversion
    try:
        result = subprocess.run(
            [MARKITDOWN, str(conversion.source), "-o", str(conversion.destination)],
            capture_output=True,
            text=True,
            # Never let the child wait on our terminal: markitdown reads stdin when
            # it decides it has no usable input file.
            stdin=subprocess.DEVNULL,
            timeout=TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        conversion.error = f"{MARKITDOWN} not found on PATH"
        return conversion
    except subprocess.TimeoutExpired:
        conversion.error = f"timed out after {TIMEOUT_SECONDS:.0f}s"
        return conversion

    if result.returncode != 0:
        # markitdown reports the useful part on stderr; keep the last line only so a
        # long traceback does not swamp the rename table.
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        conversion.error = detail[-1] if detail else f"exit status {result.returncode}"
        return conversion

    # A zero exit with no file written is a silent failure worth catching.
    if not conversion.destination.exists():
        conversion.error = "markitdown wrote no output file"
        return conversion

    conversion.ok = True
    return conversion


def convert_all(
    conversions: list[Conversion],
    *,
    on_start: Callable[[Conversion], None] | None = None,
    on_done: Callable[[Conversion], None] | None = None,
) -> list[Conversion]:
    """Convert sequentially, calling the hooks around each file.

    Each conversion takes seconds (pdfminer is slow), so callers use the hooks to
    show progress instead of going silent until the whole batch is finished.
    """
    for conversion in conversions:
        if on_start and not conversion.skipped:
            on_start(conversion)
        convert(conversion)
        if on_done:
            on_done(conversion)
    return conversions
