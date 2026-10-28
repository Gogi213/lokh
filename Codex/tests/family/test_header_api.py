"""Header api regressions."""
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

class HeaderApiBoundaryTests(unittest.TestCase):
    def test_link_providers_bind_later_at_generation_but_mutation_owner_stays_prior(self):
        from CMake.Flow.CmakeFamilyGraph import ActiveCommand, Command
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, NO_PATHS, InstantiatedCommand
        from Family.Targets.CxetFamilyMayMustGraph import _Builder, MUST
        from Family.Targets.CxetFamilyTargetRegistry import TargetDeclaration, TargetRegistry
        from Family.Targets.CxetFamilyTargetInventory import ROLE_PRODUCTION
        left = ((("optional-provider", 0),),)
        consumer, provider = 'trader_alert_contracts', 'trader_common_contracts'
        for alias, provider_paths, eof, missing, late_owner, foreign_scope, accepted in (
                (False, ALL_PATHS, ALL_PATHS, False, False, False, True),
                (True, ALL_PATHS, ALL_PATHS, False, False, False, True),
                (False, left, ALL_PATHS, False, False, False, False),
                (True, left, left, False, False, False, True),
                (False, ALL_PATHS, NO_PATHS, False, False, False, False),
                (False, ALL_PATHS, NO_PATHS, False, False, True, False),
                (False, ALL_PATHS, ALL_PATHS, True, False, False, False),
                (False, ALL_PATHS, ALL_PATHS, False, True, False, False)):
            with self.subTest(alias=alias, paths=provider_paths, eof=eof,
                              missing=missing, late_owner=late_owner, foreign_scope=foreign_scope):
                instances = []
                def instance(name, tokens, paths=ALL_PATHS, *, foreign=False):
                    ordinal = len(instances) + 1
                    active = ActiveCommand('provider' if foreign else 'forward-link', 'apps/trader/CMakeLists.txt',
                        Path('apps/trader'), Path('apps/trader'), (),
                        Command(name, ' '.join(tokens), ordinal), ordinal)
                    value = InstantiatedCommand(active, active,
                        tuple((token,) for token in tokens), ordinal, paths)
                    instances.append(value)
                    return value
                owner = None if late_owner else instance('add_library', [consumer, 'INTERFACE'])
                use = instance('target_link_libraries', [consumer, 'PUBLIC',
                    'trader::common_contracts' if alias else provider])
                if late_owner:
                    owner = instance('add_library', [consumer, 'INTERFACE'])
                declaration = instance('add_library', [provider, 'INTERFACE'], provider_paths,
                                       foreign=foreign_scope)
                alias_use = instance('add_library', ['trader::common_contracts', 'ALIAS', provider])
                registry = object.__new__(TargetRegistry)
                registry.errors = []
                registry.live_eof_paths = {'forward-link': eof, 'provider': ALL_PATHS}
                registry.order = {id(value): index for index, value in enumerate(instances)}
                registry.by_name = {consumer: [TargetDeclaration(
                    consumer, 'INTERFACE', ROLE_PRODUCTION, owner, PRODUCTION_TARGETS[consumer])]}
                if not missing:
                    registry.by_name[provider] = [TargetDeclaration(
                        provider, 'INTERFACE', ROLE_PRODUCTION, declaration, PRODUCTION_TARGETS[provider])]
                self.assertEqual(registry.resolve(provider, use, require_prior=True, report=False), [])
                if not missing and provider_paths == ALL_PATHS:
                    self.assertTrue(registry.resolve(provider, alias_use, require_prior=True, report=False))
                builder = _Builder(instances, registry,
                    {'trader::common_contracts': provider} if alias else {}, registry.errors, frozenset())
                builder._edge(use, consumer, 'trader::common_contracts' if alias else provider, MUST)
                self.assertEqual(bool(builder.edges), accepted, registry.errors)
                self.assertEqual(not registry.errors, accepted, registry.errors)

    def test_cold_quoted_abseil_import_requires_exact_tu_target_and_capability(self):
        from Family.Sources.CxetFamilyIncludeReachability import _cold_full_quoted_external
        source = 'apps/trader/src/Process/src/Traderd/Fleet/Financial/FleetFinancialMemory.cpp'
        for include, capability in (
                ('absl/container/flat_hash_map.h', 'absl::flat_hash_map'),
                ('absl/hash/hash.h', 'absl::hash')):
            with self.subTest(include=include):
                self.assertTrue(_cold_full_quoted_external('trader_traderd_process',
                    source, source, include, {capability}, public_seed=False))
                for target, physical, unit, capabilities, public in (
                        ('trader_market_client', source, source, {capability}, False),
                        ('trader_traderd_process', source, 'Other.cpp', {capability}, False),
                        ('trader_traderd_process', 'Other.cpp', source, {capability}, False),
                        ('trader_traderd_process', source, source, set(), False),
                        ('trader_traderd_process', source, source, {capability}, True)):
                    self.assertFalse(_cold_full_quoted_external(target, physical, unit,
                        include, capabilities, public_seed=public))

    def test_generated_registry_consumers_are_exact_and_keep_provider_requirements(self):
        from Family.Targets.CxetFamilyTargetPolicy import verification_unresolved_quoted_requirement
        from Family.Verification.CxetFamilyVerificationInventory import (
            _TRADER_GENERATED_STRATEGY_SOURCES, _ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES,
        )
        from Family.Sources.CxetFamilyCppPolicy import cpp_include_syntax
        include = 'trading_core/Strategy/GeneratedStrategyRegistry.hpp'
        self.assertEqual(len(_TRADER_GENERATED_STRATEGY_SOURCES), 6)
        self.assertEqual(len(_ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES), 7)
        for source in (*_TRADER_GENERATED_STRATEGY_SOURCES,
                       *_ADDITIONAL_BACKTEST_GENERATED_STRATEGY_SOURCES):
            with self.subTest(source=source):
                _, records, errors = cpp_include_syntax((ROOT / source).read_bytes())
                self.assertEqual(errors, [])
                self.assertIn((include.encode(), True), records)
                self.assertEqual(verification_unresolved_quoted_requirement(source, include),
                    ('generated', '__CXET_CMAKE_BINARY__/apps/trading-core/generated'))
        self.assertIsNone(verification_unresolved_quoted_requirement(
            'apps/trader/src/Process/src/Traderd/UnknownConsumer.cpp', include))
        self.assertIsNone(verification_unresolved_quoted_requirement(
            'apps/hft-backtest/src/Runtime/src/Run/UnknownConsumer.cpp', include))

    def test_api_seed_ownership_preserves_physical_declaration_carriers(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import canonical_api_headers, API_HEADER_OWNERS, PRIVATE_COMPOSITION_HEADER_TARGETS
        errors = []
        physical = compiler_visible_header_inventory(ROOT, {
            'trading_core_headers': ('apps/trading-core/src/Core/include',),
            'hftp_backend_headers': ('apps/hft-parser/src/Runtime/include',),
        }, errors)
        semantic = canonical_api_headers(physical, set(PRODUCTION_TARGETS), errors)
        execution = ('apps/trading-core/src/Core/include/trading_core/'
                     'Execution/SharedAccountAdmission.hpp')
        self.assertEqual(errors, [])
        self.assertIn(execution, semantic['trading_core_execution'])
        self.assertNotIn(execution, semantic['trading_core_headers'])
        self.assertEqual(exported_header_targets(physical)[execution],
                         frozenset({'trading_core_headers'}))
        price_basis = ('apps/trading-core/src/Core/include/trading_core/'
                       'Algorithm/Math/PriceQuantity/PriceBasis.hpp')
        self.assertIn(price_basis, semantic['trading_core_algorithm'])
        unavailable = ('apps/hft-parser/src/Runtime/include/hft_parser/'
                       'Internal/DepthSequence.hpp')
        self.assertNotIn(unavailable, API_HEADER_OWNERS)
        self.assertNotIn(unavailable, PRIVATE_COMPOSITION_HEADER_TARGETS)
        self.assertNotIn(unavailable, physical['hftp_backend_headers'])
        self.assertFalse(any(unavailable in headers for headers in semantic.values()))

    def test_new_unclassified_and_removed_reviewed_headers_fail_closed(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import canonical_api_headers
        errors = []
        physical = compiler_visible_header_inventory(ROOT, {
            'trader_market_client': ('apps/trader/src/Market/include',),
        }, errors)
        headers = list(physical['trader_market_client'])
        removed = headers.pop()
        added = 'apps/trader/src/Market/include/trader/Market/NewUnknown.hpp'
        errors = []
        canonical_api_headers({'trader_market_client': (*headers, added)},
                              set(PRODUCTION_TARGETS), errors)
        self.assertTrue(any(added in error and 'unclassified' in error for error in errors))
        self.assertTrue(any(removed in error and 'no longer' in error for error in errors))

    def test_current_projection_value_headers_have_real_cmake_carrier(self):
        errors = []
        root = 'apps/trader/src/Contracts/Projection/include'
        inventory = compiler_visible_header_inventory(ROOT, {
            'trader_projection_contracts': (root,),
        }, errors)
        exports = exported_header_targets(inventory)
        source = ('apps/trader/src/Market/include/trader/Market/'
                  'Algorithms/AlgorithmDescriptor.hpp')
        for name in ('trader/Algorithms/AlgorithmSelection.hpp',
                     'trader/Algorithms/IndicatorValue.hpp',
                     'trader/Analysis/SyntheticBboSpread.hpp',
                     'trader/Analysis/Ranking.hpp', 'trader/Analysis/RankingCapacity.hpp'):
            with self.subTest(name=name):
                relative = f'{root}/{name}'
                self.assertIn('trader_projection_contracts', exports[relative])
                self.assertTrue(verification_include_allowed(source, relative))
        self.assertEqual(errors, [])

    def test_contracts_only_consumer_cannot_parse_execution_without_finance(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS, NO_PATHS
        from Family.Sources import CxetFamilyIncludeReachability as reach
        core = 'apps/trading-core/src/Core/include'
        capital = 'apps/trading-core/capital/include'
        source = 'apps/trader/src/Market/src/Client/Boundary.cpp'
        execution = f'{core}/trading_core/Execution/SharedAccountAdmission.hpp'
        consumer = 'trader_market_client'
        names = [consumer, 'trading_core_headers', 'capital_finance']
        registry = SimpleNamespace(concrete_names=lambda: names,
            declaration_paths=lambda target: ALL_PATHS if target in names else NO_PATHS)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative, data in {
                source: '#include "trading_core/Execution/SharedAccountAdmission.hpp"\n',
                execution: '#include "capital/Budget/SharedCapital.hpp"\n',
                f'{capital}/capital/Budget/SharedCapital.hpp': '#pragma once\n',
            }.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            model = reach._empty_model(names)
            model.interface_roots['trading_core_headers'] = [reach._Effect(core, ALL_PATHS)]
            model.interface_roots['capital_finance'] = [reach._Effect(capital, ALL_PATHS)]
            model.compile_links[consumer] = [reach._Effect('trading_core_headers', ALL_PATHS)]
            active = SimpleNamespace(command=SimpleNamespace())
            instance = SimpleNamespace(path_alternatives=ALL_PATHS, body=active, evaluation=active)
            occurrence = ((consumer, instance, source),)
            with patch.object(reach, '_build_model', return_value=model), patch.object(
                    reach, '_seed_exported_headers', return_value=({}, {
                        execution: frozenset({'trading_core_headers'}),
                        f'{capital}/capital/Budget/SharedCapital.hpp': frozenset({'capital_finance'}),
                    })):
                errors = []
                reach.validate_compiler_include_reachability(
                    root, [], registry, {}, occurrence, frozenset(), errors)
                self.assertTrue(any('cannot resolve reviewed include capital/' in error
                                    for error in errors))
                model.compile_links[consumer].append(reach._Effect('capital_finance', ALL_PATHS))
                errors = []
                reach.validate_compiler_include_reachability(
                    root, [], registry, {}, occurrence, frozenset(), errors)
                self.assertEqual(errors, [])
                # External codec spelling cannot hide a physical repository
                # shadow, even when a real external capability is available.
                (root / source).write_text('#include <zstd.h>\n')
                (root / core / 'zstd.h').write_text('#pragma once\n')
                model.compile_external[consumer] = [reach._Effect('zstd', ALL_PATHS)]
                errors = []
                reach.validate_compiler_include_reachability(
                    root, [], registry, {}, occurrence, frozenset(), errors)
                self.assertTrue(any('external include spelling is shadowed' in error and
                                    'zstd.h' in error for error in errors))

    def test_finance_leaf_fence_applies_through_recursive_shared_headers(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import finance_leaf_include
        core = 'apps/trading-core/src/Core/include/trading_core/'
        for source in ('apps/trading-core/capital/src/Finance.cpp',
                       'apps/trading-core/capital/src/FinancialExposure.cpp',
                       'apps/trading-core/capital/src/FinanceArithmetic.hpp',
                       'apps/trading-core/src/Contracts/include/trading_core/Contracts/Numeric/Integer/WideDivision.hpp'):
            with self.subTest(source=source):
                self.assertFalse(finance_leaf_include(source,
                    core + 'Execution/SharedAccountAdmission.hpp', 'capital_finance'))
                self.assertTrue(finance_leaf_include(source,
                    'apps/trading-core/src/Contracts/include/trading_core/Contracts/IdentityTypes.hpp', 'capital_finance'))

    def test_private_root_grant_requires_guarantee_and_excludes_public_promotion(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        from Family.Sources import CxetFamilyIncludeReachability as reach
        target = 'hftp_session_native_identity'
        root = 'apps/hft-parser/src/Runtime/include'
        selected = root + '/hft_parser/Session/Native/ProfileAccountIdentity.hpp'
        model = reach._empty_model([target])
        model.compile_roots[target] = [reach._Effect(root, ALL_PATHS)]
        errors = []
        self.assertTrue(reach._private_owner_header_access(target, selected, ALL_PATHS, model, errors))
        model.interface_roots[target] = [reach._Effect(root, ALL_PATHS)]
        self.assertFalse(reach._private_owner_header_access(target, selected, ALL_PATHS, model, errors))
        model.interface_roots[target] = []
        conditional = ((("conditional", 0),),)
        model.compile_roots[target] = [reach._Effect(root, conditional)]
        self.assertFalse(reach._private_owner_header_access(target, selected, ALL_PATHS, model, errors))
        self.assertFalse(reach._private_owner_header_access(target,
            'apps/trader/src/Projection/include/trader/Projection/Publisher/PublisherTypes.hpp',
            ALL_PATHS, model, errors))
        self.assertEqual(errors, [])

    def test_unused_backend_root_remains_forbidden_to_read_only_client(self):
        from CMake.Flow.CmakeFamilyFlow import ALL_PATHS
        from Family.Sources import CxetFamilyIncludeReachability as reach
        client, publisher = 'hftp_session_private_client', 'hftp_session_private_publisher'
        names = [client, publisher]
        model = reach._empty_model(names)
        model.interface_may_links[client] = [reach._Effect(publisher, ALL_PATHS)]
        model.interface_roots[publisher] = [reach._Effect(
            'apps/hft-parser/src/Runtime/include', ALL_PATHS)]
        errors = []
        reach._validate_read_only_include_root_closures(model,
            SimpleNamespace(concrete_names=lambda: names), errors)
        self.assertTrue(any(client in error and 'forbidden roots' in error for error in errors))

    def test_private_composition_access_is_exact_and_never_a_public_seed(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import private_composition_include
        selected = 'apps/trader/alerts/include/trader/Alerts/AlertContext.hpp'
        source = 'apps/trader/src/Market/src/Analytics/Pipeline.cpp'
        roots = ('apps/trader/alerts/include',)
        self.assertTrue(private_composition_include('trader_public_analytics', source,
            selected, roots, public_seed=False))
        self.assertFalse(private_composition_include('trader_alert_contracts', source,
            selected, roots, public_seed=False))
        self.assertFalse(private_composition_include('trader_public_analytics', source,
            selected, (), public_seed=False))
        self.assertFalse(private_composition_include('trader_public_analytics', source,
            selected, roots, public_seed=True))
        selected = ('apps/hft-parser/src/Runtime/include/hft_parser/'
                    'Market/Ingestion/PublicMarketPublicationBuild.hpp')
        roots = ('apps/hft-parser/src/Runtime/include',)
        for target in ('hftp_ingestion', 'hftp_trading_ingestion',
                       'hftp_parserd_runtime', 'hftp_trading_runtime'):
            for source in ('apps/hft-parser/src/Runtime/src/Market/Ingestion/PublicMarketProcessRoot.cpp',
                           'apps/hft-parser/src/Process/src/Bootstrap/Application/ParserdApplication.cpp'):
                self.assertTrue(private_composition_include(target, source, selected, roots, public_seed=False))
                self.assertFalse(private_composition_include(target, source, selected, roots, public_seed=True))
                self.assertFalse(private_composition_include(target, source, selected, (), public_seed=False))
            self.assertFalse(private_composition_include(target,
                'apps/hft-parser/src/Runtime/include/hft_parser/Market/Ingestion/PublicMarketProcessRoot.hpp',
                selected, roots, public_seed=False))
            self.assertFalse(private_composition_include(target,
                'apps/trader/src/Market/src/Analytics/Pipeline.cpp', selected, roots, public_seed=False))
        self.assertFalse(private_composition_include('hftp_backend_headers',
            'apps/hft-parser/src/Runtime/src/Market/Ingestion/PublicMarketProcessRoot.cpp',
            selected, roots, public_seed=False))

    def test_experimental_api_and_parser_process_permissions_remain_separate(self):
        from Family.Sources.CxetFamilyHeaderApiPolicy import experimental_api_available, parser_process_include
        for name, owner in (('Planning/AccountDp.hpp', 'capital_planning'), ('Planning/Dp.hpp', 'capital_planning')):
            selected = 'apps/trading-core/capital/include/capital/' + name
            self.assertFalse(experimental_api_available(selected, {'capital_finance'}))
            self.assertTrue(experimental_api_available(selected, {owner}))
        source = 'apps/trader/src/Process/src/Traderd/Application/TraderdFleetConfigured.cpp'
        native = ('apps/hft-parser/src/Runtime/include/hft_parser/'
                  'Session/Native/NativeAccountSession.hpp')
        public = ('apps/hft-parser/src/Runtime/include/hft_parser/'
                  'Market/Ingestion/ParserStartupConfig.hpp')
        self.assertTrue(parser_process_include('trader_traderd_process', source, native))
        self.assertFalse(parser_process_include('trader_market_observe_process', source, native))
        self.assertTrue(parser_process_include('trader_market_observe_process', source, public))
        self.assertFalse(parser_process_include('trader_market_client', source, public))


if __name__ == '__main__':
    unittest.main()
