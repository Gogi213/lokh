"""Exact vendored ``add_subdirectory`` edges and source authorities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import (
    exact_context,
    first_body,
    first_if,
    structural_contexts,
)
from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_external_authority
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Policy.CmakeFamilyVendorPolicy import semantic_vendor_context


@dataclass(frozen=True)
class ExternalEdge:
    relative: str
    line: int
    source: str
    arguments: tuple[str, ...]
    context: tuple
    authority: str


_CORE_SECP = first_if(
    "src/src/CMakeLists.txt", 192,
    ("CXET_HAS_SECP256K1", "AND", "NOT", "TARGET", "secp256k1"))
_ROOT_SECP = first_if(
    "CMakeLists.txt", 230, ("CXET_HAS_SECP256K1",))
_ROOT_ABSEIL_FUNCTION = first_body(
    "function", "CMakeLists.txt", 271,
    ("cxet_add_abseil_subdirectory",))

_EDGES = {
    ("CMakeLists.txt", 249): ExternalEdge(
        "CMakeLists.txt", 249, "extra/secp256k1",
        ("extra/secp256k1", "EXCLUDE_FROM_ALL"), (_ROOT_SECP,), "secp256k1"),
    ("CMakeLists.txt", 274): ExternalEdge(
        "CMakeLists.txt", 274, "extra/abseil-cpp",
        ("extra/abseil-cpp",), (_ROOT_ABSEIL_FUNCTION,), "abseil-cpp"),
    ("src/src/CMakeLists.txt", 211): ExternalEdge(
        "src/src/CMakeLists.txt", 211, "extra/secp256k1",
        ("${CMAKE_CURRENT_SOURCE_DIR}/../../extra/secp256k1",
         "${CMAKE_CURRENT_BINARY_DIR}/_deps/secp256k1", "EXCLUDE_FROM_ALL"),
        (_CORE_SECP,), "secp256k1"),
}


def _validate(
    relative: str,
    line: int,
    source: str,
    arguments: tuple[str, ...],
    context,
    errors: list[str],
) -> ExternalEdge | None:
    origin = f"{relative}:{line}"
    candidates = [edge for edge in _EDGES.values() if edge.relative == relative and edge.source == source]
    edge = candidates[0] if len(candidates) == 1 else None
    if edge is None:
        errors.append(f"{origin}: unreviewed external add_subdirectory edge")
        return None
    if source != edge.source:
        errors.append(
            f"{origin}: external source changed from {edge.source} to {source}")
    if arguments != edge.arguments:
        errors.append(f"{origin}: external edge arguments/options changed")
    if not semantic_vendor_context(context, edge.context):
        errors.append(f"{origin}: external edge structural context changed")
    if not reviewed_external_authority(edge.authority):
        errors.append(
            f"{origin}: full {edge.authority} vendored authority changed")
    return edge


def validate_active_external_edge(
    active,
    source_relative: str,
    seen_sources: set[str],
    errors: list[str],
) -> None:
    """Validate an external edge before the composer skips vendor dialect."""
    arguments = tuple(cmake_list_words(active.command.body))
    edge = _validate(
        active.relative, active.command.line, source_relative, arguments,
        active.structural_context, errors)
    if active.source_base != Path("src/src") or active.binary_base != Path("src/src"):
        errors.append(
            f"{active.relative}:{active.command.line}: external edge is "
            "evaluated outside canonical core source/binary scope")
    if source_relative in seen_sources:
        errors.append(
            f"{active.relative}:{active.command.line}: duplicate external "
            f"source invocation {source_relative}")
    seen_sources.add(source_relative)
    if edge is not None and edge.relative == "CMakeLists.txt":
        errors.append(
            f"{active.relative}:{active.command.line}: root external edge "
            "entered the family composer")


def validate_root_external_edges(
    commands, errors: list[str], viable_offsets: frozenset[int]
) -> None:
    """Pin all root vendor edges before root target-owner exceptions apply."""
    contexts = structural_contexts(
        "CMakeLists.txt", commands, cmake_list_words, errors)
    seen_sources: set[str] = set()
    seen_edges: set[tuple[str, int]] = set()
    for command, context in zip(commands, contexts):
        if command.name != "add_subdirectory":
            continue
        tokens = tuple(cmake_list_words(command.body))
        if not tokens:
            continue
        normalized = tokens[0].rstrip("/")
        if normalized not in {
                "extra/secp256k1", "extra/abseil-cpp"}:
            continue
        key = ("CMakeLists.txt", normalized)
        _validate(
            "CMakeLists.txt", command.line, normalized, tokens, context,
            errors)
        if command.offset not in viable_offsets:
            errors.append(
                f"CMakeLists.txt:{command.line}: required external edge is "
                "not on a viable root execution path")
        if normalized in seen_sources:
            errors.append(
                f"CMakeLists.txt:{command.line}: duplicate root external "
                f"source invocation {normalized}")
        seen_sources.add(normalized)
        seen_edges.add(key)
    required = {
        (edge.relative, edge.source) for edge in _EDGES.values() if edge.relative == "CMakeLists.txt"}
    if seen_edges != required:
        errors.append(
            "CMakeLists.txt: root external edge set changed: "
            f"missing={sorted(required - seen_edges)}, "
            f"extra={sorted(seen_edges - required)}")
