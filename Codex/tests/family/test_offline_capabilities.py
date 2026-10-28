"""Offline capabilities regressions."""
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

class OfflineCapabilityTests(unittest.TestCase):
    origin = "src/tests/offline/CMakeLists.txt"

    def test_current_offline_include_inventory_matches_exact_registered_roots(self):
        from Family.Sources.CxetFamilyIncludeReachability import _EXACT_DIRECT_INCLUDE_ORDER
        from Family.Targets.CxetFamilyBuildPolicy import registered_offline_include_roots
        for target in (
                "cxet_offline_account_cashflows", "cxet_offline_account_query_runtime",
                "cxet_offline_cbr_decision", "cxet_offline_market_preparation",
                "cxet_offline_moex_normalization", "cxet_offline_native_pnl_contracts",
                "cxet_offline_native_reference_rest_request", "cxet_offline_poloniex_normalization",
                "cxet_offline_tbank_order_observations", "cxet_offline_tbank_parity",
                "cxet_offline_trading_financial_contracts", "cxet_offline_finam_auth_buffers"):
            with self.subTest(target=target):
                include = next(command for command in self._commands(target)
                    if command.name == "target_include_directories")
                roots = registered_offline_include_roots(self._instance(include), target)
                self.assertEqual(_EXACT_DIRECT_INCLUDE_ORDER[target],
                                 tuple(("PRIVATE", root) for root in roots))

    def test_new_private_fixture_edges_stay_exact_to_the_registered_translation_unit(self):
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_private_header_edge
        for target, source, headers in (
                ("cxet_offline_account_query_runtime", "Api/Account/AccountQueryRuntimeContract.cpp",
                 ("Api/User/AccountQueryRuntimeTestAccess.hpp", "Api/User/AccountQueryFailurePolicy.hpp")),
                ("cxet_offline_native_reference_rest_request", "Api/Instrument/NativeReferenceRestRequest.cpp",
                 ("Api/Reference/Internal/NativeReferenceRestRequest.hpp", "Api/Reference/Internal/ReferenceRestPreparation.hpp")),
                ("cxet_offline_core_api", "Api/Boundary/CoreApiBoundaries.cpp", ("Network/Common/BoundedDnsDoh.hpp",)),
                ("cxet_offline_transport", "Network/Common/TransportBoundaries.cpp",
                 ("Private/Network/Ws/Runtime/Detail/Common.hpp", "Private/Network/Ws/Runtime/WsRuntimeDetail.hpp",
                  "Network/Ws/Compression/WsInflateWorkBudget.hpp"))):
            registration = offline_registration(self._instance(self._commands(target)[0]), target)
            source = "src/tests/offline/" + source
            for header in headers:
                selected = "src/src/Core/src/" + header
                with self.subTest(target=target, header=header):
                    self.assertTrue(offline_private_header_edge(registration, source, selected, source))
                    self.assertFalse(offline_private_header_edge(None, source, selected, source))
                    self.assertFalse(offline_private_header_edge(registration, source, selected, "src/src/Main.cpp"))
                    self.assertFalse(offline_private_header_edge(registration, source, selected + ".future", source))

    def test_order_private_diagnostic_edges_reject_foreign_targets_and_translation_units(self):
        from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_private_header_edge
        header = "src/src/Core/src/Api/Order/OrderSessionPoolInternal.hpp"
        for owner, target, root, translation_unit, source in (
                ("CXETCPP", "cxet_offline_order_lifecycle", "src/tests/offline/",
                 "Api/Order/OrderLifecycleFence.cpp", "Api/Order/OrderLifecycleFence.cpp"),
                ("hft-parser", "hftp_offline_native_order_variants", "apps/hft-parser/tests/offline/",
                 "Session/Order/NativeOrderVariants.cpp", "Session/Order/NativeOrderVariants.cpp"),
                ("trader", "trader_offline_cases", "apps/trader/tests/offline/",
                 "Fleet/FleetNativeOwnerCases.cpp", "Fleet/FleetNativeOwnerCases/StartupFailure.ipp"),
                ("trader", "trader_offline_finam_full_path", "apps/trader/tests/offline/",
                 "Execution/FinamDelPairTransportCases.cpp", "Execution/FinamDelPairTransportCases.cpp")):
            translation_unit, source = root + translation_unit, root + source
            registration = SimpleNamespace(owner=owner, target=target, relative=root + "CMakeLists.txt",
                                           sources=(translation_unit,))
            with self.subTest(target=target):
                self.assertTrue(offline_private_header_edge(registration, source, header, translation_unit))
                self.assertFalse(offline_private_header_edge(None, source, header, translation_unit))
                self.assertFalse(offline_private_header_edge(registration, source, header, root + "Foreign.cpp"))
                self.assertFalse(offline_private_header_edge(registration, source + ".future", header, translation_unit))
                self.assertFalse(offline_private_header_edge(registration, source,
                    "src/src/Core/src/Api/Order/Common/OrderSessionOwnerState.hpp", translation_unit))
                for changes in ({"target": "foreign_offline_cases"}, {"owner": "foreign"},
                                {"relative": "foreign/tests/offline/CMakeLists.txt"}, {"sources": ()}):
                    foreign = SimpleNamespace(**(vars(registration) | changes))
                    self.assertFalse(offline_private_header_edge(foreign, source, header, translation_unit))

    def test_cstdarg_is_one_known_standard_header(self):
        self.assertTrue(approved_external_angle_include("cstdarg"))
        self.assertFalse(approved_external_angle_include("cstdarg/Future.hpp"))

    def _commands(self, target):
        errors = []
        commands = parse_commands(self.origin, (ROOT / self.origin).read_text(), errors)
        selected = [command for command in commands
                    if cmake_list_words(command.body)[:1] == [target]]
        lowered = lower_offline_registrations(ROOT, self.origin, selected, errors)
        self.assertEqual(errors, [])
        return lowered

    def _instance(self, command, ordinal=1):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        active = ActiveCommand("fixture", self.origin, Path(self.origin).parent,
                               Path(self.origin).parent, (), command, ordinal)
        groups = tuple((word.replace("${CMAKE_SOURCE_DIR}", str(ROOT)),)
                       for word in cmake_list_words(command.body))
        return InstantiatedCommand(active, active, groups, ordinal, ALL_PATHS)

    def _parser_instances(self, target=None, *, owner="hft-parser"):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        relative = f"apps/{owner}/tests/offline/CMakeLists.txt"
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        lowered = lower_offline_registrations(ROOT, relative, commands, errors)
        self.assertEqual(errors, [])
        result = []
        for ordinal, command in enumerate(lowered, 1):
            if target is not None and cmake_list_words(command.body)[:1] != [target]:
                continue
            active = ActiveCommand("parser-fixture", relative, Path(relative).parent,
                                   Path(relative).parent, (), command, ordinal)
            groups = tuple((word.replace("${CMAKE_SOURCE_DIR}", str(ROOT)).replace(
                "${CMAKE_CURRENT_SOURCE_DIR}", Path(relative).parent.as_posix()),)
                for word in cmake_list_words(command.body))
            result.append(InstantiatedCommand(active, active, groups, ordinal, ALL_PATHS))
        return result

    def test_parser_composition_properties_stay_owner_target_and_value_scoped(self):
        from dataclasses import replace
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, InstantiatedCommand
        from CMake.Policy.CmakeFamilyPropertyPolicy import _target_property
        relative = "apps/hft-parser/cmake/HftpLibraries.cmake"
        base = Path("apps/hft-parser")
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        self.assertEqual(errors, [])
        cases = []
        for command in commands:
            words = cmake_list_words(command.body)
            if command.name == "set_target_properties" and "INTERFACE_HFTP_RUNTIME_COMPOSITION" in words:
                index = words.index("PROPERTIES")
                cases.append((command, words[:index], "INTERFACE_HFTP_RUNTIME_COMPOSITION", (words[-1],)))
            elif command.name == "set_property" and "COMPATIBLE_INTERFACE_STRING" in words:
                cases.append((command, words[1:words.index("APPEND")], "COMPATIBLE_INTERFACE_STRING", (words[-1],)))
        self.assertEqual(len(cases), 3)
        for command, targets, name, values in cases:
            active = ActiveCommand("parser-composition", relative, base, base, (), command, 1)
            instance = InstantiatedCommand(active, active, tuple((word,) for word in cmake_list_words(command.body)), 1, ALL_PATHS)
            for target in targets:
                self.assertTrue(_target_property(instance, target, name, values))
                self.assertFalse(_target_property(instance, target, name, ("other",)))
                foreign = replace(active, relative="apps/trader/CMakeLists.txt")
                self.assertFalse(_target_property(replace(instance, body=foreign, evaluation=foreign), target, name, values))
            self.assertFalse(_target_property(instance, "hftp_reference", name, values))

    def test_resident_fixture_core_headers_and_cstdarg_stay_source_scoped(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_public_header_edge, offline_external_include
        from Family.Sources.CxetFamilyIncludeReachability import _EXACT_OFFLINE_INCLUDE_CONTRACTS
        from Family.Targets.CxetFamilyBuildPolicy import registered_offline_include_roots
        target = 'cxet_offline_resident_memory'
        source = 'src/tests/offline/Primitives/ResidentMemory.cpp'
        commands = self._commands(target)
        declaration = self._instance(next(command for command in commands if command.name == 'add_executable'))
        include = self._instance(next(command for command in commands if command.name == 'target_include_directories'))
        registration = offline_registration(declaration, target)
        self.assertEqual(registration.libraries, ('cxet::resident_memory',))
        roots = ('tools/Testing', 'src/src/Core/include')
        self.assertEqual(registered_offline_include_roots(include, target), roots)
        self.assertEqual(_EXACT_OFFLINE_INCLUDE_CONTRACTS[self.origin][target], roots)
        core = 'src/src/Core/include/cxet/'
        admission = core + 'Api/Stream/RuntimeEventAdmission.hpp'
        drain = core + 'Runtime/Market/MarketIngressDrain.hpp'
        view = core + 'Api/Stream/RuntimeEventView.hpp'
        for parent, selected in ((source, admission), (source, drain), (admission, view)):
            self.assertTrue(offline_public_header_edge(registration, parent, selected, source))
            for changed in (None, replace(registration, includes=()),
                            replace(registration, target='cxet_offline_future'),
                            replace(registration, libraries=())):
                self.assertFalse(offline_public_header_edge(changed, parent, selected, source))
        self.assertFalse(offline_public_header_edge(registration, source, view, source))
        self.assertFalse(offline_public_header_edge(registration, source, core + 'Api/Order/Prepared/WideOrderPath.hpp', source))
        self.assertTrue(offline_external_include(registration, source, 'cstdarg', source))
        self.assertFalse(offline_external_include(registration, source, 'future_header', source))
        self.assertFalse(offline_external_include(replace(registration, target='cxet_offline_future'), source, 'cstdarg', source))

    def test_startup_residency_cstdarg_requires_exact_private_target_and_tu(self):
        from Family.Sources.CxetFamilyOfflineSourcePolicy import (
            offline_external_include, startup_resident_external_include,
        )
        source = "apps/trader/tests/startup/StartupResidentMemory.cpp"
        for target in ("trader_startup_fixture", "trader_startup_alert_fixture"):
            self.assertTrue(offline_external_include(None, source, "cstdarg", source, target=target))
            self.assertFalse(offline_external_include(None, source, "cstdarg", source,
                target=target, public_seed=True))
            self.assertFalse(offline_external_include(None, source, "cstdarg", "apps/trader/src/Main.cpp",
                target=target))
            self.assertFalse(offline_external_include(None, "apps/trader/tests/startup/Other.cpp", "cstdarg", source,
                target=target))
            self.assertFalse(offline_external_include(None, source, "future_header", source, target=target))
            registration = SimpleNamespace(owner="trader", relative="apps/trader/tests/offline/CMakeLists.txt",
                target=target, sources=(source,))
            self.assertFalse(offline_external_include(registration, source, "cstdarg", source, target=target))
        for target in (None, "trader_startup_isolation_probe", "traderd", "trader_startup_network"):
            self.assertFalse(offline_external_include(None, source, "cstdarg", source, target=target))
        self.assertTrue(startup_resident_external_include(source, "cstdarg"))
        self.assertFalse(startup_resident_external_include(source, "future_header"))
        self.assertFalse(startup_resident_external_include("apps/trader/src/Main.cpp", "cstdarg"))
        self.assertFalse(approved_external_angle_include("cstdarg"))

    def test_shared_resident_fixture_survives_all_three_ownership_gates(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_canonical_source
        from Family.Targets.CxetFamilyTargetPolicy import declared_source_owner_error
        relative = "apps/hft-parser/tests/offline/CMakeLists.txt"
        source = "src/tests/offline/Support/ResidentMemoryFixture.cpp"
        targets = ("hftp_offline_kernel_handoff", "hftp_offline_source_recovery",
                   "hftp_offline_cold_reservoir", "hftp_offline_source_recovery_warm",
                   "hftp_offline_native_account_publication", "hftp_offline_native_order_variants")
        for target in targets:
            # This lowers the real helper through its early owner boundary.
            declaration = next(item for item in self._parser_instances(target)
                if item.body.command.name == "add_executable")
            registration = offline_registration(declaration, target)
            self.assertIn(source, registration.sources)
            self.assertIsNone(declared_source_owner_error(target, declaration, declaration, source))
            self.assertTrue(offline_canonical_source(declaration, target, source))
            self.assertIsNotNone(declared_source_owner_error(target, declaration, declaration,
                "src/tests/offline/Primitives/ResidentMemory.cpp"))
            # Equal data from a different registration cannot borrow this seam.
            unbound = replace(declaration.body, command=replace(declaration.body.command,
                registration=replace(registration)))
            self.assertIsNotNone(declared_source_owner_error(target, declaration,
                replace(declaration, body=unbound, evaluation=unbound), source))
        errors = []
        commands = parse_commands(relative, (ROOT / relative).read_text(), errors)
        original = next(command for command in commands
            if command.name == "cxet_add_offline_suite" and
            cmake_list_words(command.body)[:1] == [targets[0]])
        future = replace(original, body=original.body.replace(targets[0], "hftp_offline_future_residency", 1))
        lower_offline_registrations(ROOT, relative, [future], errors)
        self.assertTrue(any("offline source escapes its owner" in error for error in errors))

    def test_parser_helper_include_capability_requires_exact_private_recipe_and_owner(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyBuildPolicy import registered_offline_include_roots
        from Family.Targets.CxetFamilyTargetPolicy import target_include_error
        target = "hftp_offline_cases"
        instances = self._parser_instances(target)
        declaration = next(item for item in instances if item.body.command.name == "add_executable")
        include = next(item for item in instances if item.body.command.name == "target_include_directories")
        self.assertEqual(registered_offline_include_roots(include, target), (
            "tools/Testing", "apps/hft-parser/src/Runtime/include", "apps/hft-parser/src/Runtime/src"))
        root = "apps/hft-parser/tests/offline/../../src/Runtime/src"
        self.assertIsNone(target_include_error(target, declaration, root, include))
        command = replace(include.body.command, body=include.body.command.body.replace("PRIVATE", "PUBLIC"))
        active = replace(include.body, command=command)
        self.assertEqual(registered_offline_include_roots(
            replace(include, body=active, evaluation=active), target), ())
        active = replace(include.body, command=replace(include.body.command, registration=None))
        self.assertEqual(registered_offline_include_roots(
            replace(include, body=active, evaluation=active), target), ())
        self.assertIsNotNone(target_include_error(target, declaration, "src/src/Core/src", include))

    def test_parser_diagnostic_source_and_header_capabilities_are_target_and_tu_scoped(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import (
            offline_source_registrations, offline_canonical_source,
            offline_private_header_edge, offline_public_header_edge, offline_external_include,
            _PARSER_PORTABLE_REFERENCE_EDGES,
        )
        target = "hftp_offline_catalogue_identities"
        declaration = next(item for item in self._parser_instances(target)
            if item.body.command.name == "add_executable")
        registration = offline_registration(declaration, target)
        source = "apps/hft-parser/src/Runtime/src/Market/Ingestion/Detail/Topology/Source/PublicMarketStableIdentities.cpp"
        registry = SimpleNamespace(context_for_use=lambda *args, **kwargs: declaration)
        self.assertIs(offline_source_registrations([(target, declaration, source)], registry)[target, source], registration)
        self.assertTrue(offline_canonical_source(declaration, target, source))
        self.assertFalse(offline_canonical_source(declaration, "hftp_offline_cases", source))
        self.assertFalse(offline_canonical_source(declaration, target, source + ".copy.cpp"))
        header = "apps/hft-parser/src/Runtime/include/hft_parser/Internal/CheckedArithmetic.hpp"
        self.assertTrue(offline_public_header_edge(registration, source, header, source))
        self.assertFalse(offline_public_header_edge(None, source, header, source))
        self.assertFalse(offline_public_header_edge(replace(registration, includes=()), source, header, source))
        self.assertFalse(offline_public_header_edge(registration, source, header, "src/src/Main.cpp"))
        target = "hftp_offline_native_account_publication"
        declaration = next(item for item in self._parser_instances(target)
            if item.body.command.name == "add_executable")
        registration = offline_registration(declaration, target)
        source = "apps/hft-parser/tests/offline/Session/Account/NativeAccountPublication.cpp"
        header = "src/src/Core/src/Api/User/Common/NativeAccountWriterLeaseInternal.hpp"
        self.assertTrue(offline_private_header_edge(registration, source, header, source))
        self.assertFalse(offline_private_header_edge(None, source, header, source))
        self.assertFalse(offline_private_header_edge(replace(registration, target="hftp_offline_cases"), source, header, source))
        self.assertFalse(offline_private_header_edge(registration, source, header, "src/src/Main.cpp"))
        self.assertFalse(offline_private_header_edge(registration, source,
            "src/src/Core/src/Network/Grpc/Private/GrpcClientInternal.hpp", source))
        self.assertTrue(offline_external_include(registration, source, "barrier", source))
        self.assertFalse(offline_external_include(registration, source, "unknown_future.hpp", source))
        target = "hftp_offline_portable_catalog"
        declaration = next(item for item in self._parser_instances(target)
            if item.body.command.name == "add_executable")
        registration = offline_registration(declaration, target)
        translation_unit = "apps/hft-parser/tests/offline/Reference/PortablePublicCatalog.cpp"
        for source, header in _PARSER_PORTABLE_REFERENCE_EDGES:
            self.assertTrue(offline_public_header_edge(registration, source, header, translation_unit))
            self.assertFalse(offline_public_header_edge(None, source, header, translation_unit))
            self.assertFalse(offline_public_header_edge(replace(registration, includes=()), source, header, translation_unit))
            self.assertFalse(offline_public_header_edge(replace(registration, target="hftp_offline_cases"), source, header, translation_unit))
            self.assertFalse(offline_public_header_edge(registration, source, header, "src/src/Main.cpp"))
        self.assertFalse(offline_public_header_edge(registration, source,
            "src/src/Core/src/Api/Order/OrderSessionPoolInternal.hpp", translation_unit))
        self.assertFalse(offline_public_header_edge(registration, source,
            "src/src/Core/src/Network/Grpc/Private/GrpcClientInternal.hpp", translation_unit))

    def test_parser_portable_reference_edges_cover_the_current_recursive_type_headers(self):
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        from Family.Sources.CxetFamilyOfflineSourcePolicy import _PARSER_PORTABLE_REFERENCE_EDGES
        include_roots = ("src/src/Core/include", "src/src/Contracts/include",
                         "apps/hft-parser/src/Runtime/include", "apps/hft-parser/src/Contracts/include")
        queue = ["apps/hft-parser/src/Runtime/include/hft_parser/Reference/ReferenceTypes.hpp"]
        seen, required = set(), set()
        while queue:
            source = queue.pop()
            if source in seen:
                continue
            self.assertLess(len(seen), 128, "reference fixture header closure exceeded its static read bound")
            seen.add(source)
            _normalized, includes, _syntax_errors = cpp_include_syntax((ROOT / source).read_bytes())
            for spelling, quoted in includes:
                if not quoted:
                    continue
                include = spelling.decode("utf-8")
                candidates = (ROOT / Path(source).parent / include,
                              *(ROOT / base / include for base in include_roots))
                selected = next((path.relative_to(ROOT).as_posix() for path in candidates if path.is_file()), None)
                self.assertIsNotNone(selected, (source, include))
                queue.append(selected)
                core = "src/src/Core/include/"
                if selected.startswith(core):
                    logical = selected.removeprefix(core)
                    if (logical not in surface._CORE_API_HEADERS and
                            not logical.startswith(surface._CORE_HEADER_PREFIXES)):
                        required.add((source, selected))
        self.assertEqual(required, _PARSER_PORTABLE_REFERENCE_EDGES)

    def test_parser_access_control_option_stays_on_three_exact_registered_calls(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyBuildPolicy import exact_offline_options, PARSER_OFFLINE_COMPILE_OPTION_RECIPES
        for target in PARSER_OFFLINE_COMPILE_OPTION_RECIPES:
            instance = next(item for item in self._parser_instances(target)
                if item.body.command.name == "target_compile_options")
            self.assertTrue(exact_offline_options(instance, "target_compile_options",
                PARSER_OFFLINE_COMPILE_OPTION_RECIPES, owner="hft-parser"))
            self.assertFalse(exact_offline_options(instance, "target_compile_options",
                PARSER_OFFLINE_COMPILE_OPTION_RECIPES))
            active = replace(instance.body, command=replace(instance.body.command,
                body=instance.body.command.body + " -fno-rtti"))
            self.assertFalse(exact_offline_options(replace(instance, body=active, evaluation=active),
                "target_compile_options", PARSER_OFFLINE_COMPILE_OPTION_RECIPES, owner="hft-parser"))

    def test_parser_residency_wrappers_require_exact_fixture_owner_and_flags(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyLinkOptions import exact_offline_link_options, safe_link_option
        from Family.Targets.CxetFamilyBuildPolicy import (
            exact_offline_options, PARSER_OFFLINE_LINK_OPTION_RECIPES,
        )
        actual = {cmake_list_words(item.body.command.body)[0]
                  for item in self._parser_instances()
                  if item.body.command.name == "target_link_options"}
        self.assertEqual(actual, set(PARSER_OFFLINE_LINK_OPTION_RECIPES))
        for target, (_, flags) in PARSER_OFFLINE_LINK_OPTION_RECIPES.items():
            instance = next(item for item in self._parser_instances(target)
                if item.body.command.name == "target_link_options")
            self.assertTrue(exact_offline_link_options(instance, [target], list(flags)))
            self.assertFalse(exact_offline_options(instance, "target_link_options",
                PARSER_OFFLINE_LINK_OPTION_RECIPES))
            self.assertTrue(all(not safe_link_option(flag) for flag in flags))
            self.assertFalse(exact_offline_link_options(instance, [target], [*flags, "-Wl,--wrap=mmap"]))
            shifted = replace(instance.body, command=replace(instance.body.command,
                line=instance.body.command.line + 1))
            self.assertFalse(exact_offline_link_options(
                replace(instance, body=shifted, evaluation=shifted), [target], list(flags)))

    def test_trader_and_diagnostic_wrappers_keep_owner_source_and_flag_boundaries(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyLinkOptions import exact_offline_link_options, safe_link_option
        from Family.Targets.CxetFamilyBuildPolicy import (
            exact_offline_options, TRADER_OFFLINE_LINK_OPTION_RECIPES,
            DIAGNOSTIC_OFFLINE_LINK_OPTION_RECIPES,
        )
        for owner, recipes in (("trader", TRADER_OFFLINE_LINK_OPTION_RECIPES),
                               ("diagnostic", DIAGNOSTIC_OFFLINE_LINK_OPTION_RECIPES)):
            instances = [item for item in self._parser_instances(owner=owner)
                         if item.body.command.name == "target_link_options"]
            self.assertEqual({cmake_list_words(item.body.command.body)[0] for item in instances},
                             set(recipes))
            for instance in instances:
                target = cmake_list_words(instance.body.command.body)[0]
                flags = list(recipes[target][1])
                self.assertTrue(exact_offline_link_options(instance, [target], flags))
                self.assertTrue(all(not safe_link_option(flag) for flag in flags))
                self.assertFalse(exact_offline_options(instance, "target_link_options", recipes))
                self.assertFalse(exact_offline_link_options(instance, [target],
                                                           [*flags, "-Wl,--wrap=mmap"]))
                for change in ({"line": instance.body.command.line + 1},
                               {"body": instance.body.command.body + " -Wl,--wrap=mmap"}):
                    shifted = replace(instance.body, command=replace(instance.body.command, **change))
                    self.assertFalse(exact_offline_link_options(
                        replace(instance, body=shifted, evaluation=shifted), [target], flags))
                foreign = replace(instance.body, relative="apps/foreign/tests/offline/CMakeLists.txt")
                self.assertFalse(exact_offline_link_options(
                    replace(instance, body=foreign, evaluation=foreign), [target], flags))

    def test_offline_tag_requires_helper_validation_and_exact_evaluation(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration, offline_instance_context
        from CMake.Flow.CmakeFamilyGraph import Command
        target = "cxet_offline_primitive_storage"
        commands = self._commands(target)
        declaration = self._instance(commands[0])
        registration = offline_registration(declaration, target)
        self.assertIsNotNone(registration)
        self.assertTrue(all(getattr(command, "registration", None) is registration for command in commands))
        self.assertTrue(offline_instance_context(declaration, target))
        self.assertIsNone(offline_registration(declaration, "cxet_lib"))
        wrong = replace(declaration, evaluation=replace(declaration.evaluation, source_base=Path("src/src")))
        self.assertIsNone(offline_registration(wrong, target))
        ordinary = Command(commands[0].name, commands[0].body, commands[0].line)
        self.assertIsNone(offline_registration(self._instance(ordinary), target))
        copied = replace(commands[0], registration=replace(registration))
        self.assertIsNone(offline_registration(replace(declaration,
            evaluation=replace(declaration.evaluation, command=copied)), target))
        errors = []
        lower_offline_registrations(ROOT, self.origin, [Command("cxet_add_offline_suite",
            "x OWNER CXETCPP EXPECTED 999 SOURCES PrimitiveStorageContracts.cpp", 1)], errors)
        self.assertTrue(errors)
        errors = []
        active = compose_active_commands(ROOT, {self.origin: ("", commands)}, (self.origin,), set(), errors)
        model = function_model(active, errors)
        snapshots = variable_snapshots(active, model, errors)
        instances = instantiated_commands(active, model, snapshots, {command.name for command in commands}, errors)
        self.assertEqual(errors, [])
        self.assertTrue(instances)
        self.assertTrue(all(offline_registration(item, target) is registration for item in instances))

    def test_offline_compile_and_link_recipes_do_not_authorize_extra_flags(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyBuildPolicy import (
            OFFLINE_COMPILE_OPTION_RECIPES, OFFLINE_LINK_OPTION_RECIPES, exact_offline_options,
        )
        for name, recipes in (("target_compile_options", OFFLINE_COMPILE_OPTION_RECIPES),
                              ("target_link_options", OFFLINE_LINK_OPTION_RECIPES)):
            errors = []
            actual = {cmake_list_words(command.body)[0] for command in
                      parse_commands(self.origin, (ROOT / self.origin).read_text(), errors)
                      if command.name == name}
            self.assertEqual(errors, [])
            self.assertEqual(actual, set(recipes))
            for target in recipes:
                command = next(command for command in self._commands(target) if command.name == name)
                self.assertTrue(exact_offline_options(self._instance(command), name, recipes))
                self.assertFalse(exact_offline_options(self._instance(replace(command,
                    body=command.body + " -D__APPLE__=1")), name, recipes))
                self.assertFalse(exact_offline_options(self._instance(replace(command,
                    line=command.line + 1)), name, recipes))

    def test_offline_external_oracle_link_requires_exact_producer(self):
        from dataclasses import replace
        from Family.Targets.CxetFamilyBuildPolicy import exact_offline_external_link
        target = "cxet_offline_private_contract_lowering"
        command = next(item for item in self._commands(target) if item.name == "target_link_libraries")
        self.assertTrue(exact_offline_external_link(self._instance(command), target, "OpenSSL::SSL"))
        self.assertFalse(exact_offline_external_link(self._instance(command), target, "Threads::Threads"))
        self.assertFalse(exact_offline_external_link(self._instance(replace(command,
            body=command.body.replace("OpenSSL::SSL", "OpenSSL::Crypto"))), target, "OpenSSL::SSL"))

    def test_offline_liburing_carrier_requires_registration_and_provider_evidence(self):
        from Family.Targets.CxetFamilyBuildPolicy import offline_liburing_include_context
        from CMake.Flow.CmakeFamilyFlow import NO_PATHS
        target = "cxet_offline_optional_busy_poll"
        instances = [self._instance(command, index) for index, command in enumerate(self._commands(target))]
        declaration = next(item for item in instances if item.body.command.name == "add_executable")
        include = next(item for item in instances if item.body.command.name == "target_include_directories")
        registry = SimpleNamespace(context_for_use=lambda *_: declaration,
            resolve=lambda *_, **__: [object()], exact_prior_imported=lambda *_: [object()])
        self.assertTrue(offline_liburing_include_context(include, target, registry, instances))
        self.assertFalse(offline_liburing_include_context(include, target, registry, [declaration, include]))
        registry.exact_prior_imported = lambda *_: []
        self.assertFalse(offline_liburing_include_context(include, target, registry, instances))
        registry.exact_prior_imported = lambda *_: [object()]
        from dataclasses import replace
        links = [replace(item, path_alternatives=NO_PATHS) if item.body.command.name == "target_link_libraries"
                 else item for item in instances]
        self.assertFalse(offline_liburing_include_context(include, target, registry, links))

    def test_offline_private_and_header_only_seams_keep_tu_and_production_boundaries(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import (
            offline_private_header_edge, offline_public_header_edge, offline_external_include,
        )
        target = "cxet_offline_optional_busy_poll"
        registration = offline_registration(self._instance(self._commands(target)[0]), target)
        source = "src/tests/offline/Network/Ws/OptionalBusyPoll.cpp"
        selected = "src/src/Core/src/Network/Ws/Runtime/WsNapiBusyPoll.hpp"
        self.assertTrue(offline_private_header_edge(registration, source, selected, source))
        self.assertFalse(offline_private_header_edge(registration, source, selected, "src/src/Main.cpp"))
        self.assertFalse(offline_private_header_edge(None, source, selected, source))
        self.assertTrue(offline_external_include(registration, source, "cstdarg", source))
        self.assertFalse(offline_external_include(registration, source, "future.h", source))
        target = "cxet_offline_optional_parser_primitives"
        registration = offline_registration(self._instance(self._commands(target)[0]), target)
        source = registration.sources[0]
        selected = "src/src/Core/include/cxet/Network/Fix/FixTagValue.hpp"
        self.assertTrue(offline_public_header_edge(registration, source, selected, source))
        self.assertFalse(offline_public_header_edge(replace(registration, includes=()), source, selected, source))
        self.assertFalse(offline_public_header_edge(None, source, selected, source))
        self.assertFalse(offline_public_header_edge(registration, source,
            "src/src/Core/src/Network/Grpc/Private/GrpcClientInternal.hpp", source))

    def test_offline_crypto_oracle_config_tu_and_source_override_remain_separate(self):
        from Family.Sources.CxetFamilyNativeInputs import NativeInputs, native_test_configuration_error
        from Family.Sources.CxetFamilySourcePolicy import native_crypto_include_edge, native_crypto_definition_error
        target = "cxet_offline_crypto_primitives"
        cold = "cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h"
        rsa = "src/src/Core/src/Crypto/RsaMbedConfig.h"
        source = "src/tests/offline/Primitives/Crypto/RsaTestAes.c"
        self.assertEqual(native_include_context(target, source, False, {target: cold}), rsa)
        self.assertEqual(native_include_context(target, "src/tests/offline/Primitives/Crypto/RsaSigner.cpp", False, {target: cold}), cold)
        self.assertIsNone(native_include_context(target, source, True, {target: cold}))
        self.assertIsNone(native_include_context(target, source, False, {}))
        header = "extra/mbedtls-cold/include/mbedtls/build_info.h"
        self.assertTrue(native_crypto_include_edge(target, header, cold, config=cold))
        self.assertFalse(native_crypto_include_edge(target, header, cold, config=rsa))
        self.assertTrue(native_crypto_definition_error(target, "__APPLE__=1"))
        inputs = IncludeInputs(ROOT)
        native = NativeInputs(inputs)
        data = inputs.read(source)
        self.assertFalse(native.verify(source, data))
        with self.assertRaises(OSError):
            native.verify(source, data + b"\n#define __APPLE__ 1\n")
        signer = "src/tests/offline/Primitives/Crypto/RsaSigner.cpp"
        self.assertFalse(native_test_configuration_error(signer, b"#define TEST_CASE 1\n"))
        self.assertTrue(native_test_configuration_error(signer, b"# /* comment */ define __APP\\\nLE__ 1\n"))
        self.assertTrue(native_test_configuration_error(signer, b"#define MBEDTLS_AES_ALT 1\n"))

    def test_metadata_private_seam_preserves_original_fixture_public_header_capability(self):
        from dataclasses import replace
        from CMake.Policy.CmakeFamilyOfflineRecipe import offline_registration
        from Family.Sources.CxetFamilyOfflineSourcePolicy import offline_public_header_edge
        target = "cxet_offline_native_metadata_quantity"
        registration = offline_registration(self._instance(self._commands(target)[0]), target)
        translation_unit = "src/tests/offline/Api/Instrument/NativeMetadataQuantity.cpp"
        source = "src/src/Core/src/Api/Instrument/Internal/SymbolMetadataRules.ipp"
        selected = "src/src/Core/include/cxet/Api/Instrument/SymbolMetadataResolve.hpp"
        self.assertTrue(offline_public_header_edge(registration, source, selected, translation_unit))
        self.assertFalse(offline_public_header_edge(registration, source, selected,
            "src/tests/offline/Api/Order/NativeOrderQuantity.cpp"))
        self.assertFalse(offline_public_header_edge(registration,
            "src/src/Core/src/Api/Instrument/Internal/Unknown.hpp", selected, translation_unit))
        self.assertFalse(offline_public_header_edge(replace(registration, includes=()),
            source, selected, translation_unit))

    def test_dhm_alternate_header_requires_pinned_input_and_proven_inactive_config(self):
        from Family.Sources.CxetFamilyNativeInputs import NativeInputs, native_syntax_data
        inputs = IncludeInputs(ROOT)
        native = NativeInputs(inputs)
        source = "extra/mbedtls-cold/include/mbedtls/dhm.h"
        data = inputs.read(source)
        verified = native.verify(source, data)
        self.assertTrue(verified)
        cold = native.configuration("cmake/Vendor/mbedtls-cold/cxet_mbedtls_config.h")
        self.assertNotIn(b"#include \"dhm_alt.h\"", native_syntax_data(
            source, data, verified=verified, config_data=cold))
        for config in (None, cold + b"\n#define MBEDTLS_DHM_ALT\n"):
            self.assertIn(b"#include \"dhm_alt.h\"", native_syntax_data(
                source, data, verified=verified, config_data=config))
        self.assertIn(b"#include \"dhm_alt.h\"", native_syntax_data(
            source, data, verified=False, config_data=cold))


if __name__ == '__main__':
    unittest.main()
