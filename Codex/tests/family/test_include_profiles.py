"""Include profiles regressions."""
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

class IncludeProfileModelTests(unittest.TestCase):
    @staticmethod
    def _build(targets=(), instances=(), active_origins=frozenset()):
        from Family.Sources.CxetFamilyIncludeReachability import _build_model
        registry = SimpleNamespace(concrete_names=lambda: frozenset(targets))
        errors = []
        _build_model(instances, registry, {}, frozenset(targets), errors,
            active_origins=active_origins)
        return errors

    def test_inactive_include_owners_do_not_require_foreign_targets(self):
        self.assertEqual(self._build(active_origins=frozenset()), [])

    def test_active_include_owner_still_requires_missing_target(self):
        errors = self._build(active_origins=frozenset({"apps/trader/CMakeLists.txt"}))
        self.assertTrue(any("traderd" in error and "missing" in error for error in errors))
        self.assertFalse(any("hft-parserd" in error for error in errors))
        self.assertFalse(any("hftrec_corpus_contract" in error for error in errors))

    def test_moved_contract_owner_controls_include_applicability(self):
        errors = self._build(active_origins=frozenset({
            "apps/hft-parser/src/Contracts/CMakeLists.txt"}))
        self.assertTrue(any("hftp_contract_headers" in error and "missing" in error
            for error in errors))
        self.assertFalse(any("hftp_parserd_runtime" in error for error in errors))

    def test_removed_active_offline_suite_is_still_a_missing_include_target(self):
        errors = self._build(active_origins=frozenset({
            "apps/hft-backtest/tests/offline/CMakeLists.txt"}))
        self.assertTrue(any("hft_backtest_offline_quota" in error and "missing" in error
            for error in errors))
        self.assertFalse(any("traderd" in error for error in errors))

    def test_foreign_owner_cannot_activate_offline_include_contract(self):
        errors = self._build(active_origins=frozenset({
            "apps/hft-backtest/CMakeLists.txt"}))
        self.assertFalse(any("hft_backtest_offline_quota" in error for error in errors))
        self.assertTrue(any("hft_backtest_core" in error and "missing" in error
            for error in errors))

    def test_foreign_owner_cannot_inject_known_offline_direct_includes(self):
        from Family.Sources import CxetFamilyIncludeReachability as include_model
        instance = SimpleNamespace(
            body=SimpleNamespace(relative="apps/trader/tests/offline/CMakeLists.txt",
                command=SimpleNamespace(name="target_include_directories", line=1)),
            token_groups=(("hft_backtest_offline_quota",),
                ("PRIVATE", "tools/Testing", "apps/hft-backtest/src/Runtime/src")),
            path_alternatives=((),))
        with patch.object(include_model, "_include_value",
                side_effect=lambda instance, value: ("repo", value)):
            errors = self._build(("hft_backtest_offline_quota",), (instance,),
                frozenset({"apps/trader/tests/offline/CMakeLists.txt"}))
        self.assertTrue(any("hft_backtest_offline_quota" in error and
            "owner" in error for error in errors))

    def test_active_direct_include_order_and_visibility_remain_exact(self):
        from Family.Sources import CxetFamilyIncludeReachability as include_model
        def include(scope, value):
            return SimpleNamespace(
                body=SimpleNamespace(relative="apps/hft-recorder/src/Contracts/CMakeLists.txt",
                    command=SimpleNamespace(name="target_include_directories", line=1)),
                token_groups=(("hftrec_corpus_contract",), (scope, value)),
                path_alternatives=((),))
        owner = frozenset({"apps/hft-recorder/src/Contracts/CMakeLists.txt"})
        correct = (
            include("PUBLIC", "apps/hft-recorder/src/Contracts/include"),
            include("PRIVATE", "apps/hft-recorder/src/Runtime/src"))
        for instances in (correct[::-1], (
                include("PRIVATE", "apps/hft-recorder/src/Contracts/include"), correct[1])):
            with self.subTest(instances=instances), patch.object(include_model, "_include_value",
                    side_effect=lambda instance, value: ("repo", value)):
                errors = self._build(("hftrec_corpus_contract",), instances, owner)
                self.assertTrue(any("hftrec_corpus_contract: exact direct include roots changed"
                    in error for error in errors))

    def test_current_include_inventory_retires_old_targets_without_hiding_recorder_json(self):
        from Family.Sources.CxetFamilyIncludeReachability import _EXACT_DIRECT_INCLUDE_ROOTS
        self.assertIn("hftp_market_client", _EXACT_DIRECT_INCLUDE_ROOTS)
        self.assertIn("hftp_sessiond_runtime", _EXACT_DIRECT_INCLUDE_ROOTS)
        self.assertEqual(_EXACT_DIRECT_INCLUDE_ROOTS["hftrec_json_capture"], frozenset({
            ("PRIVATE", "apps/hft-recorder/src/Runtime/src")}))
        for target in ("hft_parser_execution_client", "hftp_execution_publisher",
                "hftp_market_state", "hft_trader_runtime_shared", "trader-accountd",
                "trader_account_fixture", "trader_accountd_process", "trader_profile_persistence"):
            self.assertNotIn(target, _EXACT_DIRECT_INCLUDE_ROOTS)


if __name__ == '__main__':
    unittest.main()
