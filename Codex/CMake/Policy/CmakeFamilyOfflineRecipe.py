"""Provenance carried only by validated canonical offline helper expansion."""

from dataclasses import dataclass
from pathlib import Path

from CMake.Flow.CmakeFamilyGraph import Command


@dataclass(frozen=True)
class OfflineRegistration:
    target: str
    relative: str
    owner: str
    sources: tuple[str, ...]
    libraries: tuple[str, ...]
    includes: tuple[str, ...]


@dataclass(frozen=True)
class OfflineCommand(Command):
    registration: OfflineRegistration


def offline_registration(instance, target: str) -> OfflineRegistration | None:
    """A target spelling or physical test directory alone grants no capability.

    The composer must retain the same validated helper tag at the physical
    command and its evaluation site. Callable/foreign evaluation cannot borrow
    a helper's exceptions by reusing its target name.
    """
    body, evaluation = instance.body, instance.evaluation
    if body is not evaluation:
        # instantiated_commands emits direct effects with the same active
        # occurrence in both slots. Callable effects have a distinct caller.
        return None
    registration = getattr(body.command, "registration", None)
    if not isinstance(registration, OfflineRegistration) or registration.target != target:
        return None
    if getattr(evaluation.command, "registration", None) is not registration:
        return None
    origin = Path(registration.relative).parent
    if any(active.relative != registration.relative or
           active.source_base != origin or active.binary_base != origin
           for active in (body, evaluation)):
        return None
    if (body.structural_context != evaluation.structural_context or
            body.execution_chain != evaluation.execution_chain):
        return None
    return registration


def offline_instance_context(instance, target: str) -> bool:
    registration = offline_registration(instance, target)
    return bool(registration is not None and registration.owner == "CXETCPP" and
                registration.relative == "src/tests/offline/CMakeLists.txt")


def offline_instrument_context(active, commands) -> bool:
    """An explicit instrument call retains its validated local producer tag."""
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    from types import SimpleNamespace
    registration = getattr(active.command, "registration", None)
    if not isinstance(registration, OfflineRegistration):
        return False
    target = registration.target
    if (active.command.name != "cxet_offline_instrument" or
            cmake_list_words(active.command.body) != [target] or
            offline_registration(SimpleNamespace(body=active, evaluation=active), target) is not registration or
            any(frame.kind != "if" for frame in active.structural_context)):
        return False
    declarations = [item for item in commands
        if item.command.name == "add_executable" and item.ordinal < active.ordinal and
        getattr(item.command, "registration", None) is registration and
        cmake_list_words(item.command.body)[:1] == [target] and
        all(getattr(item, key) == getattr(active, key) for key in (
            "scope", "relative", "source_base", "binary_base", "directory",
            "structural_context", "execution_chain"))]
    return len(declarations) == 1


_PARSER_LAUNCHER_CASES = {
    137: ("launcher_storage_explicit_writable_refusal", "StorageAuthority.test_explicit_writable_root_is_rejected"),
    140: ("launcher_executable_retained_descriptor", "ExecutableAuthority.test_retained_executable_survives_path_replacement"),
    143: ("launcher_executable_unsafe_ancestor_refusal", "ExecutableAuthority.test_writable_ancestor_and_special_executable_are_rejected"),
    146: ("launcher_storage_unsafe_ancestor_refusal", "StorageAuthority.test_unsafe_ancestor_is_rejected_before_children_creation"),
}


def parser_launcher_test_recipe(instance) -> bool:
    """One current cold script recipe, including its exact guarded properties."""
    from CMake.Syntax.CmakeFamilyContext import exact_context, first_if
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity
    relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
    active = instance.body
    if (active is not instance.evaluation or active.relative != relative or
            active.source_base != Path(relative).parent or active.binary_base != Path(relative).parent or
            not exact_context(active.structural_context,
                (first_if(relative, 131, ("CXET_SELECTION_ALL",)),)) or
            not reviewed_file_identity("apps/hft-parser/tests/offline/Launcher/launcher-storage-authority.py")):
        return False
    command = active.command
    case = _PARSER_LAUNCHER_CASES.get(command.line)
    if command.name == "add_test" and case is not None:
        expected = ["NAME", "offline.hft-parser." + case[0], "COMMAND", "${Python3_EXECUTABLE}",
                    "${CMAKE_CURRENT_SOURCE_DIR}/Launcher/launcher-storage-authority.py", case[1]]
        expanded = [value.replace("${CMAKE_CURRENT_SOURCE_DIR}", Path(relative).parent.as_posix())
                    for value in expected]
        return (cmake_list_words(command.body) == expected and
                [value for group in instance.token_groups for value in group] == expanded)
    names = ["offline.hft-parser." + _PARSER_LAUNCHER_CASES[line][0] for line in (140, 143, 137, 146)]
    return (command.name == "set_tests_properties" and command.line == 149 and
            cmake_list_words(command.body) == [*names, "PROPERTIES", "LABELS",
                "owner:hft-parser;offline;launcher;standalone", "TIMEOUT", "30"])
