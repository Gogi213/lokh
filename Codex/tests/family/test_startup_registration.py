"""Startup registration regressions."""
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

class StartupRegistrationTests(unittest.TestCase):
    def registration_errors(self, *, dependency="exact", objects=True, binary_shift=False):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        from Family.Targets.CxetFamilyTargetRegistry import TargetDeclaration, TargetRegistry
        from Family.Targets.CxetFamilyTargetInventory import ROLE_TEST
        owner = "apps/trader/tests/startup/CMakeLists.txt"
        evaluation = SimpleNamespace(
            source_base=Path("apps/trader/tests/startup"),
            binary_base=Path("apps/trader/tests/startup" if binary_shift else
                             "apps/trader/tests/offline/startup"), scope="startup-fixture")
        instances = []
        declarations = []
        def command(name, tokens):
            instance = SimpleNamespace(
                body=SimpleNamespace(relative=owner,
                    command=SimpleNamespace(name=name, line=len(instances) + 1)),
                evaluation=evaluation, token_groups=tuple((token,) for token in tokens),
                path_alternatives=ALL_PATHS)
            instances.append(instance)
            return instance
        names = ("trader_startup_network", "trader_startup_fixture",
                 "trader_startup_alert_fixture", "trader_startup_certificates",
                 "trader_startup_isolation_probe", "trader_offline_finam_startup_process")
        for index, name in enumerate(names):
            kind = "OBJECT" if index == 0 else "EXECUTABLE"
            tokens = [name, *( ["OBJECT"] if index == 0 else [] ), "EXCLUDE_FROM_ALL", "Fixture.cpp"]
            if objects and index in {1, 2, 4}:
                tokens.append("$<TARGET_OBJECTS:trader_startup_network>")
            instance = command("add_library" if index == 0 else "add_executable", tokens)
            declarations.append(TargetDeclaration(name, kind, ROLE_TEST, instance, None))
        if dependency == "exact":
            command("add_dependencies", [names[-1], *names[1:5]])
        elif dependency == "unrelated":
            command("add_dependencies", [names[1], names[0]])
        command("add_test", ["NAME", "offline.fixture", "COMMAND", names[-1], "--case", "fixture"])
        registry = object.__new__(TargetRegistry)
        registry.errors = []
        registry.live_eof_paths = {evaluation.scope: ALL_PATHS}
        registry.order = {id(instance): index for index, instance in enumerate(instances)}
        registry.declarations = declarations
        registry.by_name = {item.name: [item] for item in declarations}
        registry._validate_test_registrations(instances)
        return registry.errors

    def test_startup_infrastructure_inherits_registration_through_real_edges(self):
        self.assertEqual(self.registration_errors(), [])

    def test_startup_registration_does_not_survive_missing_or_unrelated_edges(self):
        for mutation in ({"dependency": "missing"}, {"dependency": "unrelated"},
                         {"objects": False}, {"binary_shift": True}):
            with self.subTest(mutation=mutation):
                errors = self.registration_errors(**mutation)
                self.assertTrue(any("not registered on every declaration path" in error
                                    for error in errors), errors)


if __name__ == '__main__':
    unittest.main()
