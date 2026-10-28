"""Include inputs regressions."""
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

class IncludeInputTests(unittest.TestCase):
    def test_positive_path_cache_keeps_leaf_probes_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "source.hpp"
            path.write_bytes(b"old")
            inputs = IncludeInputs(root)
            self.assertEqual(inputs.regular_relative(path), "source.hpp")
            self.assertEqual(inputs.regular_relative(path), "source.hpp")
            self.assertEqual(inputs.validate(), ())
            path.write_bytes(b"changed")
            with self.assertRaises(OSError):
                inputs.regular_relative(path)
            self.assertTrue(inputs.validate())

    def test_positive_path_cache_detects_parent_rename_and_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "parent"
            parent.mkdir()
            path = parent / "source.hpp"
            path.write_bytes(b"same")
            inputs = IncludeInputs(root)
            inputs.regular_relative(path)
            backup = root / "saved"
            parent.rename(backup)
            backup.rename(parent)
            self.assertEqual(inputs.regular_relative(path), "parent/source.hpp")
            self.assertTrue(inputs.validate())

    def test_positive_path_cache_detects_transient_parent_symlink_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parent = root / "parent"
            parent.mkdir()
            path = parent / "source.hpp"
            path.write_bytes(b"same")
            inputs = IncludeInputs(root)
            inputs.regular_relative(path)
            backup = root / "saved"
            parent.rename(backup)
            parent.symlink_to(backup, target_is_directory=True)
            # A leaf-only probe sees the same file inode through this link.
            inputs.regular_relative(path)
            parent.unlink()
            backup.rename(parent)
            self.assertTrue(inputs.validate())

    def test_positive_path_cache_rejects_symlink_before_parent_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "actual").mkdir()
            (root / "source.hpp").write_bytes(b"same")
            (root / "alias").symlink_to(root / "actual", target_is_directory=True)
            inputs = IncludeInputs(root)
            with self.assertRaises(OSError):
                inputs.regular_relative(root / "alias" / ".." / "source.hpp")

    def test_positive_path_cache_rejects_nonregular_kind_and_root_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            outer = Path(directory)
            root = outer / "workspace"
            root.mkdir()
            path = root / "source.hpp"
            path.write_bytes(b"same")
            (root / "directory.hpp").mkdir()
            inputs = IncludeInputs(root)
            inputs.regular_relative(path)
            with self.assertRaises(OSError):
                inputs.regular_relative(root / "directory.hpp")
            backup = outer / "saved"
            root.rename(backup)
            root.symlink_to(backup, target_is_directory=True)
            inputs.regular_relative(path)
            self.assertTrue(inputs.validate())

    def test_positive_path_cache_cap_retains_uncached_slowpath_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first, second = root / "one.hpp", root / "two.hpp"
            first.write_bytes(b"one")
            second.write_bytes(b"two")
            inputs = IncludeInputs(root, max_regular_paths=1)
            self.assertEqual(inputs.regular_relative(first), "one.hpp")
            self.assertEqual(inputs.regular_relative(second), "two.hpp")
            self.assertEqual(len(inputs._regular_paths), 1)
            self.assertEqual(inputs.validate(), ())
            second.write_bytes(b"changed")
            with self.assertRaises(OSError):
                inputs.regular_relative(second)

    def test_macro_inventory_reuses_pure_syntax_after_each_fresh_bounded_read(self):
        import contextlib
        from Family.Verification import CxetFamilyVerificationFriendPolicy as policy
        from Family.Targets import CxetFamilyTargetPolicy as target_policy
        from Family.Sources.CxetFamilyIncludeReachability import CppIncludeSyntaxMemo
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        calls = []
        def scanner(data):
            calls.append(data)
            return cpp_include_syntax(data)
        memo = CppIncludeSyntaxMemo(scanner)
        relative = "sample/nested/One.hpp"
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory)
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_bytes(b"int va\\\nlue;\n")
            stack.enter_context(patch.object(target_policy, "ROOT", root))
            stack.enter_context(patch.multiple(policy, ROOT=root,
                _VERIFICATION_SOURCE_ROOTS=("sample", "sample/nested"),
                _VERIFICATION_FRIEND_SOURCE_LINES={}, _VERIFICATION_PROTECTED_FRIEND_LINES={},
                _VERIFICATION_PROTECTED_SHA256={}, _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES={}))
            stack.enter_context(patch.object(policy, "_validate_cpp_include_microcases"))
            reader = stack.enter_context(patch.object(policy, "_bounded_verification_source_bytes",
                wraps=policy._bounded_verification_source_bytes))
            for _ in range(2):
                errors = []
                policy.validate_verification_source_macro_inventory(errors,
                    check_include_boundaries=False, syntax_memo=memo)
                self.assertEqual(errors, [])
            self.assertEqual(len(calls), 1)
            self.assertEqual(memo.full_syntax(relative, source.read_bytes())[0], b"int value;\n")
            self.assertEqual(sum(call.args[1] == relative for call in reader.call_args_list), 2)
            source.write_bytes(b"#define private public\n")
            errors = []
            policy.validate_verification_source_macro_inventory(errors,
                check_include_boundaries=False, syntax_memo=memo)
            self.assertEqual(len(calls), 2)
            self.assertTrue(any("access-control keyword macro" in error for error in errors))
            self.assertEqual(sum(call.args[1] == relative for call in reader.call_args_list), 3)

    def test_source_audit_reuses_one_scan_and_detects_snapshot_changes(self):
        import contextlib
        from Family.Verification import CxetFamilyVerificationFriendPolicy as policy
        from Family.Targets import CxetFamilyTargetPolicy as target_policy
        from Family.Sources.CxetFamilyIncludeReachability import CppIncludeSyntaxMemo
        for mutation in ("unchanged", "generated", "content", "added", "removed", "symlink"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
                root = Path(directory)
                source = root / "sample/nested/One.hpp"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"int value;\n")
                generated = source.parent / "build"
                generated.mkdir()
                stack.enter_context(patch.object(target_policy, "ROOT", root))
                stack.enter_context(patch.multiple(policy, ROOT=root,
                    _VERIFICATION_SOURCE_ROOTS=("sample", "sample/nested"),
                    _VERIFICATION_FRIEND_SOURCE_LINES={}, _VERIFICATION_PROTECTED_FRIEND_LINES={},
                    _VERIFICATION_PROTECTED_SHA256={}, _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES={}))
                stack.enter_context(patch.object(policy, "_validate_cpp_include_microcases"))
                stack.enter_context(patch.object(policy, "_generated_verification_path",
                    side_effect=lambda relative: relative.startswith("sample/nested/build")))
                scan = stack.enter_context(patch.object(policy, "validate_verification_source_macro_inventory",
                    wraps=policy.validate_verification_source_macro_inventory))
                errors = []
                audit = policy.capture_verification_source_audit(errors,
                    check_include_boundaries=False, syntax_memo=CppIncludeSyntaxMemo())
                self.assertEqual(errors, [])
                for _ in range(3):
                    policy.validate_verification_friend_contract([], [], errors,
                        check_include_boundaries=False, source_audit=audit)
                self.assertEqual(errors, [])
                self.assertEqual(scan.call_count, 1)
                self.assertEqual(len(audit.inputs.files), 1)
                if mutation == "content":
                    source.write_bytes(b"int other;\n")
                elif mutation == "generated":
                    (generated / "Output.cpp").write_bytes(b"generated output\n")
                elif mutation == "added":
                    (source.parent / "Added.hpp").write_bytes(b"int added;\n")
                elif mutation == "removed":
                    source.unlink()
                elif mutation == "symlink":
                    source.unlink()
                    source.symlink_to("Missing.hpp")
                audit.validate(errors)
                self.assertEqual(bool(errors), mutation not in {"unchanged", "generated"})

    def test_bounded_input_refuses_oversized_source_before_opening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "One.hpp").write_bytes(b"oversized")
            inputs = IncludeInputs(root)
            with patch.object(Path, "open", side_effect=AssertionError("must not open oversized source")):
                with self.assertRaisesRegex(OSError, "exceeds 4 byte bound"):
                    inputs.read("One.hpp", max_bytes=4)

    def test_source_audit_tracks_absent_unscanned_shadow_and_restoration(self):
        import contextlib
        from Family.Verification import CxetFamilyVerificationFriendPolicy as policy
        from Family.Targets import CxetFamilyTargetPolicy as target_policy
        include = "trading_core/Strategy/GeneratedStrategyRegistry.hpp"
        for restored in (False, True):
            with self.subTest(restored=restored), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
                root = Path(directory)
                source = root / "sample/One.hpp"
                source.parent.mkdir()
                source.write_text('#include "' + include + '"\n')
                shadow = root / include
                shadow.parent.mkdir(parents=True)
                stack.enter_context(patch.object(target_policy, "ROOT", root))
                stack.enter_context(patch.multiple(policy, ROOT=root,
                    _VERIFICATION_SOURCE_ROOTS=("sample",),
                    _VERIFICATION_FRIEND_SOURCE_LINES={}, _VERIFICATION_PROTECTED_FRIEND_LINES={},
                    _VERIFICATION_PROTECTED_SHA256={},
                    _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES={"sample/One.hpp": frozenset({include})}))
                stack.enter_context(patch.object(policy, "_validate_cpp_include_microcases"))
                errors = []
                audit = policy.capture_verification_source_audit(errors, check_include_boundaries=False)
                self.assertEqual(errors, [])
                self.assertIn(shadow, audit.inputs.probes)
                self.assertIn(shadow.parent, audit.inputs.probes)
                shadow.write_text("int shadow;\n")
                if restored:
                    shadow.unlink()
                audit.validate(errors)
                self.assertTrue(errors)

    def test_source_audit_probe_exhaustion_terminates_once(self):
        import contextlib
        from Family.Verification import CxetFamilyVerificationFriendPolicy as policy
        from Family.Targets import CxetFamilyTargetPolicy as target_policy
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            root = Path(directory)
            source_root = root / "sample"
            source_root.mkdir()
            for index in range(32):
                (source_root / str(index)).mkdir()
            stack.enter_context(patch.object(target_policy, "ROOT", root))
            stack.enter_context(patch.multiple(policy, ROOT=root,
                _VERIFICATION_SOURCE_ROOTS=("sample",), _VERIFICATION_RETIRED_SEAM_PATHS=(),
                _VERIFICATION_FRIEND_SOURCE_LINES={}, _VERIFICATION_PROTECTED_FRIEND_LINES={},
                _VERIFICATION_PROTECTED_SHA256={}, _VERIFICATION_UNRESOLVED_QUOTED_INCLUDES={},
                _MAX_VERIFICATION_SNAPSHOT_PROBES=8))
            stack.enter_context(patch.object(policy, "_validate_cpp_include_microcases"))
            errors = []
            audit = policy.capture_verification_source_audit(errors, check_include_boundaries=False)
            self.assertEqual(errors, ["verification source snapshot exceeds 8 path probes"])
            self.assertEqual(len(audit.inputs.probes), 8)

    def test_compile_environment_cache_keeps_exact_universe_and_profile(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        from Family.Sources.CxetFamilyIncludeReachability import _empty_model, _Effect, _EnvironmentResolver
        model = _empty_model(["consumer", "provider"])
        left, right = ((("branch", 0),),), ((("branch", 1),),)
        model.compile_roots["consumer"] = [_Effect("left", left), _Effect("right", right)]
        model.compile_links["consumer"] = [_Effect("provider", ALL_PATHS)]
        model.interface_roots["provider"] = [_Effect("published", ALL_PATHS)]
        registry = SimpleNamespace(declaration_paths=lambda target: ALL_PATHS)
        errors = []
        resolver = _EnvironmentResolver(model, registry, errors)
        first = resolver.compile("consumer", left)
        self.assertEqual(first.roots, ("left", "published"))
        self.assertIs(resolver.compile("consumer", left), first)
        self.assertEqual(resolver.compile("consumer", right).roots, ("right", "published"))
        self.assertEqual(resolver.compile("provider", left).roots, ())
        independent = _EnvironmentResolver(model, registry, errors)
        self.assertIsNot(independent.compile("consumer", left), first)
        self.assertEqual(errors, [])

    def test_shared_syntax_memo_requires_fresh_equal_adapted_bytes(self):
        from Family.Sources.CxetFamilyIncludeReachability import CppIncludeSyntaxMemo
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        calls = []
        def scanner(data):
            calls.append(data)
            return cpp_include_syntax(data)
        memo = CppIncludeSyntaxMemo(scanner)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.h"
            source.write_bytes(b"#include <a>\n")
            first = IncludeInputs(root)
            includes, errors = memo.syntax("source.h", first.read("source.h"))
            self.assertEqual(includes, ((b"a", False),))
            self.assertEqual(errors, ())
            second = IncludeInputs(root)
            self.assertEqual(memo.syntax("source.h", second.read("source.h")), (includes, errors))
            self.assertEqual(len(calls), 1)
            self.assertEqual(second.validate(), ())
            source.write_bytes(b"import unsafe_module;\n")
            third = IncludeInputs(root)
            _, errors = memo.syntax("source.h", third.read("source.h"))
            self.assertTrue(errors)
            self.assertEqual(len(calls), 2)
            self.assertTrue(first.validate())
            self.assertEqual(third.validate(), ())
            # Different target/native adaptations for the same physical file
            # must not borrow the previous byte view's lexical result.
            memo.syntax("source.h", b"#include <native_configuration>\n")
            self.assertEqual(len(calls), 3)

    def test_syntax_memo_has_source_and_payload_caps_with_lru_eviction(self):
        from Family.Sources.CxetFamilyIncludeReachability import CppIncludeSyntaxMemo
        calls = []
        def scanner(data):
            calls.append(data)
            return b"", [], []
        memo = CppIncludeSyntaxMemo(scanner, max_sources=2, max_bytes=4)
        for source in ("a", "b", "a", "c", "b"):
            self.assertEqual(memo.syntax(source, b"x"), ((), ()))
            self.assertLessEqual(len(memo.entries), 2)
            self.assertLessEqual(memo.payload_bytes, 4)
        self.assertEqual(len(calls), 4)
        memo.syntax("oversized", b"large")
        memo.syntax("oversized", b"large")
        self.assertEqual(len(calls), 6)
        self.assertNotIn("oversized", memo.entries)
        with self.assertRaises(ValueError):
            CppIncludeSyntaxMemo(scanner, max_sources=0)
        normalized = CppIncludeSyntaxMemo(lambda data: (b"normalized", [], []), max_bytes=4)
        normalized.full_syntax("a", b"x")
        self.assertFalse(normalized.entries)

    def test_unchanged_input_is_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.h").write_bytes(b"same")
            inputs = IncludeInputs(root)
            self.assertEqual(inputs.read("source.h"), inputs.read("source.h"))
            self.assertEqual(inputs.validate(), ())

    def test_reused_bytes_reject_changed_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.h"
            source.write_bytes(b"old")
            inputs = IncludeInputs(root)
            self.assertEqual(inputs.read("source.h"), b"old")
            source.write_bytes(b"new")
            self.assertEqual(inputs.read("source.h"), b"old")
            self.assertTrue(inputs.validate())

    def test_missing_candidate_cannot_become_shadow(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vector"
            inputs = IncludeInputs(Path(directory))
            self.assertFalse(inputs.probe(path))
            path.write_bytes(b"#include \"private.h\"")
            with self.assertRaises(OSError):
                inputs.probe(path)
            self.assertTrue(inputs.validate())

    def test_replacement_and_symlink_are_not_fresh_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "source.h"
            path.write_bytes(b"same")
            inputs = IncludeInputs(root)
            inputs.read("source.h")
            path.rename(root / "old.h")
            path.symlink_to(root / "old.h")
            self.assertTrue(inputs.validate())

    def test_native_rsa_and_nonrsa_keep_distinct_semantics(self):
        bindings = {"cxet_crypto": "src/src/Core/src/Crypto/RsaMbedConfig.h"}
        rsa = native_include_context("cxet_crypto", "src/src/Core/src/Crypto/Rsa.cpp", False, bindings)
        other = native_include_context("cxet_crypto", "src/src/Core/src/Crypto/Crypto.cpp", False, bindings)
        self.assertEqual(rsa, bindings["cxet_crypto"])
        self.assertIsNone(other)
        self.assertIsNone(native_include_context("cxet_crypto", "src/src/Core/src/Crypto/Rsa.cpp", True, bindings))
        self.assertEqual(other, native_include_context("cxet_crypto", "unrelated.cpp", False, bindings))


if __name__ == '__main__':
    unittest.main()
