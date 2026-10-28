"""Restricted active-CMake dialect for the CXET ownership model."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from types import SimpleNamespace

from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity
from CMake.Policy.CmakeFamilyBenchmarkRecipe import (
    BENCHMARK_TARGETS, BENCHMARK_REGISTRATION_LINES, BENCHMARK_REQUIREMENTS,
)
from CMake.Syntax.CmakeFamilyContext import (
    StructuralArm,
    StructuralFrame,
    exact_context,
    first_body,
    first_if,
    recorder_contract_context,
)
from CMake.Syntax.CmakeFamilyLexer import words


TRUSTED_BUILTIN_INCLUDES = frozenset({
    "CheckIPOSupported",
    "CTest",
    "FetchContent",
    "GNUInstallDirs",
})

TRUSTED_FIND_PACKAGE_FORMS = frozenset({
    ("PostgreSQL", "REQUIRED"),
    ("Threads", "REQUIRED"),
    ("OpenSSL", "REQUIRED"),
    ("absl", "REQUIRED"),
    ("absl", "CONFIG", "REQUIRED"),
    ("Python3", "REQUIRED", "COMPONENTS", "Interpreter"),
    ("PkgConfig", "QUIET"),
    ("ZLIB", "QUIET"),
    ("Boost", "REQUIRED", "COMPONENTS", "json"),
})

_INCLUDE_GUARD_FILES = frozenset({
    "cmake/CxetExchangeSelection.cmake",
    "cmake/CxetHotOptions.cmake",
    "apps/hft-parser/cmake/HftpLibraries.cmake",
    "apps/hft-parser/cmake/HftpProcesses.cmake",
})
_INCLUDED_EVALUATION_OWNERS = {
    "cmake/CxetExchangeSelection.cmake": "src/src/CMakeLists.txt",
    "cmake/CxetHotOptions.cmake": "src/src/CMakeLists.txt",
    "apps/hft-parser/cmake/HftpLibraries.cmake":
        "apps/hft-parser/CMakeLists.txt",
    "apps/hft-parser/cmake/HftpProcesses.cmake":
        "apps/hft-parser/CMakeLists.txt",
}
_SUBDIRECTORY_EVALUATION_OWNERS = {
    "apps/trading-core/capital/CMakeLists.txt": "apps/trading-core/CMakeLists.txt",
    "apps/trader/tests/startup/CMakeLists.txt": "apps/trader/tests/offline/CMakeLists.txt",
    "apps/trading-core/tests/offline/Execution/CMakeLists.txt":
        "apps/trading-core/CMakeLists.txt",
    "apps/trading-core/tests/offline/Math/CMakeLists.txt":
        "apps/trading-core/CMakeLists.txt",
    "apps/vetron/wasm/CMakeLists.txt": "apps/vetron/CMakeLists.txt",
}
_SUBDIRECTORY_BINARY_BASES = {
    "apps/trader/tests/startup/CMakeLists.txt": "apps/trader/tests/offline/startup",
}
_TEST_ENABLE_FILES = frozenset({
    "src/tests/offline/CMakeLists.txt",
})
_PROJECT_FORMS = {
    "src/src/CMakeLists.txt": ["cxet_lib", "LANGUAGES", "C", "CXX", "ASM"],
    "apps/hft-compressor/CMakeLists.txt": ["hft-compressor", "LANGUAGES", "CXX"],
    "tools/exchange_api_probe/CMakeLists.txt": ["exchange_api_probe", "LANGUAGES", "CXX"],
}

# Recorder production/full keeps its actual Qt/Backtest profile. Unsupported
# product edges are rejected; corpus-only evidence never substitutes for it.
_EXACT_BUILTIN_CALLS = frozenset({
    ('apps/trader/tests/startup/CMakeLists.txt', 3, 'find_package', ('OpenSSL', 'REQUIRED', 'COMPONENTS', 'SSL', 'Crypto')),
    ('apps/diagnostic/CMakeLists.txt', 15, 'find_package', ('PostgreSQL', 'REQUIRED')),
    ('src/src/CMakeLists.txt', 89, 'find_package', ('absl', 'REQUIRED')),
    ('src/src/CMakeLists.txt', 99, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-parser/CMakeLists.txt', 109, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-parser/CMakeLists.txt', 111, 'find_package', ('absl', 'CONFIG', 'REQUIRED')),
    ('apps/hft-parser/CMakeLists.txt', 113, 'include', ('GNUInstallDirs',)),
    ('apps/trader/CMakeLists.txt', 14, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-backtest/CMakeLists.txt', 56, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-backtest/CMakeLists.txt', 57, 'find_package', ('Python3', 'REQUIRED', 'COMPONENTS', 'Interpreter')),
    ('apps/hft-recorder/CMakeLists.txt', 32, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-recorder/CMakeLists.txt', 33, 'find_package', ('ZLIB', 'REQUIRED')),
    ('apps/hft-recorder/CMakeLists.txt', 35, 'find_package', ('Qt6', 'REQUIRED', 'COMPONENTS', 'Core', 'Gui', 'Qml', 'Quick', 'QuickControls2', 'QuickDialogs2', 'Network')),
    ('apps/hft-recorder/src/Contracts/CMakeLists.txt', 3, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-recorder/src/Runtime/CMakeLists.txt', 4, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-recorder/tests/offline/CMakeLists.txt', 1, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/vetron/wasm/CMakeLists.txt', 4, 'find_package', ('Python3', 'REQUIRED', 'COMPONENTS', 'Interpreter')),
    ('apps/vetron/CMakeLists.txt', 248, 'find_package', ('Python3', 'REQUIRED', 'COMPONENTS', 'Interpreter')),
    ('apps/hft-compressor/CMakeLists.txt', 36, 'find_package', ('Threads', 'REQUIRED')),
    ('apps/hft-compressor/CMakeLists.txt', 37, 'find_package', ('PkgConfig', 'QUIET')),
    ('apps/hft-compressor/CMakeLists.txt', 38, 'find_package', ('ZLIB', 'QUIET')),
    ('tools/exchange_api_probe/CMakeLists.txt', 8, 'include', ('GNUInstallDirs',)),
    ('tools/exchange_api_probe/CMakeLists.txt', 15, 'find_package', ('OpenSSL', 'REQUIRED')),
    ('tools/exchange_api_probe/CMakeLists.txt', 16, 'find_package', ('Threads', 'REQUIRED')),
    ('tools/exchange_api_probe/CMakeLists.txt', 17, 'find_package', ('Boost', 'REQUIRED', 'COMPONENTS', 'json')),
    ('tools/exchange_api_probe/CMakeLists.txt', 18, 'find_package', ('PkgConfig', 'REQUIRED')),
    ('apps/trader/tests/offline/CMakeLists.txt', 20, 'find_package', ('OpenSSL', 'REQUIRED', 'COMPONENTS', 'SSL')),
    ('src/tests/offline/CMakeLists.txt', 1, 'find_package', ('OpenSSL', 'REQUIRED', 'COMPONENTS', 'SSL')),
    ('src/tests/offline/CMakeLists.txt', 2, 'find_package', ('Threads', 'REQUIRED')),
})
_BENCHMARK_PACKAGE_CALLS = {
    (relative, line, "find_package", ("OpenSSL", "REQUIRED", "COMPONENTS", "SSL")): target
    for relative, targets in BENCHMARK_TARGETS.items()
    for target, line in zip(targets, BENCHMARK_REGISTRATION_LINES[relative])
}
_EXACT_BUILTIN_CALLS |= frozenset(_BENCHMARK_PACKAGE_CALLS)
_COMPRESSOR_PACKAGES = {
    41: ("ZSTD", "libzstd", 40), 55: ("LZ4", "liblz4", 54),
    69: ("BROTLIENC", "libbrotlienc", 68), 70: ("BROTLIDEC", "libbrotlidec", 68),
    86: ("LZMA", "liblzma", 85),
}
_EXACT_COMPRESSOR_PKG_CALLS = frozenset(
    ("apps/hft-compressor/CMakeLists.txt", line, "pkg_check_modules",
     (prefix, "QUIET", "IMPORTED_TARGET", package))
    for line, (prefix, package, _guard) in _COMPRESSOR_PACKAGES.items())
_EXACT_PKG_CALLS = _EXACT_COMPRESSOR_PKG_CALLS | frozenset({
    ("tools/exchange_api_probe/CMakeLists.txt", 19, "pkg_check_modules",
     ("NGHTTP2", "REQUIRED", "IMPORTED_TARGET", "libnghttp2")),
})
_EXACT_BUILTIN_CALLS |= _EXACT_PKG_CALLS
_COMPRESSOR_SEARCHES = {
    46: ("find_path", "ZSTD_INCLUDE_DIR", "zstd.h", 43, ("TARGET", "PkgConfig::ZSTD")),
    47: ("find_library", "ZSTD_LIBRARY", "zstd", 43, ("TARGET", "PkgConfig::ZSTD")),
    60: ("find_path", "LZ4_INCLUDE_DIR", "lz4.h", 57, ("TARGET", "PkgConfig::LZ4")),
    61: ("find_library", "LZ4_LIBRARY", "lz4", 57, ("TARGET", "PkgConfig::LZ4")),
    75: ("find_path", "BROTLI_INCLUDE_DIR", "brotli/encode.h", 72, ("TARGET", "PkgConfig::BROTLIENC", "AND", "TARGET", "PkgConfig::BROTLIDEC")),
    76: ("find_library", "BROTLIENC_LIBRARY", "brotlienc", 72, ("TARGET", "PkgConfig::BROTLIENC", "AND", "TARGET", "PkgConfig::BROTLIDEC")),
    77: ("find_library", "BROTLIDEC_LIBRARY", "brotlidec", 72, ("TARGET", "PkgConfig::BROTLIENC", "AND", "TARGET", "PkgConfig::BROTLIDEC")),
    78: ("find_library", "BROTLICOMMON_LIBRARY", "brotlicommon", 72, ("TARGET", "PkgConfig::BROTLIENC", "AND", "TARGET", "PkgConfig::BROTLIDEC")),
    91: ("find_path", "LZMA_INCLUDE_DIR", "lzma.h", 88, ("TARGET", "PkgConfig::LZMA")),
    92: ("find_library", "LZMA_LIBRARY", "lzma", 88, ("TARGET", "PkgConfig::LZMA")),
}
_EXACT_SEARCH_CALLS = frozenset(
    ("apps/hft-compressor/CMakeLists.txt", line, command, (variable, item))
    for line, (command, variable, item, _guard, _condition) in _COMPRESSOR_SEARCHES.items())
_EXACT_BUILTIN_CALLS |= _EXACT_SEARCH_CALLS

_EXACT_BOOTSTRAP_CALLS = frozenset({
    ('apps/trading-core/capital/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/diagnostic/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('src/src/CMakeLists.txt', 5, 'cmake_minimum_required', ('VERSION', '3.16')),
    ('src/src/CMakeLists.txt', 7, 'project', ('cxet_lib', 'LANGUAGES', 'C', 'CXX', 'ASM')),
    ('apps/hft-parser/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/trading-core/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/trader/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/hft-backtest/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/vetron/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/hft-compressor/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.20')),
    ('apps/hft-recorder/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.22')),
    ('apps/hft-compressor/CMakeLists.txt', 10, 'project', ('hft-compressor', 'LANGUAGES', 'CXX')),
    ('tools/exchange_api_probe/CMakeLists.txt', 1, 'cmake_minimum_required', ('VERSION', '3.20')),
    ('tools/exchange_api_probe/CMakeLists.txt', 6, 'project', ('exchange_api_probe', 'LANGUAGES', 'CXX')),
})

_EXACT_INCLUDE_GUARDS = frozenset({
    ('cmake/CxetExchangeSelection.cmake', 5, 'include_guard', ('GLOBAL',)),
    ('cmake/CxetHotOptions.cmake', 3, 'include_guard', ('GLOBAL',)),
    ('apps/hft-parser/cmake/HftpLibraries.cmake', 1, 'include_guard', ('GLOBAL',)),
    ('apps/hft-parser/cmake/HftpProcesses.cmake', 1, 'include_guard', ('GLOBAL',)),
})

_EXACT_DIRECTORY_COMPILE_DEFINITIONS = frozenset({
    ('cmake/CxetExchangeSelection.cmake', 146, 'add_compile_definitions', ('${CXET_EXCHANGE_DEFINITIONS}',)),
})

# Exact context includes the owner, guard/arm and evaluation chain. Line pins
# below are reviewed diagnostics, not an excuse to infer host/package evidence.
_CORE_STANDALONE = first_if("src/src/CMakeLists.txt", 48,
    ("CMAKE_SOURCE_DIR", "STREQUAL", "CMAKE_CURRENT_SOURCE_DIR"))
_PARSER_ABSL_GUARD = first_if("apps/hft-parser/CMakeLists.txt", 110,
    ("NOT", "TARGET", "absl::flat_hash_set"))
_EXACT_PRIVILEGED_CONTEXTS = {
    ("apps/trader/tests/startup/CMakeLists.txt", 3, "find_package", ("OpenSSL", "REQUIRED", "COMPONENTS", "SSL", "Crypto")):
        (first_if("apps/trader/tests/offline/CMakeLists.txt", 2,
            ("CXET_SELECTION_ALL", "OR", "CXET_EXCHANGE_FINAM")),),
    ("src/src/CMakeLists.txt", 89, "find_package", ("absl", "REQUIRED")): (_CORE_STANDALONE,),
    ("apps/hft-parser/CMakeLists.txt", 111, "find_package", ("absl", "CONFIG", "REQUIRED")): (_PARSER_ABSL_GUARD,),
    ("apps/hft-recorder/CMakeLists.txt", 35, "find_package", ("Qt6", "REQUIRED", "COMPONENTS", "Core", "Gui", "Qml", "Quick", "QuickControls2", "QuickDialogs2", "Network")):
        (first_if("apps/hft-recorder/CMakeLists.txt", 34, ("HFTREC_BUILD_GUI",)),),
}
_EXACT_PRIVILEGED_CONTEXTS.update({
    identity: (first_if(identity[0], _COMPRESSOR_PACKAGES[identity[1]][2], ("PkgConfig_FOUND",)),)
    for identity in _EXACT_COMPRESSOR_PKG_CALLS
})
_EXACT_PRIVILEGED_CONTEXTS.update({
    identity: (("if", identity[0], _COMPRESSOR_SEARCHES[identity[1]][3],
                _COMPRESSOR_SEARCHES[identity[1]][4], "else", (),
                (("if", _COMPRESSOR_SEARCHES[identity[1]][4]),)),)
    for identity in _EXACT_SEARCH_CALLS
})
_EXACT_PRIVILEGED_CONTEXTS.update({
    identity: tuple(first_if(identity[0], identity[1], (requirement,))
                    for requirement in BENCHMARK_REQUIREMENTS.get(target, ()))
    for identity, target in _BENCHMARK_PACKAGE_CALLS.items()
})
# The independent Compressor/helper owners select the canonical toolchain
# before project(); their reviewed preludes remain exact and bounded.
_BOOTSTRAP_PREFIX_NAMES = {
    # Configure-only, byte-pinned projection omits script-mode entrypoints.
    "cmake/CxetExchangeSelection.cmake": ["include_guard"],
    "apps/hft-compressor/CMakeLists.txt": ["cmake_minimum_required", "if", "set", "if", "message", "endif", "include", "unset", "endif", "project"],
    "tools/exchange_api_probe/CMakeLists.txt": ["cmake_minimum_required", "if", "include", "endif", "project"],
}

# These commands are interpreted by composition, snapshots, writer handling,
# or the ownership graph. Merely listing a command here never makes its values
# trusted: its owning model still validates or rejects the command.
MODELED_COMMANDS = frozenset({
    "add_compile_definitions",
    "add_compile_options",
    "add_custom_command",
    "add_custom_target",
    "add_dependencies",
    "add_executable",
    "add_library",
    "add_link_options",
    "add_subdirectory",
    "add_test",
    "aux_source_directory",
    "build_command",
    "check_ipo_supported",
    "cmake_host_system_information",
    "cmake_language",
    "cmake_parse_arguments",
    "cmake_path",
    "cxet_offline_instrument",
    "configure_file",
    "else",
    "elseif",
    "endforeach",
    "endfunction",
    "endif",
    "file",
    "find_file",
    "find_library",
    "find_package",
    "find_path",
    "find_program",
    "fetchcontent_declare",
    "fetchcontent_makeavailable",
    "foreach",
    "function",
    "get_cmake_property",
    "get_directory_property",
    "get_filename_component",
    "get_property",
    "get_source_file_property",
    "get_target_property",
    "get_test_property",
    "if",
    "include",
    "link_libraries",
    "list",
    "math",
    "message",
    "option",
    "project",
    "pkg_check_modules",
    "return",
    "separate_arguments",
    "set",
    "set_directory_properties",
    "set_property",
    "set_source_files_properties",
    "set_target_properties",
    "set_tests_properties",
    "target_compile_definitions",
    "target_compile_features",
    "site_name",
    "string",
    "target_compile_options",
    "target_include_directories",
    "target_link_libraries",
    "target_link_options",
    "target_precompile_headers",
    "target_sources",
    "unset",
})

# These current commands cannot change source ownership, link composition, or
# variables consumed by those carriers. New command names require review.
HARMLESS_COMMANDS = frozenset({
    "cmake_minimum_required",
    "enable_testing",
    "include_guard",
})

# install() is effectful and belongs to the positive registration policy, not
# to the structural allowlist.
MODELED_COMMANDS = MODELED_COMMANDS | {"install"}

EXPLICITLY_UNSUPPORTED_COMMANDS = frozenset({
    "break",
    "continue",
    "endmacro",
    "endwhile",
    "execute_process",
    "load_cache",
    "macro",
    "try_compile",
    "try_run",
    "while",
})

_BRACKET_ARGUMENT = re.compile(r"\[(=*)\[[\s\S]*\]\1\]")


def unsupported_bracket_arguments(body: str) -> tuple[str, ...]:
    """Bracket provenance is outside the bounded active-CMake interpreter."""
    return tuple(
        token for token in words(body)
        if _BRACKET_ARGUMENT.fullmatch(token) is not None)


def validate_dialect_argument_microcases(errors: list[str]) -> None:
    for body in ("[=[${SAFE_INCLUDE}]=]", "[[a;b]]"):
        if not unsupported_bracket_arguments(body):
            errors.append(
                "active-dialect self-check missed bracket argument " + body)
    if unsupported_bracket_arguments('"${SAFE_INCLUDE}"'):
        errors.append(
            "active-dialect self-check confused quoted and bracket arguments")


def _trusted_find_package(tokens: list[str], relative: str | None = None) -> bool:
    if not tokens or any(
            marker in token
            for token in tokens
            for marker in ("${", "$ENV{", "$CACHE{", "$<")):
        return False
    normalized = (tokens[0],) + tuple(
        token.upper() if token.upper() in {
            "CONFIG", "REQUIRED", "COMPONENTS"
        } else token
        for token in tokens[1:]
    )
    if normalized == ("OpenSSL", "REQUIRED", "COMPONENTS", "SSL"):
        return relative in {"src/tests/offline/CMakeLists.txt",
                            "apps/trader/tests/offline/CMakeLists.txt",
                            "cmake/CxetBenchmarks.cmake",
                            "src/benchmarks/CMakeLists.txt",
                            "apps/hft-parser/benchmarks/CMakeLists.txt",
                            "apps/trading-core/benchmarks/CMakeLists.txt",
                            "apps/trader/benchmarks/CMakeLists.txt"}
    if normalized == ("OpenSSL", "REQUIRED", "COMPONENTS", "SSL", "Crypto"):
        return relative == "apps/trader/tests/startup/CMakeLists.txt"
    if normalized == ("PkgConfig", "REQUIRED"):
        return relative == "tools/exchange_api_probe/CMakeLists.txt"
    if normalized in {("ZLIB", "REQUIRED"), ("Qt6", "REQUIRED", "COMPONENTS",
            "Core", "Gui", "Qml", "Quick", "QuickControls2", "QuickDialogs2", "Network")}:
        return relative == "apps/hft-recorder/CMakeLists.txt"
    return normalized in TRUSTED_FIND_PACKAGE_FORMS


def _reviewed_product_instrument(active, commands) -> bool:
    callers = {
        "apps/hft-compressor/CMakeLists.txt": (180, 179, "hft_compressor_core"),
        "apps/hft-recorder/src/Runtime/CMakeLists.txt": (41, 40, "hftrec_json_capture"),
        "tools/exchange_api_probe/CMakeLists.txt": (95, 94, "exchange_probe_lib"),
    }
    recipe = callers.get(active.relative)
    if recipe is None:
        return False
    line, guard, target = recipe
    base = Path(active.relative).parent
    if (active.command.line != line or tuple(words(active.command.body)) != (target,) or
            active.source_base != base or active.binary_base != base or
            not exact_context(active.structural_context,
                (first_if(active.relative, guard, ("CXET_LOCAL_TESTS",)),))):
        return False
    declarations = [item for item in commands if item.relative == active.relative and
        item.command.name in {"add_library", "add_executable"} and
        tuple(words(item.command.body))[:1] == (target,) and item.ordinal < active.ordinal and
        not item.structural_context]
    if len(declarations) != 1:
        return False
    from Family.Profile.CxetFamilyActivation import validate_offline_helper
    helper = Path(__file__).resolve().parents[4] / "cmake/CxetOfflineTests.cmake"
    try:
        return validate_offline_helper(helper.read_text(encoding="utf-8"), [])
    except (OSError, UnicodeError):
        return False


def reviewed_compressor_search(relative: str, line: int, command: str, tokens) -> bool:
    return (relative, line, command, tuple(tokens)) in _EXACT_SEARCH_CALLS


def approved_fetchcontent_form(relative, command_name, tokens) -> bool:
    """Owner/offline graphs have no first-party source acquisition stage."""
    return False


def validate_active_dialect(
    commands,
    callable_names: set[str],
    tokenize,
    errors: list[str],
) -> None:
    """Reject every command outside the explicitly reviewed active dialect."""
    reserved = MODELED_COMMANDS | HARMLESS_COMMANDS
    for callable_name in sorted(callable_names):
        if callable_name in reserved:
            errors.append(
                f"active-family callable shadows reserved CMake command "
                f"{callable_name}"
            )
    for active in commands:
        command = active.command
        origin = f"{active.relative}:{command.line}"
        bracket_arguments = unsupported_bracket_arguments(command.body)
        liburing_archive_edit = (
            active.relative == "src/src/CMakeLists.txt" and
            command.name == "add_custom_command" and
            bracket_arguments == (r"[[s/(?<=\(AR\)) r / rc /g]]",) and
            tokenize(command.body)[:3] == ["OUTPUT", "${CXET_LIBURING_ARCHIVE}", "${CXET_LIBURING_HEADER}"])
        if bracket_arguments and not liburing_archive_edit:
            errors.append(
                f"{origin}: bracket arguments are unsupported in the active "
                f"CMake graph: {list(bracket_arguments)}")
            continue
        if command.name in callable_names:
            continue
        if command.name in EXPLICITLY_UNSUPPORTED_COMMANDS:
            errors.append(
                f"{origin}: unsupported active control/writer command "
                f"{command.name}()"
            )
            continue
        if command.name not in reserved:
            errors.append(
                f"{origin}: command {command.name}() is outside the "
                "restricted active-CMake ownership dialect"
            )
            continue
        if command.name == "pkg_check_modules" and (
                active.relative, command.line, command.name, tuple(tokenize(command.body))) not in _EXACT_PKG_CALLS:
            errors.append(f"{origin}: unapproved pkg-config provider recipe")
        if command.name == "cxet_offline_instrument":
            from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instrument_context
            if not (offline_instrument_context(active, commands) or
                    _reviewed_product_instrument(active, commands)):
                errors.append(f"{origin}: unapproved offline instrumentation caller/producer")
        if (command.name == "find_package" and
                not _trusted_find_package(tokenize(command.body), active.relative)):
            errors.append(
                f"{origin}: unapproved find_package form "
                f"{tokenize(command.body)}"
            )
        if (command.name == "project" and
                tokenize(command.body) != _PROJECT_FORMS.get(
                    active.relative)):
            errors.append(f"{origin}: unapproved project language contract")
        if (command.name == "fetchcontent_declare" and
                not approved_fetchcontent_form(
                    active.relative, command.name,
                    tokenize(command.body))):
            errors.append(f"{origin}: unapproved FetchContent declaration")
        elif (command.name == "fetchcontent_makeavailable" and
              not approved_fetchcontent_form(
                  active.relative, command.name,
                  tokenize(command.body))):
            errors.append(f"{origin}: unapproved FetchContent activation")
        if command.name == "cmake_minimum_required":
            expected = (
                ["VERSION", "3.16"]
                if active.relative == "src/src/CMakeLists.txt" else
                ["VERSION", "3.20"]
                if active.relative ==
                "apps/hft-compressor/CMakeLists.txt" or active.relative ==
                "tools/exchange_api_probe/CMakeLists.txt" else
                ["VERSION", "3.22"])
            if tokenize(command.body) != expected:
                errors.append(f"{origin}: unapproved minimum CMake contract")
        elif command.name == "include_guard" and (
                active.relative not in _INCLUDE_GUARD_FILES or
                tokenize(command.body) != ["GLOBAL"]):
            errors.append(f"{origin}: unapproved include_guard scope")
        elif command.name == "enable_testing" and (
                active.relative not in _TEST_ENABLE_FILES or
                tokenize(command.body)):
            errors.append(f"{origin}: unapproved enable_testing origin/form")


def validate_exact_active_inventory(
    commands,
    tokenize,
    errors: list[str],
    *,
    active_origins: frozenset[str] | None = None,
) -> None:
    """Pin privileged builtin/bootstrap commands across the full graph."""
    def identity(active):
        return (
            active.relative,
            active.command.line,
            active.command.name,
            tuple(tokenize(active.command.body)),
        )

    actual_builtins = Counter(
        identity(active)
        for active in commands
        if (active.command.name in {"find_package", "pkg_check_modules", "find_path", "find_library"} or
            active.command.name == "include" and
            tuple(tokenize(active.command.body))[:1] and
            tuple(tokenize(active.command.body))[0] in
            TRUSTED_BUILTIN_INCLUDES))
    def selected(inventory):
        return {value: 1 for value in inventory
                if active_origins is None or value[0] in active_origins}

    expected_builtins = Counter(selected(_EXACT_BUILTIN_CALLS))
    if actual_builtins != expected_builtins:
        errors.append(
            "active builtin include/find_package inventory changed: "
            f"missing={sorted((expected_builtins - actual_builtins).elements())}, "
            f"extra={sorted((actual_builtins - expected_builtins).elements())}")

    actual_bootstrap = Counter(
        identity(active)
        for active in commands
        if active.command.name in {"cmake_minimum_required", "project"})
    expected_bootstrap = Counter(selected(_EXACT_BOOTSTRAP_CALLS))
    if actual_bootstrap != expected_bootstrap:
        errors.append(
            "active project/minimum bootstrap inventory changed: "
            f"missing={sorted((expected_bootstrap - actual_bootstrap).elements())}, "
            f"extra={sorted((actual_bootstrap - expected_bootstrap).elements())}")

    actual_guards = Counter(
        identity(active)
        for active in commands
        if active.command.name == "include_guard")
    expected_guards = Counter(selected(_EXACT_INCLUDE_GUARDS))
    if actual_guards != expected_guards:
        errors.append(
            "active include_guard inventory changed: "
            f"missing={sorted((expected_guards - actual_guards).elements())}, "
            f"extra={sorted((actual_guards - expected_guards).elements())}")

    actual_directory_definitions = Counter(
        identity(active)
        for active in commands
        if active.command.name == "add_compile_definitions")
    expected_directory_definitions = Counter(selected(_EXACT_DIRECTORY_COMPILE_DEFINITIONS))
    if actual_directory_definitions != expected_directory_definitions:
        errors.append(
            "active directory compile-definition inventory changed: "
            f"missing={sorted((expected_directory_definitions - actual_directory_definitions).elements())}, "
            f"extra={sorted((actual_directory_definitions - expected_directory_definitions).elements())}")

    expected_privileged = (
        set(_EXACT_BUILTIN_CALLS) |
        set(_EXACT_BOOTSTRAP_CALLS) |
        set(_EXACT_INCLUDE_GUARDS) |
        set(_EXACT_DIRECTORY_COMPILE_DEFINITIONS)
    )
    for active in commands:
        current = identity(active)
        if current not in expected_privileged:
            continue
        if (current in _EXACT_DIRECTORY_COMPILE_DEFINITIONS and
                not reviewed_file_identity(active.relative)):
            errors.append(
                f"{active.relative}:{active.command.line}: directory compile "
                "definitions require the exact reviewed producer identity")
        corpus = active.relative == "apps/hft-recorder/src/Contracts/CMakeLists.txt"
        context_valid = (recorder_contract_context(active) if corpus else
                         exact_context(active.structural_context, _EXACT_PRIVILEGED_CONTEXTS.get(current, ())))
        if not context_valid:
            errors.append(
                f"{active.relative}:{active.command.line}: privileged CMake "
                "call escaped its exact structural context")
        if (_evaluation_identity(active) not in _expected_evaluation_identities(active.relative) and
                not (corpus and recorder_contract_context(active))):
            errors.append(
                f"{active.relative}:{active.command.line}: privileged CMake "
                "call escaped its exact evaluation context")

    ordered_by_file: dict[str, list[object]] = {}
    for active in commands:
        ordered_by_file.setdefault(active.relative, []).append(active)
    for relative, current in ordered_by_file.items():
        current.sort(key=lambda active: (
            active.command.line, active.ordinal))
        if (relative in _INCLUDE_GUARD_FILES and
                relative not in _BOOTSTRAP_PREFIX_NAMES and (
                not current or current[0].command.name != "include_guard")):
            errors.append(
                f"{relative}: include_guard(GLOBAL) is not the first command")
        expected_names = [
            value[2] for value in sorted(
                _EXACT_BOOTSTRAP_CALLS, key=lambda value: value[1])
            if value[0] == relative
        ]
        expected_names = _BOOTSTRAP_PREFIX_NAMES.get(relative, expected_names)
        if expected_names and [
                active.command.name
                for active in current[:len(expected_names)]] != expected_names:
            errors.append(
                f"{relative}: project/minimum bootstrap is not the first "
                "reviewed command sequence")


def _expected_evaluation_identity(relative: str):
    scope = _INCLUDED_EVALUATION_OWNERS.get(relative)
    if scope is not None:
        base = Path(scope).parent.as_posix()
        directory = (scope,)
        chain = (
            (directory, scope),
            (directory, relative),
        )
        return scope, base, base, directory, chain
    scope = _SUBDIRECTORY_EVALUATION_OWNERS.get(relative)
    if scope is not None:
        base = Path(relative).parent.as_posix()
        binary = _SUBDIRECTORY_BINARY_BASES.get(relative, base)
        root_directory = (scope,)
        directory = (scope, relative)
        chain = (
            (root_directory, scope),
            (directory, relative),
        )
        return scope, base, binary, directory, chain
    base = Path(relative).parent.as_posix()
    directory = (relative,)
    return (
        relative,
        base,
        base,
        directory,
        ((directory, relative),),
    )


def _expected_evaluation_identities(relative: str):
    identities = {_expected_evaluation_identity(relative)}
    if relative == "apps/hft-recorder/src/Runtime/CMakeLists.txt":
        root = "apps/hft-recorder/CMakeLists.txt"
        source = "apps/hft-recorder/src/CMakeLists.txt"
        directory = (root, source, relative)
        base = Path(relative).parent.as_posix()
        identities.add((root, base, base, directory, (
            ((root,), root), ((root, source), source), (directory, relative))))
    return identities


def _evaluation_identity(active):
    return (
        active.scope,
        active.source_base.as_posix(),
        active.binary_base.as_posix(),
        active.directory,
        active.execution_chain,
    )


def validate_exact_active_inventory_microcases(errors: list[str]) -> None:
    """A line-stable conditional wrapper must not preserve evidence identity."""
    relative = "src/tests/offline/CMakeLists.txt"
    directory = (relative,)
    baseline = SimpleNamespace(
        scope=relative,
        source_base=Path("src/tests/offline"),
        binary_base=Path("src/tests/offline"),
        directory=directory,
        execution_chain=((directory, relative),),
        structural_context=(),
    )
    wrapped = SimpleNamespace(**{
        **baseline.__dict__,
        "structural_context": (
            StructuralFrame(
                "if", relative, 2, 0, ("FALSE",),
                StructuralArm("if", ("FALSE",))),
        ),
    })
    if _evaluation_identity(baseline) != _expected_evaluation_identity(relative):
        errors.append(
            "privileged CMake evaluation-context self-check rejected baseline")
    if exact_context(wrapped.structural_context, ()):
        errors.append(
            "privileged CMake context self-check accepted line-stable wrapper")
    for included_relative, owner in _INCLUDED_EVALUATION_OWNERS.items():
        base = Path(owner).parent
        owner_directory = (owner,)
        included = SimpleNamespace(
            scope=owner,
            source_base=base,
            binary_base=base,
            directory=owner_directory,
            execution_chain=(
                (owner_directory, owner),
                (owner_directory, included_relative),
            ),
            structural_context=(),
        )
        if _evaluation_identity(included) != _expected_evaluation_identity(
                included_relative):
            errors.append(
                "privileged CMake evaluation-context self-check rejected "
                f"included file {included_relative}")
        seeded_directory = (included_relative,)
        seeded = SimpleNamespace(
            scope=included_relative,
            source_base=Path(included_relative).parent,
            binary_base=Path(included_relative).parent,
            directory=seeded_directory,
            execution_chain=((seeded_directory, included_relative),),
            structural_context=(),
        )
        if _evaluation_identity(seeded) == _expected_evaluation_identity(
                included_relative):
            errors.append(
                "privileged CMake evaluation-context self-check accepted "
                f"seeded include identity for {included_relative}")
    for child_relative, owner in _SUBDIRECTORY_EVALUATION_OWNERS.items():
        base = Path(child_relative).parent
        binary = Path(_SUBDIRECTORY_BINARY_BASES.get(child_relative, base.as_posix()))
        root_directory = (owner,)
        child_directory = (owner, child_relative)
        child = SimpleNamespace(
            scope=owner,
            source_base=base,
            binary_base=binary,
            directory=child_directory,
            execution_chain=(
                (root_directory, owner),
                (child_directory, child_relative),
            ),
            structural_context=(),
        )
        if _evaluation_identity(child) != _expected_evaluation_identity(
                child_relative):
            errors.append(
                "privileged CMake evaluation-context self-check rejected "
                f"subdirectory {child_relative}")
        if base != binary:
            wrong_binary = SimpleNamespace(**{**child.__dict__, "binary_base": base})
            if _evaluation_identity(wrong_binary) == _expected_evaluation_identity(child_relative):
                errors.append("privileged CMake context self-check accepted misplaced descendant binary directory")
        seeded_directory = (child_relative,)
        seeded = SimpleNamespace(
            scope=child_relative,
            source_base=base,
            binary_base=base,
            directory=seeded_directory,
            execution_chain=((seeded_directory, child_relative),),
            structural_context=(),
        )
        if _evaluation_identity(seeded) == _expected_evaluation_identity(
                child_relative):
            errors.append(
                "privileged CMake evaluation-context self-check accepted "
                f"seeded subdirectory identity for {child_relative}")
        shifted = SimpleNamespace(**{
            **child.__dict__,
            "source_base": Path(owner).parent,
            "binary_base": Path(owner).parent,
        })
        if _evaluation_identity(shifted) == _expected_evaluation_identity(
                child_relative):
            errors.append(
                "privileged CMake evaluation-context self-check accepted "
                f"shifted subdirectory identity for {child_relative}")
