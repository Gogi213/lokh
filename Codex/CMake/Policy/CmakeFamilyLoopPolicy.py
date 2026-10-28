"""Fail-closed policy for state writers nested in bounded foreach loops."""

from __future__ import annotations

from Family.Sources.CxetFamilySourcePolicy import NATIVE_CRYPTO_IMPORT_MODULES

from CMake.Policy.CmakeFamilyStrategyPolicy import (
    strategy_folder, canonical_strategy_names, proven_strategy_headers,
    validate_registration_predicate, reviewed_strategy_fold_member,
)

from pathlib import Path

from CMake.Syntax.CmakeFamilyContext import (
    exact_context,
    first_body,
    first_if,
)
from CMake.Syntax.CmakeFamilyLexer import cmake_list_words


_STATE_WRITERS = frozenset({
    "aux_source_directory", "cmake_path", "file", "get_cmake_property",
    "get_directory_property", "get_filename_component", "get_property",
    "get_source_file_property", "get_target_property", "get_test_property",
    "list", "math", "separate_arguments", "set", "site_name", "string",
    "unset",
})

# Each entry is additionally protected by its owning positive policy (strategy,
# safety or HFT dynamic-test contract).  This list is the
# interpreter boundary: a new state writer inside a loop is not approximated.
_REVIEWED_WRITERS = frozenset({
    ("src/tests/CMakeLists.txt", 66, "string"),
    ("src/tests/CMakeLists.txt", 68, "list"),
    ("src/tests/CMakeLists.txt", 70, "list"),
    ("src/tests/CMakeLists.txt", 72, "list"),
    ("apps/trader/cmake/AnalyticsTests.cmake", 5, "string"),
    ("apps/trader/cmake/AnalyticsTests.cmake", 6, "set"),
    *{
        ("apps/trader/cmake/AnalyticsTests.cmake", line, "set")
        for line in range(8, 27, 2)
    },
})


def validate_loop_writer_boundary(commands, errors: list[str]) -> None:
    """Reject unreviewed state mutation in direct and callable loop bodies."""
    strategy_commands = [active for active in commands
                         if active.relative == "apps/trading-core/CMakeLists.txt"]
    strategy_members = set()
    if strategy_commands:
        # The parsed sequence, discovery producer and all lexical contexts must
        # agree before any member receives scalar-fold authority. Line shifts
        # alone confer no authority and do not revoke the exact recipe.
        proven = validate_registration_predicate(
            [active.command for active in strategy_commands], cmake_list_words, errors)
        proven_ids = {id(command) for command in proven}
        strategy_members = {id(active) for active in strategy_commands
                            if id(active.command) in proven_ids and reviewed_strategy_fold_member(active)}
    for active in commands:
        if (active.command.name not in _STATE_WRITERS or
                not any(frame.kind == "foreach"
                        for frame in active.structural_context)):
            continue
        identity = (
            active.relative, active.command.line, active.command.name)
        if _native_crypto_fold_writer(active):
            continue
        if reviewed_replay_argument_fold_member(active):
            continue
        if id(active) in strategy_members:
            continue
        if identity not in _REVIEWED_WRITERS:
            errors.append(
                f"{active.relative}:{active.command.line}: state writer "
                f"{active.command.name}() in foreach is outside reviewed "
                "ordered folds")


def reviewed_replay_argument_fold_member(active) -> bool:
    relative = "apps/hft-backtest/CMakeLists.txt"
    return (active.relative == relative and active.source_base == Path("apps/hft-backtest") and
        active.binary_base == active.source_base and active.command.name == "list" and
        tuple(cmake_list_words(active.command.body)) == (
            "APPEND", "HFT_BACKTEST_REQUIRED_STRATEGY_ARGS", "--required-strategy", "${required_strategy}") and
        exact_context(active.structural_context, (first_body("foreach", relative, 70,
            ("required_strategy", "IN", "LISTS", "HFT_BACKTEST_REQUIRED_STRATEGY_NAMES")),)))


def validate_reviewed_source_folds(commands, errors: list[str]) -> None:
    """Retain the exact reviewed scalar folds used by the graph model."""
    _validate_native_crypto_source_folds(commands, errors)
    _validate_trader_analytics_test_fold(commands, errors)


def _if_arm(relative, line, opener, kind, tokens, prior):
    return ("if", relative, line, opener, kind, tokens, prior)




def _validate_trader_analytics_test_fold(commands, errors: list[str]) -> None:
    """Pin the bounded Trader analytics target/source registration fold."""
    relative = "apps/trader/cmake/AnalyticsTests.cmake"
    if not any(active.relative == relative for active in commands):
        return
    names = (
        "relative_difference_volatility",
        "spread_volatility",
        "synthetic_bbo_spread_event",
        "synthetic_delivery_basis",
        "delivery_basis_model",
        "current_snapshot",
        "current_reference",
        "config_trust",
        "market_processor_health",
        "funding_current",
    )
    sources = (
        "RelativeDifferenceVolatilityContractTests.cpp",
        "SpreadVolatilityContractTests.cpp",
        "SyntheticBboSpreadEventContractTests.cpp",
        "SyntheticDeliveryBasisContractTests.cpp",
        "DeliveryBasisModelContractTests.cpp",
        "CurrentSnapshotContractTests.cpp",
        "CurrentReferenceContractTests.cpp",
        "ConfigTrustContractTests.cpp",
        "MarketProcessorHealthContractTests.cpp",
        "FundingCurrentContractTests.cpp",
    )
    loop_tokens = ("analytics_test", "IN", "ITEMS", *names)
    loop = first_body("foreach", relative, 2, loop_tokens)
    expected = {
        (2, "foreach"): (loop_tokens, ()),
        (5, "string"): (
            ("REPLACE", "_", "-", "analytics_target", "${analytics_test}"),
            (loop,)),
        (6, "set"): (
            ("analytics_target", "trader-${analytics_target}-contract-tests"),
            (loop,)),
        (28, "add_executable"): (
            ("${analytics_target}", "tests/analytics/${analytics_source}"),
            (loop,)),
        (29, "target_include_directories"): (
            ("${analytics_target}", "PRIVATE",
             "${CMAKE_CURRENT_SOURCE_DIR}/src/market_observe_runtime/src"),
            (loop,)),
        (31, "target_link_libraries"): (
            ("${analytics_target}", "PRIVATE", "trader::public_analytics"),
            (loop,)),
        (32, "trader_private_defaults"): (("${analytics_target}",), (loop,)),
        (33, "add_test"): (
            ("NAME", "${analytics_target}", "COMMAND", "${analytics_target}"),
            (loop,)),
        (34, "set_tests_properties"): (
            ("${analytics_target}", "PROPERTIES", "LABELS",
             "trader;contract;cxet-family;trader-autonomous-acceptance"),
            (loop,)),
        (35, "endforeach"): ((), (loop,)),
    }
    prior: tuple[tuple[str, tuple[str, ...]], ...] = ()
    opener = ("analytics_test", "STREQUAL", names[0])
    for index, (name, source) in enumerate(zip(names, sources)):
        tokens = ("analytics_test", "STREQUAL", name)
        kind = "if" if index == 0 else "elseif"
        arm = _if_arm(relative, 7, opener, kind, tokens, prior)
        expected[(8 + index * 2, "set")] = (
            ("analytics_source", source), (loop, arm))
        prior = (*prior, (kind, tokens))

    for identity, (tokens, context) in expected.items():
        found = [
            active for active in commands
            if active.relative == relative and
            (active.command.line, active.command.name) == identity]
        if (len(found) != 1 or
                tuple(cmake_list_words(found[0].command.body)) != tokens or
                not exact_context(found[0].structural_context, context)):
            errors.append(
                f"{relative}:{identity[0]}: Trader analytics test fold "
                "changed")


def reviewed_scalar_iteration_locals(body, local):
    """Return the exact scalar state for a syntactically proven current fold."""
    if (body.relative == "src/tests/CMakeLists.txt" and
            body.command.line in {76, 77}):
        return {
            **local,
            "_stress_san_flags": (
                "-fsanitize=thread", "-fsanitize=undefined"),
        }
    if reviewed_strategy_fold_member(body):
        headers = local.get("strategy_header", ())
        root = (
            Path(__file__).resolve().parents[4] /
            "apps/trading-core/src/Strategy/include/strategy")
        candidates = {
            (root / "trader" / strategy_folder(name) / "Strategy.hpp").as_posix():
                (name, root / "trader" / strategy_folder(name))
            for name in canonical_strategy_names()
        }
        candidate = (candidates.get(headers[0]) if len(headers) == 1 and
                     headers[0] in proven_strategy_headers() else None)
        if candidate is None:
            return {
                **local,
                "strategy_dir": ("${strategy_dir}",),
                "strategy_name": ("${strategy_name}",),
                "strategy_folder": ("${strategy_folder}",),
                "strategy_header_text": ("${strategy_header_text}",),
                "strategy_descriptor_text": (
                    "${strategy_descriptor_text}",),
            }
        name, directory = candidate
        descriptor = directory / "Descriptor.hpp"
        try:
            from Family.Sources.CxetFamilyHeaderContract import unsymlinked_source_path
            workspace = Path(__file__).resolve().parents[4]
            if not unsymlinked_source_path(Path(headers[0]), workspace, directory=False):
                raise OSError("unreviewed strategy header ancestry")
            if (descriptor.exists() or descriptor.is_symlink()) and not unsymlinked_source_path(
                    descriptor, workspace, directory=False):
                raise OSError("unreviewed strategy descriptor ancestry")
            header_text = Path(headers[0]).read_text(encoding="utf-8")
            descriptor_text = (
                descriptor.read_text(encoding="utf-8")
                if descriptor.is_file() else None)
        except OSError:
            return {
                **local,
                "strategy_dir": (directory.as_posix(),),
                "strategy_name": (name,),
                "strategy_folder": (directory.name,),
                "strategy_header_text": ("${strategy_header_text}",),
                "strategy_descriptor_text": (
                    "${strategy_descriptor_text}",),
            }
        combined = (
            header_text if descriptor_text is None else
            header_text + "\n" + descriptor_text)
        result = {
            **local,
            "strategy_dir": (directory.as_posix(),),
            "strategy_name": (name,),
            "strategy_folder": (directory.name,),
            "strategy_header_text": (header_text,),
            "strategy_descriptor_text": (combined,),
        }
        if descriptor_text is not None:
            result["strategy_descriptor_header_text"] = (descriptor_text,)
        return result
    if (body.relative == "apps/trader/cmake/AnalyticsTests.cmake" and
            28 <= body.command.line <= 34):
        tests = local.get("analytics_test", ())
        mapping = {
            "relative_difference_volatility":
                "RelativeDifferenceVolatilityContractTests.cpp",
            "spread_volatility": "SpreadVolatilityContractTests.cpp",
            "synthetic_bbo_spread_event":
                "SyntheticBboSpreadEventContractTests.cpp",
            "synthetic_delivery_basis":
                "SyntheticDeliveryBasisContractTests.cpp",
            "delivery_basis_model": "DeliveryBasisModelContractTests.cpp",
            "current_snapshot": "CurrentSnapshotContractTests.cpp",
            "current_reference": "CurrentReferenceContractTests.cpp",
            "config_trust": "ConfigTrustContractTests.cpp",
            "market_processor_health":
                "MarketProcessorHealthContractTests.cpp",
            "funding_current": "FundingCurrentContractTests.cpp",
        }
        if len(tests) != 1 or tests[0] not in mapping:
            return {
                **local,
                "analytics_target": ("${analytics_target}",),
                "analytics_source": ("${analytics_source}",),
            }
        test = tests[0]
        return {
            **local,
            "analytics_target": (
                f"trader-{test.replace('_', '-')}-contract-tests",),
            "analytics_source": (mapping[test],),
        }
    return local




def _native_crypto_fold_writer(active) -> bool:
    if active.relative != "src/src/CMakeLists.txt" or active.command.name != "list":
        return False
    body = tuple(cmake_list_words(active.command.body))
    guard = first_if(active.relative, 234, ("NOT", "TARGET", "cxet_crypto"))
    for modules, sources, line in (("_cxet_mbed_crypto_modules", "_cxet_mbed_crypto_sources", 311),):
        loop = first_body("foreach", active.relative, line, ("_module", "IN", "LISTS", modules))
        if (body == ("APPEND", sources, "${_cxet_mbed}/library/${_module}.c") and
                exact_context(active.structural_context, (guard, loop))):
            return True
    return False


def _validate_native_crypto_source_folds(commands, errors: list[str]) -> None:
    relative = "src/src/CMakeLists.txt"
    if not any(active.relative == relative for active in commands):
        return
    guard = first_if(relative, 234, ("NOT", "TARGET", "cxet_crypto"))
    for name, values in (("_cxet_mbed_crypto_modules", NATIVE_CRYPTO_IMPORT_MODULES),):
        assignments = [active for active in commands if active.relative == relative and
            active.command.name == "set" and tuple(cmake_list_words(active.command.body))[:1] == (name,)]
        if (len(assignments) != 1 or
                tuple(cmake_list_words(assignments[0].command.body)) != (name, *values) or
                not exact_context(assignments[0].structural_context, (guard,))):
            errors.append(f"{relative}: exact native crypto module fold changed: {name}")
    if any(active.relative == relative and active.command.name == "set" and
           cmake_list_words(active.command.body)[:1] == ["_cxet_x509_modules"] for active in commands):
        errors.append(f"{relative}: obsolete direct X.509 source fold reintroduced")
