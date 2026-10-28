"""Finite registration identities for the canonical diagnostic helper."""

from pathlib import Path


BENCHMARK_ROOTS = {
    "src/benchmarks/CMakeLists.txt": "CXETCPP",
    "apps/hft-parser/benchmarks/CMakeLists.txt": "hft-parser",
    "apps/trading-core/benchmarks/CMakeLists.txt": "trading-core",
    "apps/trader/benchmarks/CMakeLists.txt": "trader",
}
BENCHMARK_TARGETS = {
    "src/benchmarks/CMakeLists.txt": (
        "cxet_bench_core", "cxet_bench_primitive_candidates"),
    "apps/hft-parser/benchmarks/CMakeLists.txt": (
        "parser-bench-publication", "parser-bench-session",
        "parser-bench-native-fix", "parser-bench-native-market"),
    "apps/trading-core/benchmarks/CMakeLists.txt": (
        "trading-core-bench-strategies", "trading-core-bench-execution",
        "trading-core-bench-hot-functions", "trading-core-bench-hot-orders",
        "trading-core-bench-hot-account", "trading-core-bench-delivery-functions",
        "trading-core-bench-delivery-strategy"),
    "apps/trader/benchmarks/CMakeLists.txt": (
        "trader-bench-wake", "trader-bench-control", "trader-bench-hot-trader",
        "trader-bench-native-lane", "trader-bench-capacity", "trader-bench-json-ws", "trader-bench-vstack"),
}
BENCHMARK_REGISTRATION_LINES = {
    "src/benchmarks/CMakeLists.txt": (1, 8),
    "apps/hft-parser/benchmarks/CMakeLists.txt": (1, 5, 10, 16),
    "apps/trading-core/benchmarks/CMakeLists.txt": (1, 6, 10, 14, 18, 22, 26),
    "apps/trader/benchmarks/CMakeLists.txt": (1, 5, 9, 15, 22, 29, 52),
}
BENCHMARK_REQUIREMENTS = {
    "cxet_bench_core": ("CXET_SELECTION_ALL",),
    "parser-bench-native-fix": ("CXET_EXCHANGE_BINANCE", "CXET_HAS_FIX"),
    "parser-bench-native-market": ("CXET_EXCHANGE_BINANCE", "CXET_HAS_FIX"),
    "trader-bench-native-lane": ("CXET_EXCHANGE_BINANCE", "CXET_HAS_FIX"),
    "trader-bench-capacity": ("CXET_EXCHANGE_BINANCE", "CXET_HAS_FIX"),
    "trader-bench-json-ws": ("CXET_EXCHANGE_BINANCE", "CXET_HAS_WS"),
    "trader-bench-vstack": ("CXET_HAS_GRPC", "CXET_TRADER_DIAGNOSTIC", "_trader_vstack_exchange_enabled"),
}


def benchmark_target_owner(name: str, origin: str) -> str | None:
    base = name.removesuffix("_traced")
    return (BENCHMARK_ROOTS[origin]
            if base in BENCHMARK_TARGETS.get(origin, ()) else None)


def benchmark_target_context(active, target: str) -> bool:
    return (benchmark_target_owner(target, active.relative) is not None and
            active.source_base == Path(active.relative).parent and
            active.binary_base == active.source_base)
