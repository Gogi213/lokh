#!/usr/bin/env python3
"""Read-only CXET helper commands for Codex.

This module is intentionally static-only: it reads repository files and reports
evidence. It does not run builds, tests, Git, live tools, or network calls.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

if __package__:
    from .Family.Sources.CxetFamilyCppPolicy import CPP_SCAN_SUFFIXES
else:
    # File-loaded tools have no package; resolve only their sibling module.
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "CxetFamilyCppPolicy", Path(__file__).parent / "Family/Sources/CxetFamilyCppPolicy.py"
    )
    assert _spec and _spec.loader
    _policy = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_policy)
    CPP_SCAN_SUFFIXES = _policy.CPP_SCAN_SUFFIXES


REGISTER_ALL = Path("src/src/Core/src/Exchanges/RegisterAll.cpp")
REGISTER_OWNERS = Path("src/src/Core/include/cxet/Exchanges/Register.hpp")
READINESS_HEADER = Path("src/src/Core/include/cxet/Api/Connector/ExchangeProductReadiness.hpp")
CONNECTOR_HEADER = Path("src/src/Core/include/cxet/Api/Connector/ExchangeProductConnector.hpp")
RUNTIME_VALIDATION = Path("apps/trader/src/Runtime/include/trader/Runtime/Order/AdmissionPolicy.hpp")
CAPABILITY_VIEW = Path("apps/hft-parser/src/Runtime/src/Session/SessionService.cpp")
PRIVATE_AUDIT = Path("apps/hft-parser/src/Runtime/src/Session/Native/Account/NativeAccountSession.cpp")
EXCHANGE_CONTRACT = Path('docs/exchanges/EXCHANGE_CONTRACT.md')


HOTPATH_SURFACES = ("all", "market", "strategy", "order", "parser", "transport", "runtime")

HOTPATH_ROOTS: dict[str, tuple[Path, ...]] = {
    "market": (
        Path("src/src/Core/include/cxet/Api/Market"),
        Path("src/src/Core/src/Api/Market"),
        Path("src/src/Core/include/cxet/Runtime/Market"),
        Path("src/src/Core/src/Runtime/Market"),
        Path("apps/hft-parser/src/Runtime/include/hft_parser"),
        Path("apps/hft-parser/src/Runtime/src/Market"),
    ),
    "strategy": (
        Path("apps/trading-core/src/Core/include"),
        Path("apps/trading-core/src/Strategy/include/strategy"),
        Path("apps/trading-core/src/Core/src"),
        Path("apps/trader/src/Runtime/include/trader/Runtime/Strategy"),
        Path("apps/trader/src/Runtime/src/Strategy"),
    ),
    "order": (
        Path("src/src/Core/include/cxet/Api/Order/Prepared"),
        Path("src/src/Core/src/Api/Order/Prepared"),
        Path("src/src/Core/include/cxet/Api/Order"),
        Path("src/src/Core/src/Api/Order"),
        Path("apps/trading-core/src/Core/include/trading_core/Execution/Order"),
        Path("apps/trader/src/Runtime/include/trader/Runtime/Order"),
        Path("apps/hft-parser/src/Runtime/src/Session"),
    ),
    "parser": (
        Path("src/src/Core/include/cxet/Exchanges"),
        Path("src/src/Core/src/Exchanges"),
        Path("src/src/Contracts/include/cxet/Canon"),
        Path("src/src/Contracts/include/cxet/Parse"),
        Path("src/src/Contracts/include/cxet/Primitives/Composite"),
        Path("src/src/Contracts/src/Canon"),
        Path("src/src/Contracts/src/Parse"),
    ),
    "transport": (
        Path("src/src/Core/include/cxet/Network"),
        Path("src/src/Core/src/Network"),
        Path("src/src/Core/include/cxet/Api/Order"),
        Path("src/src/Core/src/Api/Order"),
        Path("src/src/Core/include/cxet/Api/User"),
        Path("src/src/Core/src/Api/User"),
    ),
    "runtime": (
        Path("apps/trader/src/Runtime/include/trader/Runtime"),
        Path("apps/trader/src/Runtime/src"),
        Path('apps/hft-parser/src/Runtime/src/Session'),
    ),
}

HOTPATH_ANCHORS: dict[str, tuple[Path, ...]] = {
    "market": (
        Path("src/src/Core/src/Runtime/Market/MarketRuntime.cpp"),
        Path("src/src/Core/src/Runtime/Market/ExecutionKernel.cpp"),
        Path("apps/hft-parser/src/Runtime/src/Market/Ingestion/Detail/Shard/Lifecycle/PublicMarketShardDepthAdmission.ipp"),
    ),
    "strategy": (
        Path("apps/trading-core/src/Core/include/trading_core/Contracts/Strategy/StrategyContract.hpp"),
        Path("apps/trading-core/src/Core/include/trading_core/Strategy/StrategyMarketData.hpp"),
        Path("apps/trader/src/Runtime/src/Strategy/ProfileUniverseStrategyRunner.cpp"),
        Path("apps/trader/src/Runtime/include/trader/Runtime/Strategy/ProfileUniverseStrategyRunner.hpp"),
    ),
    "order": (
        Path("src/src/Core/include/cxet/Api/Order/Prepared/HotOrderPath.hpp"),
        Path("src/src/Core/src/Api/Order/OrderSessionPoolSend.cpp"),
        Path("src/src/Core/src/Api/Order/OrderSessionPoolReader.cpp"),
        Path("apps/hft-parser/src/Runtime/src/Session/SessionService.cpp"),
    ),
    "parser": (
        REGISTER_ALL,
        CONNECTOR_HEADER,
        Path("src/src/Core/src/Runtime/Market/ExecutionKernel.cpp"),
        Path("src/src/Contracts/include/cxet/Primitives/Composite/Trade.hpp"),
        Path("src/src/Contracts/include/cxet/Primitives/Composite/BookTickerUpdates.hpp"),
        Path("src/src/Contracts/include/cxet/Primitives/Composite/OrderBookUpdates.hpp"),
    ),
    "transport": (
        Path("src/src/Core/include/cxet/Network/Ws/Runtime/WsRuntime.hpp"),
        Path("src/src/Core/include/cxet/Network/Ws/Runtime/WsRuntimeContract.hpp"),
        Path("src/src/Core/include/cxet/Network/Ws/Core/WsFrameCodec.hpp"),
        Path("src/src/Core/src/Private/Network/Ws/Runtime/Detail/NativeWsTls.hpp"),
        Path("src/src/Core/src/Network/Fix/FixClient.cpp"),
        Path("src/src/Core/src/Network/Grpc/GrpcClient.cpp"),
        Path("src/src/Core/src/Network/Rest/FastRestSession.cpp"),
        Path("src/src/Core/src/Api/Order/OrderSessionPoolSend.cpp"),
        Path("src/src/Core/src/Api/Order/Rest/OrderRestSessionPool.cpp"),
    ),
    "runtime": (
        RUNTIME_VALIDATION,
        Path("apps/trader/src/Runtime/include/trader/Runtime/Order/AdmissionPolicy.hpp"),
        Path("apps/trader/src/Process/src/Traderd/Application/TraderdDispatchMain.cpp"),
    ),
}

HOTPATH_CLASSIFICATION: dict[str, tuple[str, ...]] = {
    "H0": (
        "steady-state market receive/parse/publish",
        "inline strategy cycle",
        "prepared order payload patch and terminal transport write",
    ),
    "H1": (
        "order ACK/user event/session handoff",
        "queue, ring, readiness, and risk state consumed by H0",
    ),
    "C": ("configuration, connect/auth, REST preparation, reconnect, and reload",),
    "D": ("deep metrics, logs, probes, trace capture, and diagnostic viewers",),
}

REVIEW_PATTERNS: dict[str, tuple[str, ...]] = {
    "simdjson_compat": (r"\bsimdjson\b", r"\bStreamSoABuffer\b", r"\bpadded_string\b"),
    "blocking_wait": (
        r"\bsleep_for\s*\(",
        r"\bsleep_until\s*\(",
        r"\bcondition_variable\b",
        r"\.wait\s*\(",
    ),
    "allocation_growth": (
        r"\bnew\s+",
        r"\bmake_unique\s*<",
        r"\bmake_shared\s*<",
        r"\.push_back\s*\(",
        r"\.emplace_back\s*\(",
        r"\.reserve\s*\(",
        r"\.resize\s*\(",
    ),
    "locks_syscalls": (
        r"\bmutex\b",
        r"\block_guard\s*<",
        r"\bunique_lock\s*<",
        r"::send\s*\(",
        r"::recv\s*\(",
        r"\b(?:terminalWrite|writePrepared|sendEnvelope)\s*\(",
    ),
    "diagnostic": (
        r"\bstd::(?:cout|cerr|clog)\b",
        r"\b(?:f?printf)\s*\(",
        r"\bstd::format\s*\(",
        r"\bfmt::",
        r"\bspdlog::",
    ),
    "floating_point": (r"\bdouble\b", r"\bfloat\b"),
}


MARKET_PRODUCT_HINTS: dict[str, tuple[str, ...]] = {
    "spot": ("spot",),
    "futures": (
        "fapi",
        "linear",
        "uta",
        "usdt",
        "usdt-futures",
        "usdm",
        "swap",
        "futures",
    ),
    "margin": ("margin",),
    "inverse": ("inverse", "coin-futures"),
    "swap": ("swap", "usdc-futures"),
    "option": ("option", "options"),
}


READINESS_PATTERNS: dict[str, tuple[str, ...]] = {
    "market_data_runtime": (
        "parseTradesRuntimeFn",
        "parseBookTickerSideTapeRuntimeFn",
        "parseOrderBookTapeRuntimeFn",
        "parseReferenceDataRuntimeFn",
        "parsePriceLimitRuntimeFn",
        "parseLiquidationRuntimeFn",
    ),
    "user_data": (
        "parseUserDataEventFn",
        "parseUserDataEventsFn",
        "prepareSessionTargetFn",
        "keepAliveSessionTargetFn",
        "closeSessionTargetFn",
        "accountSnapshotOnly",
    ),
    "order_entry": (
        "canonicalOrderEntryConfig",
        "parseOrderAckFn",
        "parseOrderAckPayloadFn",
        "parseOrderResponseEventFn",
        "buildFixPayloadFn",
        "connectFixSessionFn",
        "sendRestOrderFn",
        "SendWsObject::Order",
        "SendObject::Order",
    ),
    "order_session": (
        "WsSendObject::Session",
        "buildWsAuthPayloadFn",
        "buildWsAuthPayloadFromChallengeFn",
        "validateWsAuthAckFn",
    ),
    "hot_adapter": ("fixedOrderAdapter", "PrepareHotSymbolOrderAdapterFn"),
    "trading_control": (
        "syncTradingStateFn",
        "refreshSymbolConfigFn",
        "refreshAccountSnapshotFn",
        "setLeverageFn",
        "setMarginTypeFn",
    ),
}


@dataclass(frozen=True)
class EvidenceLine:
    path: str
    line: int
    text: str

    def to_json(self) -> dict[str, object]:
        return {"path": self.path, "line": self.line, "text": self.text}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def clean_name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower().replace("_", "-")
    return value or None


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def repo_relative_path(value: str, root: Path) -> str | None:
    raw = Path(value).as_posix()
    root_text = root.as_posix().rstrip("/")
    if raw.lower().startswith(root_text.lower() + "/"):
        return raw[len(root_text) + 1 :]
    marker = "/cxet/"
    marker_at = raw.lower().rfind(marker)
    if marker_at >= 0:
        return raw[marker_at + len(marker) :]
    if not Path(value).is_absolute():
        return raw.lstrip("./")
    return None


def read_json(path: Path) -> object | None:
    try:
        return json.loads(read_text(path))
    except (json.JSONDecodeError, OSError):
        return None


def parse_cmake_cache(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if not line or line.startswith(("#", "//")) or "=" not in line:
            continue
        key_type, value = line.split("=", 1)
        key, _, _ = key_type.partition(":")
        values[key] = value
    return values


def build_artifact_report(root: Path, build_dir: Path, expected: dict[str, str]) -> dict[str, object]:
    commands_path = root / build_dir / "compile_commands.json"
    cache_path = root / build_dir / "CMakeCache.txt"
    raw_commands = read_json(commands_path)
    command_rows = raw_commands if isinstance(raw_commands, list) else []
    compiled: set[str] = set()
    for row in command_rows:
        if not isinstance(row, dict) or not isinstance(row.get("file"), str):
            continue
        source = Path(row["file"])
        if not source.is_absolute():
            source = Path(row.get("directory", root)) / source
        try:
            relative = source.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
        if relative.startswith(("src/src/Core/src/", "src/src/Contracts/src/",
                                "apps/trading-core/", "apps/trader/", "apps/hft-parser/")):
            compiled.add(relative)
    compiled_sources = sorted(compiled)
    missing_sources = [source for source in compiled_sources if not (root / source).is_file()]
    cache = parse_cmake_cache(cache_path)
    profile = {key: cache.get(key) for key in expected}
    mismatches = {
        key: {"expected": value, "observed": cache.get(key)}
        for key, value in expected.items()
        if cache.get(key) != value
    }
    if not commands_path.is_file():
        status = "surface_unavailable"
    elif not cache_path.is_file():
        status = "profile_unknown"
    elif mismatches:
        status = "profile_mismatch"
    elif missing_sources:
        status = "source_mismatch"
    elif not compiled_sources:
        status = "surface_unavailable"
    else:
        status = "available"
    return {
        "build_dir": build_dir.as_posix(),
        "status": status,
        "compile_commands": rel(commands_path, root),
        "cmake_cache": rel(cache_path, root),
        "profile": profile,
        "profile_mismatches": mismatches,
        "missing_sources": missing_sources,
        "compiled_source_count": len(compiled_sources),
        "compiled_sources": compiled_sources,
    }


def selected_surface_names(surface: str) -> tuple[str, ...]:
    if surface == "all":
        return tuple(name for name in HOTPATH_SURFACES if name != "all")
    if surface not in HOTPATH_SURFACES:
        raise ValueError(f"surface must be one of: {', '.join(HOTPATH_SURFACES)}")
    return (surface,)


def hotpath_surface_files(root: Path, surface: str) -> list[Path]:
    names = selected_surface_names(surface)
    paths: set[Path] = set()
    for name in names:
        for root_path in HOTPATH_ROOTS[name]:
            absolute = root / root_path
            if absolute.is_dir():
                paths.update(
                    path.relative_to(root)
                    for path in absolute.rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in CPP_SCAN_SUFFIXES
                )
        paths.update(path for path in HOTPATH_ANCHORS[name] if (root / path).is_file())

    if "parser" in names:
        exchanges = root / "src/src/Core/src/Exchanges"
        if exchanges.is_dir():
            for path in exchanges.rglob("*"):
                if (not path.is_file() or
                        path.suffix.lower() not in CPP_SCAN_SUFFIXES):
                    continue
                if path.name == "Config.cpp" or "Parse" in path.name or "PublicMarketDataPolicy" in path.name:
                    paths.add(path.relative_to(root))
    return sorted(paths, key=lambda path: path.as_posix())


def scan_review_candidates(root: Path, paths: Iterable[Path], limit_per_category: int = 40) -> dict[str, list[dict[str, object]]]:
    compiled = {
        category: tuple(re.compile(pattern) for pattern in patterns)
        for category, patterns in REVIEW_PATTERNS.items()
    }
    found: dict[str, list[dict[str, object]]] = {category: [] for category in compiled}
    for path in paths:
        text = read_text(root / path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            for category, patterns in compiled.items():
                rows = found[category]
                if len(rows) >= limit_per_category or not any(pattern.search(line) for pattern in patterns):
                    continue
                rows.append(EvidenceLine(path.as_posix(), lineno, stripped).to_json())
    return found


def build_hotpath_surface(repo_root: Path | None = None, surface: str = "all",
                          build_dir: Path | None = None) -> dict[str, object]:
    root = (repo_root or default_repo_root()).resolve()
    surface = clean_name(surface) or "all"
    names = selected_surface_names(surface)
    files = hotpath_surface_files(root, surface)
    directory = build_dir if build_dir is not None else Path("build")
    cache = parse_cmake_cache(root / directory / "CMakeCache.txt")
    owner = cache.get("CXET_BUILD_OWNER")
    owners = {"CXETCPP", "hft-parser", "trading-core", "hft-backtest",
              "trader", "vetron", "hft-recorder", "hft-compressor", "diagnostic", "TestExchangesHelper"}
    artifacts = {
        "root": build_artifact_report(
            root,
            directory,
            {
                "CMAKE_HOME_DIRECTORY": str(root),
                "CMAKE_BUILD_TYPE": "Release",
                "CXET_FULL_BUILD": "OFF",
                "CXET_BUILD_OWNER": owner if owner in owners else "canonical build owner required",
                "CXET_FAMILY_SOURCE_GRAPH": "OFF",
                "CXET_ENABLE_HFT_MAGIC": "ON",
                },
        ),
    }
    compiled = artifacts["root"].pop("compiled_sources")
    file_names = {path.as_posix() for path in files}
    compiled_surface = [path for path in compiled if path in file_names]
    anchors = sorted(
        {
            path.as_posix()
            for name in names
            for path in HOTPATH_ANCHORS[name]
            if (root / path).is_file()
        }
    )
    artifact_statuses = {item["status"] for item in artifacts.values()}
    status = "available" if artifact_statuses == {"available"} else "surface_unavailable"
    return {
        "evidence": "static-only",
        "surface": surface,
        "surface_status": status,
        "selected_surfaces": list(names),
        "build_artifacts": artifacts,
        "canonical_anchors": anchors,
        "canonical_file_count": len(files),
        "files": [path.as_posix() for path in files],
        "compiled_surface_translation_units": compiled_surface,
        "classification": {name: list(items) for name, items in HOTPATH_CLASSIFICATION.items()},
        "review_candidates": scan_review_candidates(root, files),
        "static_limitations": [
            "Canonical files are a review surface, not an automated caller-chain proof.",
            "compile_commands.json proves translation units only; header inclusion still needs an include/caller trace.",
            "Token matches are review candidates, not violations or severity findings.",
            "No speedup is claimed without a before/after measurement on an explicitly permitted workload.",
            "No build, test, benchmark, runtime, Git, network, account, or live action was run.",
        ],
    }


def grep_lines(root: Path, paths: Iterable[Path], patterns: Iterable[str], limit: int = 20) -> list[EvidenceLine]:
    needles = tuple(patterns)
    rows: list[EvidenceLine] = []
    for rel_path in paths:
        path = root / rel_path
        if not path.is_file():
            continue
        for lineno, line in enumerate(read_text(path).splitlines(), start=1):
            if not any(needle in line for needle in needles):
                continue
            rows.append(EvidenceLine(rel_path.as_posix(), lineno, line.strip()))
            if len(rows) >= limit:
                return rows
    return rows


def parse_registered_exchanges(root: Path) -> list[str]:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", "", read_text(root / REGISTER_OWNERS), flags=re.DOTALL)
    owners = re.search(r"using\s+RegisteredExchanges\s*=\s*RegistrationChain\s*<(.*?)>;", text, re.DOTALL)
    return sorted(set(re.findall(r"\b([a-z][a-z0-9_]*)::Registrar\b", owners.group(1)))) if owners else []


def to_exchange_name(camel: str) -> str:
    out: list[str] = []
    for idx, ch in enumerate(camel):
        if ch.isupper() and idx > 0 and (not camel[idx - 1].isupper()):
            out.append("-")
        out.append(ch.lower())
    return "".join(out).replace("_", "-")


def exchange_config_files(root: Path, exchange: str | None = None, market: str | None = None) -> list[Path]:
    base = root / "src/src/Core/src/Exchanges"
    if not base.is_dir():
        return []
    requested_exchange = clean_name(exchange)
    if requested_exchange:
        exchange_dirs = [
            path
            for path in base.iterdir()
            if path.is_dir() and clean_name(path.name) == requested_exchange
        ]
    else:
        exchange_dirs = [path for path in base.iterdir() if path.is_dir()]
    hints = MARKET_PRODUCT_HINTS.get(market or "", ())
    found: list[Path] = []
    for ex_dir in exchange_dirs:
        if not ex_dir.is_dir():
            continue
        for path in ex_dir.rglob("Config.cpp"):
            rel_parts = path.relative_to(ex_dir).parts
            product = rel_parts[0] if rel_parts else ""
            if hints and clean_name(product) not in hints and market not in path.as_posix().lower():
                continue
            found.append(path.relative_to(root))
    return sorted(found, key=lambda p: p.as_posix())


def collect_sources(repo_root: Path | None = None) -> dict[str, object]:
    root = (repo_root or default_repo_root()).resolve()
    config_files = exchange_config_files(root)
    anchors = [
        REGISTER_ALL,
        REGISTER_OWNERS,
        READINESS_HEADER,
        CONNECTOR_HEADER,
        RUNTIME_VALIDATION,
        CAPABILITY_VIEW,
        PRIVATE_AUDIT,
        EXCHANGE_CONTRACT,
    ]
    return {
        "evidence": "static-only",
        "repo_root": root.as_posix(),
        "anchors": [p.as_posix() for p in anchors if (root / p).exists()],
        "registered_exchanges": parse_registered_exchanges(root),
        "config_file_count": len(config_files),
        "sample_config_files": [p.as_posix() for p in config_files[:30]],
        "notes": [
            "This helper reads files only.",
            "It does not run compiled readiness code or live exchange probes.",
        ],
    }


def bool_status(rows: list[EvidenceLine]) -> str:
    return "present" if rows else "not_observed"


def build_section_report(
    root: Path,
    config_paths: list[Path],
    common_paths: list[Path],
    patterns: Iterable[str],
) -> dict[str, object]:
    needles = tuple(patterns)
    exchange_rows = grep_lines(root, config_paths, needles, limit=18)
    common_rows = grep_lines(root, common_paths, needles, limit=18)
    exchange_evidence = [row.to_json() for row in exchange_rows]
    return {
        "status": bool_status(exchange_rows),
        "status_basis": "exchange_config_evidence",
        "evidence": exchange_evidence,
        "exchange_evidence": exchange_evidence,
        "common_anchor_evidence": [row.to_json() for row in common_rows],
    }


def build_readiness_report(
    repo_root: Path | None = None,
    exchange: str | None = None,
    market: str | None = None,
) -> dict[str, object]:
    root = (repo_root or default_repo_root()).resolve()
    exchange = clean_name(exchange)
    market = clean_name(market)
    registered = parse_registered_exchanges(root)
    config_paths = exchange_config_files(root, exchange, market)
    common_paths = [
        REGISTER_ALL,
        READINESS_HEADER,
        CONNECTOR_HEADER,
        RUNTIME_VALIDATION,
        CAPABILITY_VIEW,
        PRIVATE_AUDIT,
    ]
    sections: dict[str, dict[str, object]] = {}
    for name, patterns in READINESS_PATTERNS.items():
        sections[name] = build_section_report(root, config_paths, common_paths, patterns)

    register_rows = grep_lines(root, [REGISTER_ALL], [f"register{exchange_to_register_hint(exchange)}"] if exchange else ["register"], limit=12)
    query = {"exchange": exchange or "-", "market": market or "-"}
    exchange_registered = "unknown"
    if exchange:
        exchange_registered = "present" if exchange in registered else "not_observed"

    return {
        "evidence": "static-only",
        "query": query,
        "anchors": [
            REGISTER_ALL.as_posix(),
            CONNECTOR_HEADER.as_posix(),
            READINESS_HEADER.as_posix(),
            RUNTIME_VALIDATION.as_posix(),
            CAPABILITY_VIEW.as_posix(),
            PRIVATE_AUDIT.as_posix(),
        ],
        "registration": {
            "status": exchange_registered,
            "registered_exchanges": registered,
            "evidence": [row.to_json() for row in register_rows],
        },
        "config_candidates": [p.as_posix() for p in config_paths],
        "sections": sections,
        "static_limitations": [
            "This is source inspection, not compiled ExchangeProductReadinessMask output.",
            "Section status is based only on exchange-owned Config.cpp evidence.",
            "Common anchor evidence shows shared fields/tools context and does not make a section present.",
            "No build, test, runtime binary, live exchange call, order placement, cancel, or account fetch was run.",
            "Use the manual commands below when the current task explicitly permits verification.",
        ],
        "manual_verification_commands": manual_commands(exchange, market),
    }


def exchange_to_register_hint(exchange: str | None) -> str:
    if not exchange:
        return ""
    pieces = re.split(r"[-_]+", exchange)
    return "".join(piece[:1].upper() + piece[1:] for piece in pieces)


def manual_commands(exchange: str | None, market: str | None) -> list[str]:
    # Public owner wrappers build production products; `all` runs local tests.
    # Optional full-profile diagnostic executables are not produced here.
    commands = [
        "./apps/trader/compile.sh p",
        "python3 tools/Codex/CxetToolbelt.py hotpath --surface all --build-dir build --format summary",
    ]
    return commands


def render_summary(payload: dict[str, object]) -> str:
    if "surface" in payload:
        return render_hotpath_summary(payload)
    if "sections" not in payload:
        return render_sources_summary(payload)
    query = payload.get("query", {})
    out = [
        "be0h check: static-only readiness trace",
        f"query: exchange={query.get('exchange')} market={query.get('market')}",
        f"registration: {payload.get('registration', {}).get('status')}",
        "config candidates:",
    ]
    candidates = payload.get("config_candidates", [])
    if candidates:
        out.extend(f"- {item}" for item in candidates)
    else:
        out.append("- none observed")
    out.append("sections:")
    sections = payload.get("sections", {})
    for name, section in sections.items():
        exchange_count = len(section.get("exchange_evidence", []))
        common_count = len(section.get("common_anchor_evidence", []))
        out.append(
            f"- {name}: {section.get('status')} "
            f"(exchange_config={exchange_count}, common_anchor={common_count})"
        )
    out.append("manual verification commands:")
    out.extend(f"- {cmd}" for cmd in payload.get("manual_verification_commands", []))
    out.append("not verified: build/test/runtime/live proof")
    return "\n".join(out) + "\n"


def render_hotpath_summary(payload: dict[str, object]) -> str:
    out = [
        "be0h check: static-only hot-path surface",
        f"surface: {payload.get('surface')}",
        f"surface_status: {payload.get('surface_status')}",
        "build artifacts:",
    ]
    for name, artifact in payload.get("build_artifacts", {}).items():
        out.append(
            f"- {name}: {artifact.get('status')} "
            f"(compiled_sources={artifact.get('compiled_source_count')})"
        )
        for key, mismatch in artifact.get("profile_mismatches", {}).items():
            out.append(
                f"  profile mismatch {key}: expected={mismatch.get('expected')} "
                f"observed={mismatch.get('observed')}"
            )
    out.append("canonical anchors:")
    anchors = payload.get("canonical_anchors", [])
    out.extend(f"- {item}" for item in anchors) if anchors else out.append("- none observed")
    out.append("compiled surface translation units:")
    compiled = payload.get("compiled_surface_translation_units", [])
    out.extend(f"- {item}" for item in compiled) if compiled else out.append("- none observed")
    out.append("review candidates (token matches only):")
    for name, rows in payload.get("review_candidates", {}).items():
        out.append(f"- {name}: {len(rows)}")
    out.append("not verified: caller chain/build/test/benchmark/runtime/live proof")
    return "\n".join(out) + "\n"


def render_sources_summary(payload: dict[str, object]) -> str:
    out = [
        "be0h check: static-only CXET source map",
        f"repo_root: {payload.get('repo_root')}",
        "anchors:",
    ]
    out.extend(f"- {item}" for item in payload.get("anchors", []))
    out.append("registered exchanges:")
    out.append("- " + ", ".join(payload.get("registered_exchanges", [])))
    out.append(f"config_file_count: {payload.get('config_file_count')}")
    out.append("not verified: build/test/runtime/live proof")
    return "\n".join(out) + "\n"


def emit(payload: dict[str, object], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_summary(payload))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only CXET Codex helper")
    parser.add_argument("--repo-root", default=None, help="repository root override")
    sub = parser.add_subparsers(dest="command", required=True)

    sources = sub.add_parser("sources", help="list static source anchors")
    sources.add_argument("--format", choices=("summary", "json"), default="summary")

    readiness = sub.add_parser("readiness", help="static exchange/trader readiness trace")
    readiness.add_argument("--exchange", default=None)
    readiness.add_argument("--market", default=None)
    readiness.add_argument("--format", choices=("summary", "json"), default="summary")

    hotpath = sub.add_parser("hotpath", help="static production hot-path review surface")
    hotpath.add_argument("--surface", choices=HOTPATH_SURFACES, default="all")
    hotpath.add_argument("--build-dir", type=Path, default=Path("build"),
                         help="one canonical root-graph production build directory; no fallback")
    hotpath.add_argument("--format", choices=("summary", "json"), default="summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root()
    if args.command == "sources":
        emit(collect_sources(root), args.format)
        return 0
    if args.command == "readiness":
        emit(build_readiness_report(root, args.exchange, args.market), args.format)
        return 0
    if args.command == "hotpath":
        emit(build_hotpath_surface(root, args.surface, args.build_dir), args.format)
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
