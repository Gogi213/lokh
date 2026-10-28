"""Loop profiles regressions."""
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

class LoopProfileModelTests(StrategyFixture, unittest.TestCase):
    def test_empty_surface_has_no_source_fold_requirements(self):
        from CMake.Policy.CmakeFamilyLoopPolicy import validate_reviewed_source_folds
        errors = []
        validate_reviewed_source_folds([], errors)
        self.assertEqual(errors, [])

    def test_native_crypto_fold_keeps_exact_modules_owner_guard_and_source_path(self):
        from CMake.Policy.CmakeFamilyLoopPolicy import (
            _native_crypto_fold_writer, validate_reviewed_source_folds,
        )
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        relative = 'src/src/CMakeLists.txt'
        original = (ROOT / relative).read_text()
        invalid = [
            original.replace('if(NOT TARGET cxet_crypto)', 'if(TARGET cxet_crypto)', 1),
            original.replace('_cxet_mbed_crypto_modules asn1parse', '_cxet_mbed_crypto_modules foreign_module asn1parse', 1),
            original.replace('${_cxet_mbed}/library/${_module}.c', '/tmp/${_module}.c', 1),
            original.replace('foreach(_module IN LISTS _cxet_mbed_crypto_modules)',
                             'foreach(_module IN LISTS foreign_modules)', 1),
        ]
        for text, accepted in [(original, True), *((changed, False) for changed in invalid)]:
            with self.subTest(accepted=accepted, text=text[:60]):
                errors = []
                commands = parse_commands(relative, text, errors)
                contexts = structural_contexts(relative, commands, cmake_list_words, errors)
                active = [SimpleNamespace(relative=relative, command=command, structural_context=context)
                          for command, context in zip(commands, contexts)]
                validate_reviewed_source_folds(active, errors)
                writer = next(item for item in active if item.command.name == 'list' and
                              cmake_list_words(item.command.body)[:2] == ['APPEND', '_cxet_mbed_crypto_sources'])
                if not _native_crypto_fold_writer(writer):
                    errors.append('native crypto source writer refused')
                self.assertEqual(not errors, accepted, errors)

    def test_native_crypto_optimization_requires_exact_profile_scalar_and_loop(self):
        from CMake.Policy.CmakeFamilyCommandPolicy import _compile_options
        from CMake.Syntax.CmakeFamilyContext import structural_contexts
        relative = 'src/src/CMakeLists.txt'
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        contexts = structural_contexts(relative, commands, cmake_list_words, errors)
        command, context = next((command, context) for command, context in zip(commands, contexts)
            if command.name == 'target_compile_options' and
            cmake_list_words(command.body)[:2] == ['${_tls_target}', 'PRIVATE'] and
            '${_CXET_RELEASE_OPTIMIZATION}' in command.body)
        self.assertEqual(errors, [])
        cases = [('pinned', '-O3', True), ('system-diagnostic', '-O1', True),
                 ('pinned', '-O1', False), ('system-diagnostic', '-O3', False),
                 ('pinned', '-include=/tmp/foreign.hpp', False), ('baseline', '-O3', False)]
        for profile, optimization, accepted in cases:
            with self.subTest(profile=profile, optimization=optimization):
                active = SimpleNamespace(relative=relative, source_base=Path('src/src'),
                    binary_base=Path('src/src'), structural_context=context, command=command, ordinal=100)
                tokens = cmake_list_words(command.body)
                groups = tuple((token.replace('${_tls_target}', 'cxet_crypto').replace(
                    '${_CXET_RELEASE_OPTIMIZATION}', optimization),) for token in tokens)
                instance = SimpleNamespace(body=active, evaluation=active, token_groups=groups)
                snapshots = SimpleNamespace(values={100: {'CXET_TOOLCHAIN_PROFILE': (profile,),
                    '_CXET_RELEASE_OPTIMIZATION': (optimization,)}})
                errors = []
                _compile_options(instance, cmake_list_words, errors, snapshots=snapshots)
                self.assertEqual(not errors, accepted, errors)
                if accepted:
                    active.structural_context = ()
                    errors = []
                    _compile_options(instance, cmake_list_words, errors, snapshots=snapshots)
                    self.assertTrue(errors)

    def test_actual_parser_composition_proves_strategy_fold_and_generated_consumers(self):
        from CMake.Policy.CmakeFamilyLoopPolicy import validate_loop_writer_boundary
        from CMake.Policy.CmakeFamilyStrategyPolicy import canonical_strategy_names
        from Family.Profile.CxetFamilySelectorActivation import lower_selector_modules
        checker = _ownership_checker_for_harness()
        errors = []
        roots, initial = owner_activation(ROOT, errors)["compile:hft-parser:essential:0:0:0"]
        files, initial = lower_selector_modules(ROOT, checker.cmake_files(errors), initial, errors)
        active = compose_active_commands(ROOT, files, roots, checker.APPROVED_EXTERNAL_SUBDIRECTORIES,
            errors, initial_values_by_scope=initial)
        validate_loop_writer_boundary(active, errors)
        tc = [item for item in active if item.relative == "apps/trading-core/CMakeLists.txt"]
        self.assertTrue(tc)
        fold = validate_registration_predicate([item.command for item in tc], cmake_list_words, errors)
        fold_ids = {id(command) for command in fold}
        consumer = next(item for item in tc if item.command.name == "add_library" and
                        cmake_list_words(item.command.body)[:1] == ["trading_core_strategy"])
        selected = [item for item in tc if id(item.command) in fold_ids or
            item.command.name == "set" and cmake_list_words(item.command.body)[:1] in (
                ["TRADING_CORE_GENERATED_DIR"], ["TRADING_CORE_GENERATED_STRATEGY_REGISTRY_HEADER"],
                ["TRADING_CORE_GENERATED_STRATEGY_REGISTRY_SOURCES"]) or
            item.command.name == "file" and cmake_list_words(item.command.body)[:2] ==
                ["GLOB", "TRADING_CORE_STRATEGY_HEADERS"] or item is consumer]
        model = function_model(selected, errors)
        snapshots = variable_snapshots(selected, model, errors, initial_values_by_scope=initial)
        instances = instantiated_commands(selected, model, snapshots, {"add_library"}, errors)
        self.assertEqual(errors, [])
        self.assertEqual(len(instances), 1)
        values = [value for group in instances[0].token_groups for value in group]
        for name in canonical_strategy_names():
            self.assertTrue(any(value.endswith("/GeneratedStrategyRegistry_" + name + ".cpp") for value in values), values)
        self.assertTrue(any(value.endswith("/GeneratedStrategyRegistry.hpp") for value in values), values)
        self.assertFalse(any("${" in value for value in values), values)

    def test_strategy_fold_authority_follows_exact_recipe_not_old_line_band(self):
        from CMake.Policy.CmakeFamilyLoopPolicy import validate_loop_writer_boundary
        original = (ROOT / "apps/trading-core/CMakeLists.txt").read_text()
        active = self._strategy_active("\n\n# unrelated line shift\n" + original)
        errors = []
        validate_loop_writer_boundary(active, errors)
        self.assertEqual(errors, [])
        for changed in (
                original.replace('file(READ "${strategy_header}" strategy_header_text)',
                    'file(READ "${strategy_header}" strategy_header_text)\nset(unreviewed_writer ON)', 1),
                original.replace('if(EXISTS "${strategy_dir}/Descriptor.hpp")',
                    'if(EXISTS "${strategy_dir}/Other.hpp")', 1),
                original.replace('trader/*/Strategy.hpp', 'trader/*/*.hpp', 1),
                "if(UNKNOWN_GUARD)\n" + original + "\nendif()",
                original.replace('foreach(strategy_header IN LISTS TRADING_CORE_STRATEGY_HEADERS)',
                    'function(borrowed_fold)\nforeach(strategy_header IN LISTS TRADING_CORE_STRATEGY_HEADERS)', 1)
                    .replace('endforeach()\n# A private stamp', 'endforeach()\nendfunction()\n# A private stamp', 1)):
            with self.subTest(changed=changed[:60]):
                self.assertNotEqual(changed, original)
                errors = []
                validate_loop_writer_boundary(self._strategy_active(changed), errors)
                self.assertTrue(errors)

    def test_strategy_scalar_inputs_keep_actual_owner_descriptor_and_foreign_boundary(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyLoopPolicy import reviewed_scalar_iteration_locals
        from CMake.Policy.CmakeFamilyStrategyPolicy import proven_strategy_headers
        active = self._strategy_active((ROOT / "apps/trading-core/CMakeLists.txt").read_text())
        condition = next(item for item in active if item.command.name == "if" and
            cmake_list_words(item.command.body)[:1] == ["strategy_descriptor_text"])
        header = sorted(proven_strategy_headers())[0]
        local = {"strategy_header": (header,)}
        result = reviewed_scalar_iteration_locals(condition, local)
        descriptor = Path(header).parent / "Descriptor.hpp"
        combined = Path(header).read_text()
        if descriptor.is_file():
            combined += "\n" + descriptor.read_text()
        self.assertEqual(result["strategy_descriptor_text"], (combined,))
        self.assertEqual(result["strategy_dir"], (str(Path(header).parent),))
        self.assertEqual(reviewed_scalar_iteration_locals(replace(condition,
            source_base=Path("apps/hft-parser")), local), local)
        foreign = reviewed_scalar_iteration_locals(condition, {"strategy_header": ("/foreign/Strategy.hpp",)})
        self.assertEqual(foreign["strategy_descriptor_text"], ("${strategy_descriptor_text}",))

    def test_strategy_regex_producer_requires_exact_active_context(self):
        from CMake.Flow.CmakeFamilyMutations import apply_string_command
        from CMake.Flow.CmakeFamilyState import expand_variable_tokens
        from dataclasses import replace
        active = self._strategy_active((ROOT / "apps/trading-core/CMakeLists.txt").read_text())
        producer = next(item for item in active if item.command.name == "string" and
            cmake_list_words(item.command.body)[:1] == ["REGEX"])
        for context, accepted in ((producer, True), (None, False),
                (replace(producer, structural_context=()), False),
                (replace(producer, relative="apps/hft-parser/CMakeLists.txt"), False)):
            state = {"strategy_folder": ("DeliverySumSignal",)}
            errors = []
            apply_string_command(cmake_list_words(producer.command.body), state,
                lambda raw: expand_variable_tokens(raw, state), errors, "apps/trading-core/CMakeLists.txt:117",
                strategy_context=context)
            self.assertEqual(not errors, accepted)
            if accepted:
                self.assertEqual(state["strategy_name"], ("Delivery_Sum_Signal",))

    def test_strategy_case_fold_preserves_scalar_iteration_order_and_duplicates(self):
        from CMake.Flow.CmakeFamilyMutations import apply_string_command
        from CMake.Flow.CmakeFamilyState import expand_variable_tokens
        active = self._strategy_active((ROOT / "apps/trading-core/CMakeLists.txt").read_text())
        producer = next(item for item in active if item.command.name == "string" and
            cmake_list_words(item.command.body)[:1] == ["TOLOWER"])
        inputs = ("Delivery_Sum_Signal", "Finam_Api_Probe", "Delivery_Sum_Signal")
        for context in (producer, None):
            state = {"strategy_name": inputs}
            errors = []
            apply_string_command(cmake_list_words(producer.command.body), state,
                lambda raw: expand_variable_tokens(raw, state), errors, "strategy-case-fold",
                strategy_context=context)
            self.assertEqual(errors, [])
            expected = (tuple(value.lower() for value in inputs) if context is not None else
                        ("${strategy_name}",))
            self.assertEqual(state["strategy_name"], expected)
        state = {"strategy_name": ("Foreign_Strategy",)}
        errors = []
        apply_string_command(cmake_list_words(producer.command.body), state,
            lambda raw: expand_variable_tokens(raw, state), errors, "strategy-case-fold",
            strategy_context=producer)
        self.assertTrue(errors)
        self.assertEqual(state["strategy_name"], ("${strategy_name}",))


if __name__ == '__main__':
    unittest.main()
