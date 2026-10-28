# CXET hot-path fast lane

Use this workflow for non-trivial work in the direct root graph that compiles
the Parser-backed Trader `traderd` production path. App wrappers must configure that
same root graph; they are not alternate staged build systems.

```bash
./apps/trader/compile.sh --force p
```

The goal is to prevent path-name reasoning, symptom patches, and unmeasured latency claims.
The default builds this owner's product incrementally with pinned Clang, GNU
Make, Release `-O3`, native CPU targeting and LTO OFF. `portable` disables CPU
targeting. Fresh foreign providers are reused silently; missing or stale foreign
modules are listed in one combined prompt before rebuilding them. Decline or EOF
cancels; a noninteractive invocation with stale providers exits with an explanatory
error. `--force` builds the selected product and necessary closure incrementally
with FULL LTO, without cleaning or internal dependency prompts; ThinLTO is never
selected. This wrapper behavior requires prior user consent for the exact launch
under `DevelopmentWorkflow.md`.

`all` builds and runs this owner's registered tests, then builds its diagnostic
benchmark executables without measuring them. `--force all` first builds the
optimized product. Other owners' tests and benchmarks are not selected. An empty
test registry does not establish passing test proof. Separate measurement commands
and the manual workflow are documented in `tools/Benchmarks/README.md`.

Optimized trees use `build` (native) or `build/modes/portable`; development trees
use `build/modes/dev-native` or `build/modes/dev-portable`. `CXET_BUILD_DIR` is the
exact caller-supplied path; an incompatible existing profile is rejected. Only a
successful product build updates `build/.compile-active/<owner>.json`; default
launchers resolve that selected tree. Failed, UI-only and test-only runs do not
switch it. Project-owned libraries remain static `.a`; `p` selects automatic
parallelism across all eligible CPUs, capped at one job per 2 GiB below
`MemoryHigh` (at least one job). Local `p` uses `MemAvailable` minus a 2 GiB
system reserve, clipped by inherited cgroup headroom, with a 2 GiB minimum
budget and no implicit 16 GiB ceiling. `MemoryHigh` remains 75% of the admitted
budget, `MemoryMax` remains a hard limit and swap stays disabled. CI retains
its inherited memory admission and CPU quota. Explicit positive jobs and
memory caps override automatic selection without bypassing containment.
Without `p`, the existing serial/default-memory behavior is retained unless
`-j N` selects more jobs. See `--help` for supported options.

Diagnostic and comparison CMake configurations require separate authorization.

## 1. Prove the active surface

Before proposing an optimization or hot-path fix:

1. Inspect the selected root-graph `compile_commands.json` and corresponding
   CMake cache profile.
2. Prove that the changed translation unit is compiled by the production build, or that the changed header is included by a compiled translation unit.
3. Treat missing or profile-mismatched compile artifacts as `surface unavailable`.
   Do not fall back to a staged app build surface.
4. Exclude viewers, recorder, backtest, benchmarks, offline tools, and tests unless the current task explicitly targets them.

### Capital computational core, including offline

`apps/trading-core/capital/{include/capital,src}/**` follows the H0 coding
constraints for all financial transitions, portfolio/liquidity calculations,
scenario construction, model callbacks and solvers. Use stable storage prepared
by the cold caller, explicit capacity/work limits and checked integer/fixed-point
arithmetic. No allocation or uncontrolled growth, exceptions, RTTI, virtual
dispatch, locks, sleeps, clocks, syscalls, I/O, formatting or floating point
belongs in this computational path. Refused/incomplete/stale planning cannot
permit new risk; applying authoritative financial events must continue.
Diagnostics and test oracles remain outside this path; their timing/reporting
does not weaken the computational constraints. Exact rational and fixed-point
models must declare their distinct arithmetic and rounding contracts.

For Capital offline work, inspect its selected trading-core owner-local
root-graph targets, source lists and available matching compile artifacts.
Missing artifacts mean `surface unavailable`; use source inspection and state
that limit without launching a build. Basic finance has production callers;
planning remains offline; execution simulation is removed. H0 constraints and the Capital review gate in `Subagents.md`
apply without asserting a live H0 route, microsecond latency or readiness.
Trace the actual offline event-to-decision/application closure; a future live
integration must separately prove the complete market-to-terminal chain below.

## 2. Classify the path

- `H0` - steady-state tick-to-trade: socket/TLS receive, frame decode, registered runtime parser, direct event/snapshot publication, inline strategy cycle, intent lowering, prepared payload patch, terminal TLS/socket write.
- `H1` - hot-adjacent correctness: order ACK and private user readers, pending correlation, bounded handoff queues, readiness state consumed by H0, and functional bounded counters.
- `C` - cold/control: DNS, TCP/TLS/WS connect, proxy, auth/listen-key preparation, registration, REST preparation, config load/reload, reconnect/backoff, metadata refresh, and startup gates.
- `D` - diagnostic: deep metrics, event logs, probes, viewers, status rendering, reports, and live-smoke tools.

Cold transport safety can gate H0 without being H0 latency. Do not sell faster DNS/TLS startup as faster tick-to-trade.

## 3. Trace the real chain

Market-data evidence must include:

```text
exchange config / connector
-> ObjectConfig and selected wire
-> current Core MarketRuntime binding
-> nonblocking Core MarketRuntime route poll
-> registered parse*RuntimeFn
-> current registered normalized runtime/tape payload contract
-> direct event or snapshot publication
-> Parser-owned typed publication and direct Trader consumer
-> inline strategy runCycle
```

Order evidence must continue through:

```text
OrderIntent / CancelIntent
-> execution preflight
-> armed hot context
-> prepared payload patch
-> order session and pending correlation
-> framing/masking
-> terminal TLS/socket write
```

Do not optimize an isolated codec, parser, helper, or container until its caller chain is proven.

## 4. Hard gates

- A live strategy input is hot-ready only when the selected route publishes through a project-native normalized runtime/tape callback.
- Live hot paths use only project WS, REST, FIX, and gRPC connectors plus
  project-native hotjson, protobuf, SBE, and FIX/SBE parsing primitives.
- `simdjson`, Boost, padded JSON preparation, and DOM traversal are forbidden.
  Compat `StreamSoABuffer` is allowed only behind a bounded project-native parser.
- No parser, selected-wire, session, or readiness fallback may hide missing hot coverage.
- Reconnect and backoff stay in `C`; no sleeps or retry loops may enter H0/H1.
- H0 strategy/runner work uses fixed-size, preallocated, integer-scaled state.
- The terminal TLS/socket write is allowed. Extra locks, waits, syscalls, copies, clock captures, or diagnostics before it require removal or measurement.
- Batch limits are fairness guards. Never wait for a batch to fill before publishing available market data.
- Order-book deltas may be parsed, applied, published, and consumed before a
  snapshot. Missing snapshot alone is not a readiness failure. A later
  sequence-aligned snapshot rebases the book with newer deltas replayed; only a
  proven live sequence gap fails closed.
- Deep metrics, event logs, probes, and trace capture remain diagnostic unless
  their production-hot cost and gating are explicitly proven.
- `[[nodiscard]]`, `hftLikely`, and `hftUnlikely` are not decoration. Use them only for meaningful error handling or stable measured branch bias.

## 5. HFT semantic correctness gate

Apply this gate to every live H0/H1 code change and the applicable financial,
numeric, event, lifetime and degraded-input contracts of Capital computation
already offline. It does not otherwise apply to cold, diagnostic, recorder,
backtest, benchmark, or offline work unless that task directly changes a
contract consumed by the live H0/H1 path. Capital's offline gate does not
require fabricated native session, parser or terminal-send evidence.

- Event identity and ordering: define sequence/update IDs, duplicate handling,
  out-of-order behavior, gap detection, snapshot/delta ordering, and the
  reconnect or session epoch boundary.
- Time and freshness: distinguish exchange event time, exchange processing
  time, local receive time, and monotonic elapsed time. Preserve units,
  precision, clock-domain assumptions, warm-up, and stale thresholds.
- Numeric meaning: preserve integer scale, signedness, units, valid range,
  sentinel/unknown representation, overflow behavior, and rounding direction.
  Check tick size, lot size, and minimum-notional behavior when applicable.
- Ownership and lifetime: prove the lifetime of every view, buffer, payload,
  identifier, and queued event; define fixed capacity and terminal overflow or
  refusal behavior.
- Order lifecycle: when applicable, define client/exchange ID correlation,
  ACK/reject/partial-fill/fill/cancel ordering and races, duplicate-event
  idempotency, reduce-only/position-side meaning, and terminal states.
- Missing or degraded input: the owning subsystem must explicitly define its
  stale, gap, partial, unknown, recovery, and resynchronization behavior. There
  is no repository-wide fail-closed, last-good, or automatic recovery default.
- Semantic preservation: state what observable behavior remains unchanged and
  what intentionally changes. An optimization must not silently change event,
  numeric, time, readiness, or order-state meaning.

If the affected subsystem has no explicit degraded/recovery semantics, report
a `BLOCKER`, stop the H0/H1 change, and ask the user which behavior is intended.
Do not infer a policy from another subsystem and do not preserve an accidental
behavior merely because it is current.

## 6. Evidence and permission

Evidence levels remain separate:

- `static-only` - source, config, compile surface, and call-graph inspection.
- `build proof` - the named production build ran and passed.
- `targeted-test proof` - the named affected tests ran and passed independently.
- `runtime proof` - a local binary exercised the path.
- `live proof` - a named exchange/market/session path was exercised.

Compiler and machine-code evidence also remain separate from runtime evidence:

- Record the exact pinned compiler revision and the actual root-graph
  translation unit before comparing generated code.
- Keep compiler and source-optimization baselines explicit and isolated. Match
  the standard library, linker, build mode, CPU target flags, dependency graph,
  workload, hardware, affinity, and metrics mode across both sides.
- Implement a source optimization with affected source inspection and required
  H0/H1 review. Runs of correctness tests, baselines and machine-code comparison
  require user-selected commands; they do not block implementation when unrequested.
  A measured improvement claim still needs matching before/after evidence.
  Source shape or an optimizer remark alone is insufficient for that claim.
- Assembly or disassembly confirms instruction selection and layout; it does
  not prove that the runtime caller selected the code or that latency improved.
- Ordinary wrapper results use the build host's native CPU target. Do not
  export a local Ryzen `-march=native` artifact or result as evidence for a
  different Linux production CPU. Separately authorized portable CI and server
  configurations declare their target CPU. Follow the compiler and target section of `docs/Agents/GlobalContracts.md`
  for the canonical pin and promotion boundaries.

Permission phrases:

- `изучи` / `посмотри` - read-only.
- `делай` - edits only.
- `делай и проверь` - propose exact relevant commands and wait for the user's
  selection under the command-package approval and task-scoped repeat rules
  in `DevelopmentWorkflow.md`.
- `all`, benchmarks, runtime, and live exchange checks require explicit active-task
  permission. `выполни/проверь план <id>` and a listed gate do not supply run
  consent; follow `DevelopmentWorkflow.md` for first approval and necessary
  repeats. Full builds, sanitizers, runtime/live/network, services
  and model-network calls retain their separate explicit authorization boundary.
  Permission persists across incidental status questions. Account and order actions
  always require their own explicit phrase.

An optimization remains a `candidate` until before/after evidence uses the same
build mode, workload, hardware, affinity, metrics mode, and sample definition.
Promoting the pinned compiler after its build, test, and assembly gates does not
by itself establish a performance improvement; production-like Linux
performance evidence is a later, separate gate.

## 7. Review gate

`Subagents.md` owns the independent review gates for final actual H0/H1 code
changes and substantive Capital computational changes, including offline.
`low_latency_engineer` checks computational/latency constraints; the relevant
specialist checks domain correctness.

An unchanged CLEAR surface needs no repeat. Bound follow-up review to concrete
finding repairs or material new changes. Docs, tests and cold code do not become
H0/H1 merely because their directory or subject includes hot code. Missing
unrequested runs are evidence limits, not independent veto findings.

Reviewers must return exact files/symbols, path classification, completed HFT
semantic checks, evidence level, and veto findings. Either reviewer may veto an
undefined or violated semantic contract. A veto must be repaired or resolved
with the user before the task is finalized.

## Diagnostic and temporary runtime scope

When two or more causal hypotheses remain, use the smallest authorized
counterexample that produces different predictions. A settled diagnosis does
not require another experiment. Do not substitute repeated smoke runs for the
missing acceptance evidence.

An authorized temporary runtime check owns the processes it starts. Record its
exact command and PID, and stop those owned processes when the check ends unless
the user asked to keep them running. When retained, report command/PID and stop
instructions. Never kill unrelated or pre-existing processes to clear a port or
make a check pass; handle that conflict within the authorized scope.
