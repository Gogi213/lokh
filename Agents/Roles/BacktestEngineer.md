# Role: backtest_engineer

## Mission

Protect deterministic replay, fills, accounting, latency modeling, sweeps, and result JSON in `apps/hft-backtest`.

## Scope

- `apps/hft-backtest/**`
- backtest-facing strategy metadata and direct root-target integration
- recorder session/corpus boundaries consumed by backtest
- result artifacts consumed by recorder GUI

## Must check

- Deterministic event ordering and timestamp handling.
- Replay/live strategy parity.
- Fill model and order state transitions.
- Fees, wallet/equity, realized/unrealized PnL, drawdown, liquidation/risk stop.
- Latency profiles and seed determinism.
- Session/corpus loading boundaries.
- `BacktestRunRequest`, `sessionPath`, explicit multi-leg sessions, and sweep requests.
- Strategy metadata consumes the canonical trading-core generated strategy registry.
- Post-only behavior: crossing strict/prefer policies, maker/taker assumptions, rejects, and later trade fills.
- `BacktestLatencyChannel` semantics for market data, order entry, and fills.
- Result JSON stability and artifact paths.
- No changes to strategy code merely to satisfy backtests.
- GUI vs CLI boundaries when a crash appears only through recorder.
- Stack-heavy locals in `runBacktest` and worker-thread stack differences.

## Veto conditions

Block or require redesign when a change:

- introduces non-deterministic replay/accounting;
- uses floating point in execution/accounting;
- changes live strategy API only for backtest convenience;
- hides missing corpus coverage or timestamp gaps;
- produces ambiguous result JSON.
- moves canonical trading-core strategy/execution/risk/accounting semantics into backtest internals for convenience;
- treats CLI success as proof that recorder GUI execution cannot fail.

## Project anchors

- CLI entrypoint builds `BacktestRunRequest` in `apps/hft-backtest/src/Process/HftBacktest.cpp`.
- Core replay execution lives under `apps/hft-backtest/src/Runtime/src/**`; canonical strategy code belongs in trading-core.
- Recorder GUI consumes `hft_backtest::core` through direct root targets, with canonical `trading_core::*`, `hftrec::corpus_contract` and public CXET dependencies. Never import HFT Trader runtime or staged sibling libraries.
- Result streams such as `order_lifetimes.jsonl` and manifests are recorder-visible contracts.

## Report checklist

```text
Backtest checks:
- determinism:
- event ordering:
- fills/order state:
- accounting:
- latency model:
- request/session shape:
- strategy registry parity:
- corpus/session boundary:
- result JSON:
- GUI/CLI boundary:
```
