"""Positive operand policy for the optional src/tests ownership scenario."""

from __future__ import annotations

from pathlib import Path

from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Safety.CmakeFamilySafetyPolicy import SAFETY_CMAKE, SAFETY_FUZZ_SOURCES
from CMake.Flow.CmakeFamilyState import SYNTHETIC_BINARY_ROOT


ROOT = Path(__file__).resolve().parents[4]
_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_STANDARD_LINKS = ["PRIVATE", "cxet_lib", "GTest::gtest", "GTest::gtest_main"]
_CORE_INCLUDES = (
    "src/src/Core/include",
    "src/src/Contracts/include",
)
_CORE_PRIVATE_INCLUDE = "src/src/Core/src"
_LOCAL_INCLUDE = "src/tests"

_FORBIDDEN_EFFECTS = frozenset({
    "add_custom_command", "add_dependencies", "configure_file", "file",
    "install", "link_libraries", "set_directory_properties",
    "set_property", "set_source_files_properties", "target_compile_features",
    "target_precompile_headers", "target_sources",
})


def _origin(value) -> str:
    return f"{value.body.relative}:{value.body.command.line}"


def _flat(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _local_targets(instances) -> set[str]:
    return {
        instance.token_groups[0][0]
        for instance in instances
        if instance.body.relative == SAFETY_CMAKE and
        instance.body.command.name in {
            "add_executable", "add_library", "add_custom_target"} and
        instance.token_groups and len(instance.token_groups[0]) == 1 and
        not any(marker in instance.token_groups[0][0]
                for marker in _CARRIERS)
    }


def _repo_path(instance, value: str) -> str | None:
    if any(marker in value for marker in _CARRIERS):
        return None
    path = Path(value)
    source = instance.evaluation.source_base
    normalized = path.as_posix().rstrip("/")
    source_text = source.as_posix().rstrip("/")
    if path.is_absolute():
        candidate = path
    elif normalized == source_text or normalized.startswith(source_text + "/"):
        candidate = ROOT / path
    else:
        candidate = ROOT / source / path
    try:
        return candidate.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None


def _validate_links(instance, local: set[str], errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    if target not in local:
        errors.append(f"{_origin(instance)}: non-local safety link owner {target}")
        return
    tail = tokens[1:]
    if target in SAFETY_FUZZ_SOURCES:
        expected = ["PRIVATE", "cxet_lib"]
    elif target == "hot_string_view_tests":
        expected = _STANDARD_LINKS + ["absl::flat_hash_map"]
    elif target == "local_symbol_tests":
        expected = _STANDARD_LINKS + ["absl::flat_hash_map", "absl::btree"]
    elif target == "fixed_ready_route_queue_tests":
        expected = ["PRIVATE", "GTest::gtest", "GTest::gtest_main"]
    elif target in {
            "public_market_execution_families_tests",
            "grpc_socket_immediate_tests"}:
        expected = ["PRIVATE", "cxet_lib"]
    elif target in {"replay_config_tests", "replay_session_tests"}:
        expected = (
            ["PRIVATE", "hft_compressor_core"]
            if instance.body.command.line == 746 else
            ["PRIVATE", "cxet_replay_core", "GTest::gtest",
             "GTest::gtest_main"])
    else:
        expected = _STANDARD_LINKS
    if tail != expected:
        errors.append(
            f"{_origin(instance)}: unapproved safety link operands {tail}")


def _validate_includes(instance, local: set[str], errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    if target not in local or tokens[1:2] != ["PRIVATE"]:
        errors.append(f"{_origin(instance)}: invalid safety include owner/scope")
        return
    paths = [_repo_path(instance, value) for value in tokens[2:]]
    if target == "local_symbol_tests":
        expected = [*_CORE_INCLUDES, _LOCAL_INCLUDE, _CORE_PRIVATE_INCLUDE]
    elif target in SAFETY_FUZZ_SOURCES or target in {
            "fixed_ready_route_queue_tests", "grpc_socket_immediate_tests",
            "grpc_tls_immediate_tests", "user_grpc_auth_failure_tests"}:
        expected = list(_CORE_INCLUDES)
    elif target in {"replay_config_tests", "replay_session_tests"}:
        expected = [_LOCAL_INCLUDE]
    else:
        expected = [*_CORE_INCLUDES, _LOCAL_INCLUDE]
    if paths != expected:
        errors.append(
            f"{_origin(instance)}: unapproved safety include operands {paths}")


def _validate_compile_options(instance, local, errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    raw = cmake_list_words(instance.body.command.body)
    if target not in local or tokens[1:2] != ["PRIVATE"]:
        errors.append(f"{_origin(instance)}: invalid safety compile-option owner")
        return
    approved = False
    if instance.body.command.line == 76:
        approved = (
            raw == ["stress_buffer_pool_tests", "PRIVATE",
                    "${_stress_san_flags}"] and
            set(tokens[2:]).issubset({
                "-fsanitize=thread", "-fsanitize=undefined",
                "-fsanitize=address"}))
    elif instance.body.command.line == 82:
        approved = raw == [
            "stress_buffer_pool_tests", "PRIVATE",
            "$<$<CONFIG:Release>:-O3>",
            "$<$<AND:$<CONFIG:Release>,$<NOT:$<BOOL:"
            "${CXET_PORTABLE_BUILD}>>>:-march=native>",
        ]
    elif instance.body.command.line == 715:
        approved = target in SAFETY_FUZZ_SOURCES and tokens[2:] == [
            "-fsanitize=fuzzer"]
    if not approved:
        errors.append(
            f"{_origin(instance)}: unapproved safety compile options")


def _validate_link_options(instance, local, errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    raw = cmake_list_words(instance.body.command.body)
    exact_wrappers = {
        207: (
            "grpc_socket_immediate_tests",
            ["-Wl,--wrap=recv", "-Wl,--wrap=poll"],
        ),
    }
    wrapper = exact_wrappers.get(instance.body.command.line)
    approved = (
        target in local and tokens[1:2] == ["PRIVATE"] and (
            instance.body.command.line == 77 and
            raw == ["stress_buffer_pool_tests", "PRIVATE",
                    "${_stress_san_flags}"] and
            set(tokens[2:]).issubset({
                "-fsanitize=thread", "-fsanitize=undefined",
                "-fsanitize=address"}) or
            instance.body.command.line == 716 and
            target in SAFETY_FUZZ_SOURCES and
            tokens[2:] == ["-fsanitize=fuzzer"] or
            wrapper is not None and
            target == wrapper[0] and tokens[2:] == wrapper[1]
        )
    )
    if not approved:
        errors.append(f"{_origin(instance)}: unapproved safety link options")


def _validate_definitions(instance, local, errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    expected = {
        743: ["replay_session_tests", "PRIVATE",
              f"CXET_REPO_ROOT={ROOT.as_posix()}"],
        747: ["replay_session_tests", "PRIVATE",
              "CXET_REPLAY_TEST_WITH_HFT_COMPRESSOR=1"],
    }.get(instance.body.command.line)
    if target not in local or tokens != expected:
        errors.append(
            f"{_origin(instance)}: unapproved safety compile definitions")


def _validate_target_properties(instance, local, errors: list[str]) -> None:
    tokens = _flat(instance)
    target = tokens[0] if tokens else ""
    if target not in local or tokens != [
            target, "PROPERTIES", "RUNTIME_OUTPUT_DIRECTORY",
            SYNTHETIC_BINARY_ROOT]:
        errors.append(
            f"{_origin(instance)}: unapproved safety target properties")


def validate_safety_values(commands, instances, errors: list[str]) -> None:
    """Reject every non-reviewed src/tests build, link, or ownership effect."""
    for active in commands:
        if (active.relative == SAFETY_CMAKE and
                active.command.name in _FORBIDDEN_EFFECTS):
            errors.append(
                f"{active.relative}:{active.command.line}: unsupported "
                f"safety effect {active.command.name}()")
    local = _local_targets(instances)
    for instance in instances:
        if instance.body.relative != SAFETY_CMAKE:
            continue
        command = instance.body.command.name
        if command == "target_link_libraries":
            _validate_links(instance, local, errors)
        elif command == "target_include_directories":
            _validate_includes(instance, local, errors)
        elif command == "target_compile_options":
            _validate_compile_options(instance, local, errors)
        elif command == "target_link_options":
            _validate_link_options(instance, local, errors)
        elif command == "target_compile_definitions":
            _validate_definitions(instance, local, errors)
        elif command == "set_target_properties":
            _validate_target_properties(instance, local, errors)
