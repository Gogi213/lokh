"""Parser recipes regressions."""
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

class ParserRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_parser_local_test_instrument_requires_its_active_registered_producer(self):
        from dataclasses import replace
        from Family.Profile.CxetFamilyActivation import offline_owner
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        from CMake.Syntax.CmakeFamilyDialect import validate_active_dialect
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instrument_context
        from CMake.Policy.CmakeFamilyBenchmarkRecipe import BENCHMARK_ROOTS
        from Family.Profile.CxetFamilyBenchmarkActivation import lower_benchmark_registrations
        checker = _ownership_checker_for_harness()
        errors = []
        configurations = owner_activation(ROOT, errors)
        files = checker.cmake_files(errors)
        for relative, (source, commands) in tuple(files.items()):
            if offline_owner(relative) is not None:
                files[relative] = (source, lower_offline_registrations(ROOT, relative, commands, errors))
            elif relative in BENCHMARK_ROOTS:
                files[relative] = (source, lower_benchmark_registrations(ROOT, relative, commands, errors))
        self.assertEqual(errors, [])
        for local_tests in (0, 1):
            with self.subTest(local_tests=local_tests):
                roots, initial = configurations[f"compile:hft-parser:essential:0:0:{local_tests}"]
                selected, initial = lower_selector_modules(ROOT, files, initial, errors)
                active = compose_active_commands(ROOT, selected, roots,
                    checker.APPROVED_EXTERNAL_SUBDIRECTORIES, errors, initial_values_by_scope=initial)
                validate_active_dialect(active, set(function_model(active, errors).global_definitions),
                    cmake_list_words, errors)
                self.assertEqual(errors, [])
                instruments = [item for item in active if item.command.name == "cxet_offline_instrument"
                    and item.relative == "apps/hft-parser/tests/offline/CMakeLists.txt"]
                self.assertEqual(len(instruments), local_tests)
                if not local_tests:
                    continue
                instrument = instruments[0]
                registration = instrument.command.registration
                declaration = next(item for item in active if item.command.name == "add_executable"
                    and getattr(item.command, "registration", None) is registration)
                self.assertTrue(offline_instrument_context(instrument, active))
                for changed in (
                        replace(instrument, command=replace(instrument.command, registration=None)),
                        replace(instrument, command=replace(instrument.command,
                            registration=replace(registration))),
                        replace(instrument, command=replace(instrument.command, body="cxet_lib")),
                        replace(instrument, command=replace(instrument.command, body="${foreign_target}")),
                        replace(instrument, source_base=Path("apps/trader")),
                        replace(instrument, binary_base=Path("apps/trader")),
                        replace(instrument, scope="compile:hft-parser:essential:0:0:0"),
                        replace(instrument, execution_chain=((("foreign",), instrument.relative),))):
                    rejected = []
                    mutated = [changed if item is instrument else item for item in active]
                    validate_active_dialect(mutated,
                        set(function_model(mutated, rejected).global_definitions), cmake_list_words, rejected)
                    self.assertTrue(any("unapproved offline instrumentation" in item for item in rejected))
                for mutated in (
                        [item for item in active if item is not declaration],
                        [replace(item, ordinal=instrument.ordinal + 1) if item is declaration else item
                         for item in active]):
                    self.assertFalse(offline_instrument_context(instrument, mutated))

    def test_parser_launcher_scripts_and_properties_keep_exact_cold_guarded_recipe(self):
        from dataclasses import replace
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        from CMake.Policy.CmakeFamilyOfflineRecipe import parser_launcher_test_recipe
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        checker = _ownership_checker_for_harness()
        errors = []
        roots, initial = owner_activation(ROOT, errors)["compile:hft-parser:essential:0:0:1"]
        files, initial = lower_selector_modules(ROOT, checker.cmake_files(errors), initial, errors)
        active = compose_active_commands(ROOT, files, roots,
            checker.APPROVED_EXTERNAL_SUBDIRECTORIES, errors, initial_values_by_scope=initial)
        self.assertEqual(errors, [])
        recipes = [item for item in active if item.relative == "apps/hft-parser/tests/offline/CMakeLists.txt"
            and (item.command.name == "add_test" and "launcher-storage-authority.py" in item.command.body or
                 item.command.name == "set_tests_properties")]
        self.assertEqual(len(recipes), 5)
        for item in recipes:
            groups = tuple((word.replace("${CMAKE_CURRENT_SOURCE_DIR}", item.source_base.as_posix()),)
                for word in cmake_list_words(item.command.body))
            instance = InstantiatedCommand(item, item, groups, item.ordinal, ALL_PATHS)
            self.assertTrue(parser_launcher_test_recipe(instance))
            for changed in (replace(item, structural_context=()),
                            replace(item, source_base=Path("apps/trader")),
                            replace(item, command=replace(item.command, body=item.command.body + " extra"))):
                self.assertFalse(parser_launcher_test_recipe(replace(instance, body=changed, evaluation=changed)))
            with patch("CMake.Flow.CmakeFamilyExecutionIdentity.reviewed_file_identity", return_value=False):
                self.assertFalse(parser_launcher_test_recipe(instance))

    def test_full_parser_family_current_dialect_keeps_exact_package_and_instrument_boundaries(self):
        from dataclasses import replace
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        from CMake.Syntax.CmakeFamilyDialect import validate_active_dialect, validate_exact_active_inventory
        from CMake.Policy.CmakeFamilyLoopPolicy import validate_loop_writer_boundary
        checker = _ownership_checker_for_harness()
        errors = []
        roots, initial = owner_activation(ROOT, errors)["compile:hft-parser:full:0:0:0"]
        files = checker.cmake_files(errors)
        # The main checker lowers this selected nested helper before composing
        # the production roots. Other owners' offline roots are not selected.
        relative = "apps/trading-core/capital/CMakeLists.txt"
        source, commands = files[relative]
        files[relative] = (source, lower_offline_registrations(ROOT, relative, commands, errors))
        files, initial = lower_selector_modules(ROOT, files, initial, errors)
        active = compose_active_commands(ROOT, files, roots, checker.APPROVED_EXTERNAL_SUBDIRECTORIES,
            errors, initial_values_by_scope=initial)
        validate_loop_writer_boundary(active, errors)
        validate_active_dialect(active, set(function_model(active, errors).global_definitions), cmake_list_words, errors)
        validate_exact_active_inventory(active, cmake_list_words, errors,
            active_origins=frozenset(item.relative for item in active))
        self.assertEqual(errors, [])
        pkg = next(item for item in active if item.command.name == "pkg_check_modules")
        qt = next(item for item in active if item.command.name == "find_package" and
                  cmake_list_words(item.command.body)[:1] == ["Qt6"])
        instrument = next(item for item in active if item.command.name == "cxet_offline_instrument")
        for original, changed in (
                (pkg, replace(pkg, command=replace(pkg.command, body="ZSTD QUIET IMPORTED_TARGET foreign"))),
                (pkg, replace(pkg, structural_context=())),
                (pkg, replace(pkg, source_base=Path("apps/trader"))),
                (qt, replace(qt, command=replace(qt.command, body=qt.command.body + " Widgets"))),
                (qt, replace(qt, structural_context=())),
                (instrument, replace(instrument, command=replace(instrument.command, body="${foreign_target}"))),
                (instrument, replace(instrument, structural_context=()))):
            errors = []
            mutated = [changed if item is original else item for item in active]
            validate_active_dialect(mutated, set(function_model(mutated, errors).global_definitions), cmake_list_words, errors)
            validate_exact_active_inventory(mutated, cmake_list_words, errors,
                active_origins=frozenset(item.relative for item in mutated))
            self.assertTrue(errors)

    def test_parser_reference_storage_refuses_history_or_missing_transport_edges(self):
        from Family.Targets.CxetFamilyMayMustGraph import validate_direct_and_transitive_contracts
        storage = "hftp_reference_storage"
        retained = {"hftp_backend_headers", "hftp_contracts", "cxet_lib",
                    "hftp_local_data_plane", "hftp_transport"}
        for may, must, accepted in (
                (retained, retained, True),
                (retained | {"hftp_history"}, retained | {"hftp_history"}, False),
                (retained - {"hftp_transport"}, retained - {"hftp_transport"}, False),
                (retained, retained - {"hftp_transport"}, False)):
            errors = []
            validate_direct_and_transitive_contracts(
                SimpleNamespace(may={storage: may}, must={storage: must}), errors,
                active_origins={"apps/hft-parser/cmake/HftpLibraries.cmake"})
            storage_errors = [error for error in errors
                              if error.startswith(f"target {storage}:")]
            self.assertEqual(not storage_errors, accepted, storage_errors)

    def test_parser_install_uses_exact_current_conditional_process_inventory(self):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyFlow import InstantiatedCommand
        from CMake.Policy.CmakeFamilyRegistrationPolicy import _install
        relative = "apps/hft-parser/cmake/HftpProcesses.cmake"
        processes = ("hft-parserd", "hft-algosd", "hft-resource-planner")
        active = ActiveCommand("fixture", relative, Path("apps/hft-parser"), Path("apps/hft-parser"),
            (relative,), Command("install", "", 1), 0)
        for selection, selected, accepted in (
                (("OFF",), processes, True), (("ON",), (*processes, "hft-finam-metadata-store"), True),
                (("ON",), processes, False), (("OFF",), (*processes, "hft-finam-metadata-store"), False),
                (("OFF",), (*processes, "hft-zcrx-functional-probe"), False),
                (("OFF",), processes[:-1], False), (("${unknown}",), processes, False),
                (("ON", "OFF"), processes, False), (None, processes, False)):
            instance = InstantiatedCommand(active, active, tuple((value,) for value in
                ("TARGETS", *selected, "RUNTIME", "DESTINATION", "${CMAKE_INSTALL_BINDIR}")), 0, ((),))
            errors = []
            snapshots = SimpleNamespace(values={0: {"CXET_EXCHANGE_FINAM": selection}})
            _install(instance, errors, snapshots)
            self.assertEqual(not errors, accepted, errors)


if __name__ == '__main__':
    unittest.main()
