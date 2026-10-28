"""Fail-closed output-variable handling for the bounded CMake model."""

from __future__ import annotations

import glob
import re
from pathlib import Path

from CMake.Policy.CmakeFamilyEffectPolicy import effect_variable
from CMake.Policy.CmakeFamilyProgramPolicy import apply_find_program
from CMake.Policy.CmakeFamilyWritePolicy import approved_file_side_effect
from Family.Targets.CxetFamilyTargetInventory import TRADING_CORE_CONTRACT_TESTS


SYNTHETIC_BINARY_ROOT = "__CXET_CMAKE_BINARY__"
_CMAKE_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")


def _origin_line(origin: str) -> int:
    match = re.match(r"^[^:]+:(\d+)(?::|$)", origin)
    return int(match.group(1)) if match is not None else -1


def _glob_static_anchor(path: Path) -> Path:
    """Return the lexical prefix preceding the first glob metacharacter."""
    prefix: list[str] = []
    for part in path.parts:
        if glob.has_magic(part):
            break
        prefix.append(part)
    if len(prefix) == len(path.parts):
        return path.parent
    return Path(*prefix)


def _output_variable(
    raw: str,
    expand,
    errors: list[str],
    origin: str,
) -> str | None:
    values = expand([raw])
    if (len(values) != 1 or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", values[0])):
        errors.append(f"{origin}: ambiguous output variable {values}")
        return None
    if effect_variable(values[0]):
        errors.append(
            f"{origin}: build-effect output mutation is forbidden: "
            f"{values[0]}")
        return None
    return values[0]


def _taint(
    raw: str,
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
) -> None:
    variable = _output_variable(raw, expand, errors, origin)
    if variable is not None:
        state[variable] = (f"${{{variable}}}",)


def _file_side_effect(
    operation: str,
    raw_words: list[str],
    expand,
    errors: list[str],
    origin: str,
) -> None:
    if not approved_file_side_effect(
            operation, raw_words, expand, origin):
        errors.append(
            f"{origin}: unapproved active file({operation}) provenance")


def _cmake_parse_arguments(
    raw_words: list[str],
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
) -> None:
    if not raw_words:
        errors.append(f"{origin}: cmake_parse_arguments() misses prefix")
        return
    if raw_words[0].upper() == "PARSE_ARGV":
        errors.append(
            f"{origin}: cmake_parse_arguments(PARSE_ARGV) is unsupported")
        return
    expected = [
        "HFTP_DEFAULTS", "CONTRACT_TEST", "", "", "${ARGN}"]
    if (not origin.startswith("apps/hft-parser/CMakeLists.txt:") or
            raw_words != expected):
        errors.append(
            f"{origin}: unapproved cmake_parse_arguments signature")
        return
    prefix_values = expand([raw_words[0]])
    if (len(prefix_values) != 1 or not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*", prefix_values[0])):
        errors.append(
            f"{origin}: ambiguous cmake_parse_arguments prefix {prefix_values}")
        return
    prefix = prefix_values[0]
    derived = {
        f"{prefix}_UNPARSED_ARGUMENTS",
        f"{prefix}_KEYWORDS_MISSING_VALUES",
    }
    derived.add(f"{prefix}_CONTRACT_TEST")
    for variable in derived:
        if effect_variable(variable):
            errors.append(
                f"{origin}: cmake_parse_arguments mutates build-effect "
                f"variable {variable}")
        else:
            state[variable] = (f"${{{variable}}}",)


def _file_glob(
    raw_words: list[str],
    recursive: bool,
    root: Path,
    source_dir: Path,
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
) -> None:
    if len(raw_words) < 2:
        errors.append(f"{origin}: malformed file(GLOB) command")
        return
    variable = _output_variable(raw_words[1], expand, errors, origin)
    if variable is None:
        return
    patterns: list[str] = []
    relative_base: str | None = None
    # CMake GLOB includes directories by default; GLOB_RECURSE does not.
    list_directories = not recursive
    index = 2
    while index < len(raw_words):
        token = raw_words[index]
        upper = token.upper()
        if upper == "CONFIGURE_DEPENDS":
            index += 1
            continue
        if upper in {"LIST_DIRECTORIES", "RELATIVE"}:
            if index + 1 >= len(raw_words):
                errors.append(
                    f"{origin}: file(GLOB) option {token} misses a value")
                state[variable] = (f"${{{variable}}}",)
                return
            value = expand([raw_words[index + 1]])
            if (len(value) != 1 or
                    any(marker in value[0] for marker in _CMAKE_CARRIERS)):
                errors.append(
                    f"{origin}: file(GLOB) option {token} has an "
                    "unresolved value")
                state[variable] = (f"${{{variable}}}",)
                return
            if upper == "LIST_DIRECTORIES":
                list_directories = value[0].upper() not in {
                    "0", "FALSE", "NO", "OFF"}
            else:
                relative_base = value[0]
            index += 2
            continue
        expanded = expand([token])
        if not expanded:
            state[variable] = (f"${{{variable}}}",)
            return
        patterns.extend(expanded)
        index += 1

    matches: list[str] = []
    try:
        root_resolved = root.resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(f"{origin}: cannot resolve repository root: {exc}")
        state[variable] = (f"${{{variable}}}",)
        return
    relative_base_path: Path | None = None
    if relative_base is not None:
        if ("\\" in relative_base or
                any(marker in relative_base for marker in _CMAKE_CARRIERS)):
            errors.append(
                f"{origin}: file(GLOB RELATIVE) has unresolved/escaped base")
            state[variable] = (f"${{{variable}}}",)
            return
        relative_base_path = Path(relative_base)
        if not relative_base_path.is_absolute():
            relative_base_path = source_dir / relative_base_path
        try:
            relative_base_path.resolve().relative_to(root_resolved)
        except (OSError, RuntimeError, ValueError):
            errors.append(
                f"{origin}: file(GLOB RELATIVE) base escapes repository")
            state[variable] = (f"${{{variable}}}",)
            return
    for pattern in patterns:
        if ("\\" in pattern or
                any(marker in pattern for marker in _CMAKE_CARRIERS)):
            errors.append(
                f"{origin}: file(GLOB) has unresolved/escaped pattern")
            state[variable] = (f"${{{variable}}}",)
            return
        glob_pattern = pattern
        if not Path(glob_pattern).is_absolute():
            glob_pattern = (source_dir / glob_pattern).as_posix()
        if recursive and "**" not in glob_pattern:
            pattern_path = Path(glob_pattern)
            glob_pattern = (
                pattern_path.parent / "**" / pattern_path.name).as_posix()
        try:
            _glob_static_anchor(Path(glob_pattern)).resolve().relative_to(
                root_resolved)
        except (OSError, RuntimeError, ValueError):
            errors.append(
                f"{origin}: file(GLOB) pattern anchor escapes repository: "
                f"{pattern}")
            state[variable] = (f"${{{variable}}}",)
            return
        # CMake's globbing includes leading-dot entries.  Python glob hides
        # them by default, which would omit real CMake source attachments.
        for matched in sorted(glob.glob(
                glob_pattern, recursive=recursive, include_hidden=True)):
            path = Path(matched)
            try:
                path.resolve().relative_to(root_resolved)
            except (OSError, RuntimeError, ValueError):
                errors.append(
                    f"{origin}: file(GLOB) escapes repository root: {pattern}")
                state[variable] = (f"${{{variable}}}",)
                return
            if not list_directories and path.is_dir():
                continue
            if relative_base is None:
                # CMake returns the lexical glob match.  Preserve a symlink's
                # visible suffix so source-kind validation can compare it to
                # the separately resolved canonical path.
                value = path.absolute().as_posix()
            else:
                try:
                    value = path.absolute().relative_to(
                        relative_base_path.absolute()).as_posix()
                except ValueError:
                    errors.append(
                        f"{origin}: file(GLOB RELATIVE) path escapes base")
                    state[variable] = (f"${{{variable}}}",)
                    return
            if value not in matches:
                matches.append(value)
    state[variable] = tuple(sorted(matches))


def apply_output_writer(
    command_name: str,
    raw_words: list[str],
    root: Path,
    source_dir: Path,
    state: dict[str, tuple[str, ...]],
    expand,
    errors: list[str],
    origin: str,
    directory_targets: dict[str, str] | None = None,
    program_cleared: bool = False,
) -> bool:
    """Handle known writers; return whether the command was classified."""
    if command_name == "file":
        if not raw_words:
            errors.append(f"{origin}: empty file() command")
            return True
        operation = raw_words[0].upper()
        if operation in {"GLOB", "GLOB_RECURSE"}:
            _file_glob(
                raw_words, operation == "GLOB_RECURSE", root,
                source_dir, state, expand, errors, origin)
            return True
        if operation in {"READ", "STRINGS", "SIZE", "TIMESTAMP", "REAL_PATH"}:
            if len(raw_words) < 3:
                errors.append(f"{origin}: malformed file({operation}) command")
            else:
                _taint(raw_words[2], state, expand, errors, origin)
            return True
        if operation in {
                "WRITE", "APPEND", "MAKE_DIRECTORY", "REMOVE",
                "REMOVE_RECURSE", "TOUCH", "TOUCH_NOCREATE", "GENERATE",
                "CONFIGURE", "COPY", "INSTALL", "ARCHIVE_CREATE",
                "ARCHIVE_EXTRACT"}:
            _file_side_effect(
                operation, raw_words, expand, errors, origin)
            return True
        errors.append(f"{origin}: unsupported active file({operation}) command")
        return True

    if command_name == "get_filename_component":
        if len(raw_words) != 3:
            errors.append(f"{origin}: malformed get_filename_component()")
            return True
        variable = _output_variable(raw_words[0], expand, errors, origin)
        inputs = expand([raw_words[1]])
        modes = expand([raw_words[2]])
        mode = modes[0].upper() if len(modes) == 1 else ""
        if variable is None:
            return True
        if (any(marker in raw_words[2] for marker in (
                "${", "$ENV{", "$CACHE{", "$<")) or
                mode not in {"DIRECTORY", "NAME"}):
            errors.append(
                f"{origin}: unsupported get_filename_component mode/options")
        if (any(marker in raw_words[2] for marker in (
                "${", "$ENV{", "$CACHE{", "$<")) or
                mode not in {"DIRECTORY", "NAME"} or not inputs or
                any(any(marker in value for marker in (
                    "${", "$ENV{", "$CACHE{", "$<")) for value in inputs)):
            state[variable] = (f"${{{variable}}}",)
        elif mode == "DIRECTORY":
            state[variable] = tuple(
                Path(value).parent.as_posix() for value in inputs)
        else:
            state[variable] = tuple(Path(value).name for value in inputs)
        return True

    if command_name == "find_program":
        apply_find_program(
            raw_words, origin.split(":", 1)[0], state, _output_variable,
            expand, errors, origin, program_cleared)
        return True

    if command_name in {"find_library", "find_file", "find_path"}:
        from CMake.Syntax.CmakeFamilyDialect import reviewed_compressor_search
        if not reviewed_compressor_search(origin.split(":", 1)[0], _origin_line(origin), command_name, raw_words):
            errors.append(f"{origin}: unsupported active {command_name}() search")
        if raw_words:
            # A reviewed search has an exact output owner but no host lookup
            # authority. Its path/library result remains unresolved.
            _taint(raw_words[0], state, expand, errors, origin)
        return True

    if command_name == "get_property":
        variable = (
            _output_variable(raw_words[0], expand, errors, origin)
            if raw_words else None)
        approved_signatures = {
            ("apps/hft-parser/CMakeLists.txt", "_hftp_all_targets"): (
                187, ["DIRECTORY", "PROPERTY", "BUILDSYSTEM_TARGETS"]),
            ("apps/trading-core/CMakeLists.txt",
             "_trading_core_all_targets"): (
                 205, ["DIRECTORY", "PROPERTY", "BUILDSYSTEM_TARGETS"]),
            ("apps/trading-core/CMakeLists.txt",
             "_trading_core_test_targets"): (
                 206, ["DIRECTORY", "tests", "PROPERTY",
                       "BUILDSYSTEM_TARGETS"]),
            ("apps/hft-backtest/CMakeLists.txt",
             "_hft_backtest_all_targets"): (
                 239, ["DIRECTORY", "PROPERTY", "BUILDSYSTEM_TARGETS"]),
            ("apps/trader/CMakeLists.txt", "_trader_all_targets"): 639,
            ("apps/trader/CMakeLists.txt",
             "_trader_semantic_test_targets"): (
                 646, ["DIRECTORY",
                       "${CMAKE_CURRENT_SOURCE_DIR}/../trading-core/tests",
                       "PROPERTY", "BUILDSYSTEM_TARGETS"]),
            ("apps/vetron/CMakeLists.txt", "_vetron_all_targets"): 256,
        }
        relative = origin.split(":", 1)[0]
        approved = (
            approved_signatures.get((relative, raw_words[0]))
            if raw_words else None)
        if isinstance(approved, int):
            approved = (
                approved, ["DIRECTORY", "PROPERTY", "BUILDSYSTEM_TARGETS"])
        actual_line = _origin_line(origin)
        if (variable is None or approved is None or
                actual_line != approved[0] or raw_words[1:] != approved[1]):
            errors.append(f"{origin}: unapproved get_property() provenance")
            if variable is not None:
                state[variable] = (f"${{{variable}}}",)
            return True
        if variable in {
                "_trading_core_test_targets",
                "_trader_semantic_test_targets",
        }:
            state[variable] = TRADING_CORE_CONTRACT_TESTS
        else:
            state[variable] = (
                tuple(directory_targets)
                if directory_targets is not None else (f"${{{variable}}}",))
        return True

    if command_name == "get_test_property":
        errors.append(f"{origin}: unsupported active get_test_property()")
        if len(raw_words) < 3:
            errors.append(f"{origin}: get_test_property() misses output variable")
        else:
            _taint(raw_words[2], state, expand, errors, origin)
        return True

    if command_name in {
            "get_target_property", "get_directory_property",
            "get_source_file_property", "get_cmake_property", "site_name",
            "build_command"}:
        if not raw_words:
            errors.append(f"{origin}: {command_name}() misses output variable")
        else:
            _taint(raw_words[0], state, expand, errors, origin)
        return True

    if command_name == "math":
        if len(raw_words) < 2 or raw_words[0].upper() != "EXPR":
            errors.append(f"{origin}: unsupported active math() form")
        else:
            _taint(raw_words[1], state, expand, errors, origin)
        return True

    if command_name == "cmake_parse_arguments":
        _cmake_parse_arguments(
            raw_words, state, expand, errors, origin)
        return True

    if command_name == "separate_arguments":
        if not raw_words:
            errors.append(f"{origin}: separate_arguments() misses output")
        else:
            _taint(raw_words[0], state, expand, errors, origin)
        return True

    if command_name == "try_compile":
        errors.append(f"{origin}: unsupported active try_compile()")
        return True

    if command_name == "try_run":
        errors.append(f"{origin}: unsupported active try_run()")
        return True

    if command_name == "cmake_host_system_information":
        if len(raw_words) < 2 or raw_words[0].upper() != "RESULT":
            errors.append(
                f"{origin}: unsupported cmake_host_system_information() form")
        else:
            _taint(raw_words[1], state, expand, errors, origin)
        return True

    if command_name == "aux_source_directory":
        if len(raw_words) < 2:
            errors.append(f"{origin}: malformed aux_source_directory()")
        else:
            _taint(raw_words[1], state, expand, errors, origin)
        return True

    if command_name == "execute_process":
        errors.append(f"{origin}: unsupported active execute_process()")
        return True

    if command_name == "check_ipo_supported":
        errors.append(f"{origin}: unsupported active check_ipo_supported() writer")
        return True

    if command_name == "cmake_path":
        errors.append(f"{origin}: unsupported active cmake_path() writer")
        return True
    if command_name == "load_cache":
        errors.append(f"{origin}: unsupported active load_cache() writer")
        return True
    if command_name == "configure_file":
        errors.append(f"{origin}: unsupported active configure_file() writer")
        return True
    return False
