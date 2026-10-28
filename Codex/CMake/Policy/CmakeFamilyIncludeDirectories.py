"""Exact argument grammar for target_include_directories()."""

from __future__ import annotations


_SCOPES = frozenset({"INTERFACE", "PRIVATE", "PUBLIC"})
_PREFIX = frozenset({"AFTER", "BEFORE", "SYSTEM"})


def target_include_groups(
    tokens: list[str],
) -> tuple[list[tuple[str, str]], str | None]:
    """Return scoped directory items without hiding item/control homonyms."""
    if len(tokens) < 3:
        return [], "target_include_directories requires target, scope, and item"
    index = 1
    if tokens[index] in _PREFIX:
        return [], (
            "target_include_directories ordering/system modifiers are "
            "unsupported in the reviewed family graph")
    if index >= len(tokens) or tokens[index] not in _SCOPES:
        return [], "target_include_directories has an invalid modifier/scope prefix"

    items: list[tuple[str, str]] = []
    while index < len(tokens):
        if tokens[index] not in _SCOPES:
            return [], "target_include_directories expected a visibility scope"
        scope = tokens[index]
        index += 1
        group_start = len(items)
        while index < len(tokens) and tokens[index] not in _SCOPES:
            # SYSTEM/BEFORE/AFTER are ordinary directory spellings here.  Keep
            # them so the path policy rejects any hidden shadow include root.
            items.append((scope, tokens[index]))
            index += 1
        if len(items) == group_start:
            return [], "target_include_directories has an empty scope group"
    return items, None


def target_include_items(tokens: list[str]) -> tuple[list[str], str | None]:
    """Return only directory values for existing ownership consumers."""
    groups, failure = target_include_groups(tokens)
    return [value for _, value in groups], failure


def validate_target_include_directory_microcases(errors: list[str]) -> None:
    accepted, failure = target_include_items([
        "target", "PUBLIC", "include", "PRIVATE", "src",
    ])
    if failure is not None or accepted != ["include", "src"]:
        errors.append(
            "target include grammar self-check rejected its exact baseline")
    for label, tokens in (
        ("trailing SYSTEM", ["target", "PRIVATE", "SYSTEM"]),
        ("trailing BEFORE", ["target", "PRIVATE", "BEFORE"]),
        ("trailing AFTER", ["target", "PRIVATE", "AFTER"]),
    ):
        items, failure = target_include_items(tokens)
        if failure is not None or items != [tokens[-1]]:
            errors.append(
                f"target include grammar self-check hid {label} item")
    for label, tokens in (
        ("empty group", ["target", "PRIVATE", "PUBLIC", "include"]),
        ("SYSTEM modifier", ["target", "SYSTEM", "PUBLIC", "include"]),
        ("BEFORE modifier", ["target", "BEFORE", "PUBLIC", "include"]),
        ("modifier order", ["target", "BEFORE", "SYSTEM", "PRIVATE", "x"]),
        ("missing scope", ["target", "include", "PRIVATE", "x"]),
    ):
        _, failure = target_include_items(tokens)
        if failure is None:
            errors.append(
                f"target include grammar self-check accepted {label}")
