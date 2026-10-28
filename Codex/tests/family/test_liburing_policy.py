"""Liburing policy regressions."""
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

class LiburingPolicyModelTests(unittest.TestCase):
    @staticmethod
    def _core(text=None):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        relative = "src/src/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative, text if text is not None else
            (ROOT / relative).read_text(), errors)
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        if errors:
            raise AssertionError(errors)
        return [ActiveCommand(relative, relative, Path("src/src"), Path("src/src"),
            (relative,), command, ordinal, context)
            for ordinal, (command, context) in enumerate(zip(commands, contexts))]

    def _program_selection(self, rows):
        from CMake.Policy.CmakeFamilyProgramPolicy import ProgramClearance, apply_find_program
        variable = "CXET_LIBURING_CC"
        clearance = ProgramClearance()
        state = {variable: ("/tmp/foreign",)}
        cache = {variable: ("/tmp/foreign-cache",)}
        errors = []
        clearance.cache_clear(rows[0], variable, state, cache, errors)
        clearance.normal_clear(rows[1], variable, state, errors)
        active = rows[2]
        apply_find_program(cmake_list_words(active.command.body), active.relative, state,
            lambda raw, *_args: raw, lambda values: list(values), errors,
            f"{active.relative}:{active.command.line}", clearance.ready(active, variable))
        return state, cache, errors

    def _clearance_rows(self, text=None):
        return [active for active in self._core(text) if active.command.name in
            {"unset", "find_program"} and
            cmake_list_words(active.command.body)[:1] == ["CXET_LIBURING_CC"]]

    def test_current_clearance_and_semantic_line_drift_reject_preseeds(self):
        from CMake.Policy.CmakeFamilyProgramPolicy import reviewed_program
        text = (ROOT / "src/src/CMakeLists.txt").read_text()
        for source in (text, "# harmless line drift\n\n" + text):
            with self.subTest(drift=source is not text):
                state, cache, errors = self._program_selection(self._clearance_rows(source))
                self.assertEqual(errors, [])
                self.assertEqual(cache, {})
                self.assertEqual(state["CXET_LIBURING_CC"], (reviewed_program("clang"),))

    def test_clearance_requires_exact_context_owner_order_and_program(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import Command
        rows = self._clearance_rows()
        mutants = (
            [replace(active, structural_context=()) for active in rows],
            [replace(active, source_base=Path("apps/trader")) for active in rows],
            [rows[0], rows[1], replace(rows[2], ordinal=rows[2].ordinal + 1)],
            [rows[0], rows[1], replace(rows[2], command=Command("find_program",
                "CXET_LIBURING_CC NAMES gcc REQUIRED", rows[2].command.line))],
            [rows[1], rows[0], rows[2]],
        )
        for index, changed in enumerate(mutants):
            with self.subTest(index=index):
                _, _, errors = self._program_selection(changed)
                self.assertTrue(errors)

    def test_jobs_cache_default_is_only_one_core_string_without_force(self):
        from CMake.Policy.CmakeFamilyCachePolicy import approved_direct_cache_set
        from CMake.Policy.CmakeFamilySetPolicy import parse_variable_signature
        command = next(active.command for active in self._core() if active.command.name == "set"
            and cmake_list_words(active.command.body)[:1] == ["CXET_COMPILE_JOBS"])
        words = cmake_list_words(command.body)
        def signature(tokens):
            errors = []
            result = parse_variable_signature("set", tokens, lambda values: list(values), errors, "fixture")
            self.assertEqual(errors, [])
            return result
        self.assertTrue(approved_direct_cache_set("src/src/CMakeLists.txt", signature(words)))
        for relative, tokens in (
                ("apps/trader/CMakeLists.txt", words),
                ("src/src/CMakeLists.txt", [words[0], "2", *words[2:]]),
                ("src/src/CMakeLists.txt", [*words, "FORCE"]),
                ("src/src/CMakeLists.txt", [words[0], "${foreign}", *words[2:]])):
            with self.subTest(relative=relative, tokens=tokens):
                self.assertFalse(approved_direct_cache_set(relative, signature(tokens)))

    def _vendor_errors(self, text=None, viable=None):
        from CMake.Policy.CmakeFamilyVendorPolicy import _validate_liburing_producer
        core = self._core(text)
        errors = []
        _validate_liburing_producer(core, viable if viable is not None else
            frozenset(active.ordinal for active in core), errors)
        return errors

    def test_current_output_recipe_and_inactive_flag_arms_are_valid(self):
        self.assertEqual(self._vendor_errors(), [])
        viable = frozenset(active.ordinal for active in self._core() if not any(
            frame.opener in {("CXET_LTO",), ("CXET_SELECTED_LLD",)} or
            frame.arm.kind == "else" and "CMAKE_C_COMPILER_ID" in frame.opener
            for frame in active.structural_context) and not (
                active.command.name == "message" and
                "Vendored liburing is required" in active.command.body))
        self.assertEqual(self._vendor_errors(viable=viable), [])

    def test_state_flags_clean_environment_and_jobs_mutants_fail_closed(self):
        text = (ROOT / "src/src/CMakeLists.txt").read_text()
        mutations = (
            ('set(_CXET_LIBURING_CFLAGS "${CMAKE_C_FLAGS_RELEASE}")',
             'set(_CXET_LIBURING_CFLAGS "${CMAKE_C_FLAGS}")'),
            ('if(CXET_LTO)\n    string(APPEND _CXET_LIBURING_CFLAGS',
             'if(UNKNOWN_LTO)\n    string(APPEND _CXET_LIBURING_CFLAGS'),
            ('"AR=${CMAKE_AR}"', '"AR=/usr/bin/ar"'),
            ('"PATH=/usr/bin:/bin"', '"PATH=/tmp:/usr/bin:/bin"'),
            ('"-fuse-ld=${CXET_SELECTED_LLD}"', '"-fuse-ld=/tmp/foreign"'),
            ('set(CXET_COMPILE_JOBS 1 CACHE STRING', 'set(CXET_COMPILE_JOBS 2 CACHE STRING'),
            ('set(CXET_COMPILE_JOBS 1 CACHE STRING "Private compile driver job count")',
             'if(UNKNOWN_JOBS)\nset(CXET_COMPILE_JOBS 1 CACHE STRING "Private compile driver job count")\nendif()'),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                changed = text.replace(before, after, 1)
                self.assertNotEqual(changed, text)
                self.assertTrue(self._vendor_errors(changed))

    def test_output_metadata_import_dependency_and_fatal_closure_are_exact(self):
        text = (ROOT / "src/src/CMakeLists.txt").read_text()
        mutations = (
            ('add_custom_command(OUTPUT "${CXET_LIBURING_ARCHIVE}" "${CXET_LIBURING_HEADER}"',
             'add_custom_command(OUTPUT "${CXET_LIBURING_ARCHIVE}"'),
            ('add_custom_target(cxet_liburing_ep\n    DEPENDS "${CXET_LIBURING_ARCHIVE}" "${CXET_LIBURING_HEADER}")',
             'add_custom_target(cxet_liburing_ep\n    DEPENDS "${CXET_LIBURING_ARCHIVE}")'),
            ('CXET_COMPILE_OUTPUTS "${CXET_LIBURING_ARCHIVE};${CXET_LIBURING_HEADER}"',
             'CXET_COMPILE_OUTPUTS "${CXET_LIBURING_ARCHIVE}"'),
            ('add_library(liburing::uring STATIC IMPORTED GLOBAL)',
             'add_library(liburing::uring SHARED IMPORTED GLOBAL)'),
            ('add_dependencies(cxet_lib cxet_liburing_ep)', 'set(_missing_liburing_dependency OFF)'),
            ('message(FATAL_ERROR "Vendored liburing is required',
             'message(WARNING "Vendored liburing is required'),
        )
        for before, after in mutations:
            with self.subTest(after=after):
                changed = text.replace(before, after, 1)
                self.assertNotEqual(changed, text)
                self.assertTrue(self._vendor_errors(changed))


if __name__ == '__main__':
    unittest.main()
