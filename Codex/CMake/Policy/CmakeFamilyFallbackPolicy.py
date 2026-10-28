"""Fail-closed scan for sibling/prebuilt fallbacks in family CMake."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from CMake.Policy.CmakeFamilyConditionPolicy import exact_command_contexts
from CMake.Syntax.CmakeFamilyDialect import approved_fetchcontent_form
from CMake.Flow.CmakeFamilyExecutionIdentity import unsymlinked_directory_path
from CMake.Syntax.CmakeFamilyLexer import scan_commands, strip_cmake_comments, words
from CMake.Safety.CmakeFamilySafetyPolicy import SAFETY_DIRECTORY


@dataclass(frozen=True)
class _Command:
    name: str
    body: str
    line: int
    offset: int


def _parse(relative: str, text: str, errors: list[str]) -> list[_Command]:
    return scan_commands(relative, text, errors, _Command)


def _cmake_files(
    root: Path,
    family_dirs: tuple[str, ...],
    read_required,
    generated_path,
    errors: list[str],
) -> list[tuple[str, str]]:
    scan_dirs = family_dirs + (
        "src/tests/offline", "src/src", "tools/Checks/tests/prepared_orders",
        "tools/exchange_api_probe",
    )
    required = frozenset({
        *family_dirs, "src/tests/offline", "src/src", "tools/Checks/tests/prepared_orders",
        "tools/exchange_api_probe",
    })
    if len(scan_dirs) != len(set(scan_dirs)) or set(scan_dirs) != required:
        errors.append(
            "family no-fallback scan roots changed or became incomplete")
    files: list[Path] = [root / "CMakeLists.txt"]
    root_modules = root / "cmake"
    if unsymlinked_directory_path(root_modules, root):
        for path in root_modules.rglob("*"):
            if generated_path(path.relative_to(root_modules).parts):
                continue
            if path.is_symlink():
                errors.append(
                    "root cmake scan path is symlinked: " +
                    path.relative_to(root).as_posix())
                continue
            if (path.is_file() and path.suffix == ".cmake" and
                    not generated_path(path.relative_to(root_modules).parts)):
                files.append(path)
    elif root_modules.exists() or root_modules.is_symlink():
        errors.append("root cmake module directory is nonregular or symlinked")
    for directory in scan_dirs:
        source_root = root / directory
        if not unsymlinked_directory_path(source_root, root):
            errors.append(
                "family source directory is missing, nonregular, or "
                f"symlinked: {directory}")
            continue
        for path in source_root.rglob("*"):
            if generated_path(path.relative_to(source_root).parts):
                continue
            if path.is_symlink():
                errors.append(
                    "family CMake scan path is symlinked: " +
                    path.relative_to(root).as_posix())
                continue
            if (not path.is_file() or
                    path.suffix != ".cmake" and
                    path.name != "CMakeLists.txt"):
                continue
            files.append(path)
    return [
        (path.relative_to(root).as_posix(), read_required(
            path.relative_to(root).as_posix(), errors))
        for path in sorted(set(files))
    ]


def check_no_family_fallback(
    root: Path,
    family_dirs: tuple[str, ...],
    read_required,
    generated_path,
    errors: list[str],
) -> None:
    family_name = re.compile(
        r"(?:cxet|trading[-_]?core|hft[-_]?(?:parser|trader|backtest)|"
        r"trader|vetron)", re.IGNORECASE)
    files = _cmake_files(
        root, family_dirs, read_required, generated_path, errors)
    liburing_condition = (
        "NOT", "TARGET", "liburing::uring", "AND", "EXISTS",
        '"${CMAKE_CURRENT_SOURCE_DIR}/../../extra/liburing/configure"',
    )
    liburing_scope = (("if", liburing_condition),)
    for relative, text in files:
        commands = _parse(relative, text, errors)
        scopes = {
            command.offset: scope
            for command, scope in exact_command_contexts(commands)
        }
        for command in commands:
            command_words = words(command.body)
            body = strip_cmake_comments(command.body)
            exact_import = (
                relative == "src/src/CMakeLists.txt" and
                command.name == "add_library" and
                tuple(command_words) == (
                    "liburing::uring", "STATIC", "IMPORTED", "GLOBAL") and
                scopes.get(command.offset) == liburing_scope)
            exact_properties = (
                relative == "src/src/CMakeLists.txt" and
                command.name == "set_target_properties" and
                tuple(command_words) == (
                    "liburing::uring", "PROPERTIES", "IMPORTED_LOCATION",
                    '"${CXET_LIBURING_ARCHIVE}"',
                    "INTERFACE_INCLUDE_DIRECTORIES",
                    '"${CXET_LIBURING_INSTALL_DIR}/include"') and
                scopes.get(command.offset) == liburing_scope)
            description = ""
            if (command.name == "add_library" and
                    "IMPORTED" in command_words and not exact_import):
                description = "imported library target"
            elif (command.name in {"set_property", "set_target_properties"} and
                  re.search(
                      r"\bIMPORTED_(?:LOCATION|IMPLIB)(?:_[A-Z0-9_]+)?\b",
                      body) and not exact_properties):
                description = "imported artifact location"
            elif (command.name in {"find_package", "find_library"} and
                  family_name.search(body)):
                description = "sibling package/library discovery"
            elif (command.name.startswith("fetchcontent") and
                  not approved_fetchcontent_form(
                      relative, command.name, command_words)):
                description = "network/source fallback"
            elif command.name.startswith("externalproject"):
                description = "external-project fallback"
            elif re.search(
                    r"(?:\.\./)+(?:hft-parser|hft-trader|hft-backtest|"
                    r"trading-core|trader|vetron)/build\b", body):
                description = "sibling build-tree dependency"
            elif re.search(
                    r"\blib(?:cxet|hft[_-]?(?:parser|trader|backtest)|"
                    r"trading[_-]?core|trader|vetron)[^\s\"']*"
                    r"\.(?:so|a|dylib|dll)\b", body, re.IGNORECASE):
                description = "prebuilt family artifact"
            if description:
                errors.append(
                    f"{relative}:{command.line}: forbidden {description}")
