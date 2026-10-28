# Global CXET contracts

Read this file for public-contract, dependency, ownership, structural, bounded-
storage or compiler/target changes. These are repository-wide constraints;
the nearest nested `AGENTS.md` may only make them stricter.

## One current contract

Project-owned APIs, contracts, formats and artifacts have one current form:
no versioned names (`V<number>` included), version fields, compatibility
fingerprints, legacy readers or format migrations. Update producers, consumers,
tools and checks together. Preserve external protocol/dependency versions,
data generations and integrity/provenance hashes; reject structurally
incompatible input without modifying saved data.

## Ownership and dependency direction

- `CXET` is the low-latency C++23 exchange data/API normalizer.
  `src/src/Core/**` and `src/src/Contracts/**` are core and hot/sensitive
  unless proven otherwise. Public headers live only below
  `src/src/{Core,Contracts}/include/cxet/**`; `cxet_lib` private implementation
  headers live below `src/src/Core/src/**` and
  `src/src/Core/src/private/**`. `src/src/CMakeLists.txt` and
  `src/src/cmake/Sources/**` remain build metadata. `apps/**` are product layers
  that consume public CXET targets.
- The root CXET checkout is the only canonical family build graph. It composes
  sibling product repositories with direct `add_subdirectory` and
  `target_link_libraries` edges; repository separation never authorizes copied
  SDKs, imported sibling binaries, nested source copies, or network fallback.
- `trading-core` owns deterministic strategy, execution, order lifecycle,
  route/control admission and quotas consumed by Trader and Backtest.
- `apps/trading-core/capital` owns basic accounting, fees/PnL, sizing, financial
  risk and capital reservations through `capital::finance`. Execution and
  strategy consume that provider; finance consumes only normalized CXET and
  the leaf `trading_core::contracts` value/numeric headers, never execution or
  strategy providers. One financial fact has one store; adapters qualify native
  identities and events before passing them to Capital.
  Production Capital APIs expose reusable financial primitives. Strategies
  select and compose those primitives; strategy-specific signals, episode
  timing and native admission contracts stay with their strategy/runtime owner.
- `capital::planning` contains experimental market/DP mathematics. It is
  registered only for selected trading-core local tests and is not a
  production dependency. Capital has no execution simulator. No smart
  allocation/entry/exit policy is enabled by the basic finance migration.
  Parser retains native sessions, credentials and terminal exchange I/O. CXET
  must not depend on trading-core or Capital. Computational constraints and
  reviews follow `HotPathFastLane.md` and `Subagents.md`.
- Strategy categories `hft-trader` and `trader` organize the canonical source
  tree only. A runtime may execute any category when it supplies the
  descriptor's declared inputs and execution capabilities. trading-core must
  not branch on the calling product or maintain different trading semantics
  for different consumers; native sessions and scheduling remain runtime-owned.
- Do not move app-only policy into core unless the user explicitly asks to
  promote a stable reusable API. Do not add a public API, runtime concept,
  exchange endpoint, route, connection, or strategy/risk knob without an
  explicit request. Ask how a genuinely new concept should behave.
- CXET exchange-owned code owns public-market hosts/paths, wire format,
  request/auth/control grammar, exact payload identity, bounded native decoding,
  and runtime payload normalization. Keep each exchange implementation atomic.
- Share only bounded, data-independent mechanics. Endpoints, fields, parser
  profiles, routing, auth, quirks, and fallback policy remain exchange-owned.
- `apps/hft-parser` owns its PublicMarket V2 registry, route selection,
  operational limits, raw data and producer-owned clients. In the Parser-backed
  Trader composition, one shared Parser owns all market, private/user and order
  sessions through CXET, their credentials/native account identities, network
  lifecycle, reconnect/backpressure and terminal exchange I/O. It must not
  duplicate exchange wire or add a parser fallback. Parser does not own Trader
  strategy, economic risk/admission or canonical current-run orders.
- `apps/trader` owns normalized input provenance, trading-core invocation,
  native admission enforcement and canonical current-run orders. Deterministic
  strategy policy, valuation, financial calculations and episode aggregation
  belong to trading-core (basic finance remains in Capital); Trader owns
  publication, bounded output transport and presentation. The selected
  composition is one `traderd` process with a cold-bound, producer-owned
  `hft_parser::session_client` `SessionBinding`; producer storage outlives the
  client and both execute on the same owner thread. Trader never owns native
  credentials/account identity or opens native exchange sessions.
- Before one direct Parser submission, Trader checks readiness/risk/quota,
  exact account/product/generations, ID availability and bounded capacity,
  installs canonical intent and reserves correlation. Parser validates exact
  native route and command/feedback capacity before terminal I/O. Local
  acceptance, terminal disposition and venue ACK/fill are separate evidence;
  partial or unknown outcomes never authorize automatic resend.
- One shared Parser isolates at most eight arbitrary nonzero account profile
  IDs, including native identity, product coverage, storage, generations,
  capacity and fault state. Current-run order/correlation authority stays
  account-local. Trading journals, journal-before-submit/replay authority,
  session IPC and command receipts are removed from this composition. The cold
  ID range store remains separate persistence and supplies no journal authority.
- Earlier-run/foreign orders and historical fills form an authoritative external
  account baseline; they are not adopted or treated as strategy executions.
  Only exact current-run identities enrich managed orders. Explicit application
  Stop, including SIGINT/SIGTERM, first quiesces all execution owners, then uses
  separately certified native authority to cancel every order on the exact
  account, including foreign/protective orders. It closes only proved current-run
  managed inventory and preserves foreign positions. Unknown outcomes, missing
  complete cuts/capabilities or the deadline retain ControlOnly with native
  private/ACK progress and no ordinary Place/Replace or unknown resend. Native
  sessions retire only after confirmed completion; resource retirement itself
  never submits trading actions. The Trader console's third explicit Ctrl+C
  instead requests forced process termination of that launch's owned groups.
  It retains runtime and returns 137 without certifying cancellation, flatness
  or Stop Complete; it never triggers an automatic restart or unknown resend.
  StrategyStop remains a separate scoped command.
- Diagnostic's external guardian observes bounded cold runtime projections and
  performs manual SSH status/Stop/Start. Its disconnect, shutdown or storage
  failure never stops trading runtimes. Deterministic Stop semantics belong to
  trading-core; native identity and exchange I/O stay with their existing owners.
  Risk calculations/admission stay local to execution; no network dependency is
  introduced into the hot path. Vetron may consume this projection later.
- Missing Parser/native authority refuses Full admission without downgrade,
  fabricated readiness or fallback native transport. The current implementation
  limits and evidence live in `apps/trader/docs/ParserSessionBoundary.md`, not in
  duplicated status claims here. Library/contract existence does not establish
  build, runtime or live readiness. This ownership rule does not expand the
  explicitly authorized exchange/product live scope.
- The main trading stack is CXETCPP + hft-parser + Trader + trading-core.
  HFT Trader is retired from product composition. Its capability inventory is
  preserved in `docs/Architecture/HftTraderCapabilities.md`; absent adapters
  remain refused until separately implemented. Shared strategy categories stay.
- `apps/vetron` owns browser/gateway presentation and directly compiles
  Parser-owned and Trader-owned clients. ReadOnly consumes Parser public data
  and a market-observe Trader projection through a closure that physically
  excludes private/order/control transport. Full may add only the typed
  localhost operator-control client. Vetron does not become a second
  public-market, private-session, lifecycle, risk or order-state owner.
- Current recorder sessions live on Windows `D:`. In WSL, inspect
  `/mnt/d/recordings` before treating repo-local recorder paths as truth.
- One semantic rule has one canonical owner. Remove accidental forwarding and
  copy-pasted variants; keep deliberate venue differences explicit.

## Native primitives and bounded storage

- `simdjson` and Boost are forbidden in core, hft-parser, and Trader.
  Use project-native JSON, transport, queue, and parsing primitives.
- Project-owned borrowed text is `cxet::StringView`. `std::string` is cold owning
  storage, not a borrowed-view substitute. Direct libc string/memory primitives
  belong only in the project primitive backend and explicit oracle tests.
- H0/H1 text and sequences use fixed-capacity storage or `std::array`.
  `absl::InlinedVector` requires a proven small bound and acceptable owner/stack
  growth. Abseil is not a blanket replacement for standard containers.
- Prefer Abseil hash/B-tree containers for suitable cold indexes and
  `std::vector` for contiguous cold owning sequences unless evidence supports a
  different representation.
- Treat every dynamically growing sequence as a design decision. State owner,
  maximum growth, allocation phase, and terminal overflow behavior.
- Structural refactors must not increase H0/H1 object/capacity layouts,
  allocation count, or stack-frame use. Preserve touched `sizeof`/`alignof`
  contracts and the `-Wframe-larger-than=32768` gate.

## Compiler and target contract

- Diagnostic binary deployment is an explicit isolated exception to the ordinary
  wrapper optimization profile: the canonical root helper selects
  `--deployment-profile diagnostic`, pinned LLVM, portable Release `-O2`,
  product-only, HFT features off and LTO off (or explicitly full). It uses
  `build/deploy/diagnostic/{off,full}` with canonical exchange suffixes, the same
  build lock and containment, and never changes the ordinary active build.
  Local and server deployment hosts must be Ubuntu 24.04 x86_64. Diagnostic
  delivery installs only the completed runtime release and dependencies; it
  never sends a toolchain or compiles/tests on the server. The older
  `system-diagnostic` build profile does not provide deploy support for 22.04.

- The root direct-source graph owns one exact compiler pin for CXET and every
  composed sibling. `cmake/CxetToolchain.cmake` is the canonical selector; apps
  must not introduce their own compiler revision, staged toolchain, or `PATH`
  fallback.
- Explicit user-selected exception: cold Diagnostic on Ubuntu 22.04 may use
  the canonical `system-diagnostic` profile: absolute package Clang/LLVM/LLD 14
  paths and GCC 12 headers/runtime, `-O1`, LTO OFF. Only the Diagnostic product
  and its CXETCPP/trading-core/diagnostic release offline checks may select it.
  Its product and test trees are isolated under `build/system-diagnostic` and
  `build/offline-checks/system-diagnostic`. The Diagnostic wrapper may map its
  product namespace below its actually verified owned storage's `product/`;
  a path spelling alone is never storage ownership evidence. It never impersonates a pinned LLVM
  installation or changes the compiler used by Trader, hot products or benchmarks.
  Package installation is explicit deployment preparation; missing/incompatible
  tools fail closed without bootstrap or compiler fallback.
- The family default is the official LLVM **23.1.3** Linux x86_64 binary
  release, selected on 2026-10-20. Version, immutable release URL and archive
  SHA256 live only in `cmake/CxetToolchain.cmake`. Preparation metadata uses
  one current structure and records the verified binary distribution, never a
  source-build or patch provenance claim. Old source-build stamps are refused.
  This selection alone proves neither family compatibility nor performance.
- Explicitly prepare the complete compiler with
  `python3 tools/Toolchain/BootstrapLlvm.py`. It downloads the pinned official
  archive, verifies SHA256, checks bounded paths/links, tools, resource headers
  and compiler-rt, then publishes `build/toolchains/llvm-23.1.3` atomically.
  No LLVM compilation, sudo or system compiler-link changes are involved.
  Distribution and deploy trees are bounded at 16 GiB total, 1 GiB per regular
  file and 250,000 entries; extraction refuses unsafe paths, foreign/stale
  destinations and overflow. Downloads are bounded at 4 GiB. Existing compiler
  artifacts and logs remain intact.
- Selected deploy operations for pinned profiles deliver a compact subset of
  the prepared official local release over rsync/SSH; no server LLVM download,
  compiler rebuild or binary rewriting occurs. The complete local installation
  remains intact. Deployment owns the tool/resource/internal ELF dependency
  closure, bounded inventory and content-checked archive. Preserve
  original-release provenance and the GNU libstdc++ contract.
  A same-identity full server installation may be compacted only from its saved,
  matching owned inventory to an unchanged subset, under deployment/compile locks
  while runtime is idle. Validate the new tree, atomically exchange directories
  and journal the transition for explicit recovery. Unknown/corrupt installations
  fail closed. Retain the old tree until the selected operation succeeds; then
  remove only its reviewed survivors and a matching official archive cache.
  Cleanup never changes the current compiler and may follow successful Diagnostic
  startup under its shared deployment lease. Partial/foreign caches and other
  versions remain untouched. Ordinary wrappers never download or prepare LLVM.
- Ordinary root/app wrappers, offline checks and CI require the already
  prepared release. Missing/incompatible tools fail closed with the preparation
  command; they never download, build LLVM or fall back to PATH. CI admits an
  operator-provisioned immutable installation. Native Clang/clang++, assembler,
  LLD, archivers and IR/disassembly utilities use one release prefix. Keep the
  existing Linux libstdc++ contract, CPU options, optimization and LTO policy.
  Caches from another compiler must use a fresh directory, never silently
  reconfigure or reuse old objects. Binary delivery retains its bounded
  inventory, content checks and atomic no-replace installation.
- Public root and owner wrappers delegate to one canonical root helper and
  retain their own owner targets in the direct-source graph.
  The default builds this owner's product incrementally with pinned Clang, GNU
  Make, Release `-O3`, native CPU targeting and LTO OFF. `portable` disables CPU
  targeting. Fresh foreign providers are reused silently; missing or stale foreign
  modules are listed in one combined prompt before rebuilding them. Decline or EOF
  cancels; a noninteractive invocation with stale providers exits with an explanatory
  error. `--force` builds the selected product and necessary closure incrementally
  with FULL LTO, without cleaning or internal dependency prompts; ThinLTO is
  never selected. That wrapper behavior does not grant run permission; obtain
  per-invocation consent under `DevelopmentWorkflow.md` before launch.
  `--accept-dependency-updates` explicitly accepts that same bounded provider
  closure without enabling `--force` or changing the optimization/LTO profile.

  `all` builds and runs this owner's registered tests and needed dependencies.
  For CXETCPP, hft-parser, trading-core and trader it then builds the
  owner's diagnostic benchmark executables without measuring them. Other owners
  keep their test-only stage. `--force all` first builds the optimized product.
  Other owners' tests and benchmarks are not selected. An empty test registry
  does not establish passing test proof. Separate benchmark commands and the
  manual workflow are documented in `tools/Benchmarks/README.md`.

  Optimized trees use `build` (native) or `build/modes/portable`; development trees
  use `build/modes/dev-native` or `build/modes/dev-portable`. `CXET_BUILD_DIR` is the
  exact caller-supplied path; an incompatible existing profile is rejected. Only a
  successful product build updates `build/.compile-active/<owner>.json`; default
  launchers resolve that selected tree. Failed, UI-only and test-only runs do not
  switch it. Project-owned libraries remain static `.a`; `p` and explicit
  positive `-j N` follow the CPU and memory selection policy owned by
  `HotPathFastLane.md`. See `--help` for supported options.
  Vetron `ui` selects frontend/browser WASM only, without native preparation,
  and rejects `all` or `--force`. Compiler/product overrides and standalone
  diagnostic CMake profiles remain outside this interface and require their
  own authorization. Unattended production CI recipes use `--force portable`
  and preserve their exact `CXET_BUILD_DIR` artifact paths.
- An explicitly authorized isolated compiler or source-code A/B keeps the
  baseline outside the public compile wrappers. Both
  sides use the same source state, standard library, linker, build mode, CPU
  target flags, dependency graph, workload, hardware, and measurement policy;
  only the declared variable may differ.
- A source optimization needs affected correctness tests, review, and
  generated-machine-code evidence from the actual compiled translation unit.
  Assembly or disassembly proves code generation only; it does not prove that
  the live caller selected that code or that runtime latency improved.
- The ordinary wrapper's host-native artifact is valid only for the matching,
  explicitly identified deployment CPU class. A Ryzen-native artifact or its
  performance result is not evidence for an AWS Intel or AMD target. Any
  portable wrapper produces a separate artifact tree without host-native
  flags; a separately authorized server configuration must declare its CPU target.
- Lifetime diagnostics remain a separate isolated safety profile. Their
  warnings are neither a compiler-default promotion gate nor performance
  evidence. The compiler and target rules above define the operational boundary.

## Change quality

- Use `DevelopmentWorkflow.md` for behavior changes, useful regression tests,
  user-selected checks and separate implementation/CI/runtime evidence.
- Close a touched migration through actual callers, registrations, source lists,
  generated inputs, CLI consumers and operational recipes. Search old symbols
  and paths only within that affected closure; classify historical evidence
  separately. Removing a provider without updating its consumers is incomplete.
- When competing diagnostic hypotheses remain, choose a bounded discriminating
  counterexample that separates them before fixing the symptom. Do not turn a
  settled diagnosis into a compulsory experiment or add undeclared checks.

- Treat latency behavior as correctness and use `HotPathFastLane.md` for any
  non-trivial production parser, transport, runtime, strategy, readiness, or
  latency task.
- Match the owning module's naming, formatting, error handling and file layout.
  Use a nearby cohesive implementation as the style reference; keep unrelated
  code out of formatting and naming cleanup.
- Prefer purpose-named functions and cohesive ownership. Split when independent
  responsibilities, mixed hot/cold ownership, deep nesting, or unsafe review
  boundaries demand it; do not split cohesive logic by line count alone.
- Standalone `apps/trading-core/src/Strategy/include/strategy/*/Strategy.hpp` may stay single-file when
  the strategy is deliberately isolated and the user confirmed that format.
- Keep generated, third-party, and format-frozen code out of structural cleanup
  unless the task targets it explicitly.
- Prefer a correct root-cause solution over a local workaround. If fixing or
  measuring exposes multiple valid semantic policies, stop and ask the user.
- Reuse an appropriate existing helper, type or interface before adding another.
  Share a concrete common responsibility, not merely similar syntax; keep
  genuinely strategy-specific behavior local.
- Treat `[[nodiscard]]`, `cxet::bytescan::hftLikely`, and
  `cxet::bytescan::hftUnlikely` as semantic/performance tools, not decoration.
- Use `DevelopmentWorkflow.md` to classify selected checks by their effects.
  Lightweight local workflow checks run directly with temporary fixtures;
  native build/test checks retain the owning project's prepared private cache,
  compiler, contained runner, canonical build lock and one build job unless
  a positive job count was explicitly selected.
