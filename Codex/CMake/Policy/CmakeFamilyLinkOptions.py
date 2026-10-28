"""Narrow allowlist for non-library target_link_options values."""

from __future__ import annotations

import re


SAFE_RAW_LINK_OPTIONS = frozenset({
    "-flto",
    "-fno-omit-frame-pointer",
    "-fno-sanitize-recover=all",
    "-fsanitize=address,undefined",
    "-fsanitize=fuzzer,address,undefined",
    "-fsanitize=thread",
})


def exact_benchmark_link_options(instance, targets: list[str], values: list[str]) -> bool:
    from Family.Targets.CxetFamilyBuildPolicy import benchmark_instance_context
    return (len(targets) == 1 and targets[0].endswith("_traced") and
            benchmark_instance_context(instance, targets[0]) and
            instance.body.command.name == "target_link_options" and
            [value for group in instance.token_groups for value in group] ==
            [targets[0], "PRIVATE", "-Wl,--wrap=send"] and
            values == ["-Wl,--wrap=send"])


def exact_offline_link_options(instance, targets: list[str], values: list[str]) -> bool:
    from Family.Targets.CxetFamilyBuildPolicy import (
        exact_offline_options, OFFLINE_LINK_OPTION_RECIPES, PARSER_OFFLINE_LINK_OPTION_RECIPES,
        TRADER_OFFLINE_LINK_OPTION_RECIPES, DIAGNOSTIC_OFFLINE_LINK_OPTION_RECIPES,
    )
    if len(targets) != 1:
        return False
    for owner, recipes in (("CXETCPP", OFFLINE_LINK_OPTION_RECIPES),
                           ("hft-parser", PARSER_OFFLINE_LINK_OPTION_RECIPES),
                           ("trader", TRADER_OFFLINE_LINK_OPTION_RECIPES),
                           ("diagnostic", DIAGNOSTIC_OFFLINE_LINK_OPTION_RECIPES)):
        if (targets[0] in recipes and values == list(recipes[targets[0]][1]) and
                exact_offline_options(instance, "target_link_options", recipes, owner=owner)):
            return True
    return False


def _split_top_level(value: str, delimiter: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value):
        if value.startswith("$<", index):
            depth += 1
            index += 2
            continue
        if value[index] == ">" and depth:
            depth -= 1
        elif value[index] == delimiter and depth == 0:
            result.append(value[start:index])
            start = index + 1
        index += 1
    result.append(value[start:])
    return result


def _generator(value: str) -> tuple[str, str] | None:
    if not value.startswith("$<") or not value.endswith(">"):
        return None
    content = value[2:-1]
    depth = 0
    for index, character in enumerate(content):
        if content.startswith("$<", index):
            depth += 1
        elif character == ">" and depth:
            depth -= 1
        elif character == ":" and depth == 0:
            return content[:index], content[index + 1:]
    return content, ""


def safe_link_option(value: str) -> bool:
    if "\\" in value:
        return False
    parsed = _generator(value)
    if parsed is None:
        return value in SAFE_RAW_LINK_OPTIONS
    operator, payload = parsed
    upper = operator.upper()
    if upper == "IF":
        branches = _split_top_level(payload, ",")
        return (
            len(branches) == 3 and
            all(not branch or safe_link_option(branch)
                for branch in branches[1:])
        )
    if upper in {"BUILD_INTERFACE", "LINK_ONLY"} or operator.startswith("$<"):
        values = [item for item in _split_top_level(payload, ";") if item]
        return bool(values) and all(safe_link_option(item) for item in values)
    return False
