"""Command line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .convert import Conversion, convert_all, markitdown_available, plan_conversions
from .progress import Spinner
from .rename import RenamePlan, apply_renames, plan_renames
from .resolve import collect_pdfs, resolve_titles

app = typer.Typer(
    add_completion=False,
    help="Rename arXiv PDFs (e.g. 2101.05536v1.pdf) to descriptive, title-based names.",
)


@app.command()
def run(
    paths: Annotated[
        list[Path],
        typer.Argument(
            metavar="PATH...",
            help="PDF files, or directories to scan for arXiv-named PDFs.",
        ),
    ],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Preview renames without touching disk.")
    ] = False,
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip the arXiv API and use the PDFs only.")
    ] = False,
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Descend into subdirectories.")
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Rename even when the title was only guessed from page layout.",
        ),
    ] = False,
    id_prefix: Annotated[
        bool,
        typer.Option(
            "--id-prefix/--no-id-prefix",
            help="Keep the arXiv ID at the front of the new filename.",
        ),
    ] = True,
    markdown: Annotated[
        bool,
        typer.Option(
            "--markdown",
            "-m",
            help="Also convert each file to Markdown with `markitdown FILE.pdf -o FILE.md`.",
        ),
    ] = False,
    overwrite_markdown: Annotated[
        bool,
        typer.Option(
            "--overwrite-markdown",
            help="Re-convert even when the .md file already exists.",
        ),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show which source supplied each title.")
    ] = False,
) -> None:
    if markdown and not dry_run and not markitdown_available():
        typer.secho(
            "markitdown not found on PATH; install it with `pip install markitdown[pdf]`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)
    pdfs = collect_pdfs(paths, recursive=recursive)
    if not pdfs:
        typer.secho("No arXiv-named PDFs found.", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)

    resolutions, warning = resolve_titles(pdfs, use_api=not offline)
    if warning:
        typer.secho(f"warning: {warning}", fg=typer.colors.YELLOW, err=True)

    plans = plan_renames(resolutions, id_prefix=id_prefix)

    # Layout-derived titles are the ones that historically go wrong (a drop cap read as
    # the whole title), so they are held back unless the user opts in.
    held = [
        p
        for p in plans
        if p.destination and not p.resolution.is_confident and not force and not dry_run
    ]
    for plan in held:
        plan.skipped = "low-confidence title (layout); re-run with --force to accept"
        plan.destination = None

    _report(plans, dry_run=dry_run, verbose=verbose)

    if not dry_run:
        apply_renames(plans)

    failed_conversions = False
    if markdown:
        # Convert the *destination* paths: the rename has already happened, so this is
        # where the files now live. Held-back files are left alone entirely.
        targets = [p.destination for p in plans if p.destination is not None]
        conversions = plan_conversions(targets, overwrite=overwrite_markdown)
        pending = [c for c in conversions if not c.skipped]
        width = max((len(c.source.name) for c in pending), default=0)
        typer.echo()

        def show(conversion: Conversion) -> None:
            _report_conversion(conversion, width=width, verbose=verbose)

        if dry_run:
            for conversion in conversions:
                show(conversion)
        else:
            # Each file takes seconds, so announce it before starting and print its
            # result as soon as it finishes rather than after the whole batch.
            spinner = Spinner()

            def announce(conversion: Conversion) -> None:
                position = pending.index(conversion) + 1
                spinner.start(
                    f"[{position}/{len(pending)}] converting {conversion.source.name}"
                )

            def finish(conversion: Conversion) -> None:
                spinner.stop()
                show(conversion)

            try:
                convert_all(conversions, on_start=announce, on_done=finish)
            finally:
                # Ctrl-C lands here mid-conversion; leave the terminal line clean.
                spinner.stop()

        done = len(pending) if dry_run else sum(c.ok for c in conversions)
        verb = "would convert" if dry_run else "converted"
        typer.secho(
            f"{verb} {done} of {len(conversions)} file(s) to markdown", bold=True
        )
        failed_conversions = any(c.error for c in conversions)

    if failed_conversions or any(p.destination is None for p in plans):
        raise typer.Exit(1)


def _report(plans: list[RenamePlan], *, dry_run: bool, verbose: bool) -> None:
    renames = [p for p in plans if p.destination and not p.is_noop]
    width = max((len(p.source_path.name) for p in renames), default=0)

    for plan in plans:
        name = plan.source_path.name
        if plan.destination is None:
            typer.secho(f"  skip  {name}: {plan.skipped}", fg=typer.colors.RED)
        elif plan.is_noop:
            if verbose:
                typer.echo(f"  ok    {name} (already named)")
        else:
            tag = f"  [{plan.resolution.source.value}]" if verbose else ""
            arrow = typer.style("->", fg=typer.colors.CYAN)
            typer.echo(f"  {name:<{width}} {arrow} {plan.destination.name}{tag}")

    verb = "would rename" if dry_run else "renamed"
    typer.secho(f"\n{verb} {len(renames)} of {len(plans)} file(s)", bold=True)


def _report_conversion(conversion: Conversion, *, width: int, verbose: bool) -> None:
    name = conversion.source.name
    if conversion.error:
        typer.secho(f"  fail  {name}: {conversion.error}", fg=typer.colors.RED)
    elif conversion.skipped:
        if verbose:
            typer.echo(f"  ok    {name} ({conversion.skipped})")
    else:
        arrow = typer.style("->", fg=typer.colors.CYAN)
        typer.echo(f"  {name:<{width}} {arrow} {conversion.destination.name}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
