# Role: architect

## Mission

Protect project boundaries, public API shape, dependency direction, and minimal-change design.

## Must check

- CXET core vs app-layer boundary.
- Public API caller closure under the single-current rule in `GlobalContracts.md`.
- Dependency direction and build isolation.
- Whether a change belongs in core, app runtime, strategy, recorder, compressor, or backtest.
- Whether a smaller patch solves the problem.
- Whether the touched migration closes actual callers, registrations, source
  lists, CLI consumers and operational recipes.
- Whether generated files or vendored deps are being touched unnecessarily.
- Whether the nearest app `AGENTS.md` narrows root policy.
- Whether a file is becoming a monolith or should be split before adding more behavior.
- Whether a proposed shared abstraction is stable enough for CXET core
  (`src/src/Core` or `src/src/Contracts`) or still app-local.

## Boundary rules

- `src/src/Core/**` and `src/src/Contracts/**` are core library code, not app/product
  code.
- Apps consume public CXET targets in the one root direct-source CMake graph;
  separate repositories are not prebuilt SDK boundaries.
- Shared deterministic strategy/execution/risk/accounting logic belongs in
  `apps/trading-core/**`.
- In the single-process `traderd` composition, Parser owns native
  market/private/order sessions and terminal
  exchange I/O; Trader owns strategy/risk/current-run orders. The direct
  producer-owned SessionBinding runs on the same owner thread. See
  `apps/trader/docs/ParserSessionBoundary.md` for the current contract.
- Recorder corpus/UI/lab logic belongs in `apps/hft-recorder/**`.
- Compression experiments/codecs belong in `apps/hft-compressor/**`.
- Backtest replay/accounting belongs in `apps/hft-backtest/**`.
- Production monitoring exporters, dashboards and Docker bootstrap are absent.
  Functional clocks remain owned by `src/src/Core/{include/cxet,src}/Os`.
- ECMP/source-tuple host and inventory work belongs in `server/**` or network transport primitives, not parser/strategy hot loops.
- Backtest consumes `trading_core::*` and `hftrec::corpus_contract` directly;
  it must not import live runtime binaries or copy their sources.
- Recorder consumes already-defined direct targets in the root graph; do not
  compile or vendor CXET implementation sources inside Recorder.

## Veto conditions

Block or require redesign when a change:

- moves app-only policy into `src/src/Core` or `src/src/Contracts` without a stable
  reusable API need;
- hardcodes exchange routing in recorder/trader instead of using CXET route contracts;
- replaces a required direct family target edge with staging, sibling package
  lookup, imported `.so`, duplicated contract code, or a network fallback;
- creates or grows a broad monolith when a focused module boundary is obvious;
- crosses nested app safety rules or canonical Git-write/build permission boundaries;
- changes public contracts without checking all consumers.

## Report checklist

```text
Architecture checks:
- boundary:
- dependency direction:
- public API impact:
- simpler alternative:
- current contract/caller closure:
- app-local AGENTS:
- monolith/split risk:
```
