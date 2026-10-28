"""Source catalog recipes regressions."""
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

class SourceCatalogRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_causal_prior_targets_prove_exact_provider_fold_without_self_grounding(self):
        from CMake.Flow.CmakeFamilyInstances import GRAPH_INSTANCE_NAMES, directory_target_types
        provider, consumer = "provider/CMakeLists.txt", "consumer/CMakeLists.txt"
        consumer_text = ('add_library(base INTERFACE)\nset(providers base)\n'
            'if(TARGET provider)\nadd_library(client INTERFACE)\nadd_library(client::api ALIAS client)\nendif()\n'
            'if(TARGET client)\nlist(APPEND providers client)\nendif()\n'
            'foreach(target IN LISTS providers)\ntarget_compile_features(${target} INTERFACE cxx_std_23)\nendforeach()')
        for prefix, prelude, accepted in (("NOT TARGET provider", "", True), ("TARGET provider", "", False),
                ("NOT TARGET provider", 'if(unknown)\nmessage(FATAL_ERROR "unknown")\nendif()\n', False)):
            errors = []
            provider_text = f'if({prefix})\n{prelude}add_library(provider INTERFACE)\nendif()'
            files = {relative: (text, parse_commands(relative, text, errors)) for relative, text in
                     ((provider, provider_text), (consumer, consumer_text))}
            active = compose_active_commands(ROOT, files, (provider, consumer), set(), errors)
            model = function_model(active, errors)
            bootstrap = variable_snapshots(active, model, [])
            instances = instantiated_commands(active, model, bootstrap, GRAPH_INSTANCE_NAMES, [])
            types = directory_target_types(instances, shared_namespace=True, snapshots=bootstrap,
                active_commands=active, live_eof_paths=bootstrap.live_eof_paths)
            snapshots = variable_snapshots(active, model, errors, directory_target_types=types)
            if accepted:
                self.assertEqual(errors, [])
                loop = next(item for item in active if item.relative == consumer and item.command.name == "foreach")
                self.assertEqual(snapshots.values[loop.ordinal]["providers"], ("base", "client"))
                self.assertTrue(snapshots.live_eof_paths[consumer])
            else:
                self.assertTrue(any("non-exact foreach" in error for error in errors), errors)

    def test_identical_branch_lists_stay_exact_before_guaranteed_append(self):
        from CMake.Flow.CmakeFamilyState import (
            merge_variable_states, expand_variable_tokens, UNCERTAIN_BRANCH_ALTERNATIVE,
        )
        from CMake.Flow.CmakeFamilyMutations import apply_list_command
        for initial in ((), ("first", "second", "first")):
            state = merge_variable_states([{"names": initial}, {"names": initial}])
            self.assertEqual(state["names"], initial)
            errors = []
            apply_list_command(["APPEND", "names", "last"], state,
                lambda raw: expand_variable_tokens(raw, state), errors, "merge-fixture:1")
            self.assertEqual(errors, [])
            self.assertEqual(tuple(expand_variable_tokens(["${names}"], state)), (*initial, "last"))
        for branches in (({"names": ()}, {"names": ("maybe",)}),
                         ({"names": ("first", "second")}, {"names": ("second", "first")}),
                         ({"names": ()}, {})):
            self.assertIn(UNCERTAIN_BRANCH_ALTERNATIVE,
                merge_variable_states(list(branches))["names"])

    def test_aggregate_forward_target_is_generation_time_but_path_coverage_is_required(self):
        from CMake.Policy.CmakeFamilyCommandPolicy import _custom_target_dependencies
        from CMake.Flow.CmakeFamilyFlow import InstantiatedCommand
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        relative = "apps/trader/CMakeLists.txt"
        dependencies = ("trader-market-observed", "trader_market_observe_runtime", "trader_market_observe_process",
                        "trader_market_observe_projection_publisher", "trader_market_observe_projection_server")
        instances = []
        for ordinal, (name, values) in enumerate([
                ("add_custom_target", ("trader-market-observe-product", "DEPENDS", *dependencies)),
                *[("add_executable", (target, "Main.cpp")) for target in dependencies]]):
            active = ActiveCommand("fixture", relative, Path("apps/trader"), Path("apps/trader"),
                (relative,), Command(name, " ".join(values), ordinal + 1), ordinal)
            instances.append(InstantiatedCommand(active, active, tuple((value,) for value in values), ordinal, ((),)))
        from dataclasses import replace
        for candidates, accepted in ((instances, True), (instances[:-1], False),
                ([*instances[:-1], replace(instances[-1], path_alternatives=((("maybe", 0),),))], False)):
            errors = []
            _custom_target_dependencies(candidates, {}, errors, False)
            self.assertEqual(not errors, accepted, errors)
        conditional = [*instances[:-1], replace(instances[-1], path_alternatives=((("maybe", 0),),))]
        selected_path = ((("maybe", 0),),)
        both_paths = (*selected_path, (("maybe", 1),))
        for eof, accepted in ((selected_path, True), (both_paths, False), ((), False)):
            errors = []
            snapshots = SimpleNamespace(values={}, live_eof_paths={"fixture": eof})
            _custom_target_dependencies(conditional, {}, errors, False, snapshots=snapshots)
            self.assertEqual(not errors, accepted, errors)

    def test_glob_recurse_directory_default_differs_from_glob(self):
        from CMake.Flow.CmakeFamilyWriters import apply_output_writer
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "nested.hpp").mkdir()
            (root / "nested.hpp/Leaf.hpp").write_text("// leaf\n")
            for operation, extra, directory_expected in (
                    ("GLOB_RECURSE", (), False), ("GLOB", (), True),
                    ("GLOB_RECURSE", ("LIST_DIRECTORIES", "TRUE"), True)):
                state, errors = {}, []
                apply_output_writer("file", [operation, "headers", *extra, str(root / "*.hpp")],
                    root, root, state, lambda raw: raw, errors, "glob-fixture:1")
                self.assertEqual(errors, [])
                self.assertEqual(str(root / "nested.hpp") in state["headers"], directory_expected)

    def test_source_catalog_absence_requires_inactive_prior_declarations(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        from CMake.Flow.CmakeFamilyFlow import Truth, evaluate_condition
        for prefix, absent in (("if(FALSE)\nadd_library(optional INTERFACE)\nendif()", True),
                               ("if(unknown)\nadd_library(optional INTERFACE)\nendif()", False),
                               ("add_library(${unknown_name} INTERFACE)", False)):
            text = prefix + "\nif(TARGET optional)\nendif()\nadd_library(optional INTERFACE)"
            relative = "fixture/CMakeLists.txt"
            errors = []
            files = {relative: (text, parse_commands(relative, text, errors))}
            active = compose_active_commands(ROOT, files, (relative,), set(), errors)
            model = function_model(active, errors)
            snapshots = variable_snapshots(active, model, errors)
            instances = instantiated_commands(active, model, snapshots, GRAPH_INSTANCE_NAMES, errors)
            types = directory_target_types(instances, shared_namespace=True, snapshots=snapshots,
                active_commands=active, live_eof_paths=snapshots.live_eof_paths)
            guard = next(item for item in active if item.command.body == "TARGET optional")
            facts = configure_targets_before(types, guard)
            self.assertEqual(facts.get("optional") == "SOURCE_PROVED_ABSENT", absent)
            self.assertIs(evaluate_condition(("TARGET", "optional"), {}, lambda values, preserve: values,
                known_targets=facts), Truth.FALSE if absent else Truth.UNKNOWN)

    def test_source_catalog_bootstrap_does_not_self_ground_positive_target_guard(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        for negated in (True, False):
            relative = "fixture/CMakeLists.txt"
            text = "if(" + ("NOT " if negated else "") + "TARGET bootstrap)\nadd_library(bootstrap INTERFACE)\nendif()"
            errors = []
            files = {relative: (text, parse_commands(relative, text, errors))}
            active = compose_active_commands(ROOT, files, (relative,), set(), errors)
            model = function_model(active, errors)
            snapshots = variable_snapshots(active, model, errors)
            instances = instantiated_commands(active, model, snapshots, GRAPH_INSTANCE_NAMES, errors)
            types = directory_target_types(instances, shared_namespace=True, snapshots=snapshots,
                active_commands=active, live_eof_paths=snapshots.live_eof_paths)
            snapshots = variable_snapshots(active, model, errors, directory_target_types=types)
            instances = instantiated_commands(active, model, snapshots, GRAPH_INSTANCE_NAMES, errors, types)
            types = directory_target_types(instances, shared_namespace=True, snapshots=snapshots,
                active_commands=active, live_eof_paths=snapshots.live_eof_paths)
            self.assertEqual(errors, [])
            use = SimpleNamespace(scope=relative, directory=(relative,), ordinal=len(active) + 1)
            self.assertEqual("bootstrap" in configure_targets_before(types, use), negated)

    def test_source_catalog_cannot_claim_package_or_unknown_provider_targets_absent(self):
        from CMake.Flow.CmakeFamilyInstances import directory_target_types, GRAPH_INSTANCE_NAMES
        from CMake.Flow.CmakeFamilyState import configure_targets_before
        from CMake.Flow.CmakeFamilyFlow import Truth, evaluate_condition
        for provider, name, absent in (
                ("find_package(Threads REQUIRED)", "Threads::Threads", False),
                ("if(unknown)\nfind_package(Threads REQUIRED)\nendif()", "Threads::Threads", False),
                ("find_package(${unknown_provider} REQUIRED)", "ordinary", False),
                ("if(unknown)\nfind_package(${unknown_provider} REQUIRED)\nendif()", "ordinary", False),
                ("find_package(Threads REQUIRED)", "ordinary", True)):
            relative = "fixture/CMakeLists.txt"
            text = provider + f"\nif(TARGET {name})\nendif()\nif(FALSE)\nadd_library({name} INTERFACE IMPORTED)\nendif()"
            errors = []
            files = {relative: (text, parse_commands(relative, text, errors))}
            active = compose_active_commands(ROOT, files, (relative,), set(), errors)
            model = function_model(active, errors)
            snapshots = variable_snapshots(active, model, errors)
            instances = instantiated_commands(active, model, snapshots, GRAPH_INSTANCE_NAMES, errors)
            types = directory_target_types(instances, shared_namespace=True, snapshots=snapshots,
                active_commands=active, live_eof_paths=snapshots.live_eof_paths)
            guard = next(item for item in active if item.command.body == f"TARGET {name}")
            facts = configure_targets_before(types, guard)
            self.assertEqual(errors, [])
            self.assertEqual(facts.get(name) == "SOURCE_PROVED_ABSENT", absent)
            self.assertIs(evaluate_condition(("TARGET", name), {}, lambda values, preserve: values,
                known_targets=facts), Truth.FALSE if absent else Truth.UNKNOWN)


if __name__ == '__main__':
    unittest.main()
