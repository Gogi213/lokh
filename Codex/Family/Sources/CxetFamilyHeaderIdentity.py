"""Reject byte-copied canonical headers across CXET family owners."""

from __future__ import annotations

import hashlib
from pathlib import Path

from Family.Sources.CxetFamilyHeaderContract import (
    HEADER_OWNER_ROOTS,
    logical_header_owner,
    source_header_files,
    unsymlinked_source_path,
)


def validate_exported_header_identity(
    root: Path,
    exported: dict[str, tuple[str, ...]],
    errors: list[str],
) -> None:
    canonical = frozenset(
        relative for headers in exported.values() for relative in headers)
    by_digest: dict[str, list[str]] = {}
    for owner_root, _ in HEADER_OWNER_ROOTS:
        directory = root / owner_root
        if not unsymlinked_source_path(directory, root, directory=True):
            errors.append(
                f"header identity owner root is missing/nonregular: {owner_root}")
            continue
        for path in source_header_files(
                root, directory, errors,
                f"header identity owner root {owner_root}"):
            relative = path.relative_to(root).as_posix()
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as exc:
                errors.append(f"cannot hash family header {relative}: {exc}")
                continue
            by_digest.setdefault(digest, []).append(relative)

    reported: set[tuple[str, str]] = set()
    for paths in by_digest.values():
        canonical_paths = sorted(set(paths) & canonical)
        if not canonical_paths:
            continue
        for canonical_path in canonical_paths:
            canonical_owner = logical_header_owner(canonical_path)
            for other in sorted(paths):
                other_owner = logical_header_owner(other)
                pair = tuple(sorted((canonical_path, other)))
                if (canonical_path == other or pair in reported or
                        canonical_owner is None or other_owner is None or
                        canonical_owner == other_owner):
                    continue
                reported.add(pair)
                errors.append(
                    "canonical exported header is byte-copied across owners: "
                    f"{canonical_path} ({canonical_owner}) == "
                    f"{other} ({other_owner})")
