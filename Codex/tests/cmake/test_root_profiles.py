"""Regressions for the canonical owner driver after retiring CMake presets."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace

from CMake.Root.CmakeFamilyRootEntrypoints import check_root_compile
from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
from CMake.Root.CmakeFamilyRootComposition import check_owner_composition
from CMake.Root.CmakeFamilyRootDialect import validate_root_dialect
from CMake.Root.CmakeFamilyRootGraphCommon import parse_commands
from CMake.Syntax.CmakeFamilyLexer import words
from CMake.Policy.CmakeFamilyVendorPolicy import validate_root_vendor_contract


ROOT = Path(__file__).resolve().parents[4]


class OwnerProfileTests(unittest.TestCase):
    def setUp(self):
        self.driver = (ROOT / "tools/Build/CompileTargets.py").read_text()

    def test_real_owner_driver_resolves_without_preset_document(self):
        errors = []
        profiles = resolve_root_profile_caches(self.driver, errors)
        self.assertEqual(errors, [])
        self.assertTrue(profiles)
        self.assertTrue(any(cache.get("CXET_BUILD_OWNER") == "trader"
                            and cache.get("CXET_LOCAL_TESTS") == "OFF"
                            for cache in profiles.values()))
        self.assertTrue(any(cache.get("CXET_BUILD_OWNER") == "CXETCPP"
                            and cache.get("CXET_SANITIZER_PROFILE") == "thread"
                            for cache in profiles.values()))
        self.assertEqual(profiles["offline:CXETCPP:release"]["CXET_LTO"], "OFF")
        self.assertEqual(profiles["offline:CXETCPP:release:full"]["CXET_LTO"], "ON")
        for name, cache in profiles.items():
            if name.startswith("offline:") and cache["CXET_SANITIZER_PROFILE"] != "none":
                with self.subTest(profile=name):
                    self.assertEqual(cache["CXET_LTO"], "OFF")

    def test_owner_all_profiles_select_only_supported_benchmarks(self):
        errors = []
        profiles = resolve_root_profile_caches(self.driver, errors)
        self.assertEqual(errors, [])
        supported = {"CXETCPP", "hft-parser", "trading-core", "trader"}
        compiled = {name: cache for name, cache in profiles.items()
                    if name.startswith("compile:")}
        self.assertTrue(compiled)
        for name, cache in compiled.items():
            with self.subTest(profile=name):
                enabled = (cache["CXET_BUILD_OWNER"] in supported
                           and cache["CXET_LOCAL_TESTS"] == "ON")
                self.assertEqual(cache["CXET_LOCAL_BENCHMARKS"],
                                 "ON" if enabled else "OFF")

    def test_unreviewed_configure_keyword_is_rejected(self):
        changed = self.driver.replace("trader_diagnostic=None, toolchain_profile='pinned'):",
                                      "trader_diagnostic=None, toolchain_profile='pinned', foreign=False):")
        self.assertNotEqual(changed, self.driver)
        errors = []
        self.assertEqual(resolve_root_profile_caches(changed, errors), {})
        self.assertTrue(any("configure input binding/profile guard prefix" in error
                            for error in errors))

    def test_benchmark_guard_cannot_be_removed_or_weakened(self):
        guard = ("    if benchmarks and (not tests or owner not in BENCHMARK_OWNERS):\n"
                 "        raise BuildError('benchmarks require the supported owner all stage')\n")
        for replacement in ("", guard.replace("not tests or", "not tests and")):
            with self.subTest(guard=replacement):
                changed = self.driver.replace(guard, replacement)
                self.assertNotEqual(changed, self.driver)
                errors = []
                self.assertEqual(resolve_root_profile_caches(changed, errors), {})
                self.assertTrue(any("configure input binding/profile guard prefix" in error
                                    for error in errors))

    def test_thin_root_wrapper_has_no_legacy_family_switches(self):
        errors = []
        check_root_compile((ROOT / "compile.sh").read_text(), errors)
        self.assertEqual(errors, [])

    def test_retired_verification_switches_cannot_select_an_empty_test_graph(self):
        root = (ROOT / "CMakeLists.txt").read_text()
        graph = (ROOT / "cmake/CxetCompileGraph.cmake").read_text()
        offline = (ROOT / "tools/Testing/RunOffline.py").read_text()
        self.assertIn("if(CXET_FAMILY_VERIFICATION OR CXET_EXECUTION_TESTS_ONLY)", root)
        self.assertNotIn("set(CXET_FAMILY_VERIFICATION", root)
        self.assertNotIn("CXET_EXECUTION_TESTS_ONLY", graph)
        for switch in ("CXET_FAMILY_VERIFICATION", "CXET_EXECUTION_TESTS_ONLY"):
            self.assertNotIn("-D" + switch + "=", self.driver)
            self.assertNotIn("-D" + switch + "=", offline)

    def test_driver_cannot_replace_pinned_profile(self):
        errors = []
        changed = self.driver.replace("'-DCXET_TOOLCHAIN_PROFILE=' + toolchain_profile",
                                      "'-DCXET_TOOLCHAIN_PROFILE=baseline'")
        self.assertNotEqual(changed, self.driver)
        resolve_root_profile_caches(changed, errors)
        self.assertTrue(errors)

    def test_system_diagnostic_cannot_admit_a_production_owner_or_lto(self):
        guard = "owner != 'diagnostic' or tests or force or benchmarks or low"
        for replacement in ("False", "tests or benchmarks or low"):
            changed = self.driver.replace(guard, replacement)
            self.assertNotEqual(changed, self.driver)
            errors = []
            self.assertEqual(resolve_root_profile_caches(changed, errors), {})
            self.assertTrue(errors)

    def test_system_diagnostic_offline_guard_cannot_admit_hot_owners(self):
        offline = (ROOT / 'tools/Testing/RunOffline.py').read_text()
        changed = offline.replace('args.owner not in SYSTEM_DIAGNOSTIC_OWNERS or args.profile != "release"',
                                  'args.profile != "release"')
        self.assertNotEqual(changed, offline)
        errors = []
        self.assertEqual(resolve_root_profile_caches(self.driver, errors, offline_text=changed), {})
        self.assertTrue(errors)

    def test_driver_cannot_use_a_different_owner_cache_key(self):
        errors = []
        changed = self.driver.replace("-DCXET_BUILD_OWNER=", "-DCXET_FOREIGN_OWNER=")
        self.assertNotEqual(changed, self.driver)
        resolve_root_profile_caches(changed, errors)
        self.assertTrue(errors)

    def test_offline_sanitizer_cannot_enable_full_lto(self):
        errors = []
        offline = (ROOT / "tools/Testing/RunOffline.py").read_text()
        changed = offline.replace('"ON" if lto == "full" else "OFF"',
                                  '"ON" if args.profile != "release" else "OFF"')
        self.assertNotEqual(changed, offline)
        resolve_root_profile_caches(self.driver, errors, offline_text=changed)
        self.assertTrue(errors)

    def test_driver_cannot_append_compiler_override(self):
        changed = self.driver.replace("    run(argv)",
            "    argv.append('-DCMAKE_C_COMPILER=/tmp/foreign-clang')\n    run(argv)")
        self.assertNotEqual(changed, self.driver)
        errors = []
        resolve_root_profile_caches(changed, errors)
        self.assertTrue(errors)

    def test_unreachable_configure_list_cannot_prove_emitted_profile(self):
        changed = self.driver.replace("    argv = ['cmake'", "    if False:\n        argv = ['cmake'")
        self.assertNotEqual(changed, self.driver)
        errors = []
        resolve_root_profile_caches(changed, errors)
        self.assertTrue(errors)


class OwnerGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = (ROOT / "cmake/CxetCompileGraph.cmake").read_text()
        self.driver = (ROOT / "tools/Build/CompileTargets.py").read_text()

    def rejected(self, changed):
        self.assertNotEqual(changed, self.graph)
        errors = []
        check_owner_composition(changed, errors)
        self.assertTrue(errors)

    def test_current_owner_composition_passes(self):
        errors = []
        check_owner_composition(self.graph, errors)
        self.assertEqual(errors, [])

    def test_parser_full_peer_guards_cannot_admit_owner_local_tests(self):
        guard = 'CXET_FAMILY_PROFILE STREQUAL "full" AND NOT CXET_LOCAL_TESTS'
        self.assertEqual(self.graph.count(guard), 2)
        start = 0
        for peer in ("Vetron", "Recorder"):
            offset = self.graph.index(guard, start)
            for replacement in ('CXET_FAMILY_PROFILE STREQUAL "full"',
                                'CXET_FAMILY_PROFILE STREQUAL "full" AND CXET_LOCAL_TESTS'):
                with self.subTest(peer=peer, replacement=replacement):
                    self.rejected(self.graph[:offset] + replacement + self.graph[offset + len(guard):])
            start = offset + len(guard)

    def test_benchmarks_require_local_tests_and_supported_owner(self):
        guard = (
            'if(CXET_LOCAL_BENCHMARKS AND (NOT CXET_LOCAL_TESTS OR\n'
            '   NOT CXET_BUILD_OWNER MATCHES "^(CXETCPP|hft-parser|trading-core|trader)$"))\n'
            '  message(FATAL_ERROR "Benchmarks require a supported owner\'s all stage")\n'
            'endif()\n'
        )
        for replacement in ("", guard.replace("NOT CXET_LOCAL_TESTS OR", "NOT CXET_LOCAL_TESTS AND")):
            with self.subTest(guard=replacement):
                self.rejected(self.graph.replace(guard, replacement))

    def test_benchmark_sources_cannot_escape_owner_all_scope(self):
        for edge in ('add_subdirectory(src/benchmarks EXCLUDE_FROM_ALL)',
                     'add_subdirectory("apps/${CXET_BUILD_OWNER}/benchmarks" EXCLUDE_FROM_ALL)'):
            with self.subTest(edge=edge):
                self.rejected(self.graph.replace(edge, "") + "\n" + edge + "\n")

    def test_corpus_consumers_keep_the_canonical_compressor_provider(self):
        for consumer in ("hft-backtest", "vetron"):
            with self.subTest(consumer=consumer):
                self.rejected(self.graph.replace(
                    "set(_cxet_compressor_owners hft-compressor hft-recorder hft-backtest vetron)",
                    "set(_cxet_compressor_owners " + " ".join(owner for owner in
                        ("hft-compressor", "hft-recorder", "hft-backtest", "vetron")
                        if owner != consumer) + ")"))
        self.rejected(self.graph.replace(
            "foreach(owner_list IN ITEMS _cxet_parser_owners _cxet_strategy_owners\n"
            "      _cxet_backtest_owners)",
            "foreach(owner_list IN ITEMS _cxet_parser_owners _cxet_strategy_owners\n"
            "      _cxet_compressor_owners _cxet_backtest_owners)"))

    def test_vetron_research_keeps_the_backtest_provider(self):
        self.rejected(self.graph.replace(
            "set(_cxet_backtest_owners hft-backtest hft-recorder vetron)",
            "set(_cxet_backtest_owners hft-backtest hft-recorder)"))

    def test_parser_contract_provider_keeps_its_exact_consumer_guards(self):
        edge = "add_subdirectory(apps/hft-parser/src/Contracts EXCLUDE_FROM_ALL)"
        self.rejected(self.graph.replace(edge, "") + "\n" + edge + "\n")
        self.rejected(self.graph.replace(edge,
            "add_subdirectory(apps/hft-parser/src/Contracts)"))
        guard = 'if(CXET_BUILD_OWNER IN_LIST _cxet_backtest_owners AND NOT TARGET hftp_contract_headers)'
        for replacement in (
                'if(CXET_BUILD_OWNER IN_LIST _cxet_backtest_owners)',
                'if(NOT TARGET hftp_contract_headers)'):
            with self.subTest(guard=replacement):
                self.rejected(self.graph.replace(guard, replacement))

    def test_unknown_owner_guard_cannot_be_removed(self):
        self.rejected(self.graph.replace("if(NOT CXET_BUILD_OWNER IN_LIST _cxet_compile_owners)",
                                         "if(FALSE)"))

    def test_parser_provider_cannot_acquire_hft_trader(self):
        self.rejected(self.graph.replace("set(_cxet_parser_owners hft-parser trader vetron hft-recorder)",
                                         "set(_cxet_parser_owners hft-parser trader vetron hft-recorder hft-trader)"))

    def test_foreign_source_edge_is_rejected(self):
        self.rejected(self.graph + "\nadd_subdirectory(../foreign-sdk)\n")

    def test_authority_marker_must_precede_provider_edges(self):
        self.rejected(self.graph.replace("set(CXET_ROOT_SOURCE_GRAPH ON)", "") +
                      "\nset(CXET_ROOT_SOURCE_GRAPH ON)\n")

    def test_local_tests_cannot_escape_their_owner_stage(self):
        edge = 'add_subdirectory("${test_root}" EXCLUDE_FROM_ALL)'
        self.rejected(self.graph.replace(edge, "") + "\n" + edge + "\n")

    def test_driver_cannot_enable_removed_collectors_or_profiling(self):
        for switch in ("CXET_PGO_GENERATE", "CXET_PGO_USE",
                       "CXET_HFT_TRADER_FULL_BUILD", "HFT_TRADER_FULL_BUILD",
                       "HFT_TRADER_HOT_MONO_CLOCK_CANDIDATE",
                       "CXET_HFT_TRADER_EVENT_LOG_BUILD", "HFT_TRADER_EVENT_LOG_BUILD",
                       "CXET_RAW_EXCHANGE_LOG_BUILD", "CXET_OFFLINE_BENCHMARKS", "CXET_BENCHHELLO_ONLY"):
            with self.subTest(switch=switch):
                errors = []
                changed = self.driver.replace("-DCXET_MACHINE_SAFETY_AUDIT=OFF",
                                              "-D" + switch + "=ON")
                self.assertNotEqual(changed, self.driver)
                resolve_root_profile_caches(changed, errors)
                self.assertTrue(errors)


class OwnerDialectInventoryTests(unittest.TestCase):
    def test_current_profiles_have_no_retired_positive_inventory(self):
        if not (sys.flags.isolated and sys.flags.no_site):
            # The ownership CLI intentionally refuses ordinary Python imports.
            # Execute the same assertions under its required trusted bootstrap.
            program = (
                "import pathlib, sys, unittest; "
                "sys.path.insert(0, str(pathlib.Path(sys.argv[1]))); "
                "sys.path.insert(0, str(pathlib.Path(sys.argv[1]) / 'tools/Codex')); "
                "suite = unittest.defaultTestLoader.loadTestsFromName("
                "'tools.Codex.tests.cmake.test_root_profiles.OwnerDialectInventoryTests'); "
                "result = unittest.TextTestRunner().run(suite); "
                "sys.exit(not result.wasSuccessful())"
            )
            completed = subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program,
                                        str(ROOT)], capture_output=True, text=True, timeout=60)
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            return
        from CheckCxetFamilyOwnership import (
            cmake_files, owner_activation, compose_active_commands,
            APPROVED_EXTERNAL_SUBDIRECTORIES, cmake_list_words,
        )
        from CMake.Syntax.CmakeFamilyDialect import validate_exact_active_inventory
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        errors = []
        files = cmake_files(errors)
        configurations = owner_activation(ROOT, errors)
        roots, values = configurations["offline:CXETCPP:release"]
        # RunOffline omits these configure defaults from its explicit cache.
        # Use the same owner's canonical all-exchange Core cache to supply
        # only absent defaults, preserving the selected offline profile.
        core_cache = configurations["compile:CXETCPP:essential:0:0:1"][1]["src/src/CMakeLists.txt"]
        for state in values.values():
            for key in ("CXET_EXCHANGES", "CXET_EXCHANGE_PRESET", "CXET_HOT_FEATURE_PROFILE"):
                state.setdefault(key, core_cache[key])
        files, values = lower_selector_modules(ROOT, files, values, errors)
        self.assertEqual(errors, [])
        # Other unsupported ownership models remain visible in the collector;
        # this regression isolates privileged inventory from their diagnostics.
        commands = compose_active_commands(ROOT, files, roots,
            APPROVED_EXTERNAL_SUBDIRECTORIES, [], initial_values_by_scope=values)
        inventory_errors = []
        origins = frozenset(command.relative for command in commands)
        validate_exact_active_inventory(commands, cmake_list_words, inventory_errors,
            active_origins=origins)
        self.assertEqual(inventory_errors, [])
        from dataclasses import replace
        from CMake.Syntax.CmakeFamilyContext import StructuralFrame, StructuralArm
        selected = next(index for index, active in enumerate(commands)
            if active.relative == "src/tests/offline/CMakeLists.txt"
            and active.command.name == "find_package")
        target = commands[selected]
        counterexamples = {
            "removed provider": commands[:selected] + commands[selected + 1:],
            "foreign evaluation owner": [*commands[:selected], replace(target,
                scope="apps/hft-trader/CMakeLists.txt"), *commands[selected + 1:]],
            "conditional provider": [*commands[:selected], replace(target,
                structural_context=(StructuralFrame("if", target.relative,
                    target.command.line, 0, ("FALSE",), StructuralArm("if", ("FALSE",))),)), *commands[selected + 1:]],
        }
        for reason, changed in counterexamples.items():
            with self.subTest(reason=reason):
                failures = []
                validate_exact_active_inventory(changed, cmake_list_words, failures,
                    active_origins=origins)
                self.assertTrue(failures)


class NativeCryptoPolicyTests(unittest.TestCase):
    def test_production_provider_inventory_rejects_openssl_reintroduction(self):
        from CMake.Policy.CmakeFamilyConditionPolicy import validate_root_provider_contract
        root_text = (ROOT / "CMakeLists.txt").read_text()
        core_text = (ROOT / "src/src/CMakeLists.txt").read_text()
        for owner, extra in ((None, ""), ("root", "find_package(OpenSSL REQUIRED)\n"),
                             ("core", "find_package(OpenSSL REQUIRED COMPONENTS SSL)\n")):
            with self.subTest(owner=owner):
                errors = []
                root = parse_commands("CMakeLists.txt", root_text + (extra if owner == "root" else ""), errors)
                core = parse_commands("src/src/CMakeLists.txt", core_text + (extra if owner == "core" else ""), errors)
                validate_root_provider_contract(root, core, errors)
                self.assertEqual(bool(errors), owner is not None, errors)

    def test_ssl_component_discovery_is_offline_owner_only(self):
        from CMake.Syntax.CmakeFamilyDialect import _trusted_find_package
        form = ["OpenSSL", "REQUIRED", "COMPONENTS", "SSL"]
        self.assertTrue(_trusted_find_package(form, "src/tests/offline/CMakeLists.txt"))
        for owner in (None, "CMakeLists.txt", "src/src/CMakeLists.txt", "apps/hft-trader/CMakeLists.txt"):
            self.assertFalse(_trusted_find_package(form, owner))
        self.assertFalse(_trusted_find_package(form + ["Crypto"], "src/tests/offline/CMakeLists.txt"))

    @staticmethod
    def crypto_instance(name, *, relative="src/src/CMakeLists.txt", kind="STATIC",
                        exclude=True, guard=True):
        from CMake.Syntax.CmakeFamilyContext import StructuralFrame, StructuralArm
        context = (StructuralFrame("if", "src/src/CMakeLists.txt", 234, 0,
            ("NOT", "TARGET", "cxet_crypto"), StructuralArm("if", ("NOT", "TARGET", "cxet_crypto"))),) if guard else ()
        return SimpleNamespace(
            token_groups=((name, kind, *(("EXCLUDE_FROM_ALL",) if exclude else ()), "source.c"),),
            body=SimpleNamespace(relative=relative, structural_context=context,
                command=SimpleNamespace(name="add_library", line=266)),
            evaluation=SimpleNamespace(source_base=Path("src/src"), binary_base=Path("src/src"),
                structural_context=context))

    def test_only_exact_native_crypto_libraries_may_be_excluded(self):
        from Family.Targets.CxetFamilyTargetRegistry import _classify
        from Family.Targets.CxetFamilyTargetInventory import PRODUCTION_TARGETS
        names = ("cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import", "cxet_tls_certificates", "cxet_native_tls")
        for name in names:
            with self.subTest(name=name):
                errors = []
                declaration = _classify(self.crypto_instance(name), errors)
                self.assertEqual(errors, [])
                self.assertEqual(declaration.spec, PRODUCTION_TARGETS[name])
        for name, kwargs in (("cxet_lib", {}), ("cxet_crypto_unreviewed", {}),
                             ("cxet_crypto", {"relative": "foreign/CMakeLists.txt"}),
                             ("cxet_crypto", {"kind": "SHARED"}),
                             ("cxet_crypto", {"exclude": False}),
                             ("cxet_crypto", {"guard": False})):
            with self.subTest(name=name, mutation=kwargs):
                errors = []
                self.assertIsNone(_classify(self.crypto_instance(name, **kwargs), errors))
                self.assertTrue(errors)

    def test_ssl_oracle_link_does_not_authorize_other_offline_targets(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        from dataclasses import replace
        target = "cxet_offline_tls_handshake"
        instances = self.registered_instances_fixture(target)
        declaration = next(item for item in instances if item.body.command.name == "add_executable")
        instance = next(item for item in instances if item.body.command.name == "target_link_libraries")
        contexts = self.offline_context_fixture(target, declaration)
        self.assertIsNone(external_link_error(instance, "cxet_offline_tls_handshake", "OpenSSL::SSL", contexts))
        self.assertIsNotNone(external_link_error(instance, "cxet_offline_tls_records", "OpenSSL::SSL", contexts))
        self.assertIsNotNone(external_link_error(instance, "cxet_offline_tls_handshake", "wolfssl", contexts))
        self.assertIsNotNone(external_link_error(instance, "cxet_offline_tls_handshake", "OpenSSL::Crypto", contexts))
        active = replace(instance.body, command=replace(instance.body.command, registration=None))
        self.assertIsNotNone(external_link_error(replace(instance, body=active, evaluation=active),
            target, "OpenSSL::SSL", contexts))

    @classmethod
    def registered_instances_fixture(cls, target, *, benchmark=False):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        from Family.Profile.CxetFamilyActivation import lower_offline_registrations
        from Family.Profile.CxetFamilyBenchmarkActivation import lower_benchmark_registrations
        relative = ("apps/hft-parser/benchmarks/CMakeLists.txt" if benchmark else
                    "src/tests/offline/CMakeLists.txt")
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        lower = lower_benchmark_registrations if benchmark else lower_offline_registrations
        commands = lower(ROOT, relative, commands, errors)
        if errors:
            raise AssertionError(errors)
        instances = []
        for ordinal, command in enumerate(commands, 1):
            tokens = words(command.body)
            if tokens[:1] != [target]:
                continue
            active = ActiveCommand(relative, relative, Path(relative).parent,
                                   Path(relative).parent, (), command, ordinal)
            instances.append(InstantiatedCommand(active, active,
                tuple((token,) for token in tokens), ordinal, ALL_PATHS))
        return instances

    @staticmethod
    def offline_context_fixture(target, declaration):
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Targets.CxetFamilyTargetRegistry import _classify
        errors = []
        classified = _classify(declaration, errors)
        if errors:
            raise AssertionError(errors)
        return SimpleNamespace(
            context_for_use=lambda name, use: declaration if name == target else None,
            role=lambda name, use: classified.role if name == target and
                offline_registration(declaration, target) is not None else None)

    def test_production_openssl_leaves_are_rejected_and_independent_probe_preserved(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        for owner, source in (("src/src", "cxet_lib"), ("apps/trader", "trader_live_runtime"),
                              ("tools/exchange_api_probe", "exchange_probe_lib")):
            instance = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path(owner)))
            for dependency in ("OpenSSL::SSL", "OpenSSL::Crypto"):
                with self.subTest(owner=owner, dependency=dependency):
                    error = external_link_error(instance, source, dependency, {source: instance})
                    self.assertEqual(error is None, owner == "tools/exchange_api_probe")
        instance = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path("tools/exchange_api_probe")))
        self.assertIsNotNone(external_link_error(instance, "foreign_probe", "OpenSSL::SSL", {"foreign_probe": instance}))

    def test_probe_http2_dependencies_are_restricted_to_probe_library(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        for owner, source in (("src/src", "cxet_lib"), ("apps/trader", "trader_live_runtime"),
                              ("tools/exchange_api_probe", "exchange_probe_lib")):
            instance = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path(owner)))
            for dependency in ("Boost::json", "PkgConfig::NGHTTP2"):
                with self.subTest(owner=owner, dependency=dependency):
                    error = external_link_error(instance, source, dependency, {source: instance})
                    self.assertEqual(error is None, owner == "tools/exchange_api_probe")
        instance = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path("tools/exchange_api_probe")))
        for dependency in ("Boost::json", "PkgConfig::NGHTTP2"):
            self.assertIsNotNone(external_link_error(instance, "foreign_probe", dependency,
                                                    {"foreign_probe": instance}))
        thread_instance = SimpleNamespace(
            body=SimpleNamespace(relative="tools/exchange_api_probe/CMakeLists.txt",
                                 command=SimpleNamespace(line=62)),
            evaluation=instance.evaluation)
        self.assertIsNone(external_link_error(thread_instance, "exchange_probe_lib", "Threads::Threads",
                                              {"exchange_probe_lib": thread_instance}))
        self.assertIsNotNone(external_link_error(thread_instance, "foreign_probe", "Threads::Threads",
                                                 {"foreign_probe": thread_instance}))

    def test_liburing_terminal_oracle_is_exact_offline_consumer(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        from dataclasses import replace
        terminal = "cxet_offline_tls_terminal"
        instances = self.registered_instances_fixture(terminal)
        declaration = next(item for item in instances if item.body.command.name == "add_executable")
        offline = next(item for item in instances if item.body.command.name == "target_link_libraries")
        def foreign(instance):
            active = replace(instance.body, source_base=Path("src/tests/foreign"))
            return replace(instance, body=active, evaluation=active)
        for dependency in ("liburing::uring",):
            self.assertIsNone(external_link_error(offline, terminal, dependency,
                self.offline_context_fixture(terminal, declaration)))
            for source, instance, selected_declaration in (
                    ("cxet_offline_tls_records", offline, declaration),
                    (terminal, foreign(offline), declaration),
                    (terminal, offline, foreign(declaration))):
                with self.subTest(dependency=dependency, source=source,
                                  use=instance.evaluation.source_base,
                                  declaration=selected_declaration.evaluation.source_base):
                    self.assertIsNotNone(external_link_error(instance, source, dependency,
                        self.offline_context_fixture(terminal, selected_declaration)))

    def test_root_requires_exact_asm_language_contract(self):
        source = (ROOT / "CMakeLists.txt").read_text()
        self.assertIn("project(CXET LANGUAGES C CXX ASM)", source)
        for project in ("project(CXET LANGUAGES C CXX)", "project(CXET LANGUAGES C CXX ASM CUDA)"):
            errors = []
            changed = source.replace("project(CXET LANGUAGES C CXX ASM)", project)
            validate_root_dialect(parse_commands("CMakeLists.txt", changed, errors), words, errors)
            self.assertTrue(any("bootstrap inventory changed" in error for error in errors), errors)


    def test_native_vendor_sources_stay_target_and_owner_scoped(self):
        from Family.Targets.CxetFamilyTargetPolicy import declared_source_owner_error
        native = self.crypto_instance("cxet_crypto")
        hacl = "extra/hacl-star/dist/gcc-compatible/Hacl_Ed25519.c"
        self.assertIsNone(declared_source_owner_error("cxet_crypto", native, native, hacl))
        self.assertIsNotNone(declared_source_owner_error("cxet_lib", native, native, hacl))
        self.assertIsNotNone(declared_source_owner_error("cxet_crypto", native, native,
            "extra/hacl-star/dist/gcc-compatible/unreviewed.c"))
        foreign = self.crypto_instance("cxet_crypto", relative="foreign/CMakeLists.txt")
        self.assertIsNotNone(declared_source_owner_error("cxet_crypto", native, foreign, hacl))

    def test_native_configs_resolve_only_canonical_macro_headers(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_include_data, native_crypto_definition_error
        header = "extra/mbedtls-cold/include/mbedtls/build_info.h"
        data = b"#include MBEDTLS_CONFIG_FILE\n#include MBEDTLS_USER_CONFIG_FILE\n#include FOREIGN_HEADER\n"
        bindings, binding_errors = self.native_config_bindings_fixture()
        self.assertEqual(binding_errors, [])
        rsa = native_crypto_include_data(ROOT, "cxet_crypto_rsa", header, data, bindings)
        cold = native_crypto_include_data(ROOT, "cxet_crypto_import", header, data, bindings)
        self.assertIn(b'#include "RsaMbedConfig.h"', rsa)
        self.assertIn(b'#include "cxet_mbedtls_config.h"', cold)
        self.assertEqual(native_crypto_include_data(ROOT, "cxet_offline_crypto_primitives",
            header, data, bindings), cold)
        self.assertNotIn(b"#include MBEDTLS_USER_CONFIG_FILE", rsa)
        self.assertIn(b"#include FOREIGN_HEADER", rsa)
        self.assertEqual(native_crypto_include_data(ROOT, "cxet_lib", header, data), data)
        self.assertFalse(native_crypto_definition_error("cxet_crypto_rsa", 'MBEDTLS_CONFIG_FILE="RsaMbedConfig.h"'))
        self.assertTrue(native_crypto_definition_error("cxet_crypto_rsa", 'MBEDTLS_CONFIG_FILE="foreign.h"'))
        self.assertTrue(native_crypto_definition_error("cxet_crypto_rsa", 'MBEDTLS_USER_CONFIG_FILE="foreign.h"'))

    @classmethod
    def native_config_commands_fixture(cls):
        commands = []
        for command, tokens in (
                ("target_compile_definitions", ("cxet_crypto_rsa", "PRIVATE", 'MBEDTLS_CONFIG_FILE="RsaMbedConfig.h"')),
                ("target_compile_definitions", ("cxet_crypto_import", "PUBLIC", 'MBEDTLS_CONFIG_FILE="cxet_mbedtls_config.h"')),
                ("set_source_files_properties", ("Core/src/Crypto/Rsa.cpp", "PROPERTIES", "COMPILE_DEFINITIONS", '"MBEDTLS_CONFIG_FILE=\\"RsaMbedConfig.h\\""')),
                ("target_link_libraries", ("cxet_tls_certificates", "PUBLIC", "cxet_crypto_import")),
                ("target_link_libraries", ("cxet_native_tls", "PUBLIC", "cxet_crypto", "cxet::resident_memory", "PRIVATE", "cxet_tls_certificates"))):
            instance = cls.crypto_instance("cxet_crypto")
            instance.body.command.name = command
            instance.body.command.body = " ".join(tokens)
            from CMake.Syntax.CmakeFamilyLexer import cmake_list_words
            from CMake.Flow.CmakeFamilyState import expand_variable_tokens
            instance.token_groups = tuple((token,) for token in expand_variable_tokens(
                cmake_list_words(instance.body.command.body), {}))
            instance.path_alternatives = ((),)
            commands.append(instance)
        commands.extend(item for item in cls.registered_instances_fixture("cxet_offline_crypto_primitives")
                        if item.body.command.name == "target_link_libraries")
        return commands

    @classmethod
    def native_config_bindings_fixture(cls):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_config_bindings
        errors = []
        bindings = native_crypto_config_bindings(cls.native_config_commands_fixture(), lambda target: ((),), errors)
        return bindings, errors

    def test_native_macro_rewrite_refuses_missing_or_conflicting_effective_definitions(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_config_bindings, native_crypto_include_data
        data = b"#include MBEDTLS_CONFIG_FILE\n"
        header = "extra/mbedtls-cold/include/mbedtls/build_info.h"
        for removed, target in ((0, "cxet_crypto_rsa"), (1, "cxet_crypto_import"),
                                (2, "cxet_crypto"), (3, "cxet_tls_certificates"),
                                (4, "cxet_native_tls"), (5, "cxet_offline_crypto_primitives")):
            with self.subTest(missing=removed, target=target):
                commands = self.native_config_commands_fixture()
                del commands[removed]
                errors = []
                bindings = native_crypto_config_bindings(commands, lambda name: ((),), errors)
                self.assertTrue(errors)
                self.assertNotIn(target, bindings)
                self.assertEqual(native_crypto_include_data(ROOT, target, header, data, bindings), data)
        for mutation in ("private import", "conflicting RSA", "missing residency bridge"):
            commands = self.native_config_commands_fixture()
            if mutation == "private import":
                commands[1].token_groups = (("cxet_crypto_import",), ("PRIVATE",), ('MBEDTLS_CONFIG_FILE="cxet_mbedtls_config.h"',))
                target = "cxet_tls_certificates"
            elif mutation == "conflicting RSA":
                extra = self.native_config_commands_fixture()[0]
                extra.token_groups = (("cxet_crypto_rsa",), ("PRIVATE",), ('MBEDTLS_CONFIG_FILE="foreign.h"',))
                commands.append(extra)
                target = "cxet_crypto_rsa"
            else:
                commands[4].token_groups = tuple(group for group in commands[4].token_groups
                    if group != ("cxet::resident_memory",))
                target = "cxet_native_tls"
            errors = []
            bindings = native_crypto_config_bindings(commands, lambda name: ((),), errors)
            self.assertTrue(errors, mutation)
            self.assertNotIn(target, bindings, mutation)
        self.assertEqual(native_crypto_include_data(ROOT, "cxet_crypto_rsa", header, data), data)

    def test_native_textual_source_exception_does_not_open_other_compiled_includes(self):
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_textual_source
        source = "src/src/Core/src/Crypto/RsaMbedAes.c"
        selected = "extra/mbedtls-cold/library/aes.c"
        self.assertTrue(native_crypto_textual_source("cxet_crypto_rsa", source, selected))
        self.assertFalse(native_crypto_textual_source("cxet_crypto", source, selected))
        self.assertFalse(native_crypto_textual_source("cxet_crypto_rsa", source, "extra/mbedtls-cold/library/rsa.c"))

    def test_native_production_closure_preserves_transport_free_denials(self):
        from Family.Targets.CxetFamilyTargetInventory import (
            EXACT_TRANSITIVE_CLOSURES, FORBIDDEN_TRANSITIVE_TARGETS, REQUIRED_DIRECT_LINKS,
        )
        native = {"cxet_crypto", "cxet_crypto_rsa", "cxet_crypto_import", "cxet_tls_certificates", "cxet_native_tls"}
        self.assertEqual(EXACT_TRANSITIVE_CLOSURES["cxet_native_tls"], native | {"cxet_resident_memory"})
        self.assertTrue({"cxet_crypto", "cxet_native_tls"} <= REQUIRED_DIRECT_LINKS["cxet_lib"])
        core_consumers = {name: closure for name, closure in EXACT_TRANSITIVE_CLOSURES.items()
                          if "cxet_lib" in closure}
        self.assertTrue(core_consumers)
        for name, closure in core_consumers.items():
            with self.subTest(target=name):
                self.assertTrue(native <= closure)
        self.assertTrue(native <= FORBIDDEN_TRANSITIVE_TARGETS["cxet_read_only_contracts"])
        self.assertTrue(native <= FORBIDDEN_TRANSITIVE_TARGETS["vetron_read_gateway"])
        self.assertTrue("vetron_read_gateway" in EXACT_TRANSITIVE_CLOSURES["vetron_read_runtime"])
        self.assertTrue(native.isdisjoint(EXACT_TRANSITIVE_CLOSURES["vetron_read_runtime"]))

    def test_financial_oracle_ssl_is_exact_offline_consumer(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        source = "trader_offline_finam_full_path"
        offline = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path("apps/trader/tests/offline")))
        production = SimpleNamespace(evaluation=SimpleNamespace(source_base=Path("apps/trader")))
        self.assertIsNone(external_link_error(offline, source, "OpenSSL::SSL", {source: offline}))
        self.assertIsNotNone(external_link_error(production, source, "OpenSSL::SSL", {source: offline}))
        self.assertIsNotNone(external_link_error(offline, "trader_foreign_oracle", "OpenSSL::SSL", {"trader_foreign_oracle": offline}))


    def test_diagnostic_ssl_peer_requires_benchmark_role_and_exact_helper(self):
        from Family.Targets.CxetFamilyProductPolicy import external_link_error
        from Family.Targets.CxetFamilyTargetInventory import ROLE_BENCH, ROLE_PRODUCTION
        from dataclasses import replace
        instances = self.registered_instances_fixture("parser-bench-native-fix", benchmark=True)
        declaration = next(item for item in instances if item.body.command.name == "add_executable")
        use = next(item for item in instances if item.body.command.name == "target_link_libraries")
        role = ROLE_BENCH
        contexts = SimpleNamespace(context_for_use=lambda source, instance: declaration,
                                   role=lambda source, instance: role)
        self.assertIsNone(external_link_error(use, "parser-bench-native-fix", "OpenSSL::SSL", contexts))
        role = ROLE_PRODUCTION
        self.assertIsNotNone(external_link_error(use, "parser-bench-native-fix", "OpenSSL::SSL", contexts))
        role = ROLE_BENCH
        active = replace(use.body, relative="apps/hft-parser/CMakeLists.txt")
        use = replace(use, body=active, evaluation=active)
        self.assertIsNotNone(external_link_error(use, "parser-bench-native-fix", "OpenSSL::SSL", contexts))


class RootDialectTests(unittest.TestCase):
    def test_system_diagnostic_optimization_cannot_replace_pinned_default(self):
        source = (ROOT / 'CMakeLists.txt').read_text()
        changed = source.replace('set(_CXET_RELEASE_OPTIMIZATION -O3)',
                                 'set(_CXET_RELEASE_OPTIMIZATION -O1)')
        self.assertNotEqual(changed, source)
        errors = []
        validate_root_dialect(parse_commands('CMakeLists.txt', changed, errors), words, errors)
        self.assertTrue(errors)

    def test_gcc12_library_path_cannot_escape_system_diagnostic_guard(self):
        source = (ROOT / 'CMakeLists.txt').read_text()
        path = '  add_link_options(-L/usr/lib/gcc/x86_64-linux-gnu/12)'
        changed = source.replace(path, '') + '\n' + path + '\n'
        self.assertNotEqual(changed, source)
        errors = []
        validate_root_dialect(parse_commands('CMakeLists.txt', changed, errors), words, errors)
        self.assertTrue(errors)

    def test_current_root_dialect_accepts_actual_owner_configuration(self):
        errors = []
        source = (ROOT / "CMakeLists.txt").read_text()
        profiles = resolve_root_profile_caches((ROOT / "tools/Build/CompileTargets.py").read_text(), errors)
        validate_root_dialect(parse_commands("CMakeLists.txt", source, errors), words, errors,
                              profiles=profiles)
        self.assertEqual(errors, [], '\n'.join(dict.fromkeys(errors))[:16000])

    def test_vendor_invocation_contract_survives_comment_line_drift(self):
        source = "# irrelevant line shift\n" + (ROOT / "CMakeLists.txt").read_text()
        errors = []
        commands = parse_commands("CMakeLists.txt", source, errors)
        validate_root_vendor_contract(commands, errors, frozenset(command.offset for command in commands))
        self.assertEqual(errors, [])

    def test_vendor_pic_reset_cannot_be_removed(self):
        source = (ROOT / "CMakeLists.txt").read_text().replace(
            "set(CMAKE_POSITION_INDEPENDENT_CODE OFF)", "")
        errors = []
        commands = parse_commands("CMakeLists.txt", source, errors)
        validate_root_vendor_contract(commands, errors, frozenset(command.offset for command in commands))
        self.assertTrue(errors)

    def test_vendor_system_headers_cannot_be_disabled(self):
        source = (ROOT / "CMakeLists.txt").read_text().replace(
            "set(ABSL_USE_SYSTEM_INCLUDES ON)", "set(ABSL_USE_SYSTEM_INCLUDES OFF)")
        errors = []
        commands = parse_commands("CMakeLists.txt", source, errors)
        validate_root_vendor_contract(commands, errors, frozenset(command.offset for command in commands))
        self.assertTrue(errors)

    def test_vendor_guard_cannot_be_detached(self):
        source = (ROOT / "CMakeLists.txt").read_text().replace(
            "if(CXET_SECP256K1_NATIVE_OPT)", "if(FALSE)")
        errors = []
        commands = parse_commands("CMakeLists.txt", source, errors)
        validate_root_vendor_contract(commands, errors, frozenset(command.offset for command in commands))
        self.assertTrue(errors)

    def test_thin_lto_cannot_replace_owner_full_lto(self):
        source = (ROOT / "CMakeLists.txt").read_text().replace("-flto=full", "-flto=thin")
        errors = []
        validate_root_dialect(parse_commands("CMakeLists.txt", source, errors), words, errors)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
