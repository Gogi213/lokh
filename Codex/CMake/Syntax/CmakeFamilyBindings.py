"""Fail-closed implicit CMake binding and loop-alternative helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from CMake.Policy.CmakeFamilyEffectPolicy import effect_variable
from CMake.Flow.CmakeFamilyState import ZERO_LIST_ALTERNATIVE


def invalid_binding(variable: str) -> bool:
    return (
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable) is None or
        effect_variable(variable)
    )


def invalid_formals(parameters: list[str]) -> list[str]:
    return [parameter for parameter in parameters if invalid_binding(parameter)]


def loop_alternatives(
    expanded: tuple[str, ...],
    *,
    list_mode: bool,
) -> tuple[tuple[str, ...], bool]:
    """Separate executable iterations from a typed zero-list branch.

    Duplicates and explicit empty ITEMS are real iterations.  A LISTS value
    that is solely empty executes zero times, while an internal empty element
    in a non-empty list remains an iteration.  The internal state sentinel
    records a branch whose list is defined-empty without impersonating data.
    """
    zero_possible = ZERO_LIST_ALTERNATIVE in expanded
    values = tuple(value for value in expanded
                   if value != ZERO_LIST_ALTERNATIVE)
    if list_mode and values == ("",):
        return (), True
    return values, zero_possible


@dataclass(frozen=True)
class ForeachBinding:
    variable: str
    mode: str
    operands: tuple[str, ...]


_FOREACH_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")


def parse_foreach_binding(
    raw_words: list[str],
) -> tuple[ForeachBinding | None, str | None]:
    """Classify the restricted foreach grammar before expanding any value."""
    if len(raw_words) < 2:
        return None, "foreach requires one literal binding and values"
    variable = raw_words[0]
    if invalid_binding(variable) or any(
            marker in variable for marker in _FOREACH_CARRIERS):
        return None, f"invalid/build-effect foreach binding {variable}"

    first = raw_words[1]
    if any(marker in first for marker in _FOREACH_CARRIERS):
        return None, f"dynamic foreach grammar token {first}"
    if first in {"RANGE", "ZIP_LISTS"}:
        return None, f"unsupported foreach({first}) grammar"

    if first == "IN":
        if len(raw_words) < 3:
            return None, "foreach(IN) misses its literal mode"
        mode = raw_words[2]
        if any(marker in mode for marker in _FOREACH_CARRIERS):
            return None, f"dynamic foreach(IN) mode {mode}"
        operands = tuple(raw_words[3:])
        if mode == "LISTS":
            if len(operands) != 1 or invalid_binding(operands[0]):
                return None, (
                    "foreach(IN LISTS) requires exactly one literal list "
                    "variable")
        elif mode == "ITEMS":
            if not operands or any(
                    any(marker in value for marker in _FOREACH_CARRIERS)
                    for value in operands):
                return None, (
                    "foreach(IN ITEMS) requires carrier-free literal items")
        else:
            return None, f"unsupported foreach(IN {mode}) grammar"
        return ForeachBinding(variable, mode, operands), None

    operands = tuple(raw_words[1:])
    if any(
            any(marker in value for marker in _FOREACH_CARRIERS)
            for value in operands):
        return None, "legacy foreach requires carrier-free literal items"
    return ForeachBinding(variable, "ITEMS", operands), None


def validate_foreach_binding_microcases(errors: list[str]) -> None:
    lowercase, failure = parse_foreach_binding(
        ["_fixture_test", "in", "LISTS", "_fixture_tests"])
    expected = ForeachBinding(
        "_fixture_test", "ITEMS",
        ("in", "LISTS", "_fixture_tests"))
    if failure is not None or lowercase != expected:
        errors.append(
            "foreach-binding self-check case-folded lowercase legacy "
            "operands into canonical IN LISTS")

    lowercase_mode, failure = parse_foreach_binding(
        ["item", "IN", "lists", "items"])
    if lowercase_mode is not None or failure is None:
        errors.append(
            "foreach-binding self-check accepted lowercase canonical mode")


def expand_foreach_values(
    binding: ForeachBinding,
    state: dict[str, tuple[str, ...]],
    expand,
) -> tuple[tuple[str, ...], bool]:
    """Expand values after grammar classification, preserving zero LISTS."""
    if binding.mode == "LISTS":
        variable = binding.operands[0]
        raw_values = state.get(variable)
        if not raw_values:
            return (), True
        zero_possible = ZERO_LIST_ALTERNATIVE in raw_values
        concrete = tuple(value for value in raw_values
                         if value != ZERO_LIST_ALTERNATIVE)
        expanded = list(expand(concrete, True))
        if f"${{{variable}}}" in raw_values:
            zero_possible = True
        values, expanded_zero = loop_alternatives(
            tuple(expanded), list_mode=True)
        return values, zero_possible or expanded_zero
    else:
        expanded = list(expand(binding.operands, True))
    return loop_alternatives(tuple(expanded), list_mode=False)
