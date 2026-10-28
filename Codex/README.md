# CXET Codex Toolbelt

Local Codex workflow helpers for this repository. The CXET toolbelt and MCP
surfaces are read-only; `PlanWorkflow.py` mutates only explicitly selected
plan/state artifacts and archive locations, while `SyncAgentConfig.py --apply`
updates the selected global configuration explicitly.

## Tools

- `CxetToolbelt.py sources` - lists static readiness source anchors.
- `CxetToolbelt.py readiness` - builds a static-only exchange/trader readiness trace.
- `CxetToolbelt.py hotpath` - maps a production hot-path review surface from
  local compile commands and emits unranked token candidates.
- `CxetContextIndex.py` - validates the compact context manifest, routes task
  hints, searches declared roots lazily, and postchecks changed paths.
- `CxetMcpServer.py` - stdio MCP wrapper exposing the static helpers and
  bounded context tools to Codex.
- `CxetDoctor.py` - read-only Codex, hook, MCP checkout, model, and revision
  diagnostics. It reports unavailable evidence instead of changing the setup.
- `tools/Ci/CodexCiGate.py` - GitHub Actions gate for Codex policy, context,
  skill, shell, and Python tool checks.
- `RunSkillEvals.py` - explicitly authorized manual evaluations through the
  installed, authenticated Codex CLI. Routine tests use a fake CLI only.
- `SyncAgentConfig.py` - explicitly checks or synchronizes the marked global
  instruction block; see Global instruction sync below.
- `PlanWorkflow.py` - current durable-plan state, dependency,
  ownership, evidence, rule-index, and archive management. It has no hooks,
  manifests, leases, receipts, or gate runner.
- `CheckCxetFamilyRootGraph.py` - fail-closed static proof that the CXET
  root owns one provider-first direct-source family composition, every product
  rejects standalone/sibling fallback, canonical aliases exist, and the family
  preset/wrapper select the same isolated test-enabled graph with stable
  CTest commands, scopes, and acceptance labels.
- `CheckCxetFamilyOwnership.py` - fail-closed static proof that canonical
  strategy, Parser-client, Trader, Vetron and Backtest targets have
  one compiled owner, source variables and `target_sources` cannot escape that
  owner, byte-identical compiled copies are rejected, and Trader/Vetron
  transitive closures contain no forbidden reverse, legacy, mutation, or
  terminal edge. It inventories the canonical safe roots
  `src/src/Contracts/{include,src}` and
  `apps/hft-parser/src/Clients/include`, validates their exact header/source
  closure, and independently rejects forbidden full-CXET/Parser-live targets
  from the MAY-reachable closure of read-only consumers.

The context, readiness, and hot-path helpers do not run builds, tests, Git,
live trading tools, local services, network calls, order placement, cancels, or
account fetches. `CxetDoctor.py` performs only bounded local Git/version reads
for its report.

`CodexCiGate.py` aggregates static Codex validators and Python tests, including
failures, timeouts, and zero-test discovery. The existing full-build and reuse
workflows expose independent optional `codex-ci` health jobs. Product reuse
retains mandatory policy, source/SHA, and workflow compatibility checks.
Health jobs use ordinary Bash and their own exact source checkout. With
`--report-dir build/codex-ci-report`, the gate writes `report.json`,
`report.md`, and bounded per-check logs. CI always attempts summary/artifact
publication, retains the small artifact for one day, and reports upload failures
separately. This is tooling evidence, not product readiness.

The context index is manifest-backed and lazy. Its first map response contains
owners, route documents, roots, anchors, and static checks; line excerpts are
returned only by an explicit scoped search. The manifest validator fails closed
on missing paths, unsafe paths, invalid scopes, and non-static check commands.
The obsolete `hotplans` scope has been removed. Search scans at most 20,000
directory entries and reads at most 1 MiB plus an oversize sentinel per file.
Skipped files, decoding/read errors, and exhausted budgets make
`search_complete=false`; a partial no-match is never a complete no-match.

`closure --scope` searches explicit retired symbols/paths within the selected
context. It groups source, build, CLI/recipes, documentation and test references,
including qualified C++ names. Complete text search is reference evidence only;
it does not prove callers, compilation or runtime behavior.

`CxetMcpServer.py --protocol-check` starts and reaps its own local candidate
subprocess, with a ten-second deadline and bounded stdout/stderr. It exercises
initialize, initialized, tools/list and tools/call with checkout identity checks.
Its observation is `subprocess_candidate`, separate from the active Codex server.
`CxetDoctor.py --observed-response FILE` accepts a saved complete tools/call result
and reports supplied response identity separately from configured identity. The
doctor cannot establish how or when that response was captured.

Readiness section status is based only on exchange-owned `Config.cpp` evidence.
`common_anchor_evidence` is shared context from headers/tools; it does not make a
section ready or present by itself.

The hot-path helper accepts `all`, `market`, `strategy`, `order`, `parser`,
`transport`, or `runtime`. It fails closed when the local production artifacts
are absent or profile-mismatched. Canonical paths are a review surface;
`compile_commands.json` proves translation units only, and token matches are
not violations, severity findings, or measured speedups.
The cache must name a canonical `CXET_BUILD_OWNER` and the wrapper's production
profile (`CXET_FAMILY_SOURCE_GRAPH=OFF` in the cache; Parser enables its effective
source graph internally). Public `compile.sh p` builds its owner; `all` runs local
tests. Optional capability/private-audit binaries are not promised by this recipe.

## CLI

```bash
python3 tools/Codex/CxetToolbelt.py sources --format json
python3 tools/Codex/CxetToolbelt.py readiness --exchange binance --market futures --format summary
python3 tools/Codex/CxetToolbelt.py hotpath --surface transport --format summary
python3 tools/Codex/CxetContextIndex.py validate
python3 tools/Codex/CxetContextIndex.py map --task-hint "WebSocket reconnect framing"
python3 tools/Codex/CxetContextIndex.py search --scope transport --query Ws --max-results 20
python3 tools/Codex/CxetContextIndex.py closure --scope transport --retired-symbol OldRoute --retired-path old/Route.cpp --format summary
python3 tools/Codex/CxetContextIndex.py postcheck \
  --changed-path src/src/Core/include/cxet/Network/Ws/Runtime/WsRuntime.hpp
python3 tools/Codex/CxetMcpServer.py --self-test --repo-root .
python3 tools/Codex/CxetMcpServer.py --protocol-check --repo-root . --format summary
python3 tools/Codex/CxetDoctor.py --active-model gpt-6.1-terra --format summary
python3 tools/Codex/CxetDoctor.py --observed-response saved-mcp-result.json --format summary
python3 -B tools/Codex/PlanWorkflow.py seal docs/agent-plans/active/<plan-id>
python3 -B tools/Codex/PlanWorkflow.py validate docs/agent-plans/active/<plan-id>
python3 -B tools/Codex/PlanWorkflow.py ready docs/agent-plans/active/<plan-id>
python3 -B tools/Codex/PlanWorkflow.py rules .
```

### Manual family architectural audits

These optional audits run only when the user explicitly requests a checker or
selects its exact command. Do not automatically add or recommend them in routine
check packages, or require them before a build. Ordinary verification requests,
build approval, and include/CMake changes do not select them. See
`docs/Agents/DevelopmentWorkflow.md` for the canonical run-selection policy.

Run a selected audit from the CXET root:

```bash
/usr/bin/python3 -I -S -B tools/Codex/CheckCxetFamilyRootGraph.py
/usr/bin/python3 -I -S -B tools/Codex/CheckCxetFamilyOwnership.py
```

### PlanWorkflow evidence and state

The current plan contract records independent evidence types: `static`, `schema`,
`build`, `targeted-test`, `runtime`, `browser`, `model`, `performance`, and `live`.
`static-only` remains a human report label. `requiredEvidence` is a non-empty
list; repeat `--required-evidence TYPE` when adding a task (default `static`).
Evidence has `types`, `summary`, and an ordered `commandResults` history. Each
result has the exact declared `command`, its `types`, integer `exitStatus`
(booleans are rejected), and `summary`.

Use repeatable `--evidence-type` on transitions. Each claimed non-static type
needs a matching successful latest result for a declared command. A verified
task additionally covers every required type and has latest exit status zero
for every declared command. Live proof does not imply build, test, performance
or browser proof. Failed attempts remain in the history; a later failure
invalidates an earlier pass. An integrated `done_unverified` task may retain
its closed finding. Verification automatically closes findings.

Readers and writers accept one exact current structure without an internal
version field or compatibility fingerprint. Malformed or incompatible fields
fail closed; there is no converter or migration command. Existing saved plans
and archives remain untouched. `planSha256` continues binding state to the exact
`plan.md` bytes. RuleIndex likewise validates its current fields and rule owners.

Every canonical mutator (`init`, `seal`, `add-task`, `add-finding`, `transition`,
`archive`) holds the same nonblocking exclusive POSIX `flock` on the plan
directory throughout its read/prepare/write work. There is no lock file, lease
or receipt. Busy or unavailable locking fails closed without waiting or retrying.
The directory fd retains ownership across archive rename; initialization creates
only the selected plan directory before acquiring it. Individual file writes
remain atomic. Direct external editors still require coordination; this lock
does not provide universal atomicity for multiple files or writers that ignore it.
The tool never runs recorded commands or grants permission to execute them.

On-demand operations are separate commands; nothing here installs a schedule:

```bash
python3 tools/Ci/FamilyCiStatus.py first-failure --snapshot saved-family.json --root-sha SHA --run-id ID --attempt N --format summary
python3 apps/vetron/scripts/StartupConsole.py --log-file /ABSOLUTE/PATH/startup.log --handoff-summary -- PROGRAM ARGUMENTS
tools/Ci/host/gha-prune-build-cache --dry-run --json
```

The CI digest is offline and validates the full family capture, exact run attempt,
jobs/steps and independent gates. Exit codes are 0 for complete success, 1 for
complete observed failure/cancellation and 2 for invalid/incomplete/unknown data.
It orders observed failures without claiming causality. The snapshot schema is
documented in `tools/Ci/FamilyCiStatus.py`.
Handoff describes only the launcher-owned process group and log lock.
Prune preview performs no cleanup or installation; projections exclude future
Git GC savings. Benchmark runs require explicit authorization.

## Repo-tracked skills

- Core skills live under `.agents/skills`: `cxet-context-routing`,
  `cxet-hot-path-audit`,
  `cxet-hot-parser-audit`, `cxet-hot-transport-safety`, `cxet-workflow`,
  `cxet-audit-plan`, `cxet-exchange-readiness`, and `cxet-runtime-contract`.
- Trader: runtime ownership and session boundaries under
  `apps/trader/AGENTS.md` and `apps/trader/docs/ParserSessionBoundary.md`.

Validate the canonical repository skill root:

```bash
bash tools/Codex/InstallSkills.sh
```

The validator does not copy or overwrite skills.

## MCP config

The checked-in `.codex/config.toml` currently enables `cxet_local` and
Serena, with host-specific absolute checkout and executable paths. Those paths
identify the configured host and must be reviewed when the checkout moves; they
are not portable discovery. `tools/Codex/CxetLocal.config.toml` is a separate
example fragment with `cxet_local` disabled, not the active project setting.

Starting an enabled server executes its configured program, including
checkout-controlled Python, before identity diagnostics or tool approvals.
Review the configured revision and imports; directory trust alone does not
approve later revisions. Configuration is not evidence of active server
identity or runtime trust. Use `/mcp` to inspect an active session.
The server uses MCP stdio framing with one JSON-RPC object per line.
Frames are limited to 1 MiB. Invalid frames/requests produce bounded errors
and the next valid frame remains usable. Notifications have no response;
`ping` is supported. Canonical limits bound the complete serialized **tool
result** to 6 KiB for maps and 8 KiB otherwise, including text, both identity
records and `structuredContent`; the JSON-RPC transport envelope is separate.
Oversized results remain valid JSON with `output_truncated=true` and
`output_complete=false`. Invalid limit types or values fail closed.
Every tool result exposes the served root, process cwd, script path, and an
`identity_status`; the legacy identity field remains available, and the same
data is also returned through MCP `structuredContent`. A mismatch is visible
in the text result as a warning and does not block a read-only call.
`CxetDoctor.py` reports configuration field provenance and a derived checkout
candidate separately from observed server identity. Static config does not
establish Codex merge/trust behavior or the active backend. Its hook report is
configuration-only: a saved hook record or hash does not prove current trust;
use `/hooks` for the Codex trust decision.
For a non-trivial task, call `cxet_context_map` first. Within the selected scope,
use bounded text search, covered Serena symbol navigation or `cxet_context_search`
as appropriate; do not repeat the same query across tools without a new reason.
If selected by the user, call `cxet_context_postcheck` once after the final
changed-path set. The context
tools remain static-only and only suggest narrow checks; they do not execute
tests or builds.

## Manual model evaluations

A separate cascade mode lists the isolated `atomic-cascade` scenario without
model calls:

```bash
python3 -B tools/Codex/RunSkillEvals.py --cascade
```

Only with explicit task-scoped permission for model calls, run the ephemeral
CLI-only mode:

```bash
python3 -B tools/Codex/RunSkillEvals.py --cascade --run --timeout-seconds 900
```

This mode records observed events but cannot report `passed`: missing required
native evidence produces `incomplete`; observed violations or execution errors
produce `failed` or `error`. A separate native-trace adapter supports acceptance
only when it can observe all required evidence:

```bash
python3 -B tools/Codex/RunSkillEvals.py --cascade --run --native-trace --timeout-seconds 900
```

This evaluates the preferred primary model and effort by default. To select a
different coordinator for a separately authorized run, pass both
`--primary-model MODEL` and `--primary-effort EFFORT`; the evaluation checks
the actual root against that requested pair. Model availability and supported
efforts remain the client's responsibility.

Native trace disables ephemeral mode, so normal session journals persist in the
Codex home. The adapter discovers the owned run's root and descendant logs using
bounded first-line metadata and copies matching traces into the run artifacts;
it uses observed `turn_context` model/effort and completed actual tool sends,
not self-reports. Unsupported or missing native formats yield `incomplete`.
The order of tool calls and acknowledgements does not itself prove that the
receiver processed or understood the message.
Processing checks its deadline cooperatively; a single filesystem operation or
bounded parse cannot be interrupted by that check, and a partial raw artifact
may remain if collection stops.
The fixture explicitly registers its two copied Sol roles through CLI config
overrides and starts children without copying parent history. Mixed-session
journals are retained but not attributed to the child as its own execution.
The scenario requires research to return before design is spawned, forwards the
observed research and design summaries through explicit messages, and gives each
worker a separate structured specification. These checks concern observable
messages; they do not establish what a recipient understood.
Synthetic user clarification never proves real UI messaging. A real CLI 0.164.0
run exercised seven sessions with the requested models and efforts, observed
the `researcher_sol` and `planner_sol` roles, and passed the three fixture tests.
Its final assessment was `incomplete` with no observed failures. Encrypted
message arguments and JavaScript tool wrappers leave protocol and
action-attribution evidence incomplete; that run
does not establish full acceptance. Unavailable evidence is not proof of a
protocol ordering violation. The adapter can separately record strictly bound
structured command and file-change observations from an `exec` call; these do
not prove that arbitrary JavaScript had no other effects or satisfy the protocol
gates. Path and symlink checks describe the filesystem when the trace is
collected, not necessarily when an earlier action ran. Named role loading must
also be observed, rather than inferred from reading a role file.

Both modes use a temporary fixture outside the repository, preserve CLI journal
and file snapshots in `build/skill-evals/cascade-run-*`, and set CLI concurrency
to four with a process-group timeout. The fixture and CLI sandbox do not ensure
complete read isolation or enforce arbitrary Python syscalls; imported unittest
code may act without observable events. The environment excludes incidental token
variables and preserves existing standard proxy settings, while the CLI uses its
existing authentication. Proxy values are not added to invocation metadata;
the CLI's retained raw diagnostic output may contain sensitive details. Terminating the
original process group cannot guarantee stopping detached descendants. Limits on
total descendants (eight) and commands are detected through observable events,
not enforced before actions or by a hard shell whitelist. Detected forbidden
attempts remain violations. This mode preserves the six original fixtures.


For a separately user-selected manual UI smoke check, start a new session
with newly loaded roles, record its actually selected model and effort, and use
only an isolated fixture. A Sol/high
researcher finds deliberately unspecified boolean handling and sends its
question only to the root; the root asks the user once through the actual
question UI. Dependent editing waits while an unrelated read continues. Relay
the user's answer root → planner/branch → worker without asking again. Retain
the exact owned root/child IDs and observed UI answer. Do not treat synthetic
CLI clarification as UI proof; make no unrelated project edits or checks.

`SkillEvals.yaml` contains six isolated permission/routing scenarios. Listing
them performs no model calls:

```bash
python3 tools/Codex/RunSkillEvals.py
```

Only after explicit task-scoped permission for model calls:

```bash
python3 tools/Codex/RunSkillEvals.py --run --root .
```

The runner uses the installed authenticated CLI, GPT-6.1 Sol/high, standard
tier, ephemeral sessions, and temporary fixtures inside a fresh
`build/skill-evals/run-*` report directory. It needs POSIX (Linux/WSL), creates
no Git repository, requests no API key, copies no credentials, and ignores
user configuration. External MCP, web search, agent network access and nested
agents are excluded from these fixtures. One pass runs each selected scenario
once, with a maximum CLI deadline of 300 seconds including stdin and output
capture; `--scenario ID` selects a subset without retries.

Reports retain bounded actual `events.jsonl`, stderr, structured final output,
before/after file hashes and assertion results. Model declarations alone do
not prove a result. Required inspections need successful completed read events
with file/context output; plan creation uses the canonical plan validator.
Required-path binding accepts explicit `cat` operands (optionally `--`),
directly or through one `bash`/`sh -c`/`-lc` wrapper. Comments and quoted reader
text are not inspection evidence; comment-bearing commands are unsupported.
Other readers, compound shell commands,
expansions and unknown options leave inspection `incomplete`; the checker
does not interpret arbitrary shell or Python. CLI logs remain trusted input,
and matching output does not attest a full-file read or model quality.
Forbidden attempts count even when denied. Unknown, malformed, unfinished or
missing events give `incomplete`; CLI/auth/timeout failures give `error`, and
observed assertion violations give `failed`. All are nonzero overall. Command
checks are pattern-based; this evaluates the listed assertions rather than
proving arbitrary shell behavior. Real CLI event compatibility and model
quality remain untested until the authorized manual run.

Routine `CodexCiGate.py` uses fake CLI fixtures only, including blocked stdin,
inherited open pipes, missing terminal events and forbidden attempts.

## Global instruction sync and hooks

`GlobalAgentInstructions.md` is the repository source for the portable global
instruction block. `SyncAgentConfig.py` synchronizes that block without changing
existing global configuration settings. A fresh configuration without a model,
effort, profile or provider selection gets the preferred Sol model only. Project
subagent routing stays in the project config and role files. Existing user
settings, unrelated instructions and hooks are preserved. Check or apply explicitly:

```sh
python3 tools/Codex/SyncAgentConfig.py --check
python3 tools/Codex/SyncAgentConfig.py --apply
```

Optional `--root` and `--codex-home` select paths; `--check` returns 1 for drift
and 2 for refusal. Apply needs task authorization and retains its locking, backup
and conflict checks.
A check is evidence of file contents, not of an active session loading them.

The current host's `~/.codex/hooks.json` configures Orca's optional adapter and
`agent-workflow` hooks for SessionStart, UserPromptSubmit and PostToolUse;
Orca also has hooks for additional lifecycle events. Configuration does not
prove trust or delivery: inspect `/hooks` in the active session. The former
`workflow_reminder.py` claim is stale. `docs/Agents/PlanWorkflow.md` owns native
Goal handoff after authorized plan execution starts; hooks grant no authority.

## Global automatic learning

The user's portable personal workflow is owned by
`~/.agents/skills/agent-workflow/SKILL.md`; `self-improvement/v1` and the old
`codex-self-improvement` script paths remain compatibility entries. Any agent
can use the standard-library Python CLI directly; the current automatic
adapter is Codex. Bounded lessons remain under `~/.codex/self-improvement`
without migration; native agent memory and trust are not edited. Natural
management requests map to `scripts/manage.py status`, `history`, `enable`,
`disable` and `rollback --id`. See the skill and command help for the exact
interfaces and scope.

Substantial tasks can keep independent, revision-checked cards under
`~/.local/state/agent-workflow/tasks/`. The primary maintains agreed decisions;
workers receive relevant capsules. `task get/put/close/handoff` manage an
explicit task ID; `context --task-id ... --project ... --query ...` combines
its active subject with current steering to select lessons. Cards never imply
permission, live readiness or ownership of another chat. They are not written
in Plan/read-only mode. No project-wide dispatcher or transcript polling runs.

Separate `SessionStart`, `UserPromptSubmit` and `PostToolUse` learning hooks
read bounded data and emit advisory context without writes, child processes,
model calls or turn continuation. They use `python3 -B` to prevent bytecode
cache writes. Their new definitions require ordinary `/hooks` trust. A fresh
chat must demonstrate loading; successful offline tests do not prove that.
The current Bash callback may contain stdout without an exit status. Its
empty output cannot prove failure; the agent evaluates the full tool result
in the task context instead. No transcript polling or inferred failure is used.
Windows DPAPI protects the separate sudo credential; the helper's `check`
tests authentication and `install` accepts validated apt package names only.

## Pending instant_interrupt compatibility check

The project explicitly keeps `features.instant_interrupt=false`. After
separate authorization, open Codex in an isolated scratch fixture with
`--enable instant_interrupt`, GPT-6.1 Terra and a read-only sandbox. Check steering
once during response generation and once during an explicitly authorized
20-second local wait command. Confirm the new instruction is received and
subsequent actions follow it; inspect the fixture for unintended changes.
Enable the project setting only after both checks pass. CLI compatibility,
interactive steering and the feature's runtime behavior are pending; no global
configuration is changed.
