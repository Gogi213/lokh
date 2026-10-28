"""Deterministic TARGET property parsing for instantiated CMake commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetPropertyMutation:
    target: str
    name: str
    values: tuple[str, ...]
    append: bool
    append_string: bool = False


def _ambiguous(group: list[str]) -> bool:
    return (
        len(group) != 1 or
        any(marker in group[0] for marker in (
            "${", "$ENV{", "$CACHE{", "$<"))
    )


def target_property_mutations(
    instance,
) -> tuple[list[TargetPropertyMutation], list[str]]:
    """Return literal TARGET mutations plus ambiguous property spellings."""
    command = instance.body.command
    groups = [list(group) for group in instance.token_groups]
    if command.name == "set_property":
        if not groups or groups[0] != ["TARGET"]:
            return [], []
        property_index = next(
            (index for index, group in enumerate(groups)
             if group == ["PROPERTY"]),
            None,
        )
        if property_index is None:
            ambiguous = [
                value
                for group in groups[1:]
                for value in group
                if any(marker in value for marker in (
                    "${", "$ENV{", "$CACHE{", "$<"))
            ]
            return [], ambiguous
        if property_index + 1 >= len(groups):
            return [], ["<missing>"]
        property_group = groups[property_index + 1]
        if _ambiguous(property_group):
            return [], [";".join(property_group) or "<empty>"]
        prefix = [
            token
            for group in groups[1:property_index]
            for token in group
        ]
        append = any(
            token in {"APPEND", "APPEND_STRING"}
            for token in prefix
        )
        append_string = any(
            token == "APPEND_STRING" for token in prefix)
        targets = [
            token for token in prefix
            if token not in {"APPEND", "APPEND_STRING"}
        ]
        values = tuple(
            token
            for group in groups[property_index + 2:]
            for token in group
        )
        return [
            TargetPropertyMutation(
                target, property_group[0], values, append,
                append_string)
            for target in targets
        ], []

    if command.name != "set_target_properties":
        return [], []
    properties_index = next(
        (index for index, group in enumerate(groups)
         if group == ["PROPERTIES"]),
        None,
    )
    if properties_index is None:
        ambiguous = [
            value
            for group in groups
            for value in group
            if any(marker in value for marker in (
                "${", "$ENV{", "$CACHE{", "$<"))
        ]
        return [], ambiguous
    targets = [
        token
        for group in groups[:properties_index]
        for token in group
    ]
    tail = groups[properties_index + 1:]
    ambiguous: list[str] = []
    result: list[TargetPropertyMutation] = []
    if len(tail) % 2:
        ambiguous.append("<missing-value>")
    for index in range(0, len(tail) - 1, 2):
        property_group = tail[index]
        if _ambiguous(property_group):
            ambiguous.append(";".join(property_group) or "<empty>")
            continue
        values = tuple(tail[index + 1])
        result.extend(
            TargetPropertyMutation(
                target, property_group[0], values, False)
            for target in targets
        )
    return result, ambiguous


def property_edges(
    instance,
    property_names: frozenset[str],
) -> list[tuple[str, list[str]]]:
    mutations, _ = target_property_mutations(instance)
    return [
        (mutation.target, list(mutation.values))
        for mutation in mutations
        if mutation.name in property_names
    ]


def ambiguous_target_property_names(instance) -> list[str]:
    _, ambiguous = target_property_mutations(instance)
    return ambiguous


def directory_link_property_names(instance) -> list[str]:
    """Return LINK-like directory properties, including unresolved names."""
    groups = [list(group) for group in instance.token_groups]
    command = instance.body.command
    if command.name == "set_property":
        if not groups or groups[0] != ["DIRECTORY"]:
            return []
        property_index = next(
            (index for index, group in enumerate(groups)
             if group == ["PROPERTY"]),
            None,
        )
        if property_index is None or property_index + 1 >= len(groups):
            return ["<unresolved>"]
        group = groups[property_index + 1]
        if _ambiguous(group):
            return [";".join(group) or "<unresolved>"]
        return [group[0]] if "LINK" in group[0] else []
    if command.name != "set_directory_properties":
        return []
    properties_index = next(
        (index for index, group in enumerate(groups)
         if group == ["PROPERTIES"]),
        None,
    )
    if properties_index is None:
        return ["<unresolved>"]
    result: list[str] = []
    tail = groups[properties_index + 1:]
    if len(tail) % 2:
        result.append("<unresolved>")
    for group in tail[::2]:
        if _ambiguous(group):
            result.append(";".join(group) or "<unresolved>")
        elif "LINK" in group[0]:
            result.append(group[0])
    return result
