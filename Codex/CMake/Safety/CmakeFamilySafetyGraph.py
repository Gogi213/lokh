"""Compose the optional root safety branch without activating it by default."""

from __future__ import annotations

from pathlib import Path

from CMake.Syntax.CmakeFamilyDialect import validate_active_dialect
from CMake.Flow.CmakeFamilyGraph import (
    cmake_list_words,
    compose_active_commands,
    function_model,
    instantiated_commands,
    variable_snapshots,
)
from CMake.Flow.CmakeFamilyInstances import GRAPH_INSTANCE_NAMES, directory_target_types
from CMake.Safety.CmakeFamilySafetyPolicy import SAFETY_CMAKE, validate_safety_suite
from CMake.Safety.CmakeFamilySafetyValues import validate_safety_values
from CMake.Policy.CmakeFamilyCommandPolicy import validate_command_policies
from CMake.Policy.CmakeFamilyLoopPolicy import validate_loop_writer_boundary


def validate_safety_callable_collisions(
    safety_callables, family_model, errors: list[str]
) -> None:
    collisions = sorted(
        set(family_model.global_definitions) & set(safety_callables))
    if collisions:
        errors.append(
            "src/tests CMake callable collides with active family graph: " +
            ", ".join(collisions))


def ownership_graph_instances(instances):
    """Exclude only safety link-option forms proven by its exact policy."""
    return [
        instance for instance in instances
        if not (
            instance.body.relative == SAFETY_CMAKE and
            instance.body.command.name in {
                "add_link_options", "target_link_options"})
    ]


def validate_safety_family_graph(
    root: Path,
    files,
    approved_external_subdirectories,
    errors: list[str],
) -> tuple[list, list, frozenset[str], object]:
    """Model the root's explicit safety scenarios in src/tests."""
    commands = compose_active_commands(
        root,
        files,
        (SAFETY_CMAKE,),
        approved_external_subdirectories,
        errors,
    )
    model = function_model(commands, errors)
    validate_loop_writer_boundary(commands, errors)
    validate_active_dialect(
        commands, set(model.global_definitions), cmake_list_words, errors)
    initial = {
        "CXET_LIB_INCLUDE_DIR": (
            (root / "src/src/Core/include").as_posix(),
            (root / "src/src/Contracts/include").as_posix(),
        ),
        "CXET_SAFETY_BUILD": ("ON",),
        "CXET_SANITIZER_PROFILE": ("thread", "address-undefined"),
        "CXET_STRESS_SANITIZERS": ("ON",),
    }
    bootstrap = variable_snapshots(commands, model, [], initial)
    bootstrap_instances = instantiated_commands(
        commands, model, bootstrap, GRAPH_INSTANCE_NAMES, [])
    target_types = directory_target_types(bootstrap_instances)
    snapshots = variable_snapshots(
        commands, model, errors, initial, target_types)
    instances = instantiated_commands(
        commands, model, snapshots, GRAPH_INSTANCE_NAMES, errors,
        target_types)
    validate_safety_suite(
        commands, instances, cmake_list_words,
        snapshots.viable_ordinals, errors)
    validate_safety_values(commands, instances, errors)
    policy_instances = [
        instance for instance in instances
        if not (
            instance.body.command.name == "add_custom_target" and
            instance.token_groups and
            instance.token_groups[0] == ("cxet_safety_suite",))
    ]
    validate_command_policies(
        policy_instances, cmake_list_words, errors, target_types,
        require_registry=False)
    return commands, instances, frozenset(model.global_definitions), snapshots
