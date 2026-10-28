"""Registry recipes regressions."""
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

class RegistryRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_registry_property_source_and_binary_paths_keep_exact_inputs(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyPropertyPolicy import validate_property_command
        properties = [item for item in self._registry_instances() if item.body.command.name == "set_property"]
        self.assertEqual(len(properties), 3)
        for instance in properties:
            errors = []
            validate_property_command(instance, errors)
            self.assertEqual(errors, [], instance.token_groups)
            errors = []
            changed = replace(instance, token_groups=instance.token_groups + (("/tmp/foreign.hpp",),))
            validate_property_command(changed, errors)
            self.assertTrue(errors)

    def test_registry_stamp_and_repair_have_one_each_and_identical_bindings(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyScriptPolicy import validate_invoked_script_policies
        instances = [item for item in self._registry_instances() if item.body.command.name in
                     {"add_custom_command", "add_custom_target"} and
                     any("GenerateStrategyRegistry.cmake" in value
                         for group in item.token_groups for value in group)]
        self.assertEqual(len(instances), 2)
        self.assertFalse(any("${" in value for instance in instances
            for group in instance.token_groups for value in group if value.startswith("-D")))
        for candidates, accepted in ((instances, True), (instances[:1], False),
                                    (instances + instances[1:], False),
                                    ([instances[0], instances[0]], False),
                                    ([instances[0], replace(instances[1], token_groups=tuple(
                                        tuple(value.replace("-DOUT_DIR=", "-DOTHER_DIR=") for value in group)
                                        for group in instances[1].token_groups))], False)):
            errors = []
            with patch("CMake.Policy.CmakeFamilyScriptPolicy._validate_registry") as body:
                validate_invoked_script_policies(candidates, {}, cmake_list_words, errors,
                    active_origins={"apps/trading-core/CMakeLists.txt"})
            self.assertEqual(not errors, accepted, errors)
            if accepted:
                body.assert_called_once()

    def test_registry_current_helper_recipe_binds_script_text_ast_and_output_paths(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyScriptPolicy import _validate_registry
        from CMake.Policy.CmakeFamilyStrategyPolicy import proven_strategy_headers
        from CMake.Policy.CmakeFamilyWritePolicy import approved_file_side_effect
        relative = "apps/trading-core/cmake/GenerateStrategyRegistry.cmake"
        text = (ROOT / relative).read_text()
        defines = {
            "STRATEGY_ROOT": "apps/trading-core/src/Strategy/include/strategy",
            "OUT_DIR": "__CXET_CMAKE_BINARY__/apps/trading-core/generated",
            "STRATEGY_HEADERS": "|".join(sorted(proven_strategy_headers())),
        }
        canonical = parse_commands(relative, text, [])
        errors = []
        _validate_registry(defines, {relative: (text, canonical)}, errors)
        self.assertEqual(errors, [])
        for changed in (
                text.replace('file(WRITE "${path}" "${content}")', 'file(WRITE "/tmp/foreign.hpp" "${content}")'),
                text.replace('write_strategy_registry_if_changed("${OUT_HPP}"', 'write_strategy_registry_if_changed("/tmp/foreign.hpp"'),
                text.replace('${STRATEGY_ROOT}/hft-trader/*/Strategy.hpp', '${STRATEGY_ROOT}/*/Strategy.hpp'),
                text.replace('file(REMOVE "${old_source}")', 'file(REMOVE "${OUT_HPP}")'),
                text.replace('#pragma once', '#define FOREIGN_OUTPUT 1'),
                text + '\nexecute_process(COMMAND foreign)\n'):
            self.assertNotEqual(changed, text)
            errors = []
            _validate_registry(defines, {relative: (changed, parse_commands(relative, changed, errors))}, errors)
            self.assertTrue(errors)
        errors = []
        changed_ast = [replace(command, body='OUT_HPP "/tmp/foreign.hpp"') if index == 0 else command
                       for index, command in enumerate(canonical)]
        _validate_registry(defines, {relative: (text, changed_ast)}, errors)
        self.assertTrue(errors)
        errors = []
        _validate_registry({**defines, "OUT_DIR": "/tmp"}, {relative: (text, canonical)}, errors)
        self.assertTrue(errors)
        self.assertFalse(approved_file_side_effect("WRITE", ["WRITE", "${path}", "${content}"],
            lambda raw: raw, relative + ":12"))


if __name__ == '__main__':
    unittest.main()
