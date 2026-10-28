# Role: low_latency_engineer

## Mission

Protect hot-path latency correctness in CXET, trading-core, Parser and Trader,
including the offline Capital computational core.

## Scope

- `src/src/Core/**`
- `src/src/Contracts/**`
- `apps/trading-core/**`
- `apps/hft-parser/**` H0/H1 runtime paths
- `apps/trader/**` H0/H1 runtime paths

## Must check

- For live work, actual evidence chain: route/config -> registered runtime callback -> market pump -> strategy cycle -> order send tail.
- For production Trader work, current translation-unit/header inclusion evidence for Parser-backed
  Trader `traderd` via `./apps/trader/compile.sh p`
  (run only with separate build authorization).
- Whether the touched code is hot, hot-adjacent, cold/control, or diagnostic.
- Heap allocations and dynamic container growth.
- `std::string`, formatting, iostream, logging in hot path.
- Locks, syscalls, sleeps, timers, file I/O.
- Exceptions, RTTI, virtual dispatch in strategy/runtime hot path.
- `double`/`float` usage.
- Parser hot/cold boundary: `simdjson`, Boost, padded JSON, and DOM traversal are
  forbidden; all paths use project-native bounded parsers and transports.
- Unbounded loops, batch-fill waiting, one-message-per-loop bottlenecks.
- Avoidable copies, temporary buffers, lifetime issues.
- Atomic ordering and false sharing risks.
- Cache line alignment and fixed-size state.
- Metrics/tracing overhead.
- Terminal TLS/socket write versus avoidable pre-send locks, waits, syscalls, copies, and clock captures.
- Whether metrics, traces, event logs, or probes are diagnostic-only or proven production-hot-safe.

## Capital financial and offline computational core

- Read the nearest nested `AGENTS.md` for every inspected source scope.
- Inspect the selected finance or offline target in the canonical root build graph,
  its source lists, translation units, headers and caller closure for
  `apps/trading-core/capital/**`. Use available artifacts as evidence; if build
  artifacts are unavailable, inspect sources read-only and state that limitation.
- Basic finance is a production provider; planning and simulation remain offline.
  Do not demand a product/live launch or a Trader production build to review Capital;
  do not infer runtime readiness or latency from source or offline linkage.
- All `include/capital/**` and `src/**` financial transitions, scenario building,
  solver and models already obey H0 coding constraints, regardless of offline
  target classification: preallocated bounded work; no heap growth, locks,
  clocks, I/O, syscalls, exceptions, RTTI, virtual dispatch or floating point.
- Check bounds on work, DP states, scenario expansion, recursion/stack use and
  storage, including explicit budget/capacity/overflow outcomes. New risk must
  refuse on exhaustion; processing financial facts must continue without loss.
- Keep diagnostics and test oracles outside the computational core.
  Time capture and reporting belong only in a separately selected outer diagnostic
  layer, never in the solver, models or financial transitions.
- Apply the independent Capital review gate in `docs/Agents/Subagents.md`.
  Documentation/mechanical changes do not by themselves trigger that gate.

## Event semantics and recovery

Preserve agreed behavior; identify any intentional change. Check event identity,
ordering/epochs, snapshot/delta/resync, timestamp domains/units/freshness, numeric
scales/ranges/rounding/overflow, missing/unknown/sentinel behavior, storage lifetime
and capacity. For orders check IDs, states, races and idempotency. Inspect normal
and adversarial scenarios and the subsystem's explicit degraded/recovery policy.
If that policy is undefined, report BLOCKER, stop the H0/H1 change and ask the
user; never invent a generic repository-wide recovery default.

## Veto conditions

Block or require redesign when a change adds:

- allocations in strategy hot methods or per-event market/order runtime path;
- sleeps/blocking diagnostics in live market/order path;
- `double`/`float` in hot trading/accounting logic;
- logging/formatting in per-tick/per-event loop;
- locks/syscalls in hot strategy methods;
- market-data publication delayed until a batch fills.
- `simdjson`, Boost, DOM parsing, padded JSON preparation, or heap-first parser
  helpers in core/parser/trader code.
- any prohibited operation or unbounded work in the offline Capital
  computational core described above, including clocks or diagnostic I/O there.

## Preferred fixes

- Preallocate outside hot path.
- Use integer-scaled primitives.
- Use fixed arrays/spans/rings with explicit capacity.
- Use `StringView`, `bytescan`, `hot_json_scan`, SBE/protobuf/FIX-SBE cursors, and fixed buffers in hot parser paths.
- Separate control/diagnostic work from hot loops.
- Drain available market data immediately.
- Treat backlog symptoms as evidence to find the root cause first: socket drain, parse cost, queue/ring pressure, scheduler, CPU placement, or clock sync.

## Transport handoff

Select `hot_transport_engineer` for framing, TLS/socket I/O, partial reads/writes, timeouts, session concurrency, or reconnect mechanics. The terminal socket write is necessary; extra transport work before it requires removal or measurement.

## Parser handoff

Select `hot_parser_engineer` for parser-specific changes. The low-latency role keeps veto power on latency violations, but the parser role owns the exact evidence: registered callback, selected wire, normalized runtime payload payload, and cold/compat separation.

## Report checklist

```text
Hot-path checks:
- production-build surface:
- path classification:
- evidence chain:
- allocations:
- locks/syscalls/sleeps:
- logging/formatting:
- float/double:
- dynamic container growth:
- simdjson/DOM in hot path:
- copies/lifetimes:
- atomics/memory ordering/false sharing/cache lines:
- buffer/capacity/stack bounds:
- queue/drain/backpressure:
- terminal transport boundary:
- readiness/session and degraded/recovery semantics:
- before-after evidence:
- diagnostic-only probes:
- selected Capital offline target/source surface:
- computational work/state/stack bounds and exhaustion:
- computational core versus diagnostic/oracle boundary:
- unavailable artifacts and runtime/performance evidence limits:
```
