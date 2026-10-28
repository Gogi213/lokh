"""Owner activation regressions."""
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

class OwnerActivationTests(ActivationFixture, unittest.TestCase):
    def test_full_registration_inventory_includes_startup_and_capital(self):
        errors = []
        trader = offline_registration_inventory(ROOT, "trader", errors)
        core = offline_registration_inventory(ROOT, "trading-core", errors)
        self.assertEqual(errors, [])
        self.assertIn("offline.trader.finam.startup.oracle.unknown_fresh_id_resend", trader)
        self.assertEqual(trader.count("offline.trader.launcher-preparation"), 1)
        self.assertIn("offline.trading-core.capital.kernel", core)
        self.assertEqual(len(trader), len(set(trader)))
        self.assertEqual(len(core), len(set(core)))

    def test_reviewed_offline_guard_survives_lowering(self):
        relative = "src/tests/offline/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative,
            'if(CXET_SELECTION_ALL)\n'
            'cxet_add_offline_suite(x OWNER CXETCPP EXPECTED 50 SOURCES DecodeTransactions.cpp)\n'
            'endif()', errors)
        lowered = lower_offline_registrations(ROOT, relative, commands, errors)
        self.assertEqual(errors, [])
        self.assertEqual((lowered[0].name, lowered[-1].name), ("if", "endif"))

    def test_actual_profiles_select_current_roots(self):
        errors = []
        configurations = owner_activation(ROOT, errors)
        self.assertEqual(errors, [])
        roots, values = configurations["compile:hft-parser:essential:0:0:0"]
        self.assertIn("src/src/CMakeLists.txt", roots)
        self.assertIn("apps/hft-parser/CMakeLists.txt", roots)
        self.assertNotIn("src/tests/CMakeLists.txt", roots)
        self.assertNotIn("src/tests/Family/CMakeLists.txt", roots)
        self.assertFalse(any(root.startswith("apps/hft-trader/") for root in roots))
        self.assertFalse(any(offline_owner in roots for offline_owner in
            ("src/tests/offline/CMakeLists.txt", "apps/trader/tests/offline/CMakeLists.txt")))
        offline_roots, offline_values = configurations["offline:trader:release"]
        self.assertIn("apps/trader/tests/offline/CMakeLists.txt", offline_roots)
        self.assertEqual(offline_values["apps/trader/CMakeLists.txt"]["CXET_LOCAL_TESTS"], ("ON",))

    def test_parser_full_local_tests_keep_only_owner_roots_and_production_keeps_peers(self):
        errors = []
        configurations = owner_activation(ROOT, errors)
        self.assertEqual(errors, [])
        local = {"src/src/CMakeLists.txt", "apps/hft-parser/CMakeLists.txt",
                 "apps/hft-parser/tests/offline/CMakeLists.txt", "apps/hft-parser/benchmarks/CMakeLists.txt"}
        production = {"src/src/CMakeLists.txt", "apps/hft-parser/CMakeLists.txt",
            "apps/trading-core/CMakeLists.txt", "apps/hft-compressor/CMakeLists.txt",
            "apps/hft-recorder/src/Contracts/CMakeLists.txt", "apps/hft-backtest/CMakeLists.txt",
            "apps/trader/CMakeLists.txt", "apps/vetron/CMakeLists.txt", "apps/hft-recorder/CMakeLists.txt"}
        for name, (roots, values) in configurations.items():
            if not name.startswith("compile:hft-parser:"):
                continue
            selected = values["src/src/CMakeLists.txt"]
            with self.subTest(profile=name):
                if selected["CXET_LOCAL_TESTS"] == ("ON",):
                    self.assertEqual(set(roots), local)
                    self.assertEqual(selected["CXET_LOCAL_BENCHMARKS"], ("ON",))
                elif selected["CXET_FAMILY_PROFILE"] == ("full",):
                    self.assertEqual(set(roots), production)
        for tests in (0, 1):
            roots, _values = configurations[f"compile:vetron:full:0:0:{tests}"]
            self.assertIn("apps/vetron/CMakeLists.txt", roots)
            self.assertIn("apps/trader/CMakeLists.txt", roots)
        roots, values = configurations["compile:hft-recorder:full:0:0:0"]
        self.assertIn("apps/hft-recorder/CMakeLists.txt", roots)
        self.assertEqual(values["apps/hft-recorder/CMakeLists.txt"]["HFTREC_BUILD_APP_TARGETS"], ("ON",))

    def test_recorder_production_is_never_substituted_with_offline(self):
        errors = []
        configurations = owner_activation(ROOT, errors)
        self.assertEqual(errors, [])
        for family in ("essential", "full"):
            roots, values = configurations[f"compile:hft-recorder:{family}:0:0:0"]
            self.assertIn("apps/hft-recorder/CMakeLists.txt", roots)
            self.assertEqual(values["apps/hft-recorder/CMakeLists.txt"]["HFTREC_BUILD_APP_TARGETS"], ("ON",))
            self.assertEqual(values["apps/hft-recorder/CMakeLists.txt"]["HFTREC_BUILD_GUI"],
                             ("ON",) if family == "full" else ("OFF",))
        roots, values = configurations["offline:hft-recorder:release"]
        self.assertNotIn("apps/hft-recorder/CMakeLists.txt", roots)
        self.assertIn("apps/hft-recorder/src/Runtime/CMakeLists.txt", roots)
        self.assertEqual(values["apps/hft-recorder/src/Contracts/CMakeLists.txt"]["HFTREC_BUILD_GUI"], ("OFF",))

    def test_changed_helper_cannot_prove_lowered_edges(self):
        text = (ROOT / "cmake/CxetOfflineTests.cmake").read_text()
        errors = []
        self.assertTrue(validate_offline_helper(text, errors))
        changed = text.replace("COMMAND ${target} --case", "COMMAND foreign --case")
        self.assertNotEqual(changed, text)
        errors = []
        self.assertFalse(validate_offline_helper(changed, errors))
        self.assertTrue(errors)

    def test_startup_lowering_preserves_both_independent_native_fixture_catalogs(self):
        from Family.Profile.CxetFamilyActivation import startup_cases
        relative = "apps/trader/tests/startup/CMakeLists.txt"
        text = (ROOT / relative).read_text()
        errors = []
        lowered = lower_offline_registrations(ROOT, relative, parse_commands(relative, text, errors), errors)
        self.assertEqual(errors, [])
        declarations = [cmake_list_words(command.body)[0] for command in lowered
            if command.name in {"add_library", "add_executable"}]
        for target in ("trader_startup_fixture", "trader_startup_network",
                       "trader_tbank_startup_fixture", "trader_tbank_startup_network"):
            self.assertIn(target, declarations)
        for tbank, target in ((False, "trader_offline_finam_startup_process"),
                              (True, "trader_offline_tbank_startup_process")):
            cases = startup_cases(ROOT, tbank=tbank)
            registrations = [cmake_list_words(command.body) for command in lowered if command.name == "add_test"]
            self.assertEqual([values[-1] for values in registrations if values[3] == target],
                             [case["name"] for case in cases])

    def test_wrong_owner_and_unsupported_branch_fail_closed(self):
        relative = "src/tests/offline/CMakeLists.txt"
        for text in (
            "cxet_add_offline_suite(wrong OWNER trader EXPECTED 1 SOURCES DecodeTransactions.cpp)",
            "if(UNKNOWN)\ncxet_add_offline_suite(x OWNER CXETCPP EXPECTED 36 SOURCES DecodeTransactions.cpp)\nendif()",
        ):
            errors = []
            lower_offline_registrations(ROOT, relative, parse_commands(relative, text, errors), errors)
            self.assertTrue(errors)

    def test_ranking_cpp_producer_keeps_its_dependency_fact(self):
        relative = "apps/vetron/tests/offline/CMakeLists.txt"
        text = ("cxet_add_offline_suite(vetron_offline_ranking_evidence OWNER vetron "
                "EXPECTED 10 SOURCES GatewayAuthorityCases.cpp)\n"
                "add_dependencies(vetron_offline_ranking_evidence vetron-math-wasm)")
        errors = []
        lowered = lower_offline_registrations(ROOT, relative,
            parse_commands(relative, text, errors), errors)
        self.assertEqual(errors, [])
        self.assertTrue(any(command.name == "add_dependencies" for command in lowered))

    def test_ranking_script_dependency_must_be_unique(self):
        relative = "apps/vetron/tests/offline/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        producer = next(command for command in commands
            if command.name == "cxet_add_offline_typescript_suite" and
                command.body.startswith("vetron_offline_ranking_evidence"))
        dependency = next(command for command in commands
            if command.name == "add_dependencies" and
                command.body.startswith("vetron_offline_ranking_evidence"))
        lowered = lower_offline_registrations(ROOT, relative,
            [producer, dependency], errors)
        self.assertEqual(errors, [])
        self.assertEqual(lowered, [])
        errors = []
        lower_offline_registrations(ROOT, relative,
            [producer, dependency, dependency], errors)
        self.assertTrue(any("duplicate" in error for error in errors))

    def test_case_budget_cannot_be_lowered_to_hide_missing_registration(self):
        relative = "src/tests/offline/CMakeLists.txt"
        errors = []
        text = "cxet_add_offline_suite(x OWNER CXETCPP EXPECTED 1 SOURCES DecodeTransactions.cpp)"
        lower_offline_registrations(ROOT, relative, parse_commands(relative, text, errors), errors)
        self.assertTrue(any("scenario" in error for error in errors))

    def test_independent_owner_scope_does_not_inherit_foreign_cache(self):
        errors = []
        files = {}
        roots = ("one/CMakeLists.txt", "two/CMakeLists.txt")
        for relative in roots:
            text = "set(own_target ${CXET_BUILD_OWNER})"
            files[relative] = (text, parse_commands(relative, text, errors))
        commands = compose_active_commands(ROOT, files, roots, set(), errors)
        snapshots = variable_snapshots(commands, function_model(commands, errors), errors,
            initial_values_by_scope={roots[0]: {"CXET_BUILD_OWNER": ("trader",)},
                                    roots[1]: {"CXET_BUILD_OWNER": ("hft-backtest",)}})
        self.assertEqual(errors, [])
        self.assertEqual(snapshots.values[0]["CXET_BUILD_OWNER"], ("trader",))
        self.assertEqual(snapshots.values[1]["CXET_BUILD_OWNER"], ("hft-backtest",))

    def test_unconditional_provider_precedes_unrelated_symbolic_fatal_guard(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        relative = "provider/CMakeLists.txt"
        text = ('add_library(provider STATIC Main.cpp)\n'
                'if(TARGET platform_probe)\nelse()\nmessage(FATAL_ERROR "unsupported")\nendif()')
        errors = []
        files = {relative: (text, parse_commands(relative, text, errors))}
        commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
        model = function_model(commands, errors)
        snapshots = variable_snapshots(commands, model, errors)
        declarations = instantiated_commands(commands, model, snapshots, GRAPH_INSTANCE_NAMES, errors)
        types = directory_target_types(declarations, shared_namespace=True,
            live_eof_paths=snapshots.live_eof_paths, snapshots=snapshots)
        self.assertEqual(errors, [])
        self.assertNotEqual(snapshots.live_eof_paths[relative], ((),))
        self.assertEqual(configure_targets_before(types, SimpleNamespace(ordinal=20)), {"provider": "LIBRARY"})

    def test_public_parser_process_closure_is_consistent_with_authority_denials(self):
        from Family.Targets.CxetFamilyTargetInventory import (
            EXACT_TRANSITIVE_CLOSURES, FORBIDDEN_TRANSITIVE_TARGETS, TRANSPORT_FREE_TARGETS)
        for root in ("trader_market_observe_process", "trader-market-observed"):
            with self.subTest(root=root):
                self.assertIn("hftp_trading_runtime", EXACT_TRANSITIVE_CLOSURES[root])
                self.assertNotIn("hftp_parserd_runtime", EXACT_TRANSITIVE_CLOSURES[root])
                self.assertTrue({"hftp_ipc", "hftp_history_service", "hftp_algos_runtime"} <= FORBIDDEN_TRANSITIVE_TARGETS[root])
                self.assertIn("cxet_lib", EXACT_TRANSITIVE_CLOSURES[root])
                self.assertNotIn(root, TRANSPORT_FREE_TARGETS)
                self.assertFalse(EXACT_TRANSITIVE_CLOSURES[root] & FORBIDDEN_TRANSITIVE_TARGETS[root])
                self.assertTrue({"hftp_sessiond_runtime", "hftp_session_native_account",
                    "trader_live_runtime", "trader_traderd_process"} <= FORBIDDEN_TRANSITIVE_TARGETS[root])
        self.assertTrue({"hftp_sessiond_runtime", "hftp_session_native_account",
                         "trader_live_runtime", "trader_traderd_process"} <= EXACT_TRANSITIVE_CLOSURES["traderd"])
        self.assertNotIn("traderd", TRANSPORT_FREE_TARGETS)
        for root in ("trader_market_observe_runtime", "trader_projection_client",
                     "vetron_read_runtime", "vetrond-read"):
            self.assertIn("cxet_lib", FORBIDDEN_TRANSITIVE_TARGETS[root])
            self.assertIn(root, TRANSPORT_FREE_TARGETS)

    def test_inactive_owner_branch_does_not_require_retired_include(self):
        errors = []
        relative = "one/CMakeLists.txt"
        text = "if(RETIRED_TESTS)\ninclude(retired.cmake)\nendif()\n"
        files = {relative: (text, parse_commands(relative, text, errors))}
        compose_active_commands(ROOT, files, (relative,), set(), errors,
            initial_values_by_scope={relative: {"RETIRED_TESTS": ("OFF",)}})
        self.assertEqual(errors, [])

    def test_unknown_owner_branch_is_not_silently_pruned(self):
        errors = []
        relative = "one/CMakeLists.txt"
        text = "if(UNKNOWN)\ninclude(retired.cmake)\nendif()\n"
        files = {relative: (text, parse_commands(relative, text, errors))}
        compose_active_commands(ROOT, files, (relative,), set(), errors,
            initial_values_by_scope={relative: {}})
        self.assertTrue(any("unresolved" in error for error in errors))

    def test_cache_producer_cannot_poison_an_independent_owner(self):
        errors = []
        first = "src/src/CMakeLists.txt"
        second = "apps/hft-parser/CMakeLists.txt"
        files = {}
        for relative, text in ((first, 'set(CXET_LTO OFF CACHE BOOL "Root policy")'),
                               (second, 'set(owner_value ${CXET_BUILD_OWNER})')):
            files[relative] = (text, parse_commands(relative, text, errors))
        commands = compose_active_commands(ROOT, files, (first, second), set(), [])
        snapshots = variable_snapshots(commands, function_model(commands, []), errors,
            initial_values_by_scope={second: {"CXET_BUILD_OWNER": ("hft-parser",)}})
        self.assertNotIn("CXET_LTO", snapshots.values[1])

    def test_current_read_only_physical_surfaces_are_recognized(self):
        errors = []
        surface.validate_read_only_physical_surfaces(ROOT, errors)
        self.assertEqual(errors, [])

    def test_retired_positive_owner_requirements_are_absent(self):
        retired = {"src/benchmarks/MarketIngress/CMakeLists.txt", "src/tests/Family/CMakeLists.txt",
                   "src/tests/CMakeLists.txt", "apps/hft-trader/cmake/HftTraderSafety.cmake"}
        self.assertFalse(retired & {spec.owner for spec in [*PRODUCTION_TARGETS.values(), *CUSTOM_TARGETS.values()]})
        self.assertNotIn("src/benchmarks/MarketIngress", {root for root, _owner in HEADER_OWNER_ROOTS})

    def test_defined_owner_presence_selects_one_exact_library_route(self):
        errors = []
        relative = "owner/CMakeLists.txt"
        text = "if(DEFINED CXET_BUILD_OWNER)\nadd_library(t STATIC Main.cpp)\nelse()\nadd_library(t SHARED Main.cpp)\nendif()"
        files = {relative: (text, parse_commands(relative, text, errors))}
        commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
        model = function_model(commands, errors)
        snapshots = variable_snapshots(commands, model, errors,
            initial_values_by_scope={relative: {"CXET_BUILD_OWNER": ("OFF",)}})
        instances = instantiated_commands(commands, model, snapshots, {"add_library"}, errors)
        self.assertEqual(errors, [])
        self.assertEqual([tuple(value for group in item.token_groups for value in group)
                          for item in instances], [("t", "STATIC", "Main.cpp")])

    def test_on_provider_stage_has_its_own_reachable_math_and_execution_instances(self):
        checker = _ownership_checker_for_harness()
        errors = []
        configurations = owner_activation(ROOT, errors)
        _, values = configurations["offline:trading-core:release"]
        files = {}
        for relative in ("apps/trading-core/CMakeLists.txt", "apps/trading-core/capital/CMakeLists.txt", "apps/trading-core/tests/offline/Math/CMakeLists.txt",
                         "apps/trading-core/tests/offline/Execution/CMakeLists.txt"):
            text = (ROOT / relative).read_text()
            parsed = parse_commands(relative, text, errors)
            files[relative] = (text, lower_offline_registrations(ROOT, relative, parsed, errors)
                               if relative == "apps/trading-core/capital/CMakeLists.txt" else parsed)
        initial = {"CMAKE_CXX_COMPILER_ID": ("Clang",), "CMAKE_SYSTEM_NAME": ("Linux",),
                   "CMAKE_SYSTEM_PROCESSOR": ("x86_64",)}
        _commands, instances, eof = checker.owner_local_provider_test_instances(
            files, initial, values, [], errors)
        names = {item.token_groups[0][0] for item in instances
                 if item.body.command.name in {"add_executable", "add_library"}}
        self.assertIn("trading-core-math-tests", names)
        self.assertIn("trading-core-execution-tests", names)
        self.assertNotIn("trading_core_execution", names)
        self.assertEqual(set(eof), {"offline-provider:trading-core:release"})
        self.assertTrue(eof["offline-provider:trading-core:release"])

    def test_corpus_offline_uses_its_own_contract_and_exact_shared_harness(self):
        source = "apps/hft-recorder/tests/offline/Corpus/CorpusCases.cpp"
        self.assertTrue(verification_include_allowed(source,
            "apps/hft-recorder/src/Contracts/include/hftrec/CorpusContract/BinaryMarketCorpusReader.hpp"))
        self.assertTrue(verification_include_allowed(source, "tools/Testing/OfflineCase.hpp"))
        self.assertFalse(verification_include_allowed(source, "tools/Testing/UnknownFuture.hpp"))
        self.assertFalse(verification_include_allowed("src/src/Contracts/include/cxet/Market/Depth.hpp", "tools/Testing/OfflineCase.hpp"))


if __name__ == '__main__':
    unittest.main()
