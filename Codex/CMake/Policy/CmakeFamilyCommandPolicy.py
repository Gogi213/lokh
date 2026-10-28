"""Reviewed custom-build and compile-option forms for the active family."""

from __future__ import annotations

import posixpath
import re
from collections import Counter
from pathlib import Path

from CMake.Flow.CmakeFamilyExecutionIdentity import (
    reviewed_file_identity,
    reviewed_tree_identity,
)
from CMake.Policy.CmakeFamilyPropertyPolicy import (
    validate_property_command, reviewed_wasm_inputs, normalized_recipe_input,
    reviewed_wasm_context, reviewed_wasm_alternatives,
)
from CMake.Policy.CmakeFamilyFrontendRecipe import reviewed_frontend_recipe
from CMake.Policy.CmakeFamilyProgramPolicy import reviewed_program
from CMake.Policy.CmakeFamilySelectorPolicy import validate_compile_selector_authority
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
from CMake.Flow.CmakeFamilyFlow import paths_cover, bounded_intersection, bounded_merge
from CMake.Policy.CmakeFamilyStrategyPolicy import (
    proven_strategy_headers,
    proven_strategy_names,
    registry_outputs,
)


ROOT = Path(__file__).resolve().parents[4]
BINARY_ROOT = "__CXET_CMAKE_BINARY__"
LIBURING_WORK = BINARY_ROOT + "/src/src/_deps/liburing"
LIBURING_INPUTS = "${CXET_LIBURING_INPUT_FILES}"
COMMAND_POLICY_NAMES = frozenset({
    "add_compile_options", "add_custom_command", "add_custom_target",
    "set_source_files_properties", "set_tests_properties",
    "target_compile_options",
})

CUSTOM_TARGET_CONTEXTS = {
    ("apps/hft-compressor/CMakeLists.txt", "hft-compressor-product"): Path("apps/hft-compressor"),
    ("apps/hft-compressor/CMakeLists.txt", "hft-compressor-all"): Path("apps/hft-compressor"),
    ("apps/diagnostic/CMakeLists.txt", "diagnostic-product"): Path("apps/diagnostic"),
    ("src/src/CMakeLists.txt", "cxet_liburing_ep"): Path("src/src"),
    ("src/src/CMakeLists.txt", "cxet_tls_x509_source"): Path("src/src"),
    ("apps/trading-core/CMakeLists.txt",
     "trading_core_generate_strategy_registry"): Path("apps/trading-core"),
    ("apps/vetron/wasm/CMakeLists.txt",
     "vetron-math-wasm"): Path("apps/vetron/wasm"),
    ("apps/trading-core/CMakeLists.txt",
     "trading-core-product"): Path("apps/trading-core"),
    ("apps/trading-core/CMakeLists.txt",
     "trading-core-all"): Path("apps/trading-core"),
    ("apps/hft-backtest/CMakeLists.txt",
     "hft-backtest-product"): Path("apps/hft-backtest"),
    ("apps/hft-backtest/CMakeLists.txt",
     "hft-backtest-all"): Path("apps/hft-backtest"),
    ("apps/hft-parser/CMakeLists.txt",
     "hft-parser-product"): Path("apps/hft-parser"),
    ("apps/hft-parser/CMakeLists.txt",
     "hft-parser-all"): Path("apps/hft-parser"),
    ("apps/trader/CMakeLists.txt", "trader-product"): Path("apps/trader"),
    ("apps/trader/CMakeLists.txt", "trader-full-product"): Path("apps/trader"),
    ("apps/trader/CMakeLists.txt",
     "trader-market-observe-product"): Path("apps/trader"),
    ("apps/trader/CMakeLists.txt", "trader-all"): Path("apps/trader"),
    ("apps/vetron/CMakeLists.txt", "vetron-product"): Path("apps/vetron"),
    ("apps/vetron/CMakeLists.txt", "vetron-frontend"): Path("apps/vetron"),
    ("apps/vetron/CMakeLists.txt",
     "vetron-read-product"): Path("apps/vetron"),
    ("apps/vetron/CMakeLists.txt",
     "vetron-full-control-product"): Path("apps/vetron"),
    ("apps/vetron/CMakeLists.txt",
     "vetron-full-product"): Path("apps/vetron"),
    ("apps/vetron/CMakeLists.txt", "vetron-all"): Path("apps/vetron"),
}

CUSTOM_COMMAND_CONTEXTS = {
    "src/src/CMakeLists.txt": Path("src/src"),
    "apps/trading-core/CMakeLists.txt": Path("apps/trading-core"),
    "apps/vetron/wasm/CMakeLists.txt": Path("apps/vetron/wasm"),
}

_CUSTOM_KEYWORDS = frozenset({
    "APPEND", "BYPRODUCTS", "CODEGEN", "COMMAND", "COMMAND_EXPAND_LISTS",
    "COMMENT", "DEPENDS", "DEPENDS_EXPLICIT_ONLY", "DEPFILE",
    "IMPLICIT_DEPENDS", "JOB_POOL", "JOB_SERVER_AWARE", "MAIN_DEPENDENCY",
    "OUTPUT", "TARGET", "USES_TERMINAL", "VERBATIM", "WORKING_DIRECTORY",
})
_ALLOWED_CUSTOM_KEYWORDS = frozenset({
    "BYPRODUCTS", "COMMAND", "COMMAND_EXPAND_LISTS", "COMMENT", "DEPENDS",
    "OUTPUT", "VERBATIM", "WORKING_DIRECTORY",
})
_VALUELESS_CUSTOM_KEYWORDS = frozenset({"COMMAND_EXPAND_LISTS", "VERBATIM"})
_CARRIER_MARKERS = ("${", "$ENV{", "$CACHE{", "$<")

_REVIEWED_LITERAL_COMPILE_OPTIONS = frozenset({
    "-O1", "-O2", "-O3", "-g3", "-march=native", "-maes",
    "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-Wconversion",
    "-Wshadow", "-Wsign-conversion", "-Wframe-larger-than=32768",
    "-Wframe-larger-than=131072", "-Werror=frame-larger-than",
    "-flto", "-fno-exceptions", "-fno-rtti", "-fno-inline-functions",
    "-fsanitize=address", "-fsanitize=undefined", "-fsanitize=thread",
    "-fsanitize=fuzzer", "-fsanitize=address,undefined",
    "-fsanitize=fuzzer,address,undefined",
    "-fsanitize-address-use-after-scope", "-fno-omit-frame-pointer",
    "-fno-optimize-sibling-calls", "-fno-sanitize-recover=all",
})
_STATIC_CUSTOM_DEPENDENCIES = {
    ("apps/hft-compressor/CMakeLists.txt", "hft-compressor-product"):
        frozenset({"hft_compressor_core"}),
    ("apps/hft-compressor/CMakeLists.txt", "hft-compressor-all"):
        frozenset({"hft-compressor-product"}),
    ("apps/diagnostic/CMakeLists.txt", "diagnostic-product"):
        frozenset({"diagnosticd"}),
    ("apps/vetron/wasm/CMakeLists.txt", "vetron-math-wasm"):
        frozenset({
            (ROOT / "apps/vetron/frontend/.generated/"
             "trading-core-math.wasm").as_posix(),
        }),
    ("apps/trading-core/CMakeLists.txt", "trading-core-product"):
        frozenset({"trading_core_strategy", "trading_core_math"}),
    ("apps/hft-backtest/CMakeLists.txt", "hft-backtest-all"):
        frozenset({"hft-backtest-product"}),
    ("apps/trader/CMakeLists.txt", "trader-all"):
        frozenset({"trader-product"}),
    ("apps/hft-parser/CMakeLists.txt", "hft-parser-product"): frozenset({
        "hft-public-market-catalog-dump", "hft-parserd",
        "hft-algosd", "hft-resource-planner",
        "hft_parser_projection_client", "hftp_projection_publisher",
        "hft_parser_history_client", "hft_parser_reference_client",
    }),
    ("apps/hft-parser/CMakeLists.txt", "hft-parser-all"):
        frozenset({"hft-parser-product"}),
    ("apps/hft-backtest/CMakeLists.txt", "hft-backtest-product"):
        frozenset({"hft-backtest"}),
    ("apps/trader/CMakeLists.txt", "trader-product"):
        frozenset({"traderd"}),
    ("apps/trader/CMakeLists.txt", "trader-full-product"): frozenset({
        "trader-product", "trader-control", "trader-market-observed", "trader-alertd",
        "hft_parser_session_client", "trader_order_client",
        "trader_control_client", "trader_order_bootstrap_server",
        "trader_projection_client",
        "trader_market_observe_projection_client", "trader_live_runtime",
        "trader_traderd_process",
    }),
    ("apps/trader/CMakeLists.txt", "trader-market-observe-product"):
        frozenset({
            "trader-market-observed", "trader_market_observe_runtime",
            "trader_market_observe_process",
            "trader_market_observe_projection_publisher",
            "trader_market_observe_projection_server",
        }),
    ("apps/vetron/CMakeLists.txt", "vetron-read-product"): frozenset({
        "hft-parserd", "hft-algosd", "hft-resource-planner",
        "trader-market-observe-product", "vetron-math-wasm",
        "vetron-frontend", "vetrond-read", "vetron_read_gateway", "vetron_read_runtime",
        "vetron_read_process",
    }),
    ("apps/vetron/CMakeLists.txt", "vetron-full-control-product"):
        frozenset({"vetron_full_control"}),
    ("apps/vetron/CMakeLists.txt", "vetron-full-product"): frozenset({
        "hft-parserd", "hft-algosd", "hft-resource-planner",
        "vetron-math-wasm", "vetrond-full",
        "vetron_full_process", "vetron-full-control-product",
    }),
    ("apps/vetron/CMakeLists.txt", "vetron-product"): frozenset({
        "vetron-read-product",
    }),
    ("apps/vetron/CMakeLists.txt", "vetron-all"): frozenset({
        "vetron-product", "vetron-math-wasm",
    }),
}

def _origin(instance) -> str:
    return f"{instance.body.relative}:{instance.body.command.line}"


def _flatten(instance) -> list[str]:
    return [value for group in instance.token_groups for value in group]


def _context(instance, expected: Path) -> bool:
    return (
        instance.evaluation.source_base == expected and
        instance.evaluation.binary_base == expected
    )


def _normalized(value: str) -> str:
    return posixpath.normpath(value.replace("\\", "/"))


def _repo_files(relative: str, pattern: str) -> frozenset[str]:
    return frozenset(
        path.resolve().as_posix()
        for path in (ROOT / relative).glob(pattern)
        if path.is_file()
    )


def _custom_sections(instance, tokenize, errors, start: int = 0):
    sections: dict[str, list[list[str]]] = {}
    flags: set[str] = set()
    current: list[str] | None = None
    for value in _flatten(instance)[start:]:
        is_keyword = (
            value in _CUSTOM_KEYWORDS and
            not any(marker in value for marker in _CARRIER_MARKERS)
        )
        if is_keyword:
            if value not in _ALLOWED_CUSTOM_KEYWORDS and not (
                    value == "DEPFILE" and instance.body.relative == "apps/vetron/wasm/CMakeLists.txt"):
                errors.append(
                    f"{_origin(instance)}: unsupported add_custom_command "
                    f"keyword {value}")
                return None
            if value in _VALUELESS_CUSTOM_KEYWORDS:
                if value in flags:
                    errors.append(
                        f"{_origin(instance)}: duplicate custom-command flag "
                        f"{value}")
                flags.add(value)
                current = None
            else:
                current = []
                sections.setdefault(value, []).append(current)
            continue
        if current is None:
            errors.append(
                f"{_origin(instance)}: custom-command value outside a "
                f"reviewed section: {value}")
            return None
        current.append(value)
    if "VERBATIM" not in flags:
        errors.append(f"{_origin(instance)}: custom command is not VERBATIM")
    return sections


def _validate_frontend_target(instance, tokenize, errors) -> None:
    expected_raw = [
        "vetron-frontend", "COMMAND", "${Python3_EXECUTABLE}", "${VETRON_FRONTEND_SCRIPT}",
        "--output-dir", "${VETRON_FRONTEND_OUTPUT_DIR}",
        "--stamp", "${VETRON_FRONTEND_STAMP}",
        "--cache-dir", "${CMAKE_BINARY_DIR}/frontend/npm-cache",
        "--exchanges", "${VETRON_FRONTEND_EXCHANGES}",
        "--generated-dir", "${VETRON_FRONTEND_GENERATED_DIR}",
        "${VETRON_FRONTEND_MATH_ARGUMENTS}",
        "DEPENDS", "${VETRON_FRONTEND_INPUTS}", "${VETRON_MATH_WASM_OUTPUT}",
        "BYPRODUCTS", "${VETRON_FRONTEND_STAMP}",
        "${VETRON_FRONTEND_OUTPUT_DIR}/index.html", "${VETRON_FRONTEND_GENERATED_OUTPUTS}",
        "COMMENT", "Build pinned ReadOnly Vetron frontend assets", "VERBATIM"]
    if cmake_list_words(instance.body.command.body) != expected_raw:
        errors.append(f"{_origin(instance)}: frontend raw producer recipe changed")
        return
    sections = _custom_sections(instance, tokenize, errors, start=1)
    if sections is None:
        return
    normalized = {name: [tuple(_normalized(value) for value in values)
                         for values in groups] for name, groups in sections.items()}
    for local_tests in (False, True):
        recipe = reviewed_frontend_recipe(local_tests=local_tests)
        if recipe is not None and normalized == {
                "COMMAND": [recipe["command"]],
                "DEPENDS": [recipe["dependencies"]],
                "BYPRODUCTS": [recipe["outputs"]],
                "COMMENT": [("Build pinned ReadOnly Vetron frontend assets",)]}:
            return
    errors.append(f"{_origin(instance)}: frontend producer inputs, paths or authority changed")


def _validate_custom_target(instance, tokenize, errors) -> None:
    raw = tokenize(instance.body.command.body)
    tokens = _flatten(instance)
    if not raw or not tokens:
        errors.append(f"{_origin(instance)}: ambiguous custom target owner")
        return
    target = tokens[0]
    expected = CUSTOM_TARGET_CONTEXTS.get((instance.body.relative, target))
    if expected is None or not _context(instance, expected):
        errors.append(
            f"{_origin(instance)}: unapproved active custom target {target}")
        return
    if instance.body.relative == "apps/hft-compressor/CMakeLists.txt":
        dependency = {"hft-compressor-product": "hft_compressor_core",
                      "hft-compressor-all": "hft-compressor-product"}.get(target)
        if (instance.body != instance.evaluation or instance.body.structural_context or
                instance.body.source_base != expected or
                cmake_list_words(instance.body.command.body) != [target, "DEPENDS", dependency]):
            errors.append(f"{_origin(instance)}: compressor aggregate recipe changed")
        return
    if (instance.body.relative, target) == (
            "apps/vetron/CMakeLists.txt", "vetron-frontend"):
        _validate_frontend_target(instance, tokenize, errors)
        return
    if (instance.body.relative, target) == (
            "apps/vetron/wasm/CMakeLists.txt",
            "vetron-math-wasm"):
        output = (
            ROOT / "apps/vetron/frontend/.generated/"
            "trading-core-math.wasm").as_posix()
        if tokens[1:2] == ["COMMAND"]:
            expected_tokens = [
                "vetron-math-wasm", "COMMAND", "${CMAKE_COMMAND}",
                "-E", "echo",
                "Vetron WASM: em++ is unavailable; configure "
                "VETRON_EMXX_EXECUTABLE with the approved Emscripten "
                "toolchain",
                "COMMAND", "${CMAKE_COMMAND}", "-E", "false", "VERBATIM",
            ]
            expected_expansion = [*expected_tokens[:5], *expected_tokens[5].split(";"), *expected_tokens[6:]]
            if (not reviewed_wasm_context(instance, unavailable=True) or
                    cmake_list_words(instance.body.command.body) != expected_tokens or
                    tokens != expected_expansion):
                errors.append(
                    f"{_origin(instance)}: unavailable-tool WASM target "
                    "shape changed")
        elif tokens[1:2] == ["DEPENDS"]:
            generated = BINARY_ROOT + "/apps/vetron/wasm/"
            if tokens not in (["vetron-math-wasm", "DEPENDS", generated + "math-wasm.stamp.json", output,
                              generated + "math-wasm.d"],
                             ["vetron-math-wasm", "DEPENDS", generated + "math-wasm.stamp.json",
                              generated + "trading-core-math.wasm", generated + "math-wasm.d"]):
                errors.append(
                    f"{_origin(instance)}: generated WASM target dependency "
                    "changed")
        elif tokens[1:2] == ["BYPRODUCTS"]:
            if not reviewed_wasm_context(instance, unavailable=False):
                errors.append(f"{_origin(instance)}: prepared WASM target context changed")
            sections = _custom_sections(instance, tokenize, errors, start=1)
            if sections is not None:
                _validate_wasm_custom(sections, _origin(instance), errors,
                                      instance, custom_target=True)
        else:
            errors.append(
                f"{_origin(instance)}: unreviewed WASM target declaration")
        return
    if (instance.body.relative, target) == (
            "src/src/CMakeLists.txt", "cxet_liburing_ep"):
        if tokens != [target, "DEPENDS", *_liburing_declared_dependencies()]:
            errors.append(f"{_origin(instance)}: liburing target must depend on its exact archive/header outputs")
        return
    if (instance.body.relative, target) == (
            "apps/trading-core/CMakeLists.txt", "trading_core_generate_strategy_registry"):
        sections = _custom_sections(instance, tokenize, errors, start=1)
        if sections is not None:
            _validate_trading_custom(sections, _origin(instance), errors, custom_target=True)
        return
    if len(tokens) < 2 or tokens[1] != "DEPENDS":
        errors.append(
            f"{_origin(instance)}: custom target {target} is not "
            "dependency-only")
        return
    if any(token in {
            "ALL", "BYPRODUCTS", "COMMAND", "OUTPUT", "SOURCES",
            "WORKING_DIRECTORY"} for token in tokens[2:]):
        errors.append(
            f"{_origin(instance)}: custom target {target} has an active "
            "command/output form")
        return
    dependencies = tokens[2:]
    unresolved = [
        value for value in dependencies
        if any(marker in value for marker in _CARRIER_MARKERS)
    ]
    if unresolved:
        errors.append(
            f"{_origin(instance)}: unresolved custom target dependencies "
            f"{unresolved}")


def _custom_target_dependencies(
    instances, directory_targets, errors: list[str], require_exact: bool,
    active_origins=None, snapshots=None,
) -> None:
    from Family.Targets.CxetFamilyTargetRegistry import covered_provider_scopes

    def dependency_covers(declarations, use):
        if len(declarations) != 1:
            # The reviewed unavailable producer terminates its child scope;
            # the prepared producer occupies the other successful paths.
            # No other duplicate declaration can become an aggregate proof.
            if not reviewed_wasm_alternatives(declarations):
                return False
        evidence = {}
        for declaration in declarations:
            scope = declaration.evaluation.scope
            evidence[scope] = bounded_merge(errors, f"{_origin(use)} aggregate producer paths",
                evidence.get(scope, ()), declaration.path_alternatives)
        if snapshots is None:
            return paths_cover(universe=use.path_alternatives,
                evidence=bounded_merge(errors, f"{_origin(use)} aggregate producer paths", *evidence.values()))
        live_eof = snapshots.live_eof_paths
        use_paths = bounded_intersection(use.path_alternatives,
            live_eof.get(use.evaluation.scope, ()), errors,
            f"{_origin(use)} aggregate generation paths")
        return bool(use_paths) and bool(covered_provider_scopes(
            use_scope=use.evaluation.scope, use_paths=use_paths,
            evidence_by_scope=evidence,
            live_eof_paths=live_eof))

    target_declarations = {}
    for declaration in instances:
        if (declaration.body.command.name in {"add_library", "add_executable", "add_custom_target"} and
                declaration.token_groups and len(declaration.token_groups[0]) == 1):
            target_declarations.setdefault(declaration.token_groups[0][0], []).append(declaration)
    declared = set(target_declarations)
    actual: dict[tuple[str, str], list[str]] = {}
    aggregate_declarations: dict[tuple[str, str], object] = {}
    for instance in instances:
        if not instance.token_groups:
            continue
        name = instance.body.command.name
        owner = instance.token_groups[0][0]
        if name == "add_custom_target":
            key = (instance.body.relative, owner)
            aggregate_declarations[key] = instance
            tokens = _flatten(instance)
            try:
                index = next(
                    i for i, value in enumerate(tokens)
                    if value == "DEPENDS")
            except StopIteration:
                continue
            end = next((
                position for position in range(index + 1, len(tokens))
                if (tokens[position] in _CUSTOM_KEYWORDS and
                    not any(marker in tokens[position]
                            for marker in _CARRIER_MARKERS))
            ), len(tokens))
            actual.setdefault(key, []).extend(tokens[index + 1:end])
        elif name == "add_dependencies":
            for key in aggregate_declarations:
                if key[1] == owner:
                    actual.setdefault(key, []).extend(_flatten(instance)[1:])

    for key, instance in aggregate_declarations.items():
        target = key[1]
        dependencies = actual.get(key, [])
        if key == ("src/src/CMakeLists.txt", "cxet_liburing_ep"):
            expected = frozenset(_liburing_declared_dependencies())
        elif key == (
                "src/src/CMakeLists.txt", "cxet_tls_x509_source"):
            expected = frozenset({BINARY_ROOT + "/src/src/generated/mbedtls-cold/x509.c"})
        elif key == (
                "apps/vetron/wasm/CMakeLists.txt", "vetron-math-wasm"):
            shape = _flatten(instance)[1:2]
            if shape == ["COMMAND"]:
                expected = frozenset()
            elif shape == ["BYPRODUCTS"]:
                dependencies = [normalized_recipe_input(value) for value in dependencies]
                expected = reviewed_wasm_inputs(prepared=True, actual_inputs=dependencies)
            else:
                generated = BINARY_ROOT + "/apps/vetron/wasm/"
                outputs = {generated + "math-wasm.stamp.json", generated + "math-wasm.d"}
                output = (ROOT / "apps/vetron/frontend/.generated/trading-core-math.wasm").as_posix()
                expected = frozenset(outputs | ({generated + "trading-core-math.wasm"} if
                    generated + "trading-core-math.wasm" in dependencies else {output}))
        elif key == ("apps/vetron/CMakeLists.txt", "vetron-frontend"):
            # Aggregate edges are unordered; producer argument/input order is
            # proved separately by _validate_frontend_target. The explicit
            # policy header also occurs in the reviewed catalogue glob, so
            # retain the exact recipe multiplicities rather than deduplicating.
            dependencies = [_normalized(value) for value in dependencies]
            expected = None
            for local_tests in (False, True):
                recipe = reviewed_frontend_recipe(local_tests=local_tests)
                if recipe is None:
                    continue
                candidate = tuple(_normalized(value) for value in
                                  (*recipe["dependencies"], "vetron-math-wasm"))
                if expected is None:
                    expected = candidate
                if Counter(dependencies) == Counter(candidate):
                    expected = candidate
                    break
        elif key == (
                "apps/trading-core/CMakeLists.txt",
                "trading_core_generate_strategy_registry"):
            expected = frozenset({BINARY_ROOT + "/apps/trading-core/generated/StrategyRegistry.stamp"})
        elif key == ("apps/hft-parser/CMakeLists.txt", "hft-parser-all"):
            expected = _STATIC_CUSTOM_DEPENDENCIES[key]
        elif key == ("apps/trading-core/CMakeLists.txt", "trading-core-all"):
            expected = frozenset({"trading-core-product"}) | (
                frozenset({"trading-core-math-tests"}) if
                "trading-core-math-tests" in declared else frozenset())
        else:
            expected = _STATIC_CUSTOM_DEPENDENCIES.get(key)
        if key in {
                ("apps/hft-parser/CMakeLists.txt", "hft-parser-product"),
                ("apps/trader/CMakeLists.txt", "trader-product"),
                ("apps/vetron/CMakeLists.txt", "vetron-read-product"),
                ("apps/vetron/CMakeLists.txt", "vetron-full-product")}:
            if snapshots is not None:
                selection = snapshots.values.get(
                    instance.evaluation.ordinal, {}).get("CXET_EXCHANGE_FINAM")
                if selection not in {("ON",), ("OFF",), ("1",), ("0",)}:
                    errors.append(f"{_origin(instance)}: unresolved FINAM aggregate selection")
                finam = selection in {("ON",), ("1",)}
                if key == ("apps/trader/CMakeLists.txt", "trader-product"):
                    history = snapshots.values.get(
                        instance.evaluation.ordinal, {}).get("HFT_PARSER_CANDLE_HISTORY")
                    if history not in {("ON",), ("OFF",), ("1",), ("0",)}:
                        errors.append(f"{_origin(instance)}: unresolved Parser candle history aggregate selection")
                    finam = finam and history in {("ON",), ("1",)}
            else:
                # Compatibility callers without state still validate every
                # active dependency; production passes the selected state.
                finam = "hft-finam-metadata-store" in dependencies
            if finam and expected is not None:
                expected = expected | {"hft-finam-metadata-store"}
        actual_counts = Counter(dependencies)
        expected_counts = Counter(expected or ())
        frontend = key == ("apps/vetron/CMakeLists.txt", "vetron-frontend")
        closure_changed = expected is None
        if expected is not None:
            closure_changed = (actual_counts != expected_counts if frontend else
                len(dependencies) != len(actual_counts) or
                set(dependencies) != set(expected))
        if closure_changed:
            missing = expected_counts - actual_counts
            extra = actual_counts - expected_counts
            sample = lambda values: [
                (value if len(value) <= 300 else value[:297] + "...", values[value])
                for value in sorted(values)[:8]]
            errors.append(
                f"{_origin(instance)}: custom target {target} dependency "
                f"closure changed: expected={len(expected) if expected is not None else 'unproved'}, "
                f"actual={len(dependencies)}, unique={len(actual_counts)}, "
                f"duplicates={len(dependencies) - len(actual_counts)}; "
                f"missing={sum(missing.values())} {sample(missing)}; "
                f"extra={sum(extra.values())} {sample(extra)}")
        for dependency in dependencies:
            if (key == ("apps/vetron/wasm/CMakeLists.txt", "vetron-math-wasm") and
                    expected is not None and dependency in expected):
                continue
            if (key == ("src/src/CMakeLists.txt", "cxet_liburing_ep") and
                    dependency == LIBURING_INPUTS):
                continue
            if dependency.startswith(BINARY_ROOT + "/"):
                continue
            if (expected is not None and dependency in expected and
                    ("/" in dependency or "\\" in dependency)):
                continue
            declaration = target_declarations.get(dependency)
            if declaration is None:
                errors.append(
                    f"{_origin(instance)}: custom target {target} depends "
                    f"on undeclared target/file {dependency}")
            elif not dependency_covers(declaration, instance):
                errors.append(
                    f"{_origin(instance)}: custom target {target} dependency "
                    f"{dependency} is not declared on every required path")
    if require_exact:
        origins = (set(active_origins) if active_origins is not None else
                   {instance.body.relative for instance in instances})
        expected_keys = {key for key in CUSTOM_TARGET_CONTEXTS if key[0] in origins}
        actual_keys = set(aggregate_declarations)
        if actual_keys != expected_keys:
            errors.append(
                "active family aggregate target set changed: "
                f"missing={sorted(expected_keys - actual_keys)}, "
                f"extra={sorted(actual_keys - expected_keys)}")
        validate_compile_selector_authority(errors)


def _liburing_dependencies() -> frozenset[str]:
    return frozenset({
        path.resolve().as_posix()
        for path in (ROOT / "extra/liburing").rglob("*")
        if path.is_file() and ".git" not in path.relative_to(
            ROOT / "extra/liburing").parts
    } | {(ROOT / "cmake/SanitizeCRLF.cmake").resolve().as_posix()})


def _liburing_declared_dependencies() -> tuple[str, str]:
    return (
        LIBURING_WORK + "/install/lib/liburing.a",
        LIBURING_WORK + "/install/include/liburing.h",
    )


def _validate_liburing_custom(instance, errors: list[str]) -> None:
    """Pin the current output-producing private liburing build recipe.

    VendorPolicy independently proves the exact path, clean-environment,
    compiler/LTO/LLD and job-count writers consumed by these raw arguments.
    No host path or expanded arbitrary command is accepted here.
    """
    cmake = "${CMAKE_COMMAND}"
    source = "${CXET_LIBURING_SOURCE_DIR}"
    install = "${CXET_LIBURING_INSTALL_DIR}"
    commands = [
        [cmake, "-E", "rm", "-rf", source, install],
        [cmake, "-E", "make_directory", source, install],
        [cmake, "-E", "copy_directory", "${CXET_LIBURING_VENDOR_DIR}", source],
        [cmake, "-E", "rm", "-rf", source + "/.git"],
        ["/usr/bin/perl", "-0pi", "-e", r"s/(?<=\(AR\)) r / rc /g", source + "/src/Makefile"],
        [cmake, "-DSANITIZE_CRLF_DIR=" + source, "-P", "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/SanitizeCRLF.cmake"],
    ]
    prefix = [cmake, "-E", "chdir", source, "/usr/bin/env", "-i", "${_CXET_LIBURING_CLEAN_ENV}"]
    commands += [
        prefix + ["/bin/sh", "./configure", "--prefix=" + install,
                  "--includedir=" + install + "/include", "--libdir=" + install + "/lib", "--libdevdir=" + install + "/lib"],
        prefix + ["/usr/bin/make", "-j${CXET_COMPILE_JOBS}", "library", "ENABLE_SHARED=0"],
        prefix + ["/usr/bin/make", "-j${CXET_COMPILE_JOBS}", "install", "ENABLE_SHARED=0"],
    ]
    expected = ["OUTPUT", "${CXET_LIBURING_ARCHIVE}", "${CXET_LIBURING_HEADER}"]
    for command in commands:
        expected += ["COMMAND", *command]
    expected += ["DEPENDS", "${CXET_LIBURING_INPUT_FILES}", "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake/SanitizeCRLF.cmake",
                 "WORKING_DIRECTORY", "${CMAKE_CURRENT_BINARY_DIR}", "COMMENT", "Building vendored liburing", "VERBATIM"]
    if (instance.body.relative != "src/src/CMakeLists.txt" or
            not _context(instance, Path("src/src")) or
            cmake_list_words(instance.body.command.body) != expected or
            not reviewed_tree_identity("liburing_vendor") or
            not reviewed_file_identity("cmake/SanitizeCRLF.cmake")):
        errors.append(f"{_origin(instance)}: unapproved liburing output recipe or source authority")


def _validate_strategy_producer_microcases(errors: list[str]) -> None:
    generated = BINARY_ROOT + "/apps/trading-core/generated"
    stamp = generated + "/StrategyRegistry.stamp"
    registry = generated + "/trading_core/Strategy/"
    producer = ["${CMAKE_COMMAND}",
                "-DSTRATEGY_ROOT=apps/trading-core/src/Strategy/include/strategy",
                "-DOUT_DIR=" + generated,
                "-DSTRATEGY_HEADERS=" + "|".join(sorted(proven_strategy_headers())),
                "-P", "apps/trading-core/cmake/GenerateStrategyRegistry.cmake"]
    dependencies = sorted(set(_repo_files(
        "apps/trading-core/src/Strategy/include/strategy", "**/*.hpp")) | {
        "apps/trading-core/cmake/GenerateStrategyRegistry.cmake",
        registry + "StrategyHeaders.manifest"})
    fixtures = (
        (False, {"OUTPUT": [[stamp]], "COMMAND": [producer,
                  ["${CMAKE_COMMAND}", "-E", "touch", stamp]],
                 "DEPENDS": [dependencies]}),
        (True, {"BYPRODUCTS": [sorted(registry_outputs())],
                "COMMAND": [producer], "DEPENDS": [[stamp]]}),
    )
    for custom_target, fixture in fixtures:
        found = []
        _validate_trading_custom(fixture, "strategy-producer self-check", found,
                                 custom_target=custom_target)
        if found:
            errors.append("strategy-producer self-check rejected exact stamp/byproduct protocol")
        for section in ("COMMAND", "DEPENDS", "BYPRODUCTS" if custom_target else "OUTPUT"):
            mutant = {name: [list(group) for group in groups]
                      for name, groups in fixture.items()}
            mutant[section][0].append("unreviewed-strategy-producer-input")
            found = []
            _validate_trading_custom(mutant, "strategy-producer self-check", found,
                                     custom_target=custom_target)
            if not found:
                errors.append(f"strategy-producer self-check accepted altered {section}")


def _validate_trading_custom(
    sections: dict[str, list[list[str]]],
    origin: str,
    errors: list[str],
    *, custom_target: bool = False,
) -> None:
    generated = BINARY_ROOT + "/apps/trading-core/generated"
    registry = generated + "/trading_core/Strategy/"
    strategy_names = set(proven_strategy_names())
    allowed_outputs = {
        registry + "GeneratedStrategyRegistry.hpp",
        registry + "GeneratedStrategyRegistry.cpp",
    } | {
        registry + f"GeneratedStrategyRegistry_{name}.cpp"
        for name in strategy_names
    }
    stamp = generated + "/StrategyRegistry.stamp"
    if custom_target:
        outputs = sections.get("BYPRODUCTS", [])
        valid_outputs = (not sections.get("OUTPUT") and len(outputs) == 1 and
                         len(outputs[0]) == len(allowed_outputs) and
                         set(outputs[0]) == allowed_outputs)
    else:
        valid_outputs = (sections.get("OUTPUT") == [[stamp]] and
                         not sections.get("BYPRODUCTS"))
    if not valid_outputs:
        errors.append(f"{origin}: unapproved strategy-registry outputs")
    if sections.get("WORKING_DIRECTORY"):
        errors.append(f"{origin}: strategy generator changes working directory")
    commands = sections.get("COMMAND", [])
    headers = proven_strategy_headers()
    expected_command_count = 1 if custom_target else 2
    if len(commands) != expected_command_count or not commands or len(commands[0]) != 6:
        errors.append(f"{origin}: strategy generator command shape changed")
    else:
        command = commands[0]
        header_arg = command[3].removeprefix("-DSTRATEGY_HEADERS=")
        header_values = header_arg.split("|")
        if (
            command[0] != "${CMAKE_COMMAND}" or
            _normalized(command[1]) !=
                "-DSTRATEGY_ROOT=apps/trading-core/src/Strategy/include/strategy" or
            command[2] != "-DOUT_DIR=" + generated or
            not command[3].startswith("-DSTRATEGY_HEADERS=") or
            len(header_values) != len(headers) or
            frozenset(header_values) != headers or
            command[4] != "-P" or
            _normalized(command[5]) !=
                "apps/trading-core/cmake/GenerateStrategyRegistry.cmake"
        ):
            errors.append(f"{origin}: unapproved strategy generator command")
    if not custom_target and (len(commands) != 2 or
            commands[1] != ["${CMAKE_COMMAND}", "-E", "touch", stamp]):
        errors.append(f"{origin}: unapproved strategy registry stamp writer")
    dependency_sections = sections.get("DEPENDS", [])
    dependencies = set(dependency_sections[0]) if len(
        dependency_sections) == 1 else set()
    expected_dependencies = {stamp} if custom_target else set(_repo_files(
        "apps/trading-core/src/Strategy/include/strategy", "**/*.hpp")) | {
        "apps/trading-core/cmake/GenerateStrategyRegistry.cmake",
        registry + "StrategyHeaders.manifest",
    }
    normalized = {_normalized(value) for value in dependencies}
    if (len(dependency_sections) != 1 or len(dependency_sections[0]) != len(dependencies)
            or normalized != expected_dependencies):
        errors.append(f"{origin}: unapproved strategy generator dependencies")


def _validate_wasm_custom(
    sections: dict[str, list[list[str]]],
    origin: str,
    errors: list[str],
    instance,
    *, custom_target: bool = False,
) -> None:
    generated = BINARY_ROOT + "/apps/vetron/wasm/"
    output = (ROOT / "apps/vetron/frontend/.generated/trading-core-math.wasm").as_posix()
    allowed_outputs = ([generated + "math-wasm.stamp.json", output, generated + "math-wasm.d"],
                       [generated + "math-wasm.stamp.json", generated + "trading-core-math.wasm", generated + "math-wasm.d"])
    output_key = "BYPRODUCTS" if custom_target else "OUTPUT"
    if len(sections.get(output_key, [])) != 1 or sections[output_key][0] not in allowed_outputs:
        errors.append(f"{origin}: unapproved trading-core WASM output")
    if not custom_target and sections.get("DEPFILE") != [[generated + "math-wasm.d"]]:
        errors.append(f"{origin}: unapproved trading-core WASM dependency file")
    expected_sections = {"BYPRODUCTS", "COMMAND", "DEPENDS", "COMMENT"} if custom_target else {
        "OUTPUT", "COMMAND", "DEPENDS", "DEPFILE", "COMMENT"}
    if set(sections) != expected_sections:
        errors.append(f"{origin}: unapproved trading-core WASM sections")
    if not all(reviewed_file_identity(path) for path in (
            "apps/vetron/wasm/CMakeLists.txt", "apps/vetron/wasm/BuildMathWasm.py",
            "tools/Toolchain/BootstrapEmscripten.py", "tools/Testing/RunOffline.py",
            "cmake/CxetToolchain.cmake")):
        errors.append(f"{origin}: canonical prepared-only WASM recipe identity changed")
    if sections.get("COMMENT") != [[
            "Compile canonical trading-core math for the Vetron history worker"]]:
        errors.append(f"{origin}: trading-core WASM comment changed")
    if sections.get("WORKING_DIRECTORY"):
        errors.append(f"{origin}: trading-core WASM changes working directory")
    commands = sections.get("COMMAND", [])
    raw = instance.body.command.body
    from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
    raw_words = cmake_list_words(raw)
    start = raw_words.index("COMMAND") + 1 if "COMMAND" in raw_words else 0
    stop = raw_words.index("DEPENDS") if "DEPENDS" in raw_words else start
    expected_raw = [
        "${Python3_EXECUTABLE}", "${VETRON_MATH_WASM_SCRIPT}",
        "--build-dir", "${CMAKE_CURRENT_BINARY_DIR}", "--stamp", "${VETRON_MATH_WASM_STAMP}",
        "--depfile", "${VETRON_MATH_WASM_DEPFILE}", "--output", "${VETRON_MATH_WASM_OUTPUT}",
        "--toolchains-root", "${VETRON_EMSCRIPTEN_TOOLCHAINS_ROOT}", "--",
        "-I$<JOIN:$<TARGET_GENEX_EVAL:trading_core_headers,$<TARGET_PROPERTY:trading_core_headers,INTERFACE_INCLUDE_DIRECTORIES>>,;-I>",
        "-I$<JOIN:$<TARGET_GENEX_EVAL:trading_core_contracts,$<TARGET_PROPERTY:trading_core_contracts,INTERFACE_INCLUDE_DIRECTORIES>>,;-I>",
        "-I$<JOIN:$<TARGET_GENEX_EVAL:cxet_read_only_contracts,$<TARGET_PROPERTY:cxet::read_only_contracts,INTERFACE_INCLUDE_DIRECTORIES>>,;-I>",
        "$<$<BOOL:$<TARGET_PROPERTY:cxet::read_only_contracts,INTERFACE_COMPILE_DEFINITIONS>>:-D$<JOIN:$<TARGET_PROPERTY:cxet::read_only_contracts,INTERFACE_COMPILE_DEFINITIONS>,;-D>>",
    ]
    if custom_target:
        expected_target = ["vetron-math-wasm", "BYPRODUCTS",
            "${VETRON_MATH_WASM_STAMP}", "${VETRON_MATH_WASM_OUTPUT}",
            "${VETRON_MATH_WASM_DEPFILE}", "COMMAND", *expected_raw,
            "DEPENDS", "${CMAKE_CURRENT_SOURCE_DIR}/TradingCoreMath.cpp",
            "${CMAKE_CURRENT_SOURCE_DIR}/TradingCoreMathAbi.hpp",
            "${CMAKE_CURRENT_SOURCE_DIR}/FormulaRuler.hpp", "${VETRON_EMSCRIPTEN_BOOTSTRAP}",
            "${VETRON_MATH_WASM_SCRIPT}", "${CMAKE_SOURCE_DIR}/cmake/CxetToolchain.cmake",
            "${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt", "${VETRON_EMXX_EXECUTABLE}",
            "${CXET_EMSDK_INSTALL_DIR}/.emscripten", "${vetron_math_wasm_headers}",
            "COMMENT", "Compile canonical trading-core math for the Vetron history worker",
            "COMMAND_EXPAND_LISTS", "VERBATIM"]
        if raw_words != expected_target:
            errors.append(f"{origin}: trading-core WASM target recipe changed")
    if len(commands) != 1 or raw_words[start:stop] != expected_raw:
        errors.append(f"{origin}: trading-core WASM command shape changed")
    dependencies = sections.get("DEPENDS", [])
    dependency_values = (
        {normalized_recipe_input(value) for value in dependencies[0]}
        if len(dependencies) == 1 else set())
    expected_dependencies = reviewed_wasm_inputs(prepared=True, actual_inputs=dependency_values)
    if (len(dependencies) != 1 or len(dependencies[0]) != len(dependency_values) or
            dependency_values != expected_dependencies):
        errors.append(f"{origin}: trading-core WASM dependency set changed")


def _validate_registry_attachment(instances, errors: list[str]) -> None:
    declarations = [
        instance for instance in instances
        if instance.body.command.name == "add_library" and
        instance.token_groups and instance.token_groups[0] == (
            "trading_core_strategy",)
    ]
    if len(declarations) != 1:
        errors.append(
            "apps/trading-core/CMakeLists.txt: expected one strategy target "
            "declaration")
        return
    attached = {
        _normalized(value) for value in _flatten(declarations[0])[1:]
        if "GeneratedStrategyRegistry" in value
    }
    if attached != set(registry_outputs()):
        errors.append(
            f"{_origin(declarations[0])}: trading_core_strategy registry "
            f"attachment is incomplete: {sorted(attached)}")


def _x509_repo_path(value: str) -> str:
    normalized = _normalized(value)
    prefix = ROOT.as_posix() + "/"
    return normalized[len(prefix):] if normalized.startswith(prefix) else normalized


def _validate_x509_custom(sections, origin: str, errors: list[str]) -> None:
    """One pinned source adaptation, exact command, inputs and binary output."""
    output = BINARY_ROOT + "/src/src/generated/mbedtls-cold/x509.c"
    script = "cmake/Vendor/mbedtls-cold/AdaptX509.cmake"
    if set(sections) != {"OUTPUT", "COMMAND", "DEPENDS", "COMMENT"}:
        errors.append(f"{origin}: unapproved cold X.509 custom-command sections")
    if sections.get("OUTPUT") != [[output]]:
        errors.append(f"{origin}: unapproved cold X.509 output")
    expected = [["${CMAKE_COMMAND}",
                 "-DSOURCE=extra/mbedtls-cold/library/x509.c",
                 "-DPIN_MANIFEST=cmake/Vendor/mbedtls-cold/UPSTREAM.sha256",
                 "-DBUILD_ROOT=" + BINARY_ROOT,
                 "-DOUTPUT=" + output, "-P", script]]
    commands = []
    for command in sections.get("COMMAND", []):
        normalized = []
        for value in command:
            if value.startswith(("-DSOURCE=", "-DPIN_MANIFEST=")):
                prefix, path = value.split("=", 1)
                normalized.append(prefix + "=" + _x509_repo_path(path))
            else:
                normalized.append(_x509_repo_path(value))
        commands.append(normalized)
    if commands != expected:
        errors.append(f"{origin}: unapproved cold X.509 generator command")
    dependencies = sections.get("DEPENDS", [])
    expected_dependencies = [["extra/mbedtls-cold/library/x509.c", script,
                              "cmake/Vendor/mbedtls-cold/UPSTREAM.sha256",
                              "cmake/Vendor/mbedtls-cold/UPSTREAM.md"]]
    if [[_x509_repo_path(value) for value in group] for group in dependencies] != expected_dependencies:
        errors.append(f"{origin}: unapproved cold X.509 generator dependencies")
    if sections.get("COMMENT") != [["Adapt pinned cold X.509 INNLE/OGRN NumericString parsing"]]:
        errors.append(f"{origin}: unapproved cold X.509 generator comment")
    if not reviewed_file_identity(script):
        errors.append(f"{origin}: cold X.509 generator identity changed")
    if not reviewed_file_identity("extra/mbedtls-cold/library/x509.c"):
        errors.append(f"{origin}: cold X.509 source identity changed")


def _validate_x509_attachment(instances, errors: list[str]) -> None:
    declarations = [instance for instance in instances
                    if instance.body.command.name == "add_library" and
                    instance.token_groups and instance.token_groups[0] ==
                    ("cxet_tls_certificates",)]
    if not declarations:
        return
    expected = ["cxet_tls_certificates", "STATIC", "EXCLUDE_FROM_ALL",
                BINARY_ROOT + "/src/src/generated/mbedtls-cold/x509.c",
                "extra/mbedtls-cold/library/x509_crt.c"]
    if (len(declarations) != 1 or
            not _context(declarations[0], Path("src/src")) or
            declarations[0].body.relative != "src/src/CMakeLists.txt" or
            [_x509_repo_path(value) for value in _flatten(declarations[0])] != expected):
        errors.append("src/src/CMakeLists.txt: cold X.509 source attachment changed")
    producers = [instance for instance in instances
                 if instance.body.relative == "src/src/CMakeLists.txt" and
                 instance.body.command.name == "add_custom_command" and
                 cmake_list_words(instance.body.command.body)[:2] == ["OUTPUT", "${_cxet_x509_source}"]]
    if len(producers) != 1:
        errors.append("src/src/CMakeLists.txt: expected one cold X.509 producer")


def _validate_custom_command(instance, tokenize, errors) -> None:
    expected = CUSTOM_COMMAND_CONTEXTS.get(instance.body.relative)
    if expected is None or not _context(instance, expected):
        errors.append(f"{_origin(instance)}: unapproved active custom command")
        return
    tokens = _flatten(instance)
    if not tokens or tokens[0] != "OUTPUT":
        errors.append(f"{_origin(instance)}: custom TARGET signature is forbidden")
        return
    sections = _custom_sections(instance, tokenize, errors)
    if sections is None:
        return
    if instance.body.relative == "src/src/CMakeLists.txt":
        if cmake_list_words(instance.body.command.body)[:3] == [
                "OUTPUT", "${CXET_LIBURING_ARCHIVE}", "${CXET_LIBURING_HEADER}"]:
            _validate_liburing_custom(instance, errors)
        else:
            _validate_x509_custom(sections, _origin(instance), errors)
    elif instance.body.relative == "apps/trading-core/CMakeLists.txt":
        _validate_trading_custom(sections, _origin(instance), errors)
    elif instance.body.relative == "apps/vetron/wasm/CMakeLists.txt":
        _validate_wasm_custom(sections, _origin(instance), errors, instance)
    else:
        errors.append(f"{_origin(instance)}: unapproved active custom command")


def _split_top_level(value: str, delimiter: str) -> list[str]:
    result: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value):
        if value.startswith("$<", index):
            depth += 1
            index += 2
            continue
        if value[index] == ">" and depth:
            depth -= 1
        elif value[index] == delimiter and depth == 0:
            result.append(value[start:index])
            start = index + 1
        index += 1
    result.append(value[start:])
    return result


def _genex_parts(value: str) -> tuple[str, str] | None:
    if not value.startswith("$<") or not value.endswith(">"):
        return None
    inner = value[2:-1]
    parts = _split_top_level(inner, ":")
    if len(parts) < 2:
        return None
    return parts[0], ":".join(parts[1:])


def _safe_condition(value: str) -> bool:
    parts = _genex_parts(value)
    if parts is None:
        return False
    operator, payload = parts
    upper = operator.upper()
    if upper == "CONFIG":
        return bool(re.fullmatch(r"[A-Za-z0-9_,;-]+", payload))
    if upper == "BOOL":
        return (
            re.fullmatch(r"[A-Za-z0-9_.+/-]+", payload) is not None or
            re.fullmatch(
                r"(?:\$\{[A-Z][A-Z0-9_]*\}|"
                r"\$CACHE\{[A-Z][A-Z0-9_]*\})",
                payload,
            ) is not None
        )
    if upper == "NOT":
        return _safe_condition(payload)
    if upper in {"AND", "OR"}:
        values = _split_top_level(payload, ",")
        return bool(values) and all(_safe_condition(item) for item in values)
    return False


def _safe_literal_option(value: str) -> bool:
    """Accept only options reviewed in the current bounded family graph."""
    return value in _REVIEWED_LITERAL_COMPILE_OPTIONS


def safe_compile_option(value: str) -> bool:
    if "\\" in value:
        return False
    if "$<" not in value:
        return _safe_literal_option(value)
    parts = _genex_parts(value)
    if parts is None:
        return False
    condition, payload = parts
    if not condition.startswith("$<") or not _safe_condition(condition):
        return False
    options = _split_top_level(payload, ";")
    return bool(options) and all(_safe_literal_option(item) for item in options)


def _validate_compile_option_safety_microcases(errors: list[str]) -> None:
    """Keep the exact compile-option namespace closed under refactors."""
    for option in sorted(_REVIEWED_LITERAL_COMPILE_OPTIONS):
        if not safe_compile_option(option):
            errors.append(
                "compile-option safety self-check rejected reviewed option "
                f"{option}")
    rejected = (
        "-fprofile-generate=${CXET_PGO_DIR}",
        "-fprofile-use=$CACHE{CXET_PGO_DIR}",
        "-DCXET_OPTION_SELF_CHECK=1",
        "-UCXET_OPTION_SELF_CHECK",
        "--define-macro=CXET_OPTION_SELF_CHECK=1",
        "--define-macro",
        "--undefine-macro=CXET_OPTION_SELF_CHECK",
        "--undefine-macro",
        "--include=/tmp/cxet-option-self-check.hpp",
        "--include",
        "--imacros=/tmp/cxet-option-self-check.hpp",
        "--imacros",
        "-trigraphs",
        "-undef",
        "-fno-access-control",
        "-cc1",
        "-cc1as",
        "-chroot=/tmp/cxet-option-self-check",
        "-working-directory=/tmp/cxet-option-self-check",
        "-cxx-isystem/tmp/cxet-option-self-check",
        "-stdlib++-isystem/tmp/cxet-option-self-check",
        "-vfsoverlay=/tmp/cxet-option-self-check.yaml",
        "-fembed-offload-object=/tmp/cxet-option-self-check.o",
        "-F/tmp/cxet-option-self-check",
        "-fmodules",
        "-fmodules-ts",
        "-fmodule-map-file=/tmp/cxet-option-self-check.modulemap",
        "-fmodule-mapper=/tmp/cxet-option-self-check.mapper",
        "-fcxx-modules",
        "-fimplicit-modules",
        "-xassembler",
        "-Wa,-I/tmp/cxet-option-self-check",
        "-Xassembler",
        "-nostdinc",
        "-nostdinc++",
        "-nostdlibinc",
        "-nobuiltininc",
        "-stdlib=libc++",
        "-target=x86_64-unknown-linux-gnu",
        "-E",
        "-S",
        "-c",
        "-o/tmp/cxet-option-self-check.o",
        "-fsyntax-only",
        "-fdriver-only",
        "-fintegrated-cc1",
        "-fno-integrated-cc1",
        "-fintegrated-as",
        "-fno-integrated-as",
        "-MD",
        "-MF/tmp/cxet-option-self-check.d",
        "-MJ/tmp/cxet-option-self-check.json",
        "-save-temps=obj",
        "-ftime-trace=/tmp/cxet-option-self-check.json",
        "-Wl,@/tmp/cxet-option-self-check.rsp",
        "-fprofile-generate",
        "-fprofile-generate=/tmp/cxet-option-self-check",
        "-fprofile-use=/tmp/cxet-option-self-check.profdata",
        "-fprofile-instr-use=/tmp/cxet-option-self-check.profdata",
        "-fauto-profile=/tmp/cxet-option-self-check.afdo",
        "-fmemory-profile-use=/tmp/cxet-option-self-check.memprof",
        "-frandomize-layout-seed-file=/tmp/cxet-option-self-check.seed",
        "$<$<CONFIG:Release>:--define-macro=CXET_OPTION_SELF_CHECK=1>",
        "$<$<CONFIG:Release>:--include=/tmp/cxet-option-self-check.hpp>",
        r"\-DCXET_OPTION_SELF_CHECK=1",
        r"$\<$<CONFIG:Release>:-DCXET_OPTION_SELF_CHECK=1>",
    )
    for option in rejected:
        if safe_compile_option(option):
            errors.append(
                "compile-option safety self-check accepted ownership "
                f"channel {option}")
    if not safe_compile_option("$<$<CONFIG:Release>:-O3>"):
        errors.append(
            "compile-option safety self-check rejected reviewed -O3 form")


def _compile_options(instance, tokenize, errors, *, snapshots=None) -> None:
    command = instance.body.command.name
    warning_options = ["-Wall", "-Wextra", "-Wpedantic", "-Wno-unused-parameter", "-Wno-unused-variable"]
    recorder_recipes = {
        ("apps/hft-recorder/CMakeLists.txt", 43, "add_compile_options"): warning_options,
        ("apps/hft-recorder/src/Runtime/CMakeLists.txt", 37, "target_compile_options"):
            ["hftrec_json_capture", "PRIVATE", *warning_options],
    }
    expected_warnings = recorder_recipes.get((instance.body.relative, instance.body.command.line, command))
    if (expected_warnings is not None and instance.body == instance.evaluation and
            not instance.body.structural_context and
            instance.body.source_base == instance.body.binary_base == Path(instance.body.relative).parent and
            cmake_list_words(instance.body.command.body) == expected_warnings and
            _flatten(instance) == expected_warnings):
        return
    groups = [list(group) for group in instance.token_groups]
    if command == "add_compile_options":
        options = _flatten(instance)
    elif command == "target_compile_options":
        if not groups or len(groups[0]) != 1:
            errors.append(f"{_origin(instance)}: ambiguous compile-option target")
            return
        options = [
            value for group in groups[1:] for value in group
            if value not in {"BEFORE", "PRIVATE", "PUBLIC", "INTERFACE"}
        ]
        from Family.Targets.CxetFamilyBuildPolicy import exact_offline_options, OFFLINE_COMPILE_OPTION_RECIPES
        if exact_offline_options(instance, command, OFFLINE_COMPILE_OPTION_RECIPES):
            return
        from Family.Targets.CxetFamilyBuildPolicy import PARSER_OFFLINE_COMPILE_OPTION_RECIPES
        if exact_offline_options(instance, command, PARSER_OFFLINE_COMPILE_OPTION_RECIPES,
                                 owner="hft-parser"):
            return
        from Family.Targets.CxetFamilyBuildPolicy import benchmark_instance_context
        if (groups[0][0] in {"trader-bench-vstack", "trader-bench-vstack_traced"} and
                benchmark_instance_context(instance, groups[0][0]) and
                _flatten(instance) == [groups[0][0], "PRIVATE", "-fno-access-control"]):
            return
    else:
        raw = tokenize(instance.body.command.body)
        try:
            properties = next(
                index for index, token in enumerate(raw)
                if token == "PROPERTIES")
        except StopIteration:
            errors.append(f"{_origin(instance)}: source properties miss PROPERTIES")
            return
        if (instance.body.relative == "src/src/CMakeLists.txt" and
                _context(instance, Path("src/src")) and raw == [
                    "Core/src/Crypto/Rsa.cpp", "PROPERTIES", "COMPILE_DEFINITIONS",
                    r'MBEDTLS_CONFIG_FILE=\"RsaMbedConfig.h\"']):
            return
        native_simd = (instance.body.relative == "src/src/CMakeLists.txt" and
            _context(instance, Path("src/src")) and raw == [
                "${_cxet_hacl}/Hacl_AEAD_Chacha20Poly1305_Simd128.c",
                "${_cxet_hacl}/Hacl_Chacha20_Vec128.c",
                "${_cxet_hacl}/Hacl_MAC_Poly1305_Simd128.c",
                "PROPERTIES", "COMPILE_OPTIONS", "-msse4.2"])
        if properties + 3 != len(raw) or raw[properties + 1] != "COMPILE_OPTIONS":
            errors.append(
                f"{_origin(instance)}: only one COMPILE_OPTIONS source "
                "property is approved")
            return
        sources = [
            value for group in groups[:properties] for value in group]
        core_form = (
            instance.body.relative == "src/src/CMakeLists.txt" and
            _context(instance, Path("src/src")) and
            raw == [
                "Core/src/Api/History/Candles/CandleHistoryCatalog.cpp",
                "Core/src/Api/History/Trades/HistoricalTradesPage.cpp", "PROPERTIES",
                "COMPILE_OPTIONS",
                "$<$<OR:$<CONFIG:Release>,$<BOOL:${CXET_SAFETY_BUILD}>>:"
                "-Wframe-larger-than=131072>",
            ] and
            sources == [
                "Core/src/Api/History/Candles/CandleHistoryCatalog.cpp",
                "Core/src/Api/History/Trades/HistoricalTradesPage.cpp"])
        if not core_form and not native_simd:
            errors.append(
                f"{_origin(instance)}: unapproved source-property "
                "owner/context form")
        if native_simd:
            # This option belongs only to the three reviewed HACL SIMD
            # translation units; it is not a general option capability.
            expected_sources = [str(ROOT / "extra/hacl-star/dist/gcc-compatible" / name)
                for name in ("Hacl_AEAD_Chacha20Poly1305_Simd128.c",
                             "Hacl_Chacha20_Vec128.c", "Hacl_MAC_Poly1305_Simd128.c")]
            if [_normalized(source) for source in sources] != expected_sources:
                errors.append(f"{_origin(instance)}: native SIMD source binding changed")
            return
        for source in sources:
            if any(marker in source for marker in _CARRIER_MARKERS):
                errors.append(
                    f"{_origin(instance)}: unresolved source-property carrier "
                    f"{source}")
        options = list(groups[properties + 2])
    if (command == "target_compile_options" and
            instance.body.relative == "src/src/CMakeLists.txt" and
            _context(instance, Path("src/src")) and
            groups[0][0] in {
                "cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import",
                "cxet_tls_certificates", "cxet_native_tls"} and
            cmake_list_words(instance.body.command.body) == [
                "${_tls_target}", "PRIVATE",
                "$<$<CONFIG:Release>:${_CXET_RELEASE_OPTIMIZATION}>",
                "$<$<AND:$<CONFIG:Release>,$<NOT:$<BOOL:${CXET_PORTABLE_BUILD}>>>:-march=native>",
                "$<$<COMPILE_LANGUAGE:C,CXX>:-Wframe-larger-than=32768;-Werror=frame-larger-than>",
                "$<$<COMPILE_LANGUAGE:CXX>:-fno-exceptions;-fno-rtti>",
                "$<$<AND:$<CONFIG:Release>,$<BOOL:${CXET_LTO}>>:-flto>"]):
        from CMake.Syntax.CmakeFamilyContext import exact_context, first_if, first_body
        relative = 'src/src/CMakeLists.txt'
        context = (first_if(relative, 234, ('NOT', 'TARGET', 'cxet_crypto')),
                   first_body('foreach', relative, 362,
                       ('_tls_target', 'cxet_crypto', 'cxet_crypto_rsa', 'cxet_crypto_import',
                        'cxet_tls_certificates', 'cxet_native_tls')))
        state = snapshots.values.get(instance.evaluation.ordinal, {}) if snapshots is not None else {}
        profile = state.get('CXET_TOOLCHAIN_PROFILE', ('pinned',))
        optimization = '-O1' if profile == ('system-diagnostic',) else '-O3' if profile == ('pinned',) else None
        if (optimization is not None and
                state.get('_CXET_RELEASE_OPTIMIZATION') == (optimization,) and
                groups[2] == ['$<$<CONFIG:Release>:' + optimization + '>'] and
                exact_context(instance.body.structural_context, context) and
                exact_context(instance.evaluation.structural_context, context)):
            return
        errors.append(f'{_origin(instance)}: native crypto optimization escaped its exact profile/scalar binding')
        return
    bad = [option for option in options if not safe_compile_option(option)]
    if bad:
        errors.append(
            f"{_origin(instance)}: ownership-capable or opaque compile "
            f"options {bad}")


def validate_command_policies(
    instances, tokenize, errors: list[str], directory_targets=None,
    require_registry: bool = True, *, active_origins=None, snapshots=None,
) -> None:
    """Validate every active custom-build and compile-option command."""
    _validate_compile_option_safety_microcases(errors)
    _validate_strategy_producer_microcases(errors)
    for instance in instances:
        command = instance.body.command.name
        if command in {
                "set_property", "set_source_files_properties",
                "set_target_properties", "set_tests_properties"}:
            validate_property_command(instance, errors)
        if command == "add_custom_command":
            _validate_custom_command(instance, tokenize, errors)
        elif command == "add_custom_target":
            _validate_custom_target(instance, tokenize, errors)
        elif command in {
                "add_compile_options", "target_compile_options",
                "set_source_files_properties"}:
            _compile_options(instance, tokenize, errors, snapshots=snapshots)
    _custom_target_dependencies(
        instances, directory_targets, errors, require_registry,
        active_origins=active_origins, snapshots=snapshots)
    origins = (set(active_origins) if active_origins is not None else
               {instance.body.relative for instance in instances})
    if "src/src/CMakeLists.txt" in origins:
        _validate_x509_attachment(instances, errors)
    if require_registry and "apps/trading-core/CMakeLists.txt" in origins:
        _validate_registry_attachment(instances, errors)
