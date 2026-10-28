"""Owner-relative source-tree artifact classification for family checks."""

from __future__ import annotations

from pathlib import PurePosixPath


_ARTIFACT_ANY_COMPONENTS = frozenset({
    ".git", "__pycache__", "_deps", "cmakefiles", "node_modules",
})
_EXACT_REPOSITORY_ARTIFACT_ROOTS = frozenset({
    "apps/hft-parser/dev-state",
})


def source_artifact_path(
    relative: str,
    owner_roots: tuple[str, ...],
    *,
    exact_generated_roots: frozenset[str] = frozenset(),
) -> bool:
    """Classify artifacts relative to the longest matching source owner."""
    folded_relative = relative.casefold()
    if any(
            folded_relative == root.casefold() or
            folded_relative.startswith(root.casefold() + "/")
            for root in (
                _EXACT_REPOSITORY_ARTIFACT_ROOTS | exact_generated_roots)):
        return True

    matches = [
        root for root in owner_roots
        if relative == root or relative.startswith(root + "/")
    ]
    physical_root = max(matches, key=len) if matches else None
    parts = PurePosixPath(relative).parts
    if physical_root is None:
        owner_parts = parts
    else:
        root_parts = PurePosixPath(physical_root).parts
        owner_parts = parts[len(root_parts):]
    folded = tuple(part.casefold() for part in owner_parts)
    if any(part in _ARTIFACT_ANY_COMPONENTS for part in folded):
        return True
    if folded and (
            folded[0] == "build" or
            folded[0].startswith("build-") or
            folded[0].startswith("cmake-build-")):
        return True
    return any(
        folded[index:index + 2] == ("frontend", "dist")
        for index in range(max(0, len(folded) - 1)))
