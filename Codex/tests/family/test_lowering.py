"""Lowering regressions."""
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

class LoweringModelTests(unittest.TestCase):
    def _commands(self, relative):
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        self.assertEqual(errors, [])
        return commands

    def _lower(self, relative, commands):
        errors = []
        lowered = lower_offline_registrations(ROOT, relative, commands, errors)
        return lowered, errors

    def test_literal_instrument_call_keeps_its_existing_diagnostic_target(self):
        relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
        commands = self._commands(relative)
        selected = [command for command in commands if
            command.name == "cxet_add_offline_diagnostic" and
            cmake_list_words(command.body)[0] == "hftp_public_handoff_thread" or
            command.name == "cxet_offline_instrument"]
        lowered, errors = self._lower(relative, selected)
        self.assertEqual(errors, [])
        instrument = next(command for command in lowered if command.name == "cxet_offline_instrument")
        declaration = next(command for command in lowered if command.name == "add_executable")
        self.assertEqual((instrument.name, instrument.body, instrument.line),
            (selected[-1].name, selected[-1].body, selected[-1].line))
        self.assertIs(instrument.registration, declaration.registration)

    def test_instrument_cannot_use_dynamic_foreign_or_repeated_target(self):
        relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
        diagnostic = next(command for command in self._commands(relative) if
            command.name == "cxet_add_offline_diagnostic")
        for text in ("cxet_offline_instrument(${foreign})",
                     "cxet_offline_instrument(foreign)",
                     "cxet_offline_instrument(hftp_public_handoff_thread)\n"
                     "cxet_offline_instrument(hftp_public_handoff_thread)"):
            with self.subTest(text=text):
                errors = []
                extra = parse_commands(relative, text, errors)
                _, errors = self._lower(relative, [diagnostic, *extra])
                self.assertTrue(errors)

    def test_instrument_cannot_escape_its_registered_declaration_guard(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_instrument_context
        relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
        diagnostic = next(command for command in self._commands(relative) if
            command.name == "cxet_add_offline_diagnostic")
        text = ("if(CXET_SELECTION_ALL)\n" + diagnostic.name + "(" + diagnostic.body + ")\n"
                "cxet_offline_instrument(hftp_public_handoff_thread)\nendif()")
        errors = []
        commands = parse_commands(relative, text, errors)
        lowered, errors = self._lower(relative, commands)
        active = compose_active_commands(ROOT, {relative: (text, lowered)}, (relative,), set(), errors)
        self.assertEqual(errors, [])
        instrument = next(item for item in active if item.command.name == "cxet_offline_instrument")
        self.assertTrue(offline_instrument_context(instrument, active))
        self.assertFalse(offline_instrument_context(replace(instrument, structural_context=()), active))

    def _workspace_commands(self):
        relative = "apps/vetron/tests/offline/CMakeLists.txt"
        commands = self._commands(relative)
        first = next(index for index, command in enumerate(commands) if command.name == "set")
        return relative, commands[first:]

    def test_workspace_literal_catalog_keeps_complete_finite_loop(self):
        relative, commands = self._workspace_commands()
        lowered, errors = self._lower(relative, commands)
        self.assertEqual(errors, [])
        self.assertEqual(lowered, commands)

    def test_workspace_loop_rejects_dynamic_catalog_or_foreign_body(self):
        relative, commands = self._workspace_commands()
        original = "\n".join(f"{command.name}({command.body})" for command in commands)
        for text in (
                original.replace("test_plain_local_read_bootstrap_requires_exact_browser_request", "${foreign}"),
                original.replace("IN LISTS vetron_workspace_authority_cases", "IN LISTS foreign"),
                original.replace("WorkspaceAuthorityCases.py", "Foreign.py"),
                original.replace("WorkspaceAuthorityCases.${case}", "Foreign.${case}")):
            with self.subTest(text=text):
                errors = []
                changed = parse_commands(relative, text, errors)
                _, errors = self._lower(relative, changed)
                self.assertTrue(errors)

    def test_workspace_catalog_rejects_foreign_class_and_invalid_python(self):
        from Family.Profile import CxetFamilyActivation as activation
        relative, commands = self._workspace_commands()
        actual = activation._read(ROOT, "apps/vetron/tests/offline/Workspace/AuthorityCases.py")
        for source in (actual.replace("class WorkspaceAuthorityCases(unittest.TestCase):",
                                      "class Foreign(unittest.TestCase):"),
                       "class WorkspaceAuthorityCases(:\n"):
            with self.subTest(source=source[:50]):
                with patch.object(activation, "_read", return_value=source):
                    try:
                        _, errors = self._lower(relative, commands)
                    except SyntaxError:
                        self.fail("malformed workspace catalog escaped the fail-closed boundary")
                self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
