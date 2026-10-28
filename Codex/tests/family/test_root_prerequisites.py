"""Root prerequisites regressions."""
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

class RootPrerequisiteTests(unittest.TestCase):
    def test_failed_profile_cannot_become_proof_for_remaining_profiles(self):
        import contextlib
        import io
        checker = _ownership_checker_for_harness()
        files = {
            "apps/trading-core/CMakeLists.txt": ("", []),
            checker.OFFLINE_HELPER: ("", []),
            checker.BENCHMARK_HELPER: ("", []),
        }
        profiles = {name: (("src/src/CMakeLists.txt",), {})
                    for name in ("first", "second")}
        def rejected_profile(files, roots, values, errors, *, syntax_memo=None, phase_reporter=None, source_audit=None):
            phase_reporter("fixture", 0.25)
            errors.append("configure prerequisite rejected")
        with contextlib.ExitStack() as stack:
            for name in vars(checker):
                if name.startswith("validate_") and name.endswith("_microcases"):
                    stack.enter_context(patch.object(checker, name))
            for name in ("validate_read_only_physical_surfaces", "validate_strategy_tree",
                         "check_reverse_dependencies", "check_obsolete_references"):
                stack.enter_context(patch.object(checker, name))
            stack.enter_context(patch.object(checker, "cmake_files", return_value=files))
            stack.enter_context(patch.object(checker, "owner_activation", return_value=profiles))
            stack.enter_context(patch.object(checker, "validate_offline_helper", return_value=True))
            stack.enter_context(patch.object(checker, "validate_benchmark_helper", return_value=True))
            stack.enter_context(patch.object(checker, "capture_verification_source_audit"))
            deep = stack.enter_context(patch.object(checker, "validate_configuration", side_effect=rejected_profile))
            output = io.StringIO()
            stack.enter_context(contextlib.redirect_stderr(output))
            self.assertEqual(checker.main(), 1)
            self.assertEqual(deep.call_count, 1)
            self.assertIn("configure prerequisite rejected [profiles: first]", output.getvalue())
            self.assertIn("NOTRUN: second", output.getvalue())
            self.assertIn("profile 1/2 START first", output.getvalue())
            self.assertIn("profile 1/2 END first FAIL elapsed=", output.getvalue())
            self.assertIn("PHASE first fixture elapsed=0.250s", output.getvalue())
            self.assertNotIn("START second", output.getvalue())

    def test_source_audit_is_reused_and_revalidated_after_all_profiles(self):
        import contextlib
        import io
        checker = _ownership_checker_for_harness()
        files = {"apps/trading-core/CMakeLists.txt": ("", []),
                 checker.OFFLINE_HELPER: ("", []), checker.BENCHMARK_HELPER: ("", [])}
        profiles = {name: (("src/src/CMakeLists.txt",), {}) for name in ("first", "second")}
        events = []
        audit = SimpleNamespace(validate=lambda errors: events.append("final freshness"))
        def accepted(files, roots, values, errors, *, syntax_memo=None, phase_reporter=None, source_audit=None):
            self.assertIs(source_audit, audit)
            events.append("profile")
        with contextlib.ExitStack() as stack:
            for name in vars(checker):
                if name.startswith("validate_") and name.endswith("_microcases"):
                    stack.enter_context(patch.object(checker, name))
            for name in ("validate_read_only_physical_surfaces", "validate_strategy_tree",
                         "check_reverse_dependencies", "check_obsolete_references"):
                stack.enter_context(patch.object(checker, name))
            stack.enter_context(patch.object(checker, "cmake_files", return_value=files))
            stack.enter_context(patch.object(checker, "owner_activation", return_value=profiles))
            stack.enter_context(patch.object(checker, "validate_offline_helper", return_value=True))
            stack.enter_context(patch.object(checker, "validate_benchmark_helper", return_value=True))
            capture = stack.enter_context(patch.object(checker, "capture_verification_source_audit", return_value=audit))
            stack.enter_context(patch.object(checker, "validate_configuration", side_effect=accepted))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(checker.main(), 0)
            capture.assert_called_once()
            self.assertEqual(events, ["profile", "profile", "final freshness"])
            audit.validate = lambda errors: errors.append("source snapshot changed")
            self.assertEqual(checker.main(), 1)

    def test_rejected_activation_cannot_enter_deep_configure_proofs(self):
        import contextlib
        import io
        checker = _ownership_checker_for_harness()
        files = {
            "apps/trading-core/CMakeLists.txt": ("", []),
            checker.OFFLINE_HELPER: ("", []),
            checker.BENCHMARK_HELPER: ("", []),
        }
        def rejected_activation(root, errors):
            errors.append("activation prerequisite rejected")
            return {"fixture": (("src/src/CMakeLists.txt",), {})}
        with contextlib.ExitStack() as stack:
            for name in vars(checker):
                if name.startswith("validate_") and name.endswith("_microcases"):
                    stack.enter_context(patch.object(checker, name))
            for name in ("validate_read_only_physical_surfaces", "validate_strategy_tree",
                         "check_reverse_dependencies", "check_obsolete_references"):
                stack.enter_context(patch.object(checker, name))
            stack.enter_context(patch.object(checker, "cmake_files", return_value=files))
            stack.enter_context(patch.object(checker, "owner_activation", side_effect=rejected_activation))
            stack.enter_context(patch.object(checker, "validate_offline_helper", return_value=True))
            stack.enter_context(patch.object(checker, "validate_benchmark_helper", return_value=True))
            deep = stack.enter_context(patch.object(checker, "validate_configuration"))
            output = io.StringIO()
            stack.enter_context(contextlib.redirect_stderr(output))
            self.assertEqual(checker.main(), 1)
            deep.assert_not_called()
            self.assertIn("activation prerequisite rejected", output.getvalue())
            self.assertIn("configure ownership proofs not run", output.getvalue())


if __name__ == '__main__':
    unittest.main()
