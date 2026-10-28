"""Normalize every file-like token attached to a first-party CMake target."""

from __future__ import annotations

import re
from pathlib import Path

from CMake.Flow.CmakeFamilyGraph import (
    active_binary_dir,
    has_unresolved_cmake_carrier,
    normalize_project_source_path,
)


_SOURCE_KIND_BY_SUFFIX = {
    ".c": "c",
    ".m": "c-or-cxx-m",
    ".C": "cxx",
    ".M": "cxx-m",
    ".CPP": "cxx",
    ".c++": "cxx",
    ".cc": "cxx",
    ".cpp": "cxx",
    ".cxx": "cxx",
    ".mm": "cxx-mm",
    ".mpp": "cxx-module",
    ".c++m": "cxx-module",
    ".ccm": "cxx-module",
    ".cppm": "cxx-module",
    ".cxxm": "cxx-module",
    ".ixx": "cxx-module",
    ".s": "asm",
    ".S": "asm-preprocessed",
    ".asm": "asm",
    ".nasm": "nasm",
    ".cu": "cuda",
    ".hip": "hip",
    ".ispc": "ispc",
    ".swift": "swift",
    ".rc": "resource",
    ".RC": "resource",
    ".f": "fortran",
    ".for": "fortran",
    ".f77": "fortran",
    ".f90": "fortran",
    ".f95": "fortran",
    ".f03": "fortran",
    ".f08": "fortran",
    ".F": "fortran-preprocessed",
    ".F90": "fortran-preprocessed",
    ".F95": "fortran-preprocessed",
    ".F03": "fortran-preprocessed",
    ".F08": "fortran-preprocessed",
}

_TEXT_KIND_BY_SUFFIX = {
    ".h": "header",
    ".hh": "header",
    ".hpp": "header",
    ".hxx": "header",
    ".inc": "legacy-fragment",
    ".inl": "fragment",
    ".ipp": "fragment",
    ".tcc": "fragment",
    ".tpp": "fragment",
    ".def": "legacy-module-definition",
}

_COMPILED_KINDS = frozenset(_SOURCE_KIND_BY_SUFFIX.values())
_REVIEWED_FIRST_PARTY_KINDS = frozenset({
    "c", "cxx", "header", "fragment",
})

_PREBUILT_SUFFIXES = frozenset({
    ".a", ".bc", ".dll", ".dlb", ".dylib", ".gch", ".gcm", ".ifc",
    ".jar", ".l", ".la", ".lib", ".lo", ".o", ".obj", ".pch",
    ".pcm", ".res", ".sl", ".so", ".sys", ".targets", ".tbd",
})


def attachment_kind(token: str) -> str | None:
    suffix = Path(token.strip('"')).suffix
    return (
        _SOURCE_KIND_BY_SUFFIX.get(suffix) or
        _TEXT_KIND_BY_SUFFIX.get(suffix.lower())
    )


def compiled_attachment(token: str) -> bool:
    return attachment_kind(token) in _COMPILED_KINDS


def _reviewed_first_party_kind(kind: str, source_base: Path) -> bool:
    if kind not in _REVIEWED_FIRST_PARTY_KINDS:
        return False
    return True


def prebuilt_attachment(token: str) -> bool:
    """Return true for binary artifacts forbidden in the source graph."""
    name = Path(token.strip('"')).name.lower()
    return (
        Path(name).suffix in _PREBUILT_SUFFIXES or
        re.fullmatch(r".+\.so(?:\.[A-Za-z0-9_+-]+)+", name)
        is not None
    )


def compiled_attachment_mismatch(token: str, resolved: str) -> bool:
    """Keep CMake's lexical language/source choice equal to canonical kind."""
    return attachment_kind(token) != attachment_kind(resolved)


def validate_source_attachment_microcases(errors: list[str]) -> None:
    for value in (
            "object.o", "object.obj", "module.bc", "archive.a",
            "archive.lib", "library.so", "library.so.10.0.0",
            "library.dylib", "library.dll"):
        if not prebuilt_attachment(value):
            errors.append(
                "source-attachment self-check accepted prebuilt artifact "
                f"{value}")
    for value in (
            "source.c++", "module.cppm", "objective.mm", "lane.S",
            "kernel.cu", "kernel.hip", "lane.ispc", "resource.rc",
            "model.f90"):
        if not compiled_attachment(value):
            errors.append(
                "source-attachment self-check missed compiled source "
                f"{value}")
    for token, resolved in (
            ("Alias.cpp", "Real.hpp"),
            ("Alias.hpp", "Real.cpp"),
            ("Alias", "Real.cpp"),
            ("Alias.cpp", "Real.c"),
            ("Alias.C", "Real.c"),
            ("Alias.S", "Real.s"),
            ("Alias.cppm", "Real.cpp")):
        if not compiled_attachment_mismatch(token, resolved):
            errors.append(
                "source-attachment self-check missed lexical/resolved "
                f"kind mismatch {token} -> {resolved}")
    for token, resolved in (
            ("Alias.cc", "Real.cpp"),
            ("Alias.h", "Real.hpp")):
        if compiled_attachment_mismatch(token, resolved):
            errors.append(
                "source-attachment self-check rejected equivalent "
                f"kind {token} -> {resolved}")
    if attachment_kind("unreviewed.asset") is not None:
        errors.append(
            "source-attachment self-check accepted unknown attachment kind")
    for value in ("source.c", "source.cpp", "header.hpp", "fragment.ipp"):
        kind = attachment_kind(value)
        if kind is None or not _reviewed_first_party_kind(
                kind, Path("src/src")):
            errors.append(
                "source-attachment self-check rejected reviewed first-party "
                f"kind {value}")
    for value in (
            "module.cppm", "module.mpp", "objective.m", "objective.mm",
            "lane.S", "lane.asm", "lane.nasm", "kernel.cu", "kernel.hip",
            "lane.ispc", "source.swift", "resource.rc", "model.f90",
            "fragment.inc", "exports.def"):
        kind = attachment_kind(value)
        if kind is None or _reviewed_first_party_kind(
                kind, Path("src/src")):
            errors.append(
                "source-attachment self-check accepted unsupported "
                f"first-party kind {value}")


def resolve_source_attachment(active, token: str, root: Path):
    """Return normalized repository path or a fail-closed attachment error."""
    value = token.strip('"')
    if not value:
        return None, "empty source attachment"
    if "$<" in value:
        return None, f"unclassified source generator expression {token}"
    if has_unresolved_cmake_carrier(value):
        return None, f"unresolved source carrier {token}"
    if prebuilt_attachment(value):
        return None, f"prebuilt binary attachment is forbidden: {token}"
    kind = attachment_kind(value)
    if kind is None:
        return None, f"unreviewed source attachment kind: {token}"
    native_asm = False
    if (kind == "asm-preprocessed" and active.relative == "src/src/CMakeLists.txt" and
            active.source_base == Path("src/src") and active.binary_base == Path("src/src")):
        native_source, native_error = normalize_project_source_path(active, value, root)
        native_asm = (native_error is None and native_source ==
                      "extra/hacl-star/dist/gcc-compatible/aesgcm-x86_64-linux.S")
    if not _reviewed_first_party_kind(kind, active.source_base) and not native_asm:
        return None, (
            "source attachment language/kind is not enabled or reviewed: "
            f"{token} ({kind})")
    binary_root = active_binary_dir(active)
    if value == binary_root or value.startswith(binary_root + "/"):
        return None, f"unapproved generated source attachment {token}"
    source, path_error = normalize_project_source_path(active, value, root)
    if path_error is not None or source is None:
        return None, path_error or f"invalid source attachment {token}"
    if prebuilt_attachment(source):
        return None, (
            "source attachment resolves to a forbidden prebuilt binary: "
            f"{source}")
    if compiled_attachment_mismatch(value, source):
        return None, (
            "source attachment changes language/source kind after "
            f"canonical resolution: {value} -> {source}")
    if not (root / source).is_file():
        return None, f"attached source does not exist: {token}"
    return source, None
