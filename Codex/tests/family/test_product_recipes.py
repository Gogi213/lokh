"""Product recipes regressions."""
from tools.Codex.tests.Support.family import (
    ActivationFixture,
    CUSTOM_TARGETS,
    CurrentRecipeFixture,
    HEADER_OWNER_ROOTS,
    IncludeInputs,
    PRODUCTION_TARGETS,
    Path,
    ROOT,
    SimpleNamespace,
    StrategyFixture,
    _include_value,
    _insert_before_configure_argv,
    _ownership_checker_for_harness,
    approved_external_angle_include,
    ast,
    cmake_list_words,
    compiler_visible_header_inventory,
    compose_active_commands,
    exported_header_targets,
    function_model,
    instantiated_commands,
    lower_offline_registrations,
    native_include_context,
    offline_registration_inventory,
    owner_activation,
    parse_commands,
    patch,
    registry_outputs,
    source_cases,
    source_profile_roots,
    surface,
    tempfile,
    typed_generated_source,
    unittest,
    validate_offline_helper,
    validate_registration_predicate,
    variable_snapshots,
    verification_include_allowed,
)

class ProductRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_backtest_replay_argument_fold_rejects_foreign_value_and_context(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        from CMake.Policy.CmakeFamilyLoopPolicy import reviewed_replay_argument_fold_member
        from CMake.Flow.CmakeFamilyMutations import apply_list_command
        relative = "apps/hft-backtest/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        producer = next(ActiveCommand(relative, relative, Path("apps/hft-backtest"), Path("apps/hft-backtest"),
            (relative,), command, index, context) for index, (command, context) in enumerate(zip(commands, contexts))
            if command.name == "list" and cmake_list_words(command.body)[:2] ==
               ["APPEND", "HFT_BACKTEST_REQUIRED_STRATEGY_ARGS"])
        self.assertTrue(reviewed_replay_argument_fold_member(producer))
        self.assertFalse(reviewed_replay_argument_fold_member(replace(producer, structural_context=())))
        self.assertFalse(reviewed_replay_argument_fold_member(replace(producer, source_base=Path("apps/trader"))))
        errors = []
        state = {"HFT_BACKTEST_REQUIRED_STRATEGY_ARGS": ()}
        apply_list_command(cmake_list_words(producer.command.body), state,
            lambda raw: ["foreign"] if raw == ["${required_strategy}"] else raw,
            errors, relative + ":71")
        self.assertTrue(errors)

    def test_full_family_cold_search_cache_output_and_guard_recipes_stay_closed(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyWriters import apply_output_writer
        from CMake.Policy.CmakeFamilyCachePolicy import approved_direct_cache_set, approved_direct_option
        from CMake.Policy.CmakeFamilySetPolicy import VariableSignature
        from CMake.Policy.CmakeFamilyEffectPolicy import approved_effect_set
        from CMake.Syntax.CmakeFamilyDialect import _COMPRESSOR_SEARCHES
        from CMake.Flow.CmakeFamilyFlow import reviewed_evidence_condition, evaluate_condition, Truth
        for line, (command, variable, item, _guard, _condition) in _COMPRESSOR_SEARCHES.items():
            for origin, search, accepted in ((f"apps/hft-compressor/CMakeLists.txt:{line}", item, True),
                                             (f"apps/trader/CMakeLists.txt:{line}", item, False),
                                             (f"apps/hft-compressor/CMakeLists.txt:{line}", "foreign", False)):
                state, errors = {}, []
                apply_output_writer(command, [variable, search], ROOT, ROOT / "apps/hft-compressor",
                    state, lambda raw: raw, errors, origin)
                self.assertEqual(not errors, accepted, errors)
                self.assertEqual(state[variable], ("${" + variable + "}",))
        signature = VariableSignature("VETRON_EMXX_EXECUTABLE", ("",), "FILEPATH")
        self.assertTrue(approved_direct_cache_set("apps/vetron/wasm/CMakeLists.txt", signature))
        for changed in (replace(signature, force=True), replace(signature, values=("/tmp/em++",)),
                        replace(signature, cache_type="PATH")):
            self.assertFalse(approved_direct_cache_set("apps/vetron/wasm/CMakeLists.txt", changed))
        default = ["HFT_COMPRESSOR_BUILD_CLI", "Build hft-compressor CLI", "${_HFT_COMPRESSOR_BUILD_TOOLS_DEFAULT}"]
        self.assertTrue(approved_direct_option("apps/hft-compressor/CMakeLists.txt", default[0], default))
        self.assertFalse(approved_direct_option("apps/hft-compressor/CMakeLists.txt", default[0], [*default[:2], "ON"]))
        for variable, suffix in (("CMAKE_RUNTIME_OUTPUT_DIRECTORY", "bin"),
                                 ("CMAKE_ARCHIVE_OUTPUT_DIRECTORY", "lib"),
                                 ("CMAKE_LIBRARY_OUTPUT_DIRECTORY", "lib")):
            raw = [variable, "${CMAKE_BINARY_DIR}/" + suffix]
            self.assertTrue(approved_effect_set("apps/hft-recorder/CMakeLists.txt", variable, raw,
                ["__CXET_CMAKE_BINARY__/" + suffix]))
            self.assertFalse(approved_effect_set("apps/hft-recorder/CMakeLists.txt", variable, raw, ["/tmp"]))
            self.assertFalse(approved_effect_set("apps/trader/CMakeLists.txt", variable, raw,
                ["__CXET_CMAKE_BINARY__/" + suffix]))
        guards = (("NOT", "EXISTS", "${_hft_compressor_toolchain}"),
                  ("VETRON_EMXX_EXECUTABLE", "AND", "NOT", "IS_ABSOLUTE", "${VETRON_EMXX_EXECUTABLE}"),
                  ("VETRON_EMXX_EXECUTABLE", "AND", "EXISTS", "${VETRON_EMXX_EXECUTABLE}"))
        for guard in guards:
            self.assertTrue(reviewed_evidence_condition(guard))
            self.assertIs(evaluate_condition(guard, {}, lambda raw, preserve: raw), Truth.UNKNOWN)
        self.assertFalse(reviewed_evidence_condition(("NOT", "EXISTS", "${foreign_toolchain}")))

    def test_trader_default_product_rejects_utilities_and_requires_selected_history_helper(self):
        from CMake.Policy.CmakeFamilyCommandPolicy import _custom_target_dependencies
        from CMake.Flow.CmakeFamilyFlow import InstantiatedCommand
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        relative = "apps/trader/CMakeLists.txt"
        for selection, history, dependencies, accepted in (
                (("OFF",), ("ON",), ("traderd",), True),
                (("ON",), ("ON",), ("traderd", "hft-finam-metadata-store"), True),
                (("ON",), ("ON",), ("traderd",), False),
                (("OFF",), ("ON",), ("traderd", "hft-finam-metadata-store"), False),
                (("OFF",), ("ON",), ("traderd", "trader-alertd"), False),
                (("OFF",), ("ON",), ("traderd", "trader-market-observed"), False),
                (("OFF",), ("ON",), ("traderd", "trader-control"), False),
                (("OFF",), ("ON",), ("traderd", "traderd"), False),
                (("ON",), ("OFF",), ("traderd",), True),
                (("OFF",), ("OFF",), ("traderd",), True),
                (("ON",), ("OFF",), ("traderd", "hft-finam-metadata-store"), False),
                (("OFF",), ("OFF",), ("traderd", "hft-finam-metadata-store"), False),
                (("1",), ("1",), ("traderd", "hft-finam-metadata-store"), True),
                (("1",), ("0",), ("traderd",), True),
                (("ON",), None, ("traderd",), False),
                (("OFF",), None, ("traderd",), False),
                (None, ("ON",), ("traderd",), False)):
            instances = []
            commands = [
                ("add_custom_target", ("trader-product", "DEPENDS", *dependencies)),
                *[("add_executable", (target, "Main.cpp")) for target in set(dependencies)],
            ]
            for ordinal, (name, values) in enumerate(commands):
                active = ActiveCommand("fixture", relative, Path("apps/trader"), Path("apps/trader"),
                    (relative,), Command(name, " ".join(values), ordinal + 1), ordinal)
                instances.append(InstantiatedCommand(active, active,
                    tuple((value,) for value in values), ordinal, ((),)))
            snapshots = SimpleNamespace(values={0: {"CXET_EXCHANGE_FINAM": selection,
                                                 "HFT_PARSER_CANDLE_HISTORY": history}},
                                        live_eof_paths={"fixture": ((),)})
            errors = []
            _custom_target_dependencies(instances, {}, errors, False, snapshots=snapshots)
            self.assertEqual(not errors, accepted, (selection, history, dependencies, errors))


if __name__ == '__main__':
    unittest.main()
