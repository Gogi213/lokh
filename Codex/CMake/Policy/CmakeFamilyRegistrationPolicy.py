"""Positive target compile, test-registration, and install grammar."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Flow.CmakeFamilyFlow import paths_intersect
from CMake.Policy.CmakeFamilyProgramPolicy import (
    reviewed_file_identity,
    reviewed_program,
)
from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_tree_identity
from Family.Targets.CxetFamilyTargetPolicy import (
    declaration_precedes,
    unsafe_compile_definition_carriers,
)


ROOT = Path(__file__).resolve().parents[4]
REGISTRATION_POLICY_NAMES = frozenset({
    "add_test", "install", "target_compile_definitions",
    "target_compile_features", "set_tests_properties",
})
_CARRIERS = ("${", "$ENV{", "$CACHE{")
_SCOPES = frozenset({"PRIVATE", "PUBLIC", "INTERFACE"})


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _flatten(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _opaque(value: str) -> bool:
    return any(marker in value for marker in _CARRIERS)


def _project_root(active) -> str | None:
    parts = active.source_base.parts
    if parts[:2] in {("src", "src"), ("src", "tests")}:
        return "/".join(parts[:2])
    if len(parts) >= 2 and parts[0] in {"apps", "tools"}:
        return "/".join(parts[:2])
    return None


def _has_target(contexts, target: str) -> bool:
    return (
        target in contexts.by_name
        if hasattr(contexts, "by_name") else target in contexts
    )


def _context_for_use(contexts, target: str, instance):
    return (
        contexts.context_for_use(target, instance)
        if hasattr(contexts, "context_for_use") else contexts.get(target)
    )


def _declaration_precedes(contexts, declaration, instance) -> bool:
    # A registry context was returned only after scope-aware prior/coverage
    # resolution.  The free helper is deliberately restricted to same-scope
    # compatibility callers.
    return (
        True if hasattr(contexts, "context_for_use") else
        declaration_precedes(declaration, instance)
    )



def _target_compile(
    instance,
    contexts,
    errors: list[str],
) -> None:
    groups = [list(group) for group in instance.token_groups]
    origin = _origin(instance)
    if not groups or len(groups[0]) != 1 or _opaque(groups[0][0]):
        errors.append(f"{origin}: unresolved target compile mutation owner")
        return
    target = groups[0][0]
    tail = [value for group in groups[1:] for value in group]
    if not tail or tail[0] not in _SCOPES:
        errors.append(f"{origin}: target compile mutation misses exact scope")
        return
    declaration = (
        _context_for_use(contexts, target, instance)
        if _has_target(contexts, target) else None)
    if declaration is None:
        errors.append(f"{origin}: compile mutation target {target} is undeclared")
        return
    if not _declaration_precedes(contexts, declaration, instance):
        errors.append(f"{origin}: compile mutation precedes target {target}")
        return
    if (_project_root(declaration.evaluation) !=
            _project_root(instance.evaluation)):
        errors.append(
            f"{origin}: compile mutation of {target} is outside its "
            "declaration owner")
        return
    values = [value for value in tail if value not in _SCOPES]
    if instance.body.command.name == "target_compile_features":
        if values != ["cxx_std_23"]:
            errors.append(f"{origin}: unapproved target compile features {values}")
        return
    if not values or any(
            not value or value in _SCOPES or value.startswith("-")
            for value in values):
        errors.append(f"{origin}: malformed target compile definitions {values}")
        return
    unsafe_carriers = unsafe_compile_definition_carriers(
        instance, target, values)
    if unsafe_carriers:
        errors.append(
            f"{origin}: unresolved or unreviewed target compile "
            f"definitions {list(unsafe_carriers)}")


def _target_file(value: str) -> str | None:
    match = re.fullmatch(r"\$<TARGET_FILE:([^>$]+)>", value)
    return match.group(1) if match is not None else None


def _repo_path(value: str) -> str | None:
    if _opaque(value) or "$<" in value:
        return None
    path = Path(value)
    candidate = path if path.is_absolute() else ROOT / path
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _reviewed_script(instance, command: list[str]) -> bool:
    relative = instance.body.relative
    if relative == "apps/hft-parser/tests/offline/CMakeLists.txt":
        from CMake.Policy.CmakeFamilyOfflineRecipe import parser_launcher_test_recipe
        return parser_launcher_test_recipe(instance)
    if relative == "apps/hft-parser/cmake/HftpTests.cmake":
        return (
            command == [
                "bash", 'apps/hft-parser/tests/Contracts/BoundaryTests.sh'] and
            reviewed_file_identity(
                'apps/hft-parser/tests/Contracts/BoundaryTests.sh') and
            reviewed_file_identity(
                "apps/hft-parser/scripts/check-source-ownership.sh"))
    if relative == "apps/hft-parser/benchmarks/CMakeLists.txt":
        return (
            len(command) == 2 and
            command[0] == reviewed_program("python3") and
            _repo_path(command[1]) ==
            "src/benchmarks/MarketIngress/tests/TestManifestContract.py" and
            reviewed_file_identity(
                "src/benchmarks/MarketIngress/tests/TestManifestContract.py") and
            reviewed_file_identity(
                "src/benchmarks/MarketIngress/ManifestContract.py")
        )
    if relative == "src/tests/Family/CMakeLists.txt":
        return (
            len(command) == 4 and
            command[:3] == ["${Python3_EXECUTABLE}", "-I", "-S"] and
            _repo_path(command[3]) in {
                "tools/Codex/CheckCxetFamilyRootGraph.py",
                "tools/Codex/CheckCxetFamilyOwnership.py",
            }
        )
    if relative == "apps/vetron/CMakeLists.txt":
        return (
            len(command) == 5 and command[0] == reviewed_program("npm") and
            command[1] == "--prefix" and
            _repo_path(command[2]) == "apps/vetron/frontend" and
            command[3:] == ["run", "test:contracts"] and
            reviewed_file_identity("apps/vetron/frontend/package.json") and
            reviewed_tree_identity("vetron_frontend")
        )
    return False




def _add_test(
    instance, contexts, names: dict[str, list[object]],
    errors: list[str],
) -> None:
    tokens = _flatten(instance)
    origin = _origin(instance)
    if len(tokens) < 4 or tokens[0] != "NAME":
        errors.append(f"{origin}: add_test must use NAME/COMMAND grammar")
        return
    try:
        command_index = next(
            index for index, value in enumerate(tokens)
            if value == "COMMAND")
    except StopIteration:
        errors.append(f"{origin}: add_test misses COMMAND")
        return
    if command_index != 2 or len(tokens[1:command_index]) != 1:
        errors.append(f"{origin}: ambiguous add_test name/signature")
        return
    name = tokens[1]
    if (_opaque(name) or "$<" in name or
            re.fullmatch(r"[A-Za-z0-9_.+:-]+", name) is None):
        errors.append(f"{origin}: unresolved add_test name {name}")
        return
    overlapping = [
        previous for previous in names.get(name, ())
        if paths_intersect(
            previous.path_alternatives, instance.path_alternatives)
    ]
    if overlapping:
        errors.append(f"{origin}: duplicate active test registration {name}")
    names.setdefault(name, []).append(instance)
    command = tokens[command_index + 1:]
    if not command:
        errors.append(f"{origin}: empty add_test command")
        return
    executable = command[0]
    target = _target_file(executable) or executable
    if _has_target(contexts, target):
        declaration = _context_for_use(contexts, target, instance)
        if declaration is None:
            errors.append(
                f"{origin}: add_test command target {target} has no active "
                "declaration on this control-flow path")
            return
        if declaration.body.command.name != "add_executable":
            errors.append(
                f"{origin}: add_test command target {target} is not an "
                "executable")
            return
        if not _declaration_precedes(contexts, declaration, instance):
            errors.append(
                f"{origin}: add_test command target {target} is used before "
                "declaration")
            return
        if (_project_root(declaration.evaluation) !=
                _project_root(instance.evaluation)):
            errors.append(
                f"{origin}: add_test registration for {target} crosses "
                "product ownership")
            return
        for argument in command[1:]:
            argument_target = _target_file(argument)
            if (_opaque(argument) or
                    ("$<" in argument and (
                        argument_target is None or
                        not _has_target(contexts, argument_target)))):
                errors.append(f"{origin}: opaque add_test argument {argument}")
        return
    if not _reviewed_script(instance, command):
        errors.append(f"{origin}: unapproved add_test executable {executable}")




def _install(instance, errors: list[str], snapshots=None) -> None:
    tokens = _flatten(instance)
    relative = instance.body.relative
    approved = False
    if relative == "apps/hft-parser/cmake/HftpProcesses.cmake":
        processes = ["hft-parserd", "hft-algosd", "hft-resource-planner"]
        selection = (None if snapshots is None else snapshots.values.get(
            instance.evaluation.ordinal, {}).get("CXET_EXCHANGE_FINAM"))
        if selection in {("ON",), ("OFF",), ("1",), ("0",)}:
            if selection in {("ON",), ("1",)}:
                processes.append("hft-finam-metadata-store")
            approved = tokens == ["TARGETS", *processes, "RUNTIME", "DESTINATION",
                                  "${CMAKE_INSTALL_BINDIR}"]
    if not approved:
        errors.append(f"{_origin(instance)}: unapproved install grammar {tokens}")




def validate_registration_policies(
    instances,
    registry,
    errors: list[str],
    verification_friend_proof: frozenset[int] = frozenset(),
    *, snapshots=None,
) -> None:
    """Validate commands removed from the old harmless classification."""
    del verification_friend_proof
    contexts = registry
    test_names: dict[str, list[object]] = {}
    for instance in instances:
        command = instance.body.command.name
        if command in {"target_compile_definitions", "target_compile_features"}:
            _target_compile(instance, contexts, errors)
        elif command == "add_test":
            _add_test(
                instance, contexts, test_names, errors)
        elif command == "install":
            _install(instance, errors, snapshots)
