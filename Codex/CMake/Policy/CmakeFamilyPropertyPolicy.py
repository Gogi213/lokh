"""Positive property grammar for the restricted active CMake dialect."""

from __future__ import annotations

import re
import posixpath
from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import exact_context, first_if
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Policy.CmakeFamilyStrategyPolicy import proven_strategy_names, registry_outputs
from CMake.Policy.CmakeFamilyFrontendRecipe import reviewed_frontend_recipe

from CMake.Flow.CmakeFamilyState import (
    SYNTHETIC_BINARY_ROOT,
    normalize_synthetic_binary_path,
)
from CMake.Flow.CmakeFamilyExecutionIdentity import reviewed_file_identity


ROOT = Path(__file__).resolve().parents[4]
_CARRIERS = ("${", "$ENV{", "$CACHE{", "$<")
_CACHE_STRINGS = {
    ("CMakeLists.txt", "CXET_FAMILY_PROFILE"):
        ("essential", "full"),
    ("CMakeLists.txt", "CXET_CLANG24_LIFETIME_PROFILE"):
        ("off", "permissive", "full-report"),
    ("CMakeLists.txt", "CXET_SANITIZER_PROFILE"):
        ("none", "address-undefined", "thread"),
    ("src/src/CMakeLists.txt", "CXET_SANITIZER_PROFILE"):
        ("none", "address-undefined", "thread"),
    ("apps/hft-parser/CMakeLists.txt", "HFT_PARSER_SANITIZER"):
        ("none", "address-undefined", "thread"),
}
_DEFERRED_TARGET_PROPERTIES = frozenset({
    "COMPILE_FLAGS", "COMPILE_OPTIONS", "INCLUDE_DIRECTORIES",
    "INTERFACE_COMPILE_FLAGS", "INTERFACE_COMPILE_OPTIONS",
    "INTERFACE_INCLUDE_DIRECTORIES", "INTERFACE_LINK_LIBRARIES",
    "INTERFACE_LINK_LIBRARIES_DIRECT",
    "INTERFACE_LINK_LIBRARIES_DIRECT_EXCLUDE", "INTERFACE_LINK_OPTIONS",
    "INTERFACE_PRECOMPILE_HEADERS", "INTERFACE_SOURCES", "LINK_FLAGS",
    "LINK_LIBRARIES", "LINK_OPTIONS", "MANUALLY_ADDED_DEPENDENCIES",
    "PRECOMPILE_HEADERS", "SOURCES",
})
_OUTPUT_NAMES = {
    "hft_backtest_core": ("hft_backtest_core",),
}
_TEST_PROPERTY_BASES = {
    "apps/hft-backtest/CMakeLists.txt": Path("apps/hft-backtest"),
    "apps/hft-parser/cmake/HftpTests.cmake": Path("apps/hft-parser"),
    "apps/trading-core/tests/CMakeLists.txt": Path("apps/trading-core/tests"),
    "apps/trading-core/CMakeLists.txt": Path("apps/trading-core"),
    "apps/trader/CMakeLists.txt": Path("apps/trader"),
    "apps/trader/cmake/AnalyticsTests.cmake": Path("apps/trader"),
    "apps/vetron/CMakeLists.txt": Path("apps/vetron"),
    "src/tests/CMakeLists.txt": Path("src/tests"),
    "src/tests/Family/CMakeLists.txt": Path("src/tests/Family"),
}

_TRADING_CORE_SAFETY_TESTS = (
    "trading-core-rate-limit-state-tests",
    "trading-core-user-event-identity-tests",
    "trading-core-execution-state-tracker-tests",
    "trading-core-order-state-rules-tests",
)


def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _approved_test_writer_context(instance) -> bool:
    expected = _TEST_PROPERTY_BASES.get(instance.body.relative)
    return (
        expected is not None and
        instance.body.source_base == expected and
        instance.body.binary_base == expected and
        instance.evaluation.source_base == expected and
        instance.evaluation.binary_base == expected
    )


def _approved_safety_test_writer(instance, owners: list[str]) -> bool:
    if (instance.body.relative ==
            "apps/trading-core/tests/CMakeLists.txt" and
            instance.body.command.line in {153, 155, 158}):
        expected = {
            153: [
                "${trading_core_safety_tests}", "PROPERTIES", "TIMEOUT",
                "120"],
            155: [
                "${trading_core_safety_tests}", "PROPERTIES", "ENVIRONMENT",
                "ASAN_OPTIONS=detect_stack_use_after_return=1:"
                "detect_stack_use_after_scope=1:halt_on_error=1:"
                "abort_on_error=1;"
                "UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1"],
            158: [
                "${trading_core_safety_tests}", "PROPERTIES", "ENVIRONMENT",
                "TSAN_OPTIONS=halt_on_error=1:abort_on_error=1"],
        }
        return (
            tuple(owners) == _TRADING_CORE_SAFETY_TESTS and
            cmake_list_words(instance.body.command.body) ==
            expected[instance.body.command.line])
    return True


def _opaque(value: str) -> bool:
    return any(marker in value for marker in _CARRIERS)


def _literal_group(group) -> str | None:
    if len(group) != 1 or _opaque(group[0]):
        return None
    return group[0]


def _property_pairs(groups, start: int, origin: str, errors: list[str]):
    tail = groups[start:]
    if len(tail) % 2:
        errors.append(f"{origin}: property list has a missing value")
        return []
    result = []
    for index in range(0, len(tail), 2):
        name = _literal_group(tail[index])
        if name is None:
            errors.append(f"{origin}: unresolved property name")
            continue
        result.append((name, tuple(tail[index + 1])))
    return result


def _binary_directory(values: tuple[str, ...]) -> bool:
    return (
        len(values) == 1 and
        normalize_synthetic_binary_path(values[0]) == SYNTHETIC_BINARY_ROOT
    )


def _repo_working_directory(value: str) -> bool:
    if _opaque(value):
        return False
    if normalize_synthetic_binary_path(value) is not None:
        return True
    path = Path(value)
    candidate = path if path.is_absolute() else ROOT / path
    try:
        candidate.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return False
    return ".." not in Path(value.replace("\\", "/")).parts


def _labels(values: tuple[str, ...]) -> bool:
    return bool(values) and all(
        not _opaque(value) and
        re.fullmatch(r"[A-Za-z0-9_.:+/-]+", value) is not None
        for value in values
    )


def _test_property(name: str, values: tuple[str, ...]) -> bool:
    if name == "LABELS":
        return _labels(values)
    if name == "WORKING_DIRECTORY":
        return len(values) == 1 and _repo_working_directory(values[0])
    if name == "TIMEOUT":
        return len(values) == 1 and values[0].isdigit()
    if name == "ENVIRONMENT":
        return bool(values) and all(
            not _opaque(value) and re.fullmatch(
                r"(?:ASAN|UBSAN|TSAN)_OPTIONS=[A-Za-z0-9_:=]+", value)
            is not None
            for value in values
        )
    return False


def _registered_strategies(instance, target: str, values: tuple[str, ...]) -> bool:
    names = proven_strategy_names()
    return (
        target == "trading_core_strategy" and
        instance.body.relative == "apps/trading-core/CMakeLists.txt" and
        # A quoted list is one CMake argument, but target property storage
        # serializes its elements with semicolons.
        tuple(part for value in values for part in value.split(";")) == names
    )


def normalized_recipe_input(value: str) -> str:
    if _opaque(value) or value.startswith(SYNTHETIC_BINARY_ROOT + "/"):
        return posixpath.normpath(value)
    return posixpath.normpath(value if Path(value).is_absolute() else str(ROOT / value))


def reviewed_wasm_context(instance, *, unavailable: bool) -> bool:
    base = Path("apps/vetron/wasm")
    return bool(instance.body == instance.evaluation and
        instance.body.relative == "apps/vetron/wasm/CMakeLists.txt" and
        instance.body.source_base == instance.body.binary_base == base and
        reviewed_file_identity("apps/vetron/wasm/CMakeLists.txt") and
        exact_context(instance.body.structural_context, (first_if(
            "apps/vetron/wasm/CMakeLists.txt", 32,
            ("NOT", "VETRON_EMXX_EXECUTABLE", "OR", "NOT", "EXISTS", "${VETRON_EMXX_EXECUTABLE}",
             "OR", "IS_DIRECTORY", "${VETRON_EMXX_EXECUTABLE}")),) if unavailable else ()))


def reviewed_wasm_alternatives(declarations) -> bool:
    """Identify the exact disjoint unavailable/prepared declarations, once."""
    from CMake.Flow.CmakeFamilyFlow import paths_intersect
    from CMake.Syntax.CmakeFamilyLexer import scan_commands
    if (len(declarations) != 2 or
            len({item.evaluation.scope for item in declarations}) != 1 or
            any(item.body.command.name != "add_custom_target" or
                item.token_groups[:1] != (("vetron-math-wasm",),) for item in declarations) or
            sum(reviewed_wasm_context(item, unavailable=True) for item in declarations) != 1 or
            sum(reviewed_wasm_context(item, unavailable=False) for item in declarations) != 1 or
            paths_intersect(declarations[0].path_alternatives, declarations[1].path_alternatives)):
        return False
    relative = "apps/vetron/wasm/CMakeLists.txt"
    try:
        errors = []
        parsed = scan_commands(relative, (ROOT / relative).read_text(), errors,
            lambda name, body, line, _offset: (name, body, line))
    except OSError:
        return False
    return not errors and all(
        (item.body.command.name, item.body.command.body, item.body.command.line) in parsed
        for item in declarations)


def reviewed_wasm_inputs(*, prepared: bool = False, actual_inputs=None):
    paths = ("apps/vetron/wasm/TradingCoreMath.cpp", "apps/vetron/wasm/TradingCoreMathAbi.hpp",
        "apps/vetron/wasm/FormulaRuler.hpp", "apps/vetron/wasm/BuildMathWasm.py",
        "apps/vetron/wasm/CMakeLists.txt", "cmake/CxetToolchain.cmake",
        "tools/Toolchain/BootstrapEmscripten.py")
    if not all(reviewed_file_identity(path) for path in (
            "apps/vetron/wasm/CMakeLists.txt", "apps/vetron/wasm/BuildMathWasm.py",
            "tools/Toolchain/BootstrapEmscripten.py", "tools/Testing/RunOffline.py",
            "cmake/CxetToolchain.cmake")):
        return None
    result = {str(ROOT / path) for path in paths}
    if prepared:
        # Both are unresolved inputs from the exact source-profile projection,
        # never a claim that the compiler/toolchain is installed or usable.
        compiler_forms = {"${VETRON_EMXX_EXECUTABLE}", "$<CXET_UNKNOWN_SOURCE_PROFILE>"}
        selected = compiler_forms.intersection(actual_inputs) if actual_inputs is not None else {"${VETRON_EMXX_EXECUTABLE}"}
        if len(selected) != 1:
            return None
        result.update(selected | {"${CXET_EMSDK_INSTALL_DIR}/.emscripten"})
        for relative in ("apps/trading-core/src/Core/include", "src/src/Contracts/include"):
            result.update(path.resolve().as_posix()
                for path in (ROOT / relative).glob("**/*.hpp") if path.is_file())
    return frozenset(result)


def _target_property(instance, target: str, name: str,
                     values: tuple[str, ...]) -> bool:
    from CMake.Policy.CmakeFamilyBenchmarkRecipe import benchmark_target_owner
    from Family.Targets.CxetFamilyBuildPolicy import benchmark_instance_context
    if (name == "CXET_COMPILE_INPUTS" and
            target in {"trader-bench-json-ws", "trader-bench-json-ws_traced"} and
            instance.body.relative == "apps/trader/benchmarks/CMakeLists.txt" and
            instance.body.source_base == instance.body.binary_base == Path("apps/trader/benchmarks") and
            instance.body.command.name == "set_property"):
        expected = tuple(str(ROOT / path) for path in (
            "src/benchmarks/WsBenchmarkPeer.hpp", "src/benchmarks/WsBenchmarkFixture.hpp",
            "src/benchmarks/MarketFixture.hpp", "src/benchmarks/Cases.hpp"))
        return tuple(posixpath.normpath(value) for value in values) == expected
    if (name in {"CXET_COMPILE_OWNER", "CXET_BENCHMARK"} and
            benchmark_instance_context(instance, target)):
        owner = benchmark_target_owner(target, instance.body.relative)
        return (instance.body.command.name == "set_target_properties" and
                cmake_list_words(instance.body.command.body) == [
                    target, "PROPERTIES", "CXET_COMPILE_OWNER", owner,
                    "CXET_BENCHMARK", "TRUE"] and
                values == ((owner,) if name == "CXET_COMPILE_OWNER" else ("TRUE",)))
    if name in {"INTERFACE_HFTP_RUNTIME_COMPOSITION", "COMPATIBLE_INTERFACE_STRING"}:
        base = Path("apps/hft-parser")
        standalone = ("hftp_ingestion", "hftp_parserd_runtime")
        trading = ("hftp_trading_ingestion", "hftp_trading_runtime")
        raw = cmake_list_words(instance.body.command.body)
        context = (instance.body == instance.evaluation and
            instance.body.relative == "apps/hft-parser/cmake/HftpLibraries.cmake" and
            instance.body.source_base == instance.body.binary_base == base and
            not instance.body.structural_context)
        if not context:
            return False
        if name == "INTERFACE_HFTP_RUNTIME_COMPOSITION":
            group, value = (standalone, "standalone") if target in standalone else (trading, "trading")
            return (target in group and values == (value,) and
                instance.body.command.name == "set_target_properties" and
                raw == [*group, "PROPERTIES", name, value])
        return (target in (*standalone, *trading) and values == ("HFTP_RUNTIME_COMPOSITION",) and
            instance.body.command.name == "set_property" and
            raw == ["TARGET", *standalone, *trading, "APPEND", "PROPERTY", name, "HFTP_RUNTIME_COMPOSITION"])
    core_context = (
        instance.body.relative == "src/src/CMakeLists.txt" and
        instance.body.source_base == Path("src/src") and
        instance.body.binary_base == Path("src/src") and
        instance.evaluation.source_base == Path("src/src") and
        instance.evaluation.binary_base == Path("src/src"))
    raw = cmake_list_words(instance.body.command.body)
    if target == "cxet_resident_memory" and name == "CXET_COMPILE_OWNER":
        return (core_context and instance.body == instance.evaluation and
                not instance.body.structural_context and
                instance.body.command.name == "set_target_properties" and
                raw == [target, "PROPERTIES", "CXET_COMPILE_OWNER", "CXETCPP",
                        "POSITION_INDEPENDENT_CODE", "ON"] and values == ("CXETCPP",))
    if target == "hft_compressor_core" and name in {"CXX_STANDARD", "CXX_STANDARD_REQUIRED", "CXX_EXTENSIONS"}:
        base = Path("apps/hft-compressor")
        return bool(instance.body == instance.evaluation and
            instance.body.relative == "apps/hft-compressor/CMakeLists.txt" and
            instance.body.source_base == instance.body.binary_base == base and
            not instance.body.structural_context and
            instance.body.command.name == "set_target_properties" and raw == [target, "PROPERTIES",
                "CXX_STANDARD", "23", "CXX_STANDARD_REQUIRED", "ON", "CXX_EXTENSIONS", "OFF"] and
            values == {"CXX_STANDARD": ("23",), "CXX_STANDARD_REQUIRED": ("ON",), "CXX_EXTENSIONS": ("OFF",)}[name])
    if target == "vetron-math-wasm" and name in {"CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS"}:
        base = Path("apps/vetron/wasm")
        if not (instance.body.relative == "apps/vetron/wasm/CMakeLists.txt" and
                instance.body.source_base == instance.evaluation.source_base == base and
                instance.body.binary_base == instance.evaluation.binary_base == base):
            return False
        unavailable = bool(instance.body.structural_context)
        if not reviewed_wasm_context(instance, unavailable=unavailable):
            return False
        normalized = tuple(normalized_recipe_input(value) for group in values for value in group.split(";"))
        if name == "CXET_COMPILE_OUTPUTS":
            generated = SYNTHETIC_BINARY_ROOT + "/apps/vetron/wasm/"
            if raw not in (["TARGET", target, "PROPERTY", name, "${CMAKE_CURRENT_BINARY_DIR}/math-wasm.stamp.json", "${VETRON_MATH_WASM_OUTPUT}"],
                    ["TARGET", target, "PROPERTY", name, "${VETRON_MATH_WASM_STAMP}", "${VETRON_MATH_WASM_OUTPUT}", "${VETRON_MATH_WASM_DEPFILE}"]):
                return False
            return any(recipe is not None and normalized ==
                    (generated + "math-wasm.stamp.json", *recipe["wasm"],
                     *((generated + "math-wasm.d",) if not unavailable else ()))
                for local_tests in (False, True)
                for recipe in (reviewed_frontend_recipe(local_tests=local_tests),))
        common = ["TARGET", target, "PROPERTY", name,
            "${CMAKE_CURRENT_SOURCE_DIR}/TradingCoreMath.cpp", "${CMAKE_CURRENT_SOURCE_DIR}/TradingCoreMathAbi.hpp",
            "${CMAKE_CURRENT_SOURCE_DIR}/FormulaRuler.hpp", "${VETRON_MATH_WASM_SCRIPT}", "${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt"]
        if raw == [*common, "${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake", "${CMAKE_SOURCE_DIR}/tools/Toolchain/BootstrapEmscripten.py"]:
            expected = reviewed_wasm_inputs() if unavailable else None
        elif raw == [*common, "${VETRON_EMSCRIPTEN_BOOTSTRAP}", "${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake",
                "${VETRON_EMXX_EXECUTABLE}", "${CXET_EMSDK_INSTALL_DIR}/.emscripten", "${vetron_math_wasm_headers}"]:
            expected = reviewed_wasm_inputs(prepared=True, actual_inputs=normalized) if not unavailable else None
        else:
            return False
        return len(normalized) == len(set(normalized)) and set(normalized) == expected
    if target == "vetron-frontend" and name in {
            "CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS", "CXET_COMPILE_OUTPUT_MANIFEST"}:
        base = Path("apps/vetron")
        if not (instance.body.relative == "apps/vetron/CMakeLists.txt" and
                instance.body.source_base == instance.evaluation.source_base == base and
                instance.body.binary_base == instance.evaluation.binary_base == base):
            return False
        raw_values = {
            "CXET_COMPILE_INPUTS": ["${VETRON_FRONTEND_INPUTS}", "${VETRON_MATH_WASM_OUTPUT}"],
            "CXET_COMPILE_OUTPUTS": ["${VETRON_FRONTEND_STAMP}",
                "${VETRON_FRONTEND_OUTPUT_DIR}/index.html", "${VETRON_FRONTEND_GENERATED_OUTPUTS}"],
            "CXET_COMPILE_OUTPUT_MANIFEST": ["${VETRON_FRONTEND_STAMP}"],
        }
        if raw != ["TARGET", target, "PROPERTY", name, *raw_values[name]]:
            return False
        normalized = tuple(posixpath.normpath(value)
            for group in values for value in group.split(";"))
        key = {"CXET_COMPILE_INPUTS": "dependencies",
               "CXET_COMPILE_OUTPUTS": "outputs",
               "CXET_COMPILE_OUTPUT_MANIFEST": "manifest"}[name]
        return any(recipe is not None and normalized == recipe[key]
            for local_tests in (False, True)
            for recipe in (reviewed_frontend_recipe(local_tests=local_tests),))
    if core_context and target == "cxet_liburing_ep" and name in {
            "CXET_COMPILE_OWNER", "CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS"}:
        # VendorPolicy proves the exact variable writers and producer context.
        # The glob remains an opaque carrier in this bounded interpreter.
        return raw == [
            "cxet_liburing_ep", "PROPERTIES", "CXET_COMPILE_OWNER", "vendor:liburing",
            "CXET_COMPILE_INPUTS", "${CXET_LIBURING_INPUT_FILES};${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/SanitizeCRLF.cmake",
            "CXET_COMPILE_OUTPUTS", "${CXET_LIBURING_ARCHIVE};${CXET_LIBURING_HEADER}"]
    if core_context and name == "CXET_COMPILE_OWNER":
        return (target in {
            "cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
            "cxet_tls_certificates", "cxet_native_tls"} and
            values == ("CXETCPP",) and raw == [
                "${_tls_target}", "PROPERTIES", "CXET_COMPILE_OWNER", "CXETCPP",
                "POSITION_INDEPENDENT_CODE", "ON"])
    if (target == "liburing::uring" and
            name == "IMPORTED_LOCATION"):
        return values == (
            "__CXET_CMAKE_BINARY__/src/src/_deps/liburing/"
            "install/lib/liburing.a",)
    if (target == "liburing::uring" and
            name == "INTERFACE_INCLUDE_DIRECTORIES"):
        return values == (
            "__CXET_CMAKE_BINARY__/src/src/_deps/liburing/install/include",)
    if not target or _opaque(target) or any(_opaque(value) for value in values):
        return False
    if name in _DEFERRED_TARGET_PROPERTIES:
        return True
    if name in {
            "RUNTIME_OUTPUT_DIRECTORY", "LIBRARY_OUTPUT_DIRECTORY",
            "ARCHIVE_OUTPUT_DIRECTORY"}:
        return _binary_directory(values)
    if name == "POSITION_INDEPENDENT_CODE":
        return values == ("ON",)
    if name == "INTERPROCEDURAL_OPTIMIZATION":
        return values == ("TRUE",)
    if name == "EXCLUDE_FROM_ALL":
        return False
    if name in {"VERSION", "SOVERSION"}:
        return False
    if name == "OUTPUT_NAME":
        return values == _OUTPUT_NAMES.get(target)
    if name == "INSTALL_RPATH":
        return False
    if name == "BUILD_WITH_INSTALL_RPATH":
        return False
    if name == "TRADING_CORE_REGISTERED_STRATEGY_NAMES":
        return _registered_strategies(instance, target, values)
    if (name == "CXET_COMPILE_INPUTS" and target == "cxet_crypto_rsa" and
            core_context):
        if raw != ["TARGET", "cxet_crypto_rsa", "PROPERTY", "CXET_COMPILE_INPUTS",
                "${_cxet_mbed}/library/aes.c", "${_cxet_mbed}/library/aesni.c",
                "${_cxet_mbed}/library/constant_time.c",
                "${CMAKE_CURRENT_SOURCE_DIR}/Core/src/Crypto/RsaMbedAdapt.py",
                "${CMAKE_CURRENT_SOURCE_DIR}/Core/src/Crypto/RsaMbedProvenance.md"]:
            return False
        expected = tuple(str(ROOT / path) for path in (
            "extra/mbedtls-cold/library/aes.c", "extra/mbedtls-cold/library/aesni.c",
            "extra/mbedtls-cold/library/constant_time.c",
            "src/src/Core/src/Crypto/RsaMbedAdapt.py",
            "src/src/Core/src/Crypto/RsaMbedProvenance.md"))
        # CMake's property storage serializes its five arguments as a list;
        # instantiated callers may retain either that list or argument groups.
        normalized = tuple(posixpath.normpath(
            part if Path(part).is_absolute() else str(ROOT / part))
            for value in values for part in value.split(";"))
        return normalized == expected
    if (name in {"CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS"} and
            target in {"cxet_tls_certificates", "cxet_tls_x509_source"} and
            instance.body.relative == "src/src/CMakeLists.txt" and
            instance.evaluation.source_base == Path("src/src") and
            instance.evaluation.binary_base == Path("src/src")):
        if name == "CXET_COMPILE_OUTPUTS":
            return values == (SYNTHETIC_BINARY_ROOT +
                              "/src/src/generated/mbedtls-cold/x509.c",)
        expected = tuple(str(ROOT / path) for path in (
            "extra/mbedtls-cold/library/x509.c",
            "cmake/Vendor/mbedtls-cold/AdaptX509.cmake",
            "cmake/Vendor/mbedtls-cold/UPSTREAM.sha256",
            "cmake/Vendor/mbedtls-cold/UPSTREAM.md"))
        return tuple(posixpath.normpath(value) for value in values) == expected
    if name in {"CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS"}:
        if (target != "trading_core_generate_strategy_registry" or
                instance.body.relative != "apps/trading-core/CMakeLists.txt"):
            return False
        generated = SYNTHETIC_BINARY_ROOT + "/apps/trading-core/generated"
        if name == "CXET_COMPILE_OUTPUTS":
            expected = set(registry_outputs()) | {generated + "/StrategyRegistry.stamp"}
        else:
            expected = {path.as_posix() for path in
                        (ROOT / "apps/trading-core/src/Strategy/include/strategy").glob("**/*.hpp")
                        if path.is_file()} | {
                (ROOT / "apps/trading-core/cmake/GenerateStrategyRegistry.cmake").as_posix(),
                generated + "/trading_core/Strategy/StrategyHeaders.manifest",
            }
        normalized = tuple(
            normalize_synthetic_binary_path(value)
            if value.startswith(SYNTHETIC_BINARY_ROOT + "/") else
            posixpath.normpath(value if Path(value).is_absolute() else str(ROOT / value))
            for value in values)
        return len(normalized) == len(expected) and set(normalized) == expected
    if name in {"IMPORTED_LOCATION", "INTERFACE_INCLUDE_DIRECTORIES"}:
        # The downstream target policy accepts only the exact liburing values.
        return target == "liburing::uring"
    return False


def _validate_set_property(instance, groups, errors: list[str]) -> None:
    origin = _origin(instance)
    scope = _literal_group(groups[0]) if groups else None
    if scope is None:
        errors.append(f"{origin}: unresolved set_property scope")
        return
    if scope in {"GLOBAL", "DIRECTORY", "INSTALL"}:
        errors.append(f"{origin}: forbidden set_property({scope}) mutation")
        return
    property_index = next(
        (index for index, group in enumerate(groups) if group == ("PROPERTY",)),
        None,
    )
    if property_index is None or property_index + 1 >= len(groups):
        errors.append(f"{origin}: malformed set_property signature")
        return
    name = _literal_group(groups[property_index + 1])
    if name is None:
        errors.append(f"{origin}: unresolved property name")
        return
    prefix = [value for group in groups[1:property_index] for value in group]
    append = "APPEND" in prefix
    append_string = "APPEND_STRING" in prefix
    owners = [
        value for value in prefix
        if value not in {"APPEND", "APPEND_STRING"}]
    values = tuple(
        value for group in groups[property_index + 2:] for value in group)
    if append_string or not owners or any(_opaque(owner) for owner in owners):
        errors.append(f"{origin}: unresolved/unsupported property owner")
        return
    if scope == "CACHE":
        expected = _CACHE_STRINGS.get((instance.body.relative, owners[0]))
        if (len(owners) != 1 or append or name != "STRINGS" or
                values != expected):
            errors.append(f"{origin}: unapproved CACHE property metadata")
        return
    if scope == "TEST":
        if (not _approved_test_writer_context(instance) or
                "DIRECTORY" in prefix or not append or
                not _test_property(name, values)):
            errors.append(f"{origin}: unapproved TEST property {name}")
        return
    if scope == "TARGET":
        if name in {"CXET_COMPILE_INPUTS", "CXET_COMPILE_OUTPUTS"} and (append or append_string):
            errors.append(f"{origin}: compile producer metadata cannot append inputs/outputs")
            return
        for target in owners:
            if not _target_property(instance, target, name, values):
                errors.append(
                    f"{origin}: unapproved TARGET property {name} on {target}")
        return
    if scope == "SOURCE":
        errors.append(
            f"{origin}: set_property(SOURCE) is unsupported; use the exact "
            "reviewed set_source_files_properties forms")
        return
    errors.append(f"{origin}: unsupported set_property({scope}) grammar")


def validate_property_command(instance, errors: list[str]) -> None:
    """Default-deny every active property command and property spelling."""
    command = instance.body.command.name
    groups = [tuple(group) for group in instance.token_groups]
    origin = _origin(instance)
    if command == "set_property":
        _validate_set_property(instance, groups, errors)
        return
    marker = "PROPERTIES"
    marker_index = next(
        (index for index, group in enumerate(groups) if group == (marker,)),
        None,
    )
    if marker_index is None or marker_index == 0:
        errors.append(f"{origin}: malformed {command} property signature")
        return
    pairs = _property_pairs(groups, marker_index + 1, origin, errors)
    if command == "set_source_files_properties":
        owners = [value for group in groups[:marker_index] for value in group]
        rsa = (instance.body.relative == "src/src/CMakeLists.txt" and
               instance.body.source_base == instance.evaluation.source_base == Path("src/src") and
               instance.body.binary_base == instance.evaluation.binary_base == Path("src/src") and
               owners == ["Core/src/Crypto/Rsa.cpp"] and
               cmake_list_words(instance.body.command.body) == [
                   "Core/src/Crypto/Rsa.cpp", "PROPERTIES", "COMPILE_DEFINITIONS",
                   r'MBEDTLS_CONFIG_FILE=\"RsaMbedConfig.h\"'])
        if rsa:
            return
        if len(pairs) != 1 or pairs[0][0] != "COMPILE_OPTIONS":
            errors.append(f"{origin}: unapproved SOURCE property grammar")
        return
    owners = [value for group in groups[:marker_index] for value in group]
    if not owners or any(_opaque(owner) for owner in owners):
        errors.append(f"{origin}: unresolved {command} owner")
        return
    if command == "set_tests_properties":
        from CMake.Policy.CmakeFamilyOfflineRecipe import parser_launcher_test_recipe
        if parser_launcher_test_recipe(instance):
            return
        if not _approved_test_writer_context(instance):
            errors.append(
                f"{origin}: TEST property writer origin is not reviewed")
            return
        if not _approved_safety_test_writer(instance, owners):
            errors.append(
                f"{origin}: safety TEST writer is not exact/reviewed")
            return
        if "DIRECTORY" in owners:
            errors.append(
                f"{origin}: cross-directory TEST property mutation is "
                "forbidden")
            return
        for name, values in pairs:
            if not _test_property(name, values):
                errors.append(f"{origin}: unapproved TEST property {name}")
        return
    if command == "set_target_properties":
        if any(name == "EXCLUDE_FROM_ALL" for name, _ in pairs):
            trading_core_context = (
                first_if("apps/trading-core/benchmarks/CMakeLists.txt", 18,
                         ("CXET_FAMILY_VERIFICATION",)),)
            trading_core_exact = (
                instance.body.relative ==
                "apps/trading-core/benchmarks/CMakeLists.txt" and
                instance.body.command.line == 19 and
                tuple(owners) == ("trading-core-bench",) and
                pairs == [("EXCLUDE_FROM_ALL", ("TRUE",))] and
                exact_context(
                    instance.evaluation.structural_context,
                    trading_core_context))
            if not trading_core_exact:
                errors.append(
                    f"{origin}: EXCLUDE_FROM_ALL is allowed only for the "
                    "exact reviewed family benchmark set")
            return
        for target in owners:
            for name, values in pairs:
                if not _target_property(instance, target, name, values):
                    errors.append(
                        f"{origin}: unapproved TARGET property {name} "
                        f"on {target}")
        return
    errors.append(f"{origin}: unsupported property command {command}")


def validate_root_property_command(
    command_name: str,
    tokens: list[str],
    root_targets: set[str],
    origin: str,
    errors: list[str],
) -> None:
    """Positive raw-token subset used before root family composition."""
    if command_name == "set_property":
        if (len(tokens) >= 5 and tokens[:1] == ["CACHE"] and
                tokens[2:4] == ["PROPERTY", "STRINGS"] and
                tuple(tokens[4:]) == _CACHE_STRINGS.get(
                    ("CMakeLists.txt", tokens[1]))):
            return
        scope = tokens[0] if tokens else "<missing>"
        errors.append(f"{origin}: unapproved root set_property({scope})")
        return
    if command_name != "set_target_properties":
        return
    try:
        marker = tokens.index("PROPERTIES")
    except ValueError:
        errors.append(f"{origin}: malformed root target property signature")
        return
    targets = tokens[:marker]
    tail = tokens[marker + 1:]
    if (not targets or any(target not in root_targets for target in targets) or
            len(tail) % 2):
        errors.append(f"{origin}: unresolved root target property owner")
        return
    for index in range(0, len(tail), 2):
        name, value = tail[index], tail[index + 1]
        approved = (
            name == "RUNTIME_OUTPUT_DIRECTORY" and
            value == "${CMAKE_BINARY_DIR}"
        ) or (
            name == "OUTPUT_NAME" and
            re.fullmatch(r"[A-Za-z0-9_.+-]+", value) is not None
        )
        if not approved:
            errors.append(f"{origin}: unapproved root TARGET property {name}")
