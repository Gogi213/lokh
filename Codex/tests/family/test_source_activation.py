"""Source activation regressions."""
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

class SourceActivationTests(ActivationFixture, unittest.TestCase):
    def test_diagnostic_owner_has_only_core_finance_and_own_source_roots(self):
        errors = []
        configurations = owner_activation(ROOT, errors)
        self.assertEqual(errors, [])
        for family in ("essential", "full"):
            roots, _ = configurations[f"compile:diagnostic:{family}:0:0:0"]
            self.assertEqual(set(roots), {
                "src/src/CMakeLists.txt", "apps/trading-core/CMakeLists.txt", "apps/diagnostic/CMakeLists.txt"})
        roots, _ = configurations["offline:diagnostic:release"]
        self.assertEqual(set(roots), {
            "src/src/CMakeLists.txt", "apps/diagnostic/CMakeLists.txt",
            "apps/trading-core/CMakeLists.txt",
            "apps/diagnostic/tests/offline/CMakeLists.txt"})

    def test_real_suite_lowers_sources_links_and_registered_cases(self):
        relative = "src/tests/offline/CMakeLists.txt"
        text = (ROOT / relative).read_text()
        errors = []
        commands = parse_commands(relative, text, errors)
        lowered = lower_offline_registrations(ROOT, relative, commands, errors)
        self.assertEqual(errors, [])
        self.assertTrue(any(command.name == "add_executable" and "DecodeTransactions.cpp" in command.body for command in lowered))
        self.assertTrue(any(command.name == "target_link_libraries" and "cxet::read_only_contracts" in command.body for command in lowered))
        self.assertEqual(sum(command.name == "add_test" and "cxet_offline_decode --case" in command.body for command in lowered), 50)

    def test_dormant_guarded_source_root_is_not_activated(self):
        errors = []
        graph = (ROOT / "cmake/CxetCompileGraph.cmake").read_text()
        graph += '\nif(CXET_OFFLINE_BENCHMARKS)\nadd_subdirectory(src/benchmarks/offline EXCLUDE_FROM_ALL)\nendif()\n'
        roots = source_profile_roots(graph, {"CXET_BUILD_OWNER": "CXETCPP", "CXET_LOCAL_TESTS": "OFF",
            "CXET_FAMILY_PROFILE": "essential", "CXET_OFFLINE_BENCHMARKS": "OFF"}, errors)
        self.assertEqual(errors, [])
        self.assertNotIn("src/benchmarks/offline/CMakeLists.txt", roots)

    def test_provider_roots_have_one_actual_reachable_source_profile(self):
        errors = []
        configurations = owner_activation(ROOT, errors)
        self.assertEqual(errors, [])
        roots, values = configurations["compile:hft-parser:essential:0:0:0"]
        self.assertEqual(values["apps/hft-parser/CMakeLists.txt"]["CXET_BUILD_OWNER"], ("hft-parser",))
        self.assertEqual(values["apps/trader/CMakeLists.txt"]["CXET_BUILD_OWNER"], ("hft-parser",))
        _, trader_values = configurations["compile:trader:essential:0:0:0"]
        self.assertEqual(trader_values["apps/hft-parser/CMakeLists.txt"]["CXET_BUILD_OWNER"], ("trader",))
        self.assertNotIn("apps/hft-recorder/CMakeLists.txt", roots)
        _, recorder_values = configurations["offline:hft-recorder:release"]
        self.assertEqual(recorder_values["apps/hft-recorder/src/Contracts/CMakeLists.txt"]["CXET_BUILD_OWNER"], ("hft-recorder",))
        self.assertEqual(recorder_values["apps/hft-recorder/src/Contracts/CMakeLists.txt"]["CXET_LOCAL_TESTS"], ("ON",))

    def test_unknown_source_guard_cannot_create_an_edge(self):
        errors = []
        roots = source_profile_roots('if(EXISTS /unknown)\nadd_subdirectory(src/foreign EXCLUDE_FROM_ALL)\nendif()', {}, errors)
        self.assertEqual(roots, {})
        self.assertTrue(any("unsupported" in error for error in errors))

    def test_case_catalog_expands_only_direct_literal_sibling_fragments(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Cases.cpp"
            fragment = Path(directory) / "Entries.ipp"
            source.write_text('const Case cases[]{\n#include "Entries.ipp"\n};')
            fragment.write_text('Case{"real.case", +[]{const char* s=R"x(Case{"fake", f})x";}},')
            self.assertEqual(source_cases("", source=source), ["real.case"])
            for include, contents in (
                    ('#include "../Entries.ipp"', 'Case{"escaped", f},'),
                    ('#include "Entries.ipp"\n#include "Entries.ipp"', 'Case{"duplicate", f},'),
                    ('#include "Entries.ipp"', '#include "Entries.ipp"\n'),
                    ('#if UNKNOWN\n#include "Entries.ipp"\n#endif', 'Case{"conditional", f},')):
                with self.subTest(include=include, contents=contents):
                    source.write_text('const Case cases[]{\n' + include + '\n};')
                    fragment.write_text(contents)
                    with self.assertRaises(ValueError):
                        source_cases("", source=source)

    def test_file_catalog_preserves_existing_source_diagnostic_directives(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "Cases.cpp"
            text = ('const Case cases[]{Case{"existing.case", +[]{\n'
                    '#if DIAGNOSTIC_PROFILE\nconst auto value = 1;\n#endif\n'
                    '#pragma diagnostic push\n}},};')
            source.write_text(text)
            self.assertEqual(source_cases(text), ["existing.case"])
            self.assertEqual(source_cases("", source=source), source_cases(text))
        for relative in (
                "src/tests/offline/Primitives/BytePrimitivesContracts.cpp",
                "src/tests/offline/Primitives/OptionalIdentityPrimitives.cpp",
                "apps/trader/tests/offline/Fleet/TraderCases.cpp"):
            with self.subTest(source=relative):
                source = ROOT / relative
                self.assertEqual(source_cases("", source=source), source_cases(source.read_text()))

    def test_root_resident_fixture_carrier_stays_exact_and_target_scoped(self):
        relative = "apps/trader/tests/offline/CMakeLists.txt"
        fixture = "${CMAKE_SOURCE_DIR}/src/tests/offline/Support/ResidentMemoryFixture.cpp"
        command = next(command for command in parse_commands(relative, (ROOT / relative).read_text(), [])
            if command.name == "cxet_add_offline_suite" and cmake_list_words(command.body)[0] == "trader_offline_cases")
        suite = "cxet_add_offline_suite(" + command.body + ")"
        errors = []
        lower_offline_registrations(ROOT, relative, parse_commands(relative, suite, errors), errors)
        self.assertEqual(errors, [])
        for changed in (suite.replace(fixture, "${CMAKE_SOURCE_DIR}/src/tests/offline/Future.cpp"),
                        suite.replace("trader_offline_cases", "foreign_target")):
            errors = []
            lower_offline_registrations(ROOT, relative, parse_commands(relative, changed, errors), errors)
            self.assertTrue(errors)

    def test_parser_entrypoint_loop_cannot_change_its_literal_catalog_or_command(self):
        relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
        text = (ROOT / relative).read_text()
        for old, new in (
                ("    parser_missing_required_cli\n", ""),
                ("Entrypoints.test_${hftp_entrypoint_case}", "Entrypoints.test_unknown"),
                ("$<TARGET_FILE:hft-resource-planner>", "$<TARGET_FILE:foreign>")):
            changed = text.replace(old, new)
            self.assertNotEqual(changed, text)
            errors = []
            lower_offline_registrations(ROOT, relative, parse_commands(relative, changed, errors), errors)
            self.assertTrue(any("entrypoint" in error for error in errors))

    def test_parser_contract_guard_uses_only_prior_proved_providers(self):
        graph = (ROOT / "cmake/CxetCompileGraph.cmake").read_text()
        for owner in ("hft-backtest", "trader", "vetron", "hft-recorder"):
            for tests in ("ON", "OFF"):
                with self.subTest(owner=owner, tests=tests):
                    errors = []
                    roots = source_profile_roots(graph, {
                        "CXET_BUILD_OWNER": owner, "CXET_LOCAL_TESTS": tests,
                        "CXET_FAMILY_PROFILE": "essential"}, errors)
                    self.assertEqual(errors, [])
                    standalone = owner == "hft-backtest" or (owner == "hft-recorder" and tests == "ON")
                    self.assertEqual("apps/hft-parser/src/Contracts/CMakeLists.txt" in roots, standalone)
                    self.assertEqual("apps/hft-parser/CMakeLists.txt" in roots, not standalone)

    def test_unknown_target_source_guard_stays_unresolved(self):
        errors = []
        roots = source_profile_roots(
            'if(NOT TARGET unknown_provider)\nadd_subdirectory(src/foreign EXCLUDE_FROM_ALL)\nendif()',
            {}, errors)
        self.assertEqual(roots, {})
        self.assertTrue(any("no exact active profile guard" in error for error in errors))

    def test_parser_contract_projection_rejects_changed_provider_evidence(self):
        from Family.Profile import CxetFamilyActivation as activation
        read = activation._read
        for relative, old, new in (
                ("apps/hft-parser/CMakeLists.txt",
                 "add_subdirectory(src/Contracts EXCLUDE_FROM_ALL)",
                 "if(UNKNOWN)\nadd_subdirectory(src/Contracts EXCLUDE_FROM_ALL)\nendif()"),
                ("apps/hft-parser/src/Contracts/CMakeLists.txt",
                 "add_library(hftp_contract_headers INTERFACE)",
                 "add_library(hftp_contract_headers STATIC Foreign.cpp)")):
            with self.subTest(relative=relative):
                def changed(root, path):
                    text = read(root, path)
                    if path == relative:
                        self.assertIn(old, text)
                        return text.replace(old, new)
                    return text
                errors = []
                with patch.object(activation, "_read", side_effect=changed):
                    source_profile_roots('add_subdirectory(apps/hft-parser EXCLUDE_FROM_ALL)', {}, errors)
                self.assertTrue(any("Parser contract provider" in error for error in errors))

    def test_future_unreviewed_header_still_fails_closed(self):
        read = surface._relative_files
        for future in ("cxet/UnknownFuture/Transport.hpp", "cxet/Os/FutureTransport.hpp",
                       "cxet/Order/FutureSubmission.hpp"):
            def injected(root, relative, errors):
                files = read(root, relative, errors)
                if relative == surface._CORE_INCLUDE:
                    files[future] = ROOT / relative / "cxet/Market/Depth.hpp"
                return files
            errors = []
            with patch.object(surface, "_relative_files", side_effect=injected):
                surface.validate_read_only_physical_surfaces(ROOT, errors)
            self.assertTrue(any(future in error and "unreviewed" in error for error in errors))

    def test_normalized_data_headers_export_through_the_real_contract_interface(self):
        errors = []
        inventory = compiler_visible_header_inventory(ROOT, {
            "cxet_read_only_contracts": ("src/src/Contracts/include",)}, errors)
        exports = exported_header_targets(inventory)
        for header in ("InstrumentInfoRow.hpp", "Ticker24hRow.hpp"):
            relative = "src/src/Contracts/include/cxet/Primitives/Composite/" + header
            self.assertEqual(exports[relative], frozenset({"cxet_read_only_contracts"}))

    def test_real_build_interface_source_carrier_keeps_contract_exports(self):
        evaluation = SimpleNamespace(source_base=Path("src/src"))
        body = SimpleNamespace(relative="src/src/CMakeLists.txt", command=SimpleNamespace(
            body="cxet_read_only_contracts PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/Contracts/include>"))
        instance = SimpleNamespace(body=body, evaluation=evaluation,
            token_groups=(("cxet_read_only_contracts",), ("PUBLIC",)))
        self.assertEqual(_include_value(instance, "$<BUILD_INTERFACE:src/src/Contracts/include>"),
                         ("repo", "src/src/Contracts/include"))
        body.command.body = "cxet_read_only_contracts PUBLIC $<BUILD_INTERFACE:src/src/Contracts/include>"
        self.assertIsNone(_include_value(instance, "$<BUILD_INTERFACE:src/src/Contracts/include>"))

    def test_standard_headers_keep_closed_allowlist(self):
        self.assertTrue(approved_external_angle_include("tuple"))
        self.assertTrue(approved_external_angle_include("variant"))
        self.assertFalse(approved_external_angle_include("unknown_future_external.hpp"))


if __name__ == '__main__':
    unittest.main()
