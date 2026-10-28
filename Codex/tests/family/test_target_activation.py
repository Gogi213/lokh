"""Target activation regressions."""
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

class TargetActivationTests(ActivationFixture, unittest.TestCase):
    def test_partial_provider_paths_cannot_prove_global_target_presence(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        left, right = ((('condition', 0),),), ((('condition', 1),),)
        declarations = [
            self._declaration("split", ("STATIC", "Main.cpp"), "provider", 1, left),
            self._declaration("split", ("STATIC", "Main.cpp"), "provider", 2, right),
            self._declaration("split::api", ("ALIAS", "split"), "provider", 3),
            self._declaration("dead", ("STATIC", "Main.cpp"), "dead", 4),
        ]
        use = SimpleNamespace(scope="consumer", directory=("consumer",), ordinal=8)
        types = directory_target_types(declarations, shared_namespace=True,
            live_eof_paths={"provider": (*left, *right), "dead": ()})
        self.assertEqual(configure_targets_before(types, use), {})

    def test_target_predicate_uses_only_definite_same_configure_presence(self):
        from CMake.Flow.CmakeFamilyFlow import evaluate_condition, reviewed_evidence_condition, Truth
        expand = lambda values, preserve: values
        self.assertTrue(reviewed_evidence_condition(("NOT", "TARGET", "provider::api")))
        self.assertIs(evaluate_condition(("TARGET", "provider::api"), {}, expand,
            known_targets={"provider::api": "LIBRARY"}), Truth.TRUE)
        self.assertIs(evaluate_condition(("NOT", "TARGET", "provider::api"), {}, expand,
            known_targets={"provider::api": "LIBRARY"}), Truth.FALSE)
        self.assertIs(evaluate_condition(("NOT", "TARGET", "missing"), {}, expand,
            known_targets={"provider::api": "LIBRARY"}), Truth.UNKNOWN)

    def test_unknown_target_fatal_arm_cannot_ground_namespace_presence(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        relative = "provider/CMakeLists.txt"
        text = ('if(TARGET ghost)\nadd_library(real STATIC Real.cpp)\n'
                'else()\nmessage(FATAL_ERROR "missing")\nendif()')
        errors = []
        files = {relative: (text, parse_commands(relative, text, errors))}
        commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
        model = function_model(commands, errors)
        snapshots = variable_snapshots(commands, model, errors)
        declarations = instantiated_commands(commands, model, snapshots,
            GRAPH_INSTANCE_NAMES, errors)
        self.assertEqual(errors, [])
        self.assertTrue(snapshots.live_eof_paths[relative])
        types = directory_target_types(declarations, shared_namespace=True,
            live_eof_paths=snapshots.live_eof_paths, snapshots=snapshots)
        consumer = SimpleNamespace(scope="consumer", directory=("consumer",), ordinal=20)
        self.assertEqual(configure_targets_before(types, consumer), {})

    def test_callable_declaration_cannot_borrow_unconditional_caller_snapshot(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        relative = "provider/CMakeLists.txt"
        text = ('function(install_provider)\nif(TARGET ghost)\n'
                'add_library(provider STATIC Main.cpp)\nelse()\n'
                'message(FATAL_ERROR "missing")\nendif()\nendfunction()\ninstall_provider()')
        errors = []
        files = {relative: (text, parse_commands(relative, text, errors))}
        commands = compose_active_commands(ROOT, files, (relative,), set(), errors)
        model = function_model(commands, errors)
        snapshots = variable_snapshots(commands, model, errors)
        declarations = instantiated_commands(commands, model, snapshots, GRAPH_INSTANCE_NAMES, errors)
        types = directory_target_types(declarations, shared_namespace=True,
            live_eof_paths=snapshots.live_eof_paths, snapshots=snapshots)
        self.assertEqual(errors, [])
        self.assertEqual(configure_targets_before(types, SimpleNamespace(ordinal=30)), {})

    def test_profile_contract_applicability_does_not_skip_missing_active_targets(self):
        from Family.Targets.CxetFamilyMayMustGraph import validate_direct_and_transitive_contracts
        graphs = SimpleNamespace(may={}, must={})
        errors = []
        validate_direct_and_transitive_contracts(graphs, errors,
            active_origins=frozenset({"apps/trader/CMakeLists.txt"}))
        self.assertTrue(any("target traderd:" in error for error in errors))
        self.assertFalse(any("target hft-parserd:" in error for error in errors))
        errors = []
        validate_direct_and_transitive_contracts(graphs, errors,
            active_origins=frozenset({"apps/trader/CMakeLists.txt"}),
            disabled_contract_targets={'traderd'})
        self.assertTrue(any('unreviewed disabled contract targets' in error for error in errors))
        self.assertTrue(any('target traderd:' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
