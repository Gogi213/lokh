"""Selector activation regressions."""
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

class SelectorActivationTests(ActivationFixture, unittest.TestCase):
    def test_selector_projection_rejects_unproved_exchange_profile_and_changed_source(self):
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        relatives = ("cmake/CxetExchangeSelection.cmake", "cmake/CxetHotOptions.cmake")
        files = {}
        for relative in relatives:
            source = (ROOT / relative).read_text()
            files[relative] = (source, parse_commands(relative, source, []))
        # The adapter must not infer all exchanges from the physical module
        # alone, nor borrow a valid disk hash for substituted parsed input.
        errors = []
        lower_selector_modules(ROOT, files, {"fixture": {}}, errors)
        self.assertTrue(any("no proven all-exchange" in error for error in errors))
        relative = relatives[0]
        changed = dict(files)
        changed[relative] = (files[relative][0], [])
        errors = []
        lower_selector_modules(ROOT, changed, {"fixture": {}}, errors)
        self.assertTrue(any("identity changed" in error for error in errors))

    def test_catalog_reader_counts_only_direct_typed_array_entries(self):
        text = '''const cxet::testing::Case cases[]{
          {"first", +[]{ const char* raw=R"x(Case{"fake", f})x";
            const Other nested[]{ {"fixture", 1} }; }},
          cxet::testing::Case{"second", f},
        }; // Case{"comment", f}
        '''
        self.assertEqual(source_cases(text), ["first", "second"])

    def test_typescript_catalog_keeps_property_identifier_boundary(self):
        self.assertEqual(source_cases(
            '{ hostname: "127.0.0.1", name: "real.case", run: f }',
            typescript=True), ["real.case"])

    def test_current_driver_jobs_cannot_be_rebound_by_a_literal_cache_writer(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
        text = (ROOT / "tools/Build/CompileTargets.py").read_text()
        for value in ("evil", "0", "64"):
            with self.subTest(value=value):
                changed = text.replace("'-DCXET_COMPILE_JOBS=' + str(jobs)",
                                       repr("-DCXET_COMPILE_JOBS=" + value))
                self.assertNotEqual(changed, text)
                errors = []
                self.assertEqual(resolve_root_profile_caches(changed, errors), {})
                self.assertTrue(errors)

    def test_successful_vetron_driver_selects_prepared_compiler_only_for_compile(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
        errors = []
        profiles = resolve_root_profile_caches(
            (ROOT / "tools/Build/CompileTargets.py").read_text(), errors)
        self.assertEqual(errors, [])
        cache = profiles["compile:vetron:essential:0:0:0"]
        self.assertEqual(cache["VETRON_EMXX_EXECUTABLE"],
            "__CXET_REPOSITORY_ROOT__/build/toolchains/emsdk-6.0.9/upstream/emscripten/em++")
        self.assertNotIn("VETRON_EMXX_EXECUTABLE", profiles["offline:vetron:release"])

    def test_vetron_compiler_append_requires_exact_successful_query(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
        text = (ROOT / "tools/Build/CompileTargets.py").read_text()
        append = "argv.append('-DVETRON_EMXX_EXECUTABLE=' + emxx)"
        for changed in (text.replace(append, "pass"),
                        text.replace(append, "argv.append('-DVETRON_EMXX_EXECUTABLE=' + owner)"),
                        text.replace("if owner == 'vetron':", "if owner != 'vetron':")):
            with self.subTest(change=changed[-100:]):
                self.assertNotEqual(changed, text)
                errors = []
                self.assertEqual(resolve_root_profile_caches(changed, errors), {})
                self.assertTrue(errors)

    def test_configure_prefix_cannot_rebind_profile_inputs(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
        text = (ROOT / "tools/Build/CompileTargets.py").read_text()
        for writer in ("portable = True", "owner = 'vetron'", "tests = True", "force = True", "jobs = 4"):
            with self.subTest(writer=writer):
                changed = _insert_before_configure_argv(text, writer)
                self.assertNotEqual(changed, text)
                errors = []
                self.assertEqual(len(resolve_root_profile_caches(changed, errors)), 0)
                self.assertTrue(errors)

    def test_vetron_compiler_append_before_list_is_not_profile_evidence(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches
        text = (ROOT / "tools/Build/CompileTargets.py").read_text()
        append = "    argv.append('-DVETRON_EMXX_EXECUTABLE=' + emxx)"
        changed = _insert_before_configure_argv(text.replace(append, "    pass"), append.strip())
        self.assertNotEqual(changed, text)
        errors = []
        self.assertEqual(len(resolve_root_profile_caches(changed, errors)), 0)
        self.assertTrue(errors)

    def test_prepared_wasm_absence_and_incomplete_data_remain_distinct(self):
        from CMake.Root.CmakeFamilyRootProfilePolicy import prepared_wasm_selection
        fixture_root = ROOT / "build/agent-tmp"
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as directory:
            fixture = Path(directory)
            for relative in ("cmake/CxetToolchain.cmake",
                             "tools/Toolchain/BootstrapEmscripten.py"):
                path = fixture / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / relative).read_bytes())
            errors = []
            self.assertIsNone(prepared_wasm_selection(fixture, errors))
            self.assertEqual(errors, [])
            (fixture / "build/toolchains/emsdk-6.0.9").mkdir(parents=True)
            errors = []
            self.assertIsNone(prepared_wasm_selection(fixture, errors))
            self.assertTrue(any("unsupported prepared WASM" in error for error in errors))

    def test_configure_target_visibility_keeps_directory_catalog_local(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types
        from CMake.Flow.CmakeFamilyState import configure_targets_before, directory_targets_before
        declarations = [
            self._declaration("provider", ("STATIC", "Main.cpp"), "provider", 1),
            self._declaration("provider::api", ("ALIAS", "provider"), "provider", 2),
            self._declaration("vendor", ("STATIC", "IMPORTED", "GLOBAL"), "provider", 3),
            self._declaration("private_import", ("STATIC", "IMPORTED"), "provider", 4),
            self._declaration("own", ("STATIC", "Main.cpp"), "consumer", 6),
            self._declaration("future", ("STATIC", "Main.cpp"), "consumer", 9),
        ]
        use = SimpleNamespace(scope="consumer", directory=("consumer",), ordinal=8)
        types = directory_target_types(declarations, shared_namespace=True,
            live_eof_paths={"provider": ((),), "consumer": ((),)})
        self.assertEqual(set(directory_targets_before(types, use)), {"own"})
        self.assertEqual(set(configure_targets_before(types, use)),
            {"provider", "provider::api", "vendor", "own"})
        independent = directory_target_types(declarations)
        self.assertEqual(configure_targets_before(independent, use), {})

    def test_current_strategy_fold_and_generated_spelling_are_exact(self):
        text = (ROOT / "apps/trading-core/CMakeLists.txt").read_text()
        errors = []
        commands = parse_commands("apps/trading-core/CMakeLists.txt", text, errors)
        from CMake.Flow.CmakeFamilyGraph import cmake_list_words
        validate_registration_predicate(commands, cmake_list_words, errors)
        self.assertEqual(errors, [])
        active = SimpleNamespace(source_base=Path("apps/trading-core"), binary_base=Path("apps/trading-core"))
        self.assertTrue(all(typed_generated_source("trading_core_strategy", active, value) for value in registry_outputs()))
        self.assertFalse(typed_generated_source("trading_core_strategy", active,
            "__CXET_CMAKE_BINARY__/apps/trading-core/generated/trading_core/Strategy/UnknownFuture.cpp"))

    def test_strategy_selection_discovery_refuses_escape_and_unbounded_inputs(self):
        relative = 'apps/trading-core/CMakeLists.txt'
        original = (ROOT / relative).read_text()
        unknown = 'message(FATAL_ERROR "Unknown TRADING_CORE_STRATEGY_SELECTION strategy: ${strategy_name}")'
        invalid = [
            'if(UNKNOWN_GUARD)\n' + original + '\nendif()',
            original.replace('trader/*/Strategy.hpp', 'trader/*/*.hpp', 1),
            original.replace('${strategy_dir}/*.ipp', '/tmp/*.ipp', 1),
            original.replace('list(REMOVE_DUPLICATES TRADING_CORE_UNIQUE_SELECTED_STRATEGY_NAMES)', '', 1),
            original.replace(unknown, 'message(STATUS "ignored unknown strategy")', 1),
            original.replace('elseif(NOT TRADING_CORE_STRATEGY_SELECTION STREQUAL "all")', 'else()', 1),
            original.replace('list(APPEND TRADING_CORE_STRATEGY_HEADERS "${strategy_header}")',
                             'list(APPEND TRADING_CORE_STRATEGY_HEADERS "/tmp/foreign/Strategy.hpp")', 1),
            original.replace('file(MAKE_DIRECTORY "${TRADING_CORE_GENERATED_DIR}/trading_core/Strategy")',
                             'list(APPEND TRADING_CORE_STRATEGY_HEADERS "/tmp/foreign/Strategy.hpp")\n'
                             'file(MAKE_DIRECTORY "${TRADING_CORE_GENERATED_DIR}/trading_core/Strategy")', 1),
            original.replace('foreach(strategy_header IN LISTS TRADING_CORE_ALL_STRATEGY_HEADERS)',
                             'while(TRUE)', 1).replace('endforeach()', 'endwhile()', 1),
        ]
        for changed in invalid:
            with self.subTest(change=changed[:80]):
                self.assertNotEqual(changed, original)
                errors = []
                commands = parse_commands(relative, changed, errors)
                self.assertEqual(validate_registration_predicate(commands, cmake_list_words, errors), ())
                self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
