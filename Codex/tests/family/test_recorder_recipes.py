"""Recorder recipes regressions."""
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

class RecorderRecipesTests(CurrentRecipeFixture, unittest.TestCase):
    def test_recorder_reuses_only_an_earlier_unconditional_declared_corpus_provider(self):
        contract = "apps/hft-recorder/src/Contracts/CMakeLists.txt"
        recorder = "apps/hft-recorder/CMakeLists.txt"
        relatives = (contract, recorder, "apps/hft-recorder/src/CMakeLists.txt",
                     "apps/hft-recorder/src/Runtime/CMakeLists.txt")
        sources = {relative: (ROOT / relative).read_text() for relative in relatives}
        initial = {relative: {"CXET_LOCAL_TESTS": ("OFF",), "HFTREC_BUILD_APP_TARGETS": ("OFF",),
                              "HFTREC_BUILD_GUI": ("OFF",)} for relative in (contract, recorder)}
        for change, accepted in ((None, True), ("conditional-alias", False), ("unguarded-reuse", False)):
            current = dict(sources)
            if change == "conditional-alias":
                current[contract] = current[contract].replace(
                    "add_library(hftrec::corpus_contract ALIAS hftrec_corpus_contract)",
                    "if(unknown)\nadd_library(hftrec::corpus_contract ALIAS hftrec_corpus_contract)\nendif()")
            elif change == "unguarded-reuse":
                current[recorder] = current[recorder].replace(
                    "if(NOT TARGET hftrec::corpus_contract)", "if(TRUE)")
            errors = []
            files = {relative: (text, parse_commands(relative, text, errors)) for relative, text in current.items()}
            active = compose_active_commands(ROOT, files, (contract, recorder), set(), errors,
                initial_values_by_scope=initial)
            self.assertEqual(not errors, accepted, errors)
            if accepted:
                self.assertEqual(sum(item.command.name == "add_library" and
                    cmake_list_words(item.command.body)[:1] == ["hftrec_corpus_contract"] for item in active), 1)

    def test_recorder_corpus_return_stops_descendants_and_preserves_active_duplicate_rejection(self):
        from dataclasses import replace
        from CMake.Syntax.CmakeFamilyContext import reviewed_source_return
        from CMake.Syntax.CmakeFamilyDialect import validate_active_dialect, validate_exact_active_inventory
        recorder = "apps/hft-recorder/CMakeLists.txt"
        contract = "apps/hft-recorder/src/Contracts/CMakeLists.txt"
        relatives = (recorder, contract, "apps/hft-recorder/src/CMakeLists.txt",
                     "apps/hft-recorder/src/Runtime/CMakeLists.txt")
        sources = {relative: (ROOT / relative).read_text() for relative in relatives}
        values = {"CXET_LOCAL_TESTS": ("ON",), "HFTREC_BUILD_APP_TARGETS": ("OFF",),
                  "HFTREC_BUILD_GUI": ("OFF",)}
        for seeded in (False, True):
            with self.subTest(seeded=seeded):
                errors = []
                files = {relative: (text, parse_commands(relative, text, errors))
                         for relative, text in sources.items()}
                roots = (contract, recorder) if seeded else (recorder,)
                active = compose_active_commands(ROOT, files, roots, set(), errors,
                    initial_values_by_scope={relative: values for relative in roots})
                validate_active_dialect(active, set(function_model(active, errors).global_definitions),
                    cmake_list_words, errors)
                validate_exact_active_inventory(active, cmake_list_words, errors,
                    active_origins=frozenset(item.relative for item in active))
                self.assertEqual(errors, [])
                self.assertEqual(sum(item.command.name == "add_library" and
                    cmake_list_words(item.command.body)[:1] == ["hftrec_corpus_contract"] for item in active), 1)
                self.assertFalse(any(item.relative in relatives[2:] for item in active))
                self.assertTrue(any(item.relative == recorder and item.command.name == "add_subdirectory"
                    and item.command.line == 50 for item in active))
                returned = next(item for item in active if item.relative == recorder and
                    item.command.name == "return")
                self.assertTrue(reviewed_source_return(returned, sources[recorder], files[recorder][1], values))
                for changed in (replace(returned, structural_context=()),
                                replace(returned, binary_base=Path("apps/trader"))):
                    self.assertFalse(reviewed_source_return(changed, sources[recorder], files[recorder][1], values))
                self.assertFalse(reviewed_source_return(returned, sources[recorder], files[recorder][1],
                    dict(values, CXET_LOCAL_TESTS=("ON", "OFF"))))
                self.assertFalse(reviewed_source_return(returned, sources[recorder], files[recorder][1][1:], values))
                if not seeded:
                    package = next(item for item in active if item.relative == contract and
                        item.command.name == "find_package")
                    for changed in (replace(package, structural_context=()),
                                    replace(package, scope=contract),
                                    replace(package, binary_base=Path("apps/trader")),
                                    replace(package, execution_chain=())):
                        rejected = []
                        mutated = [changed if item is package else item for item in active]
                        validate_exact_active_inventory(mutated, cmake_list_words, rejected,
                            active_origins=frozenset(item.relative for item in mutated))
                        self.assertTrue(any("privileged CMake call escaped" in item for item in rejected))
        for change in ("missing-return", "callable-return", "unknown-guard", "active-duplicate"):
            with self.subTest(change=change):
                current = dict(sources)
                if change == "missing-return":
                    current[recorder] = current[recorder].replace("    return()", "")
                elif change == "callable-return":
                    current[recorder] = current[recorder].replace("    return()",
                        "function(borrowed_return)\nreturn()\nendfunction()\nborrowed_return()")
                elif change == "unknown-guard":
                    current[recorder] = current[recorder].replace("if(CXET_LOCAL_TESTS)", "if(unknown)", 1)
                else:
                    current[recorder] = current[recorder].replace("        add_subdirectory(src/Contracts)",
                        "        add_subdirectory(src/Contracts)\n        add_subdirectory(src/Contracts)", 1)
                errors = []
                files = {relative: (text, parse_commands(relative, text, errors))
                         for relative, text in current.items()}
                compose_active_commands(ROOT, files, (recorder,), set(), errors,
                    initial_values_by_scope={recorder: values})
                self.assertTrue(any("duplicate active invocation" in error for error in errors), errors)

    def test_recorder_child_canonical_alias_grounding_reaches_evaluated_provider_fold(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyInstances import GRAPH_INSTANCE_NAMES, directory_target_types
        from Family.Targets.CxetFamilyAliasPolicy import source_owned_recorder_alias, target_aliases
        from Family.Targets.CxetFamilyTargetRegistry import TargetRegistry
        from Family.Targets.CxetFamilyTargetPolicy import canonical_source_structural_error
        recorder = "apps/hft-recorder/CMakeLists.txt"
        contract = "apps/hft-recorder/src/Contracts/CMakeLists.txt"
        provider = "provider/CMakeLists.txt"
        sources = {relative: (ROOT / relative).read_text() for relative in (
            recorder, contract, "apps/hft-recorder/src/CMakeLists.txt",
            "apps/hft-recorder/src/Runtime/CMakeLists.txt")}
        values = {"CXET_ROOT_SOURCE_GRAPH": ("ON",), "CXET_LOCAL_TESTS": ("ON",),
                  "CXET_SANITIZER_PROFILE": ("thread",), "HFTREC_BUILD_APP_TARGETS": ("OFF",),
                  "HFTREC_BUILD_GUI": ("OFF",)}
        for mode in ("fresh", "preseeded", "shadow", "opaque", "unknown-fatal"):
            with self.subTest(mode=mode):
                current = dict(sources)
                current[provider] = "add_library(hftp_contract_headers INTERFACE)\n"
                if mode == "shadow":
                    current[provider] += ("add_library(shadow INTERFACE)\nif(unknown)\n"
                        "add_library(hftrec::corpus_contract ALIAS shadow)\nendif()")
                elif mode == "opaque":
                    current[provider] += "add_library(${opaque} INTERFACE)\n"
                elif mode == "unknown-fatal":
                    current[provider] = 'if(unknown)\nmessage(FATAL_ERROR "unknown")\nendif()\n' + current[provider]
                errors = []
                files = {relative: (text, parse_commands(relative, text, errors))
                         for relative, text in current.items()}
                roots = (provider, contract, recorder) if mode == "preseeded" else (provider, recorder)
                active = compose_active_commands(ROOT, files, roots, set(), errors,
                    initial_values_by_scope={relative: values for relative in roots})
                self.assertEqual(errors, [])
                self.assertTrue(source_owned_recorder_alias("hftrec::corpus_contract", active))
                self.assertFalse(source_owned_recorder_alias("Threads::Threads", active))
                self.assertFalse(source_owned_recorder_alias("future::unknown", active))
                model = function_model(active, errors)
                bootstrap = variable_snapshots(active, model, [], initial_values_by_scope={relative: values for relative in roots})
                instances = instantiated_commands(active, model, bootstrap, GRAPH_INSTANCE_NAMES, [])
                types = directory_target_types(instances, shared_namespace=True, snapshots=bootstrap,
                    active_commands=active, live_eof_paths=bootstrap.live_eof_paths)
                snapshots = variable_snapshots(active, model, errors, directory_target_types=types,
                    initial_values_by_scope={relative: values for relative in roots})
                if mode not in {"fresh", "preseeded"}:
                    self.assertTrue(any("non-exact foreach" in error for error in errors), errors)
                    continue
                self.assertEqual(errors, [])
                loop = next(item for item in active if item.relative == contract and item.command.name == "foreach")
                self.assertEqual(snapshots.values[loop.ordinal]["_hftrec_offline_providers"],
                    ("hftrec_corpus_contract", "hftrec_capture_launch", "hftrec_capture_client"))
                instances = instantiated_commands(active, model, snapshots, GRAPH_INSTANCE_NAMES, errors, types)
                corpus = [item for item in instances if item.body.relative == contract]
                registry = TargetRegistry(corpus, errors, live_eof_paths=snapshots.live_eof_paths,
                    active_origins=frozenset({contract}), active_commands=active, snapshots=snapshots)
                aliases = target_aliases(corpus, errors, registry)
                self.assertEqual(aliases["hftrec::corpus_contract"], "hftrec_corpus_contract")
                declaration = next(item for item in corpus if item.body.command.name == "add_library" and
                    item.token_groups[0] == ("hftrec_corpus_contract",))
                self.assertIsNone(canonical_source_structural_error("hftrec_corpus_contract", declaration))
                self.assertEqual(errors, [])
                alias = next(item for item in active if item.relative == contract and
                    cmake_list_words(item.command.body)[:2] == ["hftrec::corpus_contract", "ALIAS"])
                mutated = [replace(item, structural_context=()) if item is alias else item for item in active]
                if mode == "fresh":
                    self.assertFalse(source_owned_recorder_alias("hftrec::corpus_contract", mutated))

    def test_recorder_warning_exceptions_stay_at_exact_owner_commands(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyCommandPolicy import _compile_options, safe_compile_option
        self.assertFalse(safe_compile_option("-Wno-unused-parameter"))
        for relative, line in (("apps/hft-recorder/CMakeLists.txt", 43),
                ("apps/hft-recorder/src/Runtime/CMakeLists.txt", 37)):
            instance = self._current_metadata_instance(relative, line, {})
            errors = []
            _compile_options(instance, cmake_list_words, errors)
            self.assertEqual(errors, [])
            for changed in (replace(instance.body, source_base=Path("apps/trader")),
                    replace(instance.body, command=replace(instance.body.command, line=line + 1))):
                errors = []
                _compile_options(replace(instance, body=changed, evaluation=changed), cmake_list_words, errors)
                self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
