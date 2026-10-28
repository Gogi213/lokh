"""Expanded set/unset/option signatures for the bounded CMake model."""

from __future__ import annotations

import re
from dataclasses import dataclass


_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_CACHE_TYPES = frozenset({"BOOL", "FILEPATH", "INTERNAL", "PATH", "STRING"})
_SIGNATURE_WORDS = _CACHE_TYPES | {"CACHE", "FORCE", "PARENT_SCOPE"}


@dataclass(frozen=True)
class VariableSignature:
    variable: str
    values: tuple[str, ...] = ()
    cache_type: str | None = None
    force: bool = False
    parent_scope: bool = False
    cache_removal: bool = False


def _expanded_groups(raw_words: list[str], expand) -> list[tuple[str, ...]]:
    result: list[tuple[str, ...]] = []
    for raw in raw_words:
        values = tuple(expand([raw]))
        result.append(values or (("",) if raw == "" else ()))
    return result


def expanded_variable_name(
    raw: str,
    expand,
    errors: list[str],
    origin: str,
) -> str | None:
    values = tuple(expand([raw]))
    if (len(values) != 1 or
            any(marker in values[0] for marker in _CARRIERS) or
            re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", values[0]) is None):
        errors.append(f"{origin}: unresolved variable destination {values}")
        return None
    return values[0]


def parse_variable_signature(
    command_name: str,
    raw_words: list[str],
    expand,
    errors: list[str],
    origin: str,
) -> VariableSignature | None:
    """Parse signature after expansion; dynamic control words are forbidden."""
    if not raw_words:
        errors.append(f"{origin}: {command_name}() misses its destination")
        return None
    groups = _expanded_groups(raw_words, expand)
    variable = expanded_variable_name(raw_words[0], expand, errors, origin)
    if variable is None:
        return None
    for raw, values in zip(raw_words[1:], groups[1:]):
        if (any(marker in raw for marker in _CARRIERS) and
                any(value.upper() in _SIGNATURE_WORDS for value in values)):
            errors.append(
                f"{origin}: dynamic token changes {command_name}() signature")
            return None
    tail = [value for group in groups[1:] for value in group]
    upper = [value.upper() for value in tail]

    if command_name == "unset":
        if not tail:
            return VariableSignature(variable)
        if len(tail) != 1 or upper[0] not in {"CACHE", "PARENT_SCOPE"}:
            errors.append(f"{origin}: unsupported expanded unset() signature")
            return None
        return VariableSignature(
            variable,
            parent_scope=upper[0] == "PARENT_SCOPE",
            cache_removal=upper[0] == "CACHE",
        )
    if command_name != "set":
        errors.append(f"{origin}: unsupported variable command {command_name}")
        return None

    cache_positions = [i for i, value in enumerate(upper) if value == "CACHE"]
    parent_positions = [
        i for i, value in enumerate(upper) if value == "PARENT_SCOPE"]
    if cache_positions and parent_positions:
        errors.append(f"{origin}: set() mixes CACHE and PARENT_SCOPE")
        return None
    if parent_positions:
        if parent_positions != [len(tail) - 1]:
            errors.append(f"{origin}: malformed expanded PARENT_SCOPE signature")
            return None
        return VariableSignature(
            variable, tuple(tail[:-1]), parent_scope=True)
    if not cache_positions:
        return VariableSignature(variable, tuple(tail))
    if len(cache_positions) != 1:
        errors.append(f"{origin}: ambiguous expanded CACHE signature")
        return None
    cache_index = cache_positions[0]
    suffix = tail[cache_index + 1:]
    suffix_upper = upper[cache_index + 1:]
    force = bool(suffix_upper and suffix_upper[-1] == "FORCE")
    if force:
        suffix = suffix[:-1]
        suffix_upper = suffix_upper[:-1]
    if len(suffix) != 2 or suffix_upper[0] not in _CACHE_TYPES:
        errors.append(f"{origin}: malformed expanded CACHE signature")
        return None
    return VariableSignature(
        variable,
        tuple(tail[:cache_index]),
        suffix_upper[0],
        force,
    )


def approved_vetron_wasm_parent_scope(
    active, signature: VariableSignature, state, repository_root, binary_root: str,
) -> bool:
    """Publish only the current canonical child output to its Vetron parent."""
    parent = "apps/vetron/CMakeLists.txt"
    child = "apps/vetron/wasm/CMakeLists.txt"
    variable = "VETRON_MATH_WASM_OUTPUT"
    outputs = {
        (repository_root / "apps/vetron/frontend/.generated/trading-core-math.wasm").as_posix(),
        f"{binary_root}/apps/vetron/frontend-generated/trading-core-math.wasm",
        f"{binary_root}/apps/vetron/wasm/trading-core-math.wasm",
    }
    return bool(
        active.relative == child and active.command.name == "set" and
        active.command.line == 29 and not active.structural_context and
        active.source_base.as_posix() == "apps/vetron/wasm" and
        active.binary_base.as_posix() == "apps/vetron/wasm" and
        active.directory[-2:] == (parent, child) and
        signature.variable == variable and signature.parent_scope and
        signature.cache_type is None and not signature.force and
        signature.values == state.get(variable) and
        len(signature.values) == 1 and signature.values[0] in outputs)
