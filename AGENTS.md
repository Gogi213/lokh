# Agent rules — CXET

Respond in the user's language. Lead non-trivial reports with `be0h check:`
and a concrete result/proposal. Solve the root cause; preserve unrelated work.

## Context routing

Read inherited and nearest nested `AGENTS.md` for the selected scope. Read
unchanged rules once per active context; reload only for changes or missing
handoff details. Load details on the following triggers, not as a startup bundle.
`docs/Agents/RuleIndex.json` is the machine-readable map.

| Trigger | Canonical owner |
|---|---|
| Contract, dependency, ownership, structure, storage or compiler/target | `docs/Agents/GlobalContracts.md` |
| Uncertain ownership or selecting expertise | `docs/Agents/RoleRouter.md` |
| Behavior change, bug fix, refactor, test or check selection | `docs/Agents/DevelopmentWorkflow.md` |
| Hot/parser/transport/readiness/market/strategy/order path; Capital computation | `docs/Agents/HotPathFastLane.md` |
| Plan mode, agreed plan execution, durable plan or native Goal | `docs/Agents/PlanWorkflow.md` |
| Delegation, code-simplicity participation, mandatory review or model routing | `docs/Agents/Subagents.md` |
| Non-trivial report/review | `docs/Agents/ReportFormat.md` |
| Selecting a Superpowers procedure | `docs/Agents/Superpowers.md` |
| AWS/secrets | `docs/Agents/AwsWorkflow.md` and relevant AWS skill |

For non-trivial multi-file context selection, use `cxet-context-routing`.
A route selects relevant documents and expertise, not all matching roles or
threads. Subject-specific checklists live in `docs/Agents/Roles/`.
Do not automatically load a document merely because another one links to it.

## Code simplicity

Every agent looks for an existing suitable implementation, its owner and actual
callers before adding a new helper, type, layer or parallel implementation.
Prefer the smallest complete design that makes intent clear, removes unnecessary
duplication and boilerplate, and keeps responsibilities cohesive. Extract, inline,
split or combine code when that improves understanding; line or file count alone
is not the goal. Keep meaningful differences and necessary correctness, lifecycle,
ownership and hot-path constraints. Follow the simplicity specialist's task
participation and owner discussion rules in `docs/Agents/Subagents.md`.

## Authority and completion

- Active-task permission persists until completion/cancellation/scope change;
  status does not revoke it. Finish independent authorized work. Skills/plans/
  Goals/hooks grant no authority. Follow instruction priority; explain a blocking
  rule with its exact link/quote.
- Study/review/diagnosis/status are read-only. `составь план` permits only selected
  plan artifacts outside Plan mode. `делай`/`implement`/`выполни план` permit
  requested edits and useful tests, not runs. `проверь план`/`делай и проверь`
  means static inspection, authorized edits, then separate exact check selection.
- `DevelopmentWorkflow.md` owns first approval of exact check packages and
  justified repeats until task completion. New commands/targets/profiles or
  increased jobs/resources need new selection.
  Full builds/sanitizers/benchmarks/services/browser/runtime/live/network/model
  actions retain separate selection. Every Git write, formatter rewrite, GitHub
  mutation through any client, and account/order action needs explicit permission.
- Local read-only Git is allowed throughout the family, including Recorder.
  `default.rules` never grants authorization or bypasses required prompts;
  rebase/reset/amend/history rewrite/force-push remain prompt-gated.
- Implement at the canonical owner; close affected callers/registrations/source
  lists/generated inputs/CLI/recipes. Preserve tests; useful regression, optional
  test-first. Finish edits before optional runs; report unrun evidence `static-only`.
- Resolve routine details; ask only about material behavior/ownership/security/
  recovery/API/live decisions. No ordinary durable artifacts or extra ceremony.
  Worker reports are claims. Independent chat ownership follows `Subagents.md`.
  Repository-owned assignment/integration rules live there; the compact result
  contract is in `docs/Agents/ReportFormat.md` under "Subagent results".
  Neither requires personal notes.

## Plans, agents and runs

- Risk S: trivial, no ceremony. M: in-chat plan. H: decision-complete in-chat plan
  before H0/H1, live/order/session, serialized-contract, recovery/security changes.
  Persist a simple plan only when requested or cross-session continuation is needed.
- For a Risk H or non-trivial full-cascade plan, use the fresh-context plan
  review in `docs/Agents/Subagents.md`; an unavailable review is reported, not simulated.
- Automatically create a native Goal for explicitly authorized execution of an agreed
  non-trivial plan. Plan mode does not create or mutate a Goal. Follow
  `PlanWorkflow.md` for get_goal, reuse, achieved-old-Goal completion/new-Goal
  handoff and truthful completion. A new plan never proves unfinished work complete.
- Codex model routing is canonical in `Subagents.md`: Sol/high is the primary
  default preference; the user’s explicit model or effort selection takes
  precedence. Apply common workflow with any selected primary and in other agent
  systems using available capabilities. Confirm actual model and effort;
  instruction text does not switch a session.
- Delegate useful independent results under higher-level controls. The root
  approves proposed subtrees internally, integrates shared files and routes
  material questions to the user. For a non-trivial full cascade the user agrees
  the ready solution before first implementation; an already agreed plan and
  active execution permission need no repeated approval. Small direct tasks need
  no full cascade. Use non-overlapping ownership and near-patch task capsules;
  `Subagents.md` owns the details and mandatory independent reviews.
- For substantive code tasks, the coordinator delegates to native
  `code_simplicity_engineer` at the start and after the relevant final specialist
  reviews. Tiny mechanical tasks remain lightweight; unavailable participation
  is reported without blocking other work.
- Actual final H0/H1 code changes require two independent native read-only reviews:
  `low_latency_engineer` plus the relevant specialist. Substantive Capital computation
  requires `strategy_quant` + `low_latency_engineer` already offline. Follow
  `Subagents.md`; docs/test-only/mechanical changes do not themselves trigger this pair.
- Lightweight local workflow checks and utility tests run directly without the
  CXET build lock. Native build checks use the owner's prepared private offline
  tree, exact compiler/targets, contained runner and canonical build lock;
  default one job. Busy native lock/missing containment is BLOCKED. Classify by
  actual effects under `DevelopmentWorkflow.md`. Never bypass native boundaries,
  reconfigure active product selection, clean/bootstrap/restart services or
  escalate to repair a failure.
  Preserve logs; inspect prior process/cache/log after interruption; never kill
  another owner's processes. `DevelopmentWorkflow.md` owns the full execution rules.
- Keep reads and displayed output compact: default to 40 lines / 8 KiB,
  mark truncation and reread the needed range. Preserve full check logs and
  exit status; `DevelopmentWorkflow.md` owns output and evidence handling.
- Superpowers is selective optional tooling, without mandatory startup/bootstrap,
  extra stages or authority. Heavy procedures such as TDD need explicit request.
  Global `agent-workflow` owns portable task cards and personal learning
  (`self-improvement/v1` remains compatible); project learning writes
  require task authority. Checks still need selection; native memory/trust stores
  are not editable. Plan mode/no-write means no learning writes or outgoing messages.

## Product and hot-path guards

`GlobalContracts.md` owns full architecture, the single-current contract, bounded storage and
compiler rules. Read it for those changes; nested rules add domain constraints.

- Core/Contracts stay below `src/src/{Core,Contracts}`; apps consume public
  targets in the one root direct-source graph, never staged/copied sibling SDKs
  or binaries. `src/src/CMakeLists.txt` and `src/src/cmake/Sources/**` own metadata.
- trading-core owns deterministic strategy/execution/order lifecycle/admission;
  Capital owns basic finance, with experimental planning offline. CXET depends
  on neither; finance consumes normalized CXET/leaf values, not strategy providers.
- Parser owns native sessions/credentials/identity/terminal I/O; Trader owns
  strategy/risk/current-run orders. One `traderd`, same-owner-thread SessionBinding,
  exact account/product/generation/capacity fences and intent/correlation before
  one submission. Unknown outcomes never authorize automatic resend.
- Explicit Stop (SIGINT/SIGTERM included) quiesces owners, cancels all exact-account
  orders through certified native authority and closes only proved current-run
  inventory. Missing authority/uncertainty retains ControlOnly; retirement issues
  no trading actions and guardian loss never requests Stop. Missing native authority
  refuses Full without downgrade/fallback. Current limits:
  `apps/trader/docs/ParserSessionBoundary.md`; structure is not readiness evidence.
- Vetron owns projections, never native sessions/risk/order state. ReadOnly excludes
  private/order/control links; Full adds typed localhost control without downgrade.
  HFT Trader is retired; corpus truth is `/mnt/d/recordings`. Keep one current
  contract/semantic owner and atomic exchanges; no silent fallback or unrequested API.
- Boost/simdjson are forbidden in core/Parser/Trader; borrowed text is
  `cxet::StringView`. Growing storage needs owner/bound/allocation/overflow policy.
- Latency is correctness: prove compiled route, parser, pump, strategy and terminal
  write. H0 per-tick/strategy forbids allocation/growth, exceptions/RTTI/virtual calls,
  locks/sleeps/blocking, file/console I/O, formatting and floating point.
  Capital computation obeys H0 already offline; diagnostics/oracles stay outside.
  Publish available data immediately; batches only guard fairness; probes need
  production-hot-safe evidence.
