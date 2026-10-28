#!/usr/bin/env python3
"""Lexical repository path normalization for family CMake checks."""

from __future__ import annotations

import os
from pathlib import Path


def logical_relative_path(value: str, base: Path) -> Path | None:
    """Join and normalize a relative path without permitting root escape."""
    if "\\" in value:
        return None
    path = Path(value)
    if path.is_absolute():
        return None
    parts: list[str] = []
    for part in (base / path).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    return Path(*parts) if parts else Path()


def normalize_project_source_path(
    active: object,
    token: str,
    root: Path,
) -> tuple[str | None, str | None]:
    """Normalize a source token before ownership checks and reject root escape."""
    value = token.strip('"')
    if "\\" in value:
        return None, f"source uses unsupported CMake escape: {token}"
    path = Path(value)
    source_base = getattr(active, "source_base")
    relative_file = getattr(active, "relative")
    root_lexical = Path(os.path.abspath(root))
    if path.is_absolute():
        candidate = path
    else:
        source_parts = source_base.parts
        list_parts = Path(relative_file).parent.parts
        source_rooted = (
            bool(source_parts) and
            path.parts[:len(source_parts)] == source_parts
        )
        list_rooted = (
            bool(list_parts) and
            path.parts[:len(list_parts)] == list_parts
        )
        if source_rooted or list_rooted:
            candidate = root_lexical / path
        else:
            candidate = root_lexical / source_base / path
    try:
        raw_relative = candidate.relative_to(root_lexical)
    except ValueError:
        return None, f"source escapes repository root: {token}"
    current = root_lexical
    try:
        if current.is_symlink():
            return None, "repository root is symlinked"
        for part in raw_relative.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if current == root_lexical:
                    return None, f"source escapes repository root: {token}"
                current = current.parent
                continue
            current /= part
            if current.is_symlink():
                return None, f"source uses symlinked repository path: {token}"
        current.resolve().relative_to(root_lexical.resolve())
    except (OSError, ValueError):
        return None, f"source escapes repository root: {token}"
    relative_path = current.relative_to(root_lexical)
    return relative_path.as_posix(), None
