"""Root owns no auxiliary executables after retiring the old benchmark tree.

Products and owner-local suites are declared by their direct source owners.
Any new root executable/library or dependency requires a reviewed inventory.
"""
from __future__ import annotations

_DECLARATIONS = {}
_LINKS = {}
_INCLUDES = {}
_EFFECT_COUNTS = {}
_EFFECT_NAMES = ("target_include_directories", "target_compile_features",
    "target_compile_options", "target_compile_definitions", "target_link_libraries",
    "target_link_options", "set_target_properties", "add_dependencies")


def validate_root_target_inventory(commands, tokenize, errors: list[str]) -> None:
    declarations = {}
    links = {}
    includes = {}
    effects = {target: [0] * len(_EFFECT_NAMES) for target in _DECLARATIONS}
    for command in commands:
        tokens = tokenize(command.body)
        if not tokens:
            continue
        target = tokens[0]
        if command.name in {"add_library", "add_executable"}:
            declarations.setdefault(target, []).append(
                (command.name, tuple(tokens[1:])))
        if target not in effects:
            continue
        if command.name == "target_link_libraries":
            links.setdefault(target, []).append(tuple(tokens[1:]))
        if command.name == "target_include_directories":
            includes.setdefault(target, []).append(tuple(tokens[1:]))
        if command.name in _EFFECT_NAMES:
            effects[target][_EFFECT_NAMES.index(command.name)] += 1
    if set(declarations) != set(_DECLARATIONS):
        errors.append(
            "CMakeLists.txt: root-owned target declaration set changed: "
            f"{sorted(declarations)}")
    for target, expected in _DECLARATIONS.items():
        if declarations.get(target) != [expected]:
            errors.append(
                f"CMakeLists.txt: root target {target} source/declaration "
                "inventory changed")
        expected_link = _LINKS.get(target)
        actual_links = links.get(target, [])
        if actual_links != ([] if expected_link is None else [expected_link]):
            errors.append(
                f"CMakeLists.txt: root target {target} link inventory changed")
        if tuple(includes.get(target, ())) != _INCLUDES[target]:
            errors.append(
                f"CMakeLists.txt: root target {target} include inventory "
                "changed")
        if tuple(effects[target]) != _EFFECT_COUNTS[target]:
            errors.append(
                f"CMakeLists.txt: root target {target} mutation-count "
                "inventory changed")
    dependencies = [
        tuple(tokenize(command.body)) for command in commands
        if command.name == "add_dependencies"]
    if dependencies:
        errors.append("CMakeLists.txt: root build-dependency inventory changed")
