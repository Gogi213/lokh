"""Global provider-to-consumer policy for every first-party target edge."""

from __future__ import annotations

from pathlib import Path

from CMake.Policy.CmakeFamilyBenchmarkRecipe import benchmark_target_context
from Family.Targets.CxetFamilyBuildPolicy import exact_offline_external_link
from Family.Targets.CxetFamilyCompressionPolicy import (
    COMPRESSION_EXTERNAL_LEAVES, compression_external_link, family_external_link,
)

from Family.Targets.CxetFamilyTargetInventory import (
    FORBIDDEN_TRANSITIVE_TARGETS,
    ROLE_BENCH,
    ROLE_FUZZ,
    ROLE_PRODUCTION,
    ROLE_TEST,
)


def product_root(active) -> str | None:
    parts = active.source_base.parts
    if parts[:2] in {
            ("src", "src"), ("src", "tests"),
            ("src", "benchmarks"), ("src", "replay")}:
        return "/".join(parts[:2])
    if len(parts) >= 2 and parts[0] in {"apps", "tools"}:
        return "/".join(parts[:2])
    return None


_PROVIDERS = {
    "apps/common": frozenset({"apps/common"}),
    "tools/exchange_api_probe": frozenset({"tools/exchange_api_probe", "src/src"}),
    "apps/diagnostic": frozenset({"apps/diagnostic", "apps/common", "apps/trading-core", "src/src"}),
    "src/src": frozenset({"src/src"}),
    "src/tests": frozenset({"src/tests", "src/src", "src/replay"}),
    "src/replay": frozenset({"src/replay", "src/src"}),
    "apps/trading-core": frozenset({"apps/trading-core", "src/src"}),
    "apps/hft-parser": frozenset({
        "apps/hft-parser", "src/benchmarks", "src/src"}),
    "apps/hft-recorder": frozenset({
        "apps/hft-recorder", "apps/hft-compressor", "apps/hft-parser", "src/src"}),
    "apps/hft-compressor": frozenset({"apps/hft-compressor"}),
    "apps/hft-backtest": frozenset({
        "apps/hft-backtest", "apps/hft-recorder", "apps/trading-core",
        "src/src"}),
    "apps/trader": frozenset({
        "apps/trader", "apps/common", "apps/hft-parser", "apps/trading-core", "src/src"}),
    "apps/vetron": frozenset({
        "apps/vetron", "apps/hft-parser", "apps/trader",
        "apps/trading-core", "src/src"}),
    "src/tests/Family": frozenset({
        "src/tests/Family", "apps/hft-backtest", 
        "apps/hft-parser", "apps/hft-recorder", "apps/trader",
        "apps/trading-core", "src/src"}),
    "src/benchmarks": frozenset({"src/benchmarks", "src/src"}),
}

_EXTERNAL_ROOTS = {
    "PostgreSQL::PostgreSQL": frozenset({"apps/diagnostic"}),
    "CURL::libcurl": frozenset({"apps/diagnostic"}),
    "OpenSSL::SSL": frozenset({"src/tests", "apps/trader", "tools/exchange_api_probe"}),
    "OpenSSL::Crypto": frozenset({"tools/exchange_api_probe"}),
    "PkgConfig::NGHTTP2": frozenset({"tools/exchange_api_probe"}),
    "Boost::json": frozenset({"tools/exchange_api_probe"}),
    "Threads::Threads": frozenset({
        "src/src", "apps/hft-parser", "apps/trading-core", 
        "apps/hft-backtest", "src/benchmarks", "tools/exchange_api_probe"}),
    "absl::flat_hash_map": frozenset({
        "src/src", "src/tests", "apps/hft-backtest"}),
    "absl::btree": frozenset({"src/src"}),
    "absl::flat_hash_set": frozenset({
        "src/src", "apps/hft-parser"}),
    "absl::inlined_vector": frozenset({
        "src/src", "apps/hft-backtest"}),
    "GTest::gtest": frozenset({"src/tests"}),
    "GTest::gtest_main": frozenset({"src/tests"}),
    "liburing::uring": frozenset({"src/src", "apps/hft-parser"}),
    "secp256k1": frozenset({"src/src"}),
    "anl": frozenset({"src/src"}),
}


def external_link_error(instance, source: str, dependency: str, contexts):
    """Approve an exact external leaf only in a reviewed consumer product."""
    if dependency in COMPRESSION_EXTERNAL_LEAVES or dependency in {
            'Threads::Threads', 'absl::flat_hash_map'}:
        declaration = contexts.context_for_use(source, instance) if hasattr(
            contexts, 'context_for_use') else contexts.get(source)
        if (declaration is not None and declaration.body.relative == instance.body.relative and
                (compression_external_link(instance, source, dependency) or
                 family_external_link(instance, source, dependency))):
            return None
        if dependency in COMPRESSION_EXTERNAL_LEAVES:
            return f'compression external leaf {dependency} escaped its exact provider recipe'
    if (dependency == "Threads::Threads" and
            source in {"trader_alert_service", "trader_live_market_relay", "trader_live_runtime"} and
            instance.body.relative == "apps/trader/CMakeLists.txt" and
            instance.evaluation.source_base == Path("apps/trader") and
            instance.evaluation.binary_base == Path("apps/trader")):
        declaration = contexts.context_for_use(source, instance) if hasattr(
            contexts, "context_for_use") else contexts.get(source)
        if declaration is not None and declaration.body.relative == instance.body.relative:
            return None
    if dependency == "Threads::Threads" and product_root(
            instance.evaluation) == "apps/trading-core" and not (
                source == "trading-core-rate-limit-state-tests" and
                instance.body.relative ==
                "apps/trading-core/tests/CMakeLists.txt" and
                instance.body.command.line == 140):
        return (
            "trading-core may link Threads::Threads only from the exact "
            "rate-limit-state test edge")
    if source in FORBIDDEN_TRANSITIVE_TARGETS:
        return (
            f"read-only target {source} cannot link external leaf "
            f"{dependency}"
        )
    declaration = (
        contexts.context_for_use(source, instance)
        if hasattr(contexts, "context_for_use") else contexts.get(source))
    consumer = (
        product_root(declaration.evaluation)
        if declaration is not None else None)
    if (consumer == "src/tests" and declaration is not None and
            hasattr(contexts, "role") and contexts.role(source, instance) == ROLE_TEST and
            exact_offline_external_link(instance, source, dependency)):
        return None
    if (dependency == "OpenSSL::SSL" and declaration is not None and
            hasattr(contexts, "role") and contexts.role(source, instance) == ROLE_BENCH and
            instance.body.command.name == "target_link_libraries" and
            all(benchmark_target_context(active, source) for active in (
                instance.body, instance.evaluation,
                declaration.body, declaration.evaluation)) and
            instance.body.relative == declaration.body.relative):
        return None
    if (dependency in {"absl::flat_hash_map", "absl::hash"} and
            source == "trader_traderd_process" and consumer == "apps/trader" and
            instance.body.relative == "apps/trader/CMakeLists.txt" and
            declaration.body.relative == instance.body.relative and
            instance.evaluation.source_base == Path("apps/trader")):
        return None
    if (dependency == "OpenSSL::Crypto" and source in {
            "trader_startup_certificates", "trader_tbank_startup_certificates"} and
            consumer == "apps/trader" and
            instance.body.relative == "apps/trader/tests/startup/CMakeLists.txt" and
            declaration.body.relative == instance.body.relative and
            declaration.evaluation.source_base == Path("apps/trader/tests/startup") and
            instance.evaluation.source_base == Path("apps/trader/tests/startup")):
        return None
    if dependency == "CURL::libcurl" and not (
            source == "diagnostic_runtime" and consumer == "apps/diagnostic" and
            instance.body.relative == "apps/diagnostic/CMakeLists.txt" and
            declaration.body.relative == instance.body.relative):
        return "CURL::libcurl is restricted to the Diagnostic runtime adapter"
    if (dependency == "OpenSSL::SSL" and consumer == "src/tests" and
            not exact_offline_external_link(instance, source, dependency)):
        return "offline OpenSSL::SSL is restricted to exact registered oracle edges"
    if (dependency in {"OpenSSL::SSL", "OpenSSL::Crypto"} and
            consumer == "tools/exchange_api_probe" and
            (source != "exchange_probe_lib" or
             product_root(instance.evaluation) != "tools/exchange_api_probe")):
        return "probe OpenSSL leaves are restricted to exchange_probe_lib"
    if (dependency in {"PkgConfig::NGHTTP2", "Boost::json", "Threads::Threads"} and consumer == "tools/exchange_api_probe" and
            (source != "exchange_probe_lib" or
             product_root(instance.evaluation) != "tools/exchange_api_probe")):
        return f"probe {dependency} leaf is restricted to exchange_probe_lib"
    if (dependency == "OpenSSL::SSL" and consumer == "apps/trader" and
            (source != "trader_offline_finam_full_path" or
             declaration.evaluation.source_base != Path("apps/trader/tests/offline") or
             instance.evaluation.source_base != Path("apps/trader/tests/offline"))):
        return "Trader OpenSSL::SSL is restricted to the FINAM offline oracle"
    allowed = _EXTERNAL_ROOTS.get(dependency)
    if allowed is None:
        return f"unreviewed external link leaf {dependency}"
    if consumer not in allowed:
        return (
            f"external link leaf {dependency} is not approved for "
            f"{consumer or '<unknown>'} target {source}")
    vendor_consumers = {
        "liburing::uring": {"cxet_lib", "hftp_transport",
                            "hft-zcrx-capability-probe", "hft-zcrx-functional-probe"},
        "secp256k1": {"cxet_lib"},
    }
    if (dependency in vendor_consumers and
            source not in vendor_consumers[dependency]):
        return f"vendor link leaf {dependency} escapes reviewed consumers"
    return None


def product_edge_error(instance, consumer: str, provider: str, registry):
    """Validate one path-visible first-party dependency direction."""
    consumers = registry.resolve(
        consumer, instance, require_prior=True,
        allow_same=instance.body.command.name in {"add_library", "add_executable"},
        report=False)
    providers = registry.resolve(
        provider, instance,
        require_prior=instance.body.command.name != "target_link_libraries",
        report=False)
    if not consumers:
        return f"target {consumer} is not declared on the dependency path"
    if not providers:
        return f"dependency {provider} is not declared on the dependency path"
    consumer_roots = {
        product_root(item.instance.evaluation) for item in consumers}
    provider_roots = {
        product_root(item.instance.evaluation) for item in providers}
    if len(consumer_roots) != 1 or len(provider_roots) != 1:
        return f"ambiguous product ownership for {consumer} -> {provider}"
    consumer_root = next(iter(consumer_roots))
    provider_root = next(iter(provider_roots))
    if consumer_root not in _PROVIDERS:
        return f"target {consumer} has no reviewed product owner"
    if (provider_root == "src/benchmarks" and
            (consumer, provider) not in {
                ("hft-parser-bench", "cxet_market_ingress_bench_support"),
            }):
        return f"unreviewed benchmark-support edge {consumer} -> {provider}"
    if provider_root not in _PROVIDERS[consumer_root]:
        return (
            f"forbidden product edge {consumer_root} -> "
            f"{provider_root or '<unknown>'} through {provider}")
    consumer_roles = {item.role for item in consumers}
    provider_roles = {item.role for item in providers}
    if (ROLE_PRODUCTION in consumer_roles and
            provider_roles & {ROLE_TEST, ROLE_BENCH, ROLE_FUZZ}):
        return f"production target {consumer} depends on test/bench {provider}"
    return None
