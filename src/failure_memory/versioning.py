"""Path compatibility for artifacts recorded before the v1/v2 directory split."""

from __future__ import annotations

from pathlib import Path


VERSIONED_TOP_LEVEL = frozenset({"configs", "docs", "experiments", "outputs", "schemas"})


def resolve_versioned_artifact(
    root: Path,
    value: str | Path,
    *,
    version: str = "proper_v1",
) -> Path:
    """Resolve an absolute, already-versioned, or historical repository path."""

    path = Path(value)
    if path.is_absolute():
        return path
    parts = path.parts
    if parts and parts[0] in VERSIONED_TOP_LEVEL:
        if len(parts) > 1 and parts[1] in {"proper_v1", "proper_v2"}:
            return root / path
        return root / parts[0] / version / Path(*parts[1:])
    return root / path
