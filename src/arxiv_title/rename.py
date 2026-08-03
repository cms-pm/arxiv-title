"""Planning and applying the actual file renames."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .naming import target_name
from .resolve import Resolution


@dataclass
class RenamePlan:
    resolution: Resolution
    destination: Path | None = None
    skipped: str | None = None

    @property
    def source_path(self) -> Path:
        return self.resolution.path

    @property
    def is_noop(self) -> bool:
        return self.destination == self.source_path


def plan_renames(
    resolutions: list[Resolution], *, id_prefix: bool = True
) -> list[RenamePlan]:
    """Compute a destination for each resolved title.

    Destinations claimed earlier in the batch are tracked so that two papers sharing a
    title do not silently collapse onto one filename.
    """
    plans: list[RenamePlan] = []
    claimed: set[Path] = set()

    for resolution in resolutions:
        if not resolution.ok:
            plans.append(RenamePlan(resolution, skipped=resolution.error))
            continue
        try:
            name = target_name(
                resolution.arxiv_id,
                resolution.title,
                id_prefix=id_prefix,
                suffix=resolution.path.suffix or ".pdf",
            )
        except ValueError as exc:
            plans.append(RenamePlan(resolution, skipped=str(exc)))
            continue

        destination = _free_path(resolution.path.with_name(name), resolution.path, claimed)
        claimed.add(destination)
        plans.append(RenamePlan(resolution, destination=destination))
    return plans


def _free_path(desired: Path, current: Path, claimed: set[Path]) -> Path:
    """Return ``desired``, or a ``_2``/``_3``-suffixed variant if it is taken.

    ``current`` is never a conflict with itself: re-running over an already-renamed
    directory has to land on the same name it produced last time.
    """
    if _available(desired, current, claimed):
        return desired
    stem, suffix = desired.stem, desired.suffix
    counter = 2
    while True:
        candidate = desired.with_name(f"{stem}_{counter}{suffix}")
        if _available(candidate, current, claimed):
            return candidate
        counter += 1


def _available(candidate: Path, current: Path, claimed: set[Path]) -> bool:
    if candidate == current:
        return True
    return not candidate.exists() and candidate not in claimed


def apply_renames(plans: list[RenamePlan]) -> list[RenamePlan]:
    """Perform the renames. Returns the plans that actually moved a file."""
    applied: list[RenamePlan] = []
    for plan in plans:
        if plan.destination is None or plan.is_noop:
            continue
        plan.source_path.replace(plan.destination)
        applied.append(plan)
    return applied
