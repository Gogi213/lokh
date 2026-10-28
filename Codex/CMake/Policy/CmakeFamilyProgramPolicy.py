"""Typed provenance for programs and non-CMake scripts used by the family."""

from __future__ import annotations

import re
from pathlib import Path

from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity
from CMake.Policy.CmakeFamilyVendorPolicy import (
    _CORE_LIBURING, _CORE_LIBURING_CC_ELSE, semantic_vendor_context,
)
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words


PROGRAM_PREFIX = "__CXET_REVIEWED_PROGRAM__"

_FIND_PROGRAM_FORMS = {
    ("src/src/CMakeLists.txt", "CXET_LIBURING_CC",
     ("NAMES", "clang", "REQUIRED")): PROGRAM_PREFIX + "/clang",
    ("apps/hft-parser/benchmarks/CMakeLists.txt",
     "HFTP_PYTHON3_EXECUTABLE",
     ("python3", "REQUIRED")): PROGRAM_PREFIX + "/python3",
    ("apps/vetron/CMakeLists.txt", "VETRON_NPM_EXECUTABLE",
     ("NAMES", "npm", "REQUIRED")): PROGRAM_PREFIX + "/npm",
}

_CLEAR_SITES = {
    ("src/src/CMakeLists.txt", "CXET_LIBURING_CC"): (105, 106, 107),
    ("apps/hft-parser/benchmarks/CMakeLists.txt",
     "HFTP_PYTHON3_EXECUTABLE"): (40, 41, 42),
    ("apps/vetron/CMakeLists.txt", "VETRON_NPM_EXECUTABLE"): (241, 242, 243),
}

_CONFIGURABLE_FIND_PROGRAM_FORMS = {
    ("apps/vetron/wasm/CMakeLists.txt", 8,
     "VETRON_EMXX_EXECUTABLE", ("NAMES", "em++")):
        PROGRAM_PREFIX + "/em++",
}


def apply_find_program(
    raw_words: list[str],
    relative: str,
    state: dict[str, tuple[str, ...]],
    output_variable,
    expand,
    errors: list[str],
    origin: str,
    cleared: bool = False,
) -> None:
    """Accept the three reviewed searches and bind a typed program sentinel."""
    if not raw_words:
        errors.append(f"{origin}: find_program() misses output variable")
        return
    variable = output_variable(raw_words[0], expand, errors, origin)
    if variable is None:
        return
    expected_lines = _CLEAR_SITES.get((relative, variable))
    origin_match = re.match(r"^[^:]+:(\d+)(?::|$)", origin)
    line = int(origin_match.group(1)) if origin_match is not None else -1
    configurable = _CONFIGURABLE_FIND_PROGRAM_FORMS.get(
        (relative, line, variable, tuple(raw_words[1:])))
    if configurable is not None:
        state[variable] = (configurable,)
        return
    core_selection = (relative, variable) == ("src/src/CMakeLists.txt", "CXET_LIBURING_CC")
    if expected_lines is None or (not core_selection and line != expected_lines[2]) or not cleared:
        errors.append(
            f"{origin}: find_program lacks its exact immediate CACHE/normal "
            f"preseed clearance for {variable}")
        state[variable] = (f"${{{variable}}}",)
        return
    if variable in state:
        errors.append(f"{origin}: find_program input {variable} was preseeded")
        state[variable] = (f"${{{variable}}}",)
        return
    if any(marker in raw for raw in raw_words[1:] for marker in (
            "${", "$ENV{", "$CACHE{", "$<")):
        errors.append(f"{origin}: dynamic find_program grammar is forbidden")
        state[variable] = (f"${{{variable}}}",)
        return
    groups = [tuple(expand([raw])) for raw in raw_words[1:]]
    if any(len(group) != 1 for group in groups):
        errors.append(f"{origin}: ambiguous expanded find_program grammar")
        state[variable] = (f"${{{variable}}}",)
        return
    tail = tuple(group[0] for group in groups)
    program = _FIND_PROGRAM_FORMS.get((relative, variable, tail))
    if program is None:
        errors.append(
            f"{origin}: unapproved find_program producer {variable} {tail}")
        state[variable] = (f"${{{variable}}}",)
        return
    state[variable] = (program,)


def reviewed_program(name: str) -> str:
    return PROGRAM_PREFIX + "/" + name


def reviewed_program_variable(variable: str) -> bool:
    return any(variable == item[1] for item in _CLEAR_SITES)


def approved_program_clear(
    relative: str,
    line: int,
    variable: str,
    cache: bool,
) -> bool:
    lines = _CLEAR_SITES.get((relative, variable))
    return lines is not None and line == lines[0 if cache else 1]


def _core_liburing_site(active, variable: str, name: str, tail: tuple[str, ...]) -> bool:
    """Prove the exact current fallback arm without binding line numbers."""
    relative = "src/src/CMakeLists.txt"
    return (
        variable == "CXET_LIBURING_CC" and active.relative == relative and
        active.scope == relative and active.source_base == Path("src/src") and
        active.binary_base == Path("src/src") and active.command.name == name and
        cmake_list_words(active.command.body) == [variable, *tail] and
        semantic_vendor_context(active.structural_context,
            (_CORE_LIBURING, _CORE_LIBURING_CC_ELSE))
    )


class ProgramClearance:
    """Track the exact adjacent CACHE unset, normal unset, search sequence."""

    def __init__(self) -> None:
        self._phases: dict[tuple[str, tuple[str, ...], str], tuple[int, int]] = {}

    @staticmethod
    def _key(active, variable: str) -> tuple[str, tuple[str, ...], str]:
        return active.scope, active.directory, variable

    def cache_clear(
        self, active, variable: str, state, global_cache, errors
    ) -> bool:
        core_selection = (active.relative, variable) == ("src/src/CMakeLists.txt", "CXET_LIBURING_CC")
        exact = (_core_liburing_site(active, variable, "unset", ("CACHE",)) if core_selection else
                 approved_program_clear(active.relative, active.command.line, variable, True))
        if not exact:
            return False
        self._phases[self._key(active, variable)] = (1, active.ordinal)
        global_cache.pop(variable, None)
        state.pop(variable, None)
        return True

    def normal_clear(self, active, variable: str, state, errors) -> bool:
        core_selection = (active.relative, variable) == ("src/src/CMakeLists.txt", "CXET_LIBURING_CC")
        exact = (_core_liburing_site(active, variable, "unset", ()) if core_selection else
                 approved_program_clear(active.relative, active.command.line, variable, False))
        if reviewed_program_variable(variable) and not exact:
            errors.append(
                f"{active.relative}:{active.command.line}: reviewed program "
                f"variable {variable} is cleared outside its exact site")
            return True
        if not exact:
            return False
        key = self._key(active, variable)
        if self._phases.get(key) != (1, active.ordinal - 1):
            errors.append(
                f"{active.relative}:{active.command.line}: normal program "
                f"clear lacks its immediate CACHE clear for {variable}")
        else:
            self._phases[key] = (2, active.ordinal)
        state.pop(variable, None)
        return True

    def ready(self, active, variable: str) -> bool:
        if ((active.relative, variable) == ("src/src/CMakeLists.txt", "CXET_LIBURING_CC") and
                not _core_liburing_site(active, variable, "find_program", ("NAMES", "clang", "REQUIRED"))):
            return False
        return self._phases.get(self._key(active, variable)) == (2, active.ordinal - 1)

    def consume(self, active, variable: str) -> None:
        self._phases.pop(self._key(active, variable), None)
