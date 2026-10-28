# Role router

Select expertise silently for simple tasks. Read this router for uncertain
ownership or non-trivial role selection; it does not require a thread per role.
Before risky edits state only actual delegated ownership and material risks.

## Workflow owners

- `DevelopmentWorkflow.md`: behavior, caller closure, useful tests and exact
  command selection. Editing permission never grants check permission.
- `PlanWorkflow.md`: S/M/H planning and native Goals. S stays lightweight,
  M uses an in-chat plan, H needs settled behavior before edits. Persist only
  requested/cross-session work; planning alone never starts execution.
- `cxet-workflow`: durable creation/execution. `cxet-audit-plan`: existing
  plan audit. Select an explicit ID or the only compatible active plan, never
  by recency. Risk and mechanical/logical complexity remain separate axes.
- `Subagents.md`: model routing, simplicity participation, workers, vetoes and
  mandatory final independent H0/H1 and substantive offline Capital review. Reuse CLEAR for unchanged
  surfaces; repeat only for repairs/material changes on the affected scope.
  Missing unrequested runs are limits, not vetoes.

## Expertise map

The primary may apply expertise directly. Follow the simplicity participation
rule in `Subagents.md`; other separate reviews need a serious concrete risk or
user request.

| Role | Scope and triggers |
|---|---|
| `orchestrator` | Non-trivial task routing, plan, ownership and integration |
| `code_simplicity_engineer` | Reuse, boilerplate, duplication, unnecessary complexity and cohesive structure; consultation and separately authorized simplification |
| `architect` / native `architect_reviewer` | Public API/ABI/schema, migration, dependencies, portability, app/core boundaries, CMake and structural workflow changes |
| `low_latency_engineer` | H0/H1 latency, allocation, cache/memory, locks/queues/drain/batches, market pump/runner, all Capital computation |
| `hot_parser_engineer` | Native JSON/StringView/bytescan, SBE/protobuf/FIX-SBE, registered parse*RuntimeFn/normalized runtime payload/tape, private wrappers and hot/cold separation |
| `hot_transport_engineer` | WS/FIX/gRPC/hot REST, TLS/socket/framing, partial I/O/WANT_READ, compression, heartbeat/timeouts/reconnect and terminal send |
| `trader_runtime_engineer` | Trader readiness/reload/recovery, SessionBinding, provenance/generations, order/user lifecycle, external baseline and inline execution |
| `strategy_quant` | trading-core signals/intent/execution/risk, accounting/PnL/fees, backtest interpretation; Capital finance/liquidity/portfolio/obligations/scenarios/DP |
| `exchange_normalizer_engineer` | Exchange-native endpoints/auth/requests/wire/schema/logical streams and normalization into runtime payloads |
| `exchange_readiness_engineer` | Connector registration, ObjectConfig/RoutePlan/capabilities, selected wire, public/private/order hooks and consumer readiness |
| `hft_parser_engineer` | Parser public/private/order fabric, producer clients, native sessions, account isolation, shard/core/capacity planning and public fan-in |
| `hft_parser_security_engineer` | Credentials, peer/local IPC identity, filesystem/browser trust, mutation exclusion and terminal-send authority |
| `hft_parser_reliability_reviewer` | Bounds, queue overflow/gaps/staleness, backpressure, reconnect storms and consumer/storage/UI failure containment |
| `backtest_engineer` | Deterministic replay/fills/accounting/sweeps and result JSON |
| `recorder_corpus_engineer` | Capture/corpus/validation, Qt/QML GUI and compression lab |
| `compression_engineer` | Codec/pipeline work and zstd/lz4/brotli/xz baselines |
| `observability_engineer` | Diagnostic/probe cost, metrics/dashboard meanings, timestamp/RTT/p50/p99 interpretation and removal |
| `network_placement_engineer` | ECMP/source tuples/binds/lanes, endpoint inventory, region/AZ uncertainty and network placement evidence |

## Path selection

For production hot work first use `HotPathFastLane.md`: prove the selected
compiled/registered route and H0/H1/C/D surface. Capital instead identifies its
selected owner-local root-graph finance/offline surface; offline linkage grants
no live readiness or launch permission.

| Affected surface | Relevant expertise |
|---|---|
| `src/src/Contracts/**` | Architecture + latency; normalizer for canonical API/primitives; parser for wire/runtime payload |
| `src/src/Core/**` | Latency; normalizer for exchange/API; parser for runtime codecs |
| Core `Network/**`, `Api/{Market,Order,User}/**`, prepared send | Transport + latency; normalizer for wire/route; readiness for selected sessions/consumption |
| Parse/canonical runtimes and exchange Market/User/Order implementations | Parser + normalizer; transport for framing/session effects |
| `apps/trading-core/**` | Quant + latency; strategies/registry/deterministic semantics stay here, native adapter in Trader |
| `apps/trading-core/capital/**` | Quant + latency already offline; nested financial rules and substantive-computation review pair; architecture for owner/caller migration |
| `apps/trader/**` | Runtime + latency for H0/H1; transport for Parser client/terminal send; architecture for strategy/risk/order and projection boundaries |
| `apps/hft-parser/**` | Parser coordinator and app-local `docs/agents/ROLE_ROUTER.md`; transport/latency for native I/O; normalizer/parser for CXET codecs; runtime/architecture for Trader clients |
| `apps/vetron/**` | Parser/architecture for Parser projections; runtime/architecture for Trader projections/control; security for mutation/authentication |
| `apps/hft-recorder/**` | Corpus and its app-local `docs/Agents/RoleRouter.md`; architecture for CXET boundaries |
| `apps/hft-compressor/**`, `apps/hft-backtest/**` | Compression; or backtest + quant for changed strategy/risk |
| Monitoring/probes or measurement removal | Observability + latency when hot cost is involved |
| `server/**`, `var/ecmp/**`, transport bind/lanes/inventory | Placement + architecture; transport retains socket/TLS implementation |
| CMake/public headers/cross-app linkage | Architecture + affected specialist; `cxet-runtime-contract` |

For Parser CPU sharding/queues/backpressure select latency; for journals/status
select observability. See `Roles/` only for the actual specialist question.

## Decisions and vetoes

Ask only about material unsettled ownership, overlapping worker scope, public
behavior/API, risk/recovery/security semantics, ambiguous active plan or missing
exact check selection. Overlap of hot/runtime expertise does not revoke settled
authorization or require repeated permission.

Veto ownership: latency protects bounded hot computation; parser protects native
decoding and hot/cold separation; transport protects TLS/framing/bounded terminal
I/O; runtime protects readiness/session/order state; quant protects financial/
risk/lookahead/accounting semantics. Security protects trust and authority;
reliability protects bounds/loss/fallback/recovery; observability protects probe
cost and truthful latency; placement rejects unauthorized routing mutation and
unsupported AZ/matching-engine claims. Architecture blocks a boundary issue
when a hard rule is violated. Resolve findings at the owning invariant, not by
silencing a reviewer.
