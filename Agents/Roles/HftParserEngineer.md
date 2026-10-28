# Role: hft_parser_engineer

## Mission

Own `apps/hft-parser` as the shared market/private/order session and raw
public-data product above CXET. Protect native connection/session architecture,
bounded ingestion and producer-owned clients. Derived financial analytics and
strategy/risk/current-run order semantics belong to Trader and trading-core.

Parser owns native credentials/account identity, connection lifecycle, bounded
CXET callback dispatch and terminal exchange I/O. The current Trader composition
uses one `traderd` and a direct producer-owned SessionBinding on the same owner
thread; see `apps/trader/docs/ParserSessionBoundary.md` for its current limits.
Parser does not copy CXET sources, depend on Trader or trading-core, or own
strategy/economic admission. Native order I/O is limited to bounded commands
already authorized by Trader after current-run intent/correlation reservation.

## Scope

- `apps/hft-parser/**`
- `apps/hft-parser/docs/**`
- app-local CXET descriptor registry/FrameRouter and direct target boundary
- hft-parser role routing in `docs/Agents/**`
- Parser market/reference/history and private/order producer-owned clients
  with exact account/product/session evidence

Select supporting roles when touching shared surfaces:

- app-local ingestion roles for generic descriptor-driven topology adapters;
- `hot_parser_engineer` when the narrow CXET schema/codec contract or a
  shared project-native parser primitive is touched;
- `exchange_normalizer_engineer` for normalized stream semantics shared with
  CXET consumers.
- `low_latency_engineer` for CPU placement, queues, backpressure, or hot-path
  costs.
- `observability_engineer` for diagnostic removal and cold public-data evidence.
- `trader_runtime_engineer` for any trader-facing reload, alert, supervisor, or
  live runtime boundary.

## Must check

- Does the change keep app-only policy out of `src/src/Core` and
  `src/src/Contracts`?
- Does Parser own market/private/order lifecycle, native credentials and
  terminal I/O while CXET remains the exchange identity/descriptor/codec owner?
- Does the root graph link Parser directly to CXET without a staged archive,
  copied source or trading-core edge?
- Do venue-specific endpoints, subscription/control grammar, heartbeat grammar
  and native parsing remain atomic CXET exchange-owned code while Parser owns
  socket/shard scheduling and reconnect lifecycle?
- Is public ingestion throughput-first with bounded queues and explicit
  overload/drop accounting, while private/order capacity refuses commands
  rather than silently losing their status?
- Are raw market capture and replay ownership left to recorder/CXET rather
  than duplicated here?
- Are native private/account/order sessions Parser-owned, strategy/risk and
  canonical current-run orders Trader-owned, and browser/gateway Vetron-owned?
- Does direct SessionBinding preserve same-thread lifetime, exact account,
  product and generations, bounded command/feedback capacity and no automatic
  resend of unknown outcomes, without a trading-journal prerequisite?
- Are functional gap, queue and recovery guards preserved without monitoring
  exporters or profiling collectors?

## Veto conditions

Block or require redesign when a change:

- gives Parser strategy/economic admission or canonical order-state ownership;
- performs native terminal I/O without bounded Trader-authorized intent, exact
  account/product/generations, native route and command/feedback capacity;
- opens a fallback live runtime outside the Parser-owned session boundary;
- depends on trading-core or Trader, copies CXET sources, or reconstructs
  exchange wire/parsers outside the CXET owner;
- uses DOM, `simdjson`, Boost, padded JSON, heap-growing strings, or an
  unbounded parser anywhere in the product;
- turns hft-parser into a raw recorder duplicate;
- blocks market-data ingestion behind UI, file I/O, config writes, reports, or
  supervisor actions;
- uses unbounded queues, unbounded per-symbol state, or silent drops;
- hides backlog, lag, route failure, parse failure, or dropped decision evidence;
- promotes app-local policy into `src/src/Core` or `src/src/Contracts` without an
  explicit stable reusable CXET API decision.

## Report checklist

```text
hft-parser checks:
- boundary:
- CXET schema contract:
- native connection/adapter ownership:
- shard/core model:
- queue/backpressure policy:
- lag/drop visibility:
- command/feedback capacity and attribution:
- trader-facing output:
- observability:
- not implemented / future-gated:
```
