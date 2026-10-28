# Subagent policy

Delegate independent tasks when parallel work saves time or improves quality,
subject to higher-level controls. Prefer one agent for tightly coupled work.
The main agent owns final integration and safety. Mandatory H reviews remain
independent reviewer threads.

## Native Codex and Orca coordination

Prefer native Codex subagents for independent investigations, implementation
scopes and reviews, including large CXETCPP tasks. Select relevant project
skills and expertise through the existing context/role routing; a task mentioning
multiple agents does not by itself require the Orca orchestration skill.

Use `orca-cli` for actual Orca worktree and terminal operations and full ownership
handoffs. Use `orchestration` when the task needs supervised Orca workers,
cross-workspace dependencies or long-running coordination through Orca. Select
that skill from the task's needs without requiring the user to name it explicitly.
Once selected, use real Orca runtime state and tools; native subagents are not
substitutes for Orca workers, task records or delivery receipts.

Keep small, tightly coupled tasks with one agent. This selection adds no startup
bundle or approval stage and does not change model routing, mandatory native
reviewers, independent-chat ownership or task-scoped authorization for runs.

## Model routing (canonical)

The machine-readable route data is `tools/Codex/AgentRouting.json`; this
section owns its policy meaning. This model/tool configuration applies to Codex.
Common delegation, questions through root, independent research and review,
ownership and permission rules apply regardless of the selected primary model
and effort. Other agent systems apply them through their available capabilities;
do not require Codex-specific model names or native APIs there.

Identify the minimum agreed user outcome and its necessary prerequisites early.
After sufficient research, progress toward that outcome. Additional agents,
messages and infrastructure must address a concrete task, dependency or review;
avoid duplicate coordination and unrelated expansion without numerical quotas.

For a useful full cascade, research first reports its findings to the root. The
root considers that result and then invokes a separate design agent with the
relevant findings and decisions. If material questions remain, the root asks
the user before the dependent step; independent work may continue. After design
returns, the root integrates the ready plan and applies the existing agreement
and authorization rule before implementation. Small tasks need no full cascade.

- `gpt-6.1-sol` high is the preferred root orchestrator and default worker for
  investigation, implementation and integration. An explicit user selection
  takes precedence; instructions do not switch an already-running session.
- Independent research uses Sol high; design and substantive independent review
  use Sol xhigh. Preserve the mandatory critical reviewer pairs below.
- `gpt-6.1-terra` high performs bounded mechanical edits, simple specified tests, log and
  machine-code inspection, and selected lightweight checks. Give a sufficient
  specification; if it is missing or requires judgment, report the gap to Sol and
  stop the dependent work. Do not independently expand the solution.
- Astra medium or high is rare and needs a concrete reason and bounded evidence.
  It may proactively assist a very broad cross-domain problem; the root explains
  why. Do not use ultra by default.
- Use standard/default service tier. Fast mode may be selected manually; keep
  `features.fast_mode = true`. Do not switch to Fast without user selection.

`mechanical_luna` and `mechanical_luna_broad` are stable technical identifiers
for Terra high. Native role files can pin model and effort and take precedence
over spawn settings; verify the actual role setting and never claim a setting
changed merely because a prompt or follow-up requests it. If a required role
cannot run with the required setting, report the blocked review and continue
independent work. This is routing policy, not a measured quality guarantee.

The two mechanical workers may receive scoped read-only assignments without
implementation authorization. Editing requires persisted explicit
implementation authorization for the active task. For study, review,
diagnosis, planning, and status work, do not edit. A workspace-write sandbox
is capability, not authorization.

Read-only role instructions are a behavior requirement, not proof of an isolated
read-only sandbox. Native agents inherit the parent's permissions; a standalone
role's `sandbox_mode` does not replace those permissions. Verify actual actions
and keep the no-edit requirement explicit in research and review assignments
([native agent permissions](https://learn.chatgpt.com/docs/agent-configuration/subagents)).

## Agent behavior contract

- Give the model a concrete outcome, relevant context, constraints, and the
  required output shape or writing style.
- Continue clearly authorized work and ask a question only when the missing
  answer can change the outcome; prepare the concrete result before requesting
  approval for an external or irreversible action.
- Audit `AGENTS.md` and skills when behavior is surprising, especially for
  conflicting instructions or missing task context.
- State when delegation is expected and keep worker ownership non-overlapping.
- Match verification to the change. Small reversible policy edits need focused
  static checks; broader checks require a task-scoped authorization.
- For future OpenAI API examples, use the Responses API for reasoning with
  tools/function calling. Match model and effort to the task and available API.

## Code simplicity participation

For substantive code tasks, including features, fixes, refactors and substantial
code reviews, the coordinator delegates two consultations to native
`code_simplicity_engineer`, subject to higher-level controls: early, once the
task scope is known and before choosing the implementation or editing; and at
the end, after the relevant specialist reviews, including the H0/H1 or Capital
pair when applicable. Reuse the initial thread when it remains an independent
reviewer. Trivial mechanical tasks do not
need these calls. All agents apply the common simplicity rules in root `AGENTS.md`.

The early consultation searches the relevant owner, callers and analogues, and
helps choose reuse or a simpler complete design. The final consultation examines
the actual changes attributable to this task and their context, not unrelated
dirty work. Both are read-only: the specialist brings concrete findings and
alternatives to the coordinator, who identifies the change owner and routes each
actionable finding for discussion. If the coordinator owns the change, the
discussion is with the coordinator; if the owner is unavailable, report that.
The owner and coordinator decide what to do within the active task; an observation
alone neither mandates edits nor expands permission.
If resulting changes materially affect a previously reviewed H0/H1 or Capital
surface, repeat the affected required specialist reviews and then the simplicity
review for that changed surface. Never substitute simplicity review for a required
domain review or use the author as its own independent final reviewer.

A direct request for simplicity, boilerplate, duplication or structure also routes
to this specialist. In a separate authorized implementation assignment it makes a
proportionate plan and may edit its owned scope; a study, review or planning-only
request remains read-only. Existing rules decide when a material decision or an
agreed full cascade needs user agreement; no repeated routine approval is added.
Its model and effort follow the native role in `AgentRouting.json`. If the role
cannot be launched or finish, continue independent authorized work and report the
missing consultation; never claim that it ran or cleared the scope. These are
instructions for coordination, not a hook-enforced delivery guarantee.

## Automatic subagents

Delegate concrete independent subtasks automatically when parallel work saves
time or improves quality, subject to higher-level controls. Explorer and reviewer
subagents remain read-only and may not run builds, tests, benchmarks, runtime,
live tools, Git writes, or network checks without separate authorization.

Editing workers may launch automatically only with implementation permission
for the active task (`делай`, `implement`, or an equivalent direct change request).
Study, planning, review, diagnosis, and status requests grant no new editing
permission. An incidental question does not revoke existing task permission; an
explicit pause, cancellation, or scope change controls subsequent work.

An explicit `выполни план <id>` / `Implement the plan <id>` invocation for the
active task authorizes plan-scoped workers. Runs require the user's explicit
selection of exact commands under `DevelopmentWorkflow.md`; a proposed command
in a plan does not authorize a run. First package approval and justified repeats
until task completion are owned by `DevelopmentWorkflow.md`. The primary coordinates
check launches and results; delegation never extends the approved package.
Existing implementation authorization remains
valid for source edits. Keep ownership and actions within the task capsule.

Use threads as needed within the configured native session limit and
higher-level controls, without arbitrary thread-count or depth quotas. The
configured limit is a ceiling, not a target. An agent proposes its subtree's
model, effort and scopes to the root before spawning; the root approves the
proposal internally. The agent owns its accepted branch and returns consolidated
results. This is instruction-level coordination, not a tool-enforced gate.
Split independent scopes with non-overlapping file ownership; the root owns
shared manifests, routers, registries and final integration files. Prefer
one agent for tightly coupled work and reuse existing threads for related work.
Small tasks do not need the full cascade.

All user questions go through the root, which deduplicates them and asks only
material questions. While an answer is unresolved, dependent work waits and
independent work continues. For a non-trivial task using the full cascade, the
user agrees the ready solution before first implementation; no separate research
approval is compulsory. An already agreed plan and active task permission persist:
authorized execution needs no repeated approval. Small direct tasks bypass the
full cascade.

For durable plans, pass the complete task capsule rather than asking a worker to
read the whole plan. A worker report is a claim. Only the primary may mark the
centrally inspected result `done_unverified`; only the verification workflow may
advance it to `verified`.

For actual delegation, briefly state each agent's role, owned scope, expected
output, and reason. Ordinary tasks do not need an empty subagent template.

Task capsules are near-patch specifications: concrete result, owned paths,
symbols and structures, branch behavior, known callers and boundaries, test
scenarios, acceptance criteria, settled decisions and evidence, and exact
authorized actions/checks (or none). The worker decides technical details
within settled semantics. Material gaps return to the designer or root; user
changes to agreed semantics go through the root. Root owns shared integration
files; reviewers are independent of authors. Point to `ReportFormat.md` under
"Subagent results" for the return format. These repository documents define
assignment and acceptance without personal notes, home-directory files or
previous chat history; personal memory can supplement context.

The primary integrates results by merging duplicate findings, resolving
contradictions and checking key or disputed claims at their source and affected
callers/registrations. Check that changed boundaries fit the integrated result
and keep unchecked surfaces explicit. Reuse supported worker evidence; repeat
discovery only for a concrete missing link, contradiction or affected change.
If reports conflict, inspect the disputed anchors and relevant caller, then
resolve the claim or report the remaining material question. Do not decide by
agent count or escalate static evidence into build/runtime proof. This adds no
review stage or authority to launch checks; mandatory independent reviews keep
their existing scope and rules.

The portable `agent-workflow` skill owns personal experience and task cards;
`self-improvement/v1` remains a compatibility entry. The primary maintains its
own task card and passes relevant decisions to workers, which do not update it.
Separate chats in one checkout do not share a card merely because paths match.
The user's standing personal-workflow choice grants no project actions or runs;
checks still need user-selected commands under `DevelopmentWorkflow.md`.
Give each helper concrete non-overlapping ownership and keep integration with
the primary. Study/review still forbids project edits, and Plan mode permits
no learning writes or outgoing messages. Existing standalone chats may exchange
only concrete shared-file conflicts, necessary dependencies or defect attribution
through exposed native tools; messages grant no authority or task ownership.
Independent helper threads do not own a separate session Goal.

## Context and continuity

- When a substantial task has an `agent-workflow` card, carry its agreed decisions
  into worker capsules. A handoff is context, not acceptance, permission or a
  transfer of ownership. Keep cards and updates small; no extra approval ritual.
- Select roles without creating a separate thread for every role. Delegate a
  concrete independent result when parallel work saves time or adds necessary
  independent review; handle small, tightly coupled searches directly.
- Start independent workers with `fork_turns="none"`. Supply the goal, owned
  paths, relevant contracts, settled decisions, evidence and authorized checks
  in a short task capsule. Include surrounding history only when the task
  actually depends on it, and limit the fork to that relevant context.
- Continue related work through the existing agent with `followup_task`.
  Start a replacement only if that agent is unavailable or the work needs a
  distinct owner. Carry its prior findings forward rather than restart discovery.
  A new fresh-context plan review is a distinct assignment and needs a new
  thread; follow-up can clarify an existing finding but is not a fresh review.
- After a thread-limit error, do not repeat spawn until capacity or the
  assignment has materially changed. Reuse an available agent or continue as
  primary; a failed spawn is not completed work or an independent review.
- Read applicable rules once per unchanged active context. Re-read when files
  change, scope changes, or compaction/handoff leaves required details missing.
  Each new worker still reads its nearest `AGENTS.md` and triggered rules.
- Keep searches and tool output bounded to the question. Discover paths and
  short matches first, then read only the needed excerpts. Follow the 40-line /
  8-KiB display default and truncation/reread rules in `DevelopmentWorkflow.md`.
  Return concise findings, exact paths, decisions and evidence limitations
  rather than whole files or transcripts. Preserve the mandatory independent
  H0/H1 reviews.

## Fresh-context plan review

After integrating a plan and before presenting it to the user, attempt one
fresh independent review for a non-trivial full cascade or Risk H plan. For
other plans use it when a concrete serious risk makes it useful or the user
requests it. Small direct tasks keep their lightweight path. This applies to
in-chat and durable plans, not retroactively to an unchanged agreed plan.

Use a new reviewer independent of the plan's author, researcher and designer,
with the existing review model route and a read-only assignment. In Codex set
`fork_turns="none"`; other agent systems need an equivalent fresh conversation
context. Confirm actual role/model/effort under the existing routing rules.
Provide the complete exact plan text, applicable instructions, bounded source
references and, for a durable plan, the `plan.md` path. Put settled decisions
and constraints in the plan itself. Do not provide conversation history, author
explanations, previous reviews, personal memory or suggested answers. Do not
create an artifact merely to review an in-chat plan. Fresh conversation context
does not isolate the shared filesystem or memory; mandatory project rules still
apply, but earlier discussions or notes must not fill gaps in the plan.

First the reviewer reconstructs the proposed result, behavior, sequence,
boundaries and acceptance from the plan and identifies what is unclear without
guessing. Then the reviewer reads relevant referenced sources and checks hidden
assumptions, ownership and callers, dependencies, contradictions, failure
behavior and feasibility. Return a concise paraphrase and actionable findings
with severity, plan section or source anchor, violated condition and evidence
limits, including inaccessible sources. A CLEAR verdict covers only the reviewed
text and inspected scope; it is not test, runtime or live evidence.

The primary compares the paraphrase with the user's intent, checks disputed
claims against sources and integrates findings. Resolve routine gaps within
current authority; route material unresolved decisions to the user. A known
unresolved blocker still stops dependent work under existing rules. If the
reviewer, fresh context, necessary sources or complete plan text are unavailable,
or the reviewer does not finish, report that the fresh plan review was not
completed and why. Present the plan with that limitation and continue authorized
independent work; the author's self-check is not an independent review.

For a durable plan, the primary supplies the complete text snapshot and path,
and compares the current file with that snapshot before presenting the review.
If it changed, the review applies to the snapshot only; do not claim the changed
text was reviewed. For an in-chat plan likewise identify the exact reviewed
text. If a complete snapshot cannot be supplied or read, report the review as
incomplete. No new artifact, state field, receipt or attestation is required.
After a material change to behavior, ownership, interfaces, dependencies,
failure policy, permissions or acceptance, attempt a new fresh review of the
affected revision. Editorial changes need no repeat; identify changes made after
the reviewed snapshot and inspect them as primary. These rules do not revoke
existing authorization or replace mandatory final H0/H1 or Capital reviews.

## Mandatory hot review

For the final integrated H0/H1 code change, run two independent read-only reviews:

- `low_latency_engineer`;
- one relevant specialist: `hot_parser_engineer`, `hot_transport_engineer`, `trader_runtime_engineer`, or `strategy_quant`.

Substantive changes to Capital's computational core require the independent
`strategy_quant` + `low_latency_engineer` pair already during its offline stage.
This includes financial transitions, accounting, reservations, order lifecycle,
risk/sizing, liquidity/portfolio evaluation, scenario construction, solver
algorithms, arithmetic and memory/work bounds under
`apps/trading-core/capital/{include/capital,src}/**`. A shared provider change
that changes those semantics is part of the same affected review surface.
Documentation, test-only changes and mechanical edits preserving semantics,
algorithms and resource bounds do not trigger this Capital gate by themselves.
The offline exception is a review requirement, not a claim of production
linkage or measured latency. Use the selected offline root-graph surface;
missing production linkage is expected and never permission to launch a build.

Classify the actual changed path first. Mentioning hot code, editing its docs or
writing a test does not itself trigger the pair. Other domains use a separate
reviewer only for a concrete serious risk or an explicit review request; role
selection is not a requirement to launch every matching role. Reuse a CLEAR
review for an unchanged surface. Review again only for a finding repair or new
material change, bounded to its affected scope. Reviewers identify concrete
violations; absent unrequested builds, tests or baselines are evidence limits,
not veto findings or permission to run them.

The main agent must resolve every veto finding before finalizing. Ask the user
when a correct resolution leaves a material decision about public behavior,
risk policy, session semantics, or fallback policy unresolved by current
instructions or the agreed plan. Do not ask again about settled behavior.

Run mandatory H reviews in the same main verification chat as two distinct
Codex reviewer threads. Project-scoped native definitions live under
`.codex/agents/*.toml`; there is no copied template owner. Critical specialist
reviewers (`low_latency_engineer`, `hot_parser_engineer`,
`hot_transport_engineer`, `trader_runtime_engineer`, and `strategy_quant`) are
`gpt-6.1-sol` xhigh and `read-only`, as is the architecture reviewer,
subject to actual runtime role support as specified by the model routing above.
Return a clear or findings verdict, severity, exact path/line evidence, violated
invariants, and evidence limitations. The primary records actionable findings in
the selected simple plan when one is in use and current permission authorizes
those plan/state writes; otherwise report findings in chat. Do not require
receipt JSON, digest bindings, hook attestations, or imported evidence transport.

## Standalone chats

The primary owns its task, not every related chat. Read or contact another owner
only for an actual shared-file conflict or necessary dependency. Send a concrete
foreign defect to the chat that introduced it when authorship is established,
then continue independent work. A message does not assign, accept or transfer
foreign work. Report a blocked dependent part to the user. Preserve the build
lock without operating a project-wide build/check queue, polling unrelated
owners or waiting for their entire task. Suppress duplicate notices and ACK loops.

## Subagent types

### Explorer

Reads/searches only. Does not edit. Good for:

- independent codebase investigation;
- finding invariants;
- mapping call paths;
- looking for similar patterns.

Explorer requirements:

- inspect the nearest `AGENTS.md` before relying on broad repo rules;
- return concrete file paths and symbols, not generic summaries;
- separate static wiring from build/test/runtime/live proof;
- for hot parser work, start from registered callback and selected wire before judging the parser implementation.
- for hot work, prove the selected production-build translation unit/header
  inclusion surface and classify H0/H1/C/D; Capital offline work uses the
  separately identified offline surface in `HotPathFastLane.md`.

### Worker

May edit only assigned files/modules. Good for:

- one isolated strategy;
- one parser/transform;
- one doc set;
- one app-local module.

Worker requirements:

- non-overlapping file ownership;
- no shared integration-file ownership unless assigned as the sole integrator;
- no broad formatting;
- no drive-by cleanup;
- no reverting user/other-agent changes;
- stop and report when the assigned boundary is insufficient or conflicts with another worker;
- report changed paths and unresolved risks.
- never mark its own work verified or close plan acceptance.

### Reviewer

Reviews a plan, diff, or subsystem for a specific role. Good for:

- low-latency review;
- live runtime safety review;
- transport/TLS/session safety review;
- quant/risk review;
- architecture boundary review.

## Forbidden for all subagents unless explicitly allowed

- Builds, compilers, tests, benchmarks.
- Live trading tools, long-running binaries, local servers.
- Destructive Git actions.
- Git inside `apps/hft-recorder`.
- External web/GitHub/CI/release checks.
- Editing generated files unless the user explicitly asks.

## Standard subagent prompt skeleton

```text
You are the <role> subagent for CXET.
Model/effort: <selected under docs/Agents/Subagents.md model routing>.
Follow the canonical model routing above and use the standard/default tier.
Confirm actual model and effort; prompt text does not switch an active thread.
Task/result: <specific observable result>
Owned scope: <files/modules>
Known boundaries: <affected callers/consumers/registrations and shared owners>
Settled decisions and evidence: <relevant constraints and source anchors>
Authorized actions/checks: <task-scoped permission and exact selected checks, or none>
Do not edit outside owned scope.
Do not run builds/tests/benchmarks/live tools.
Do not run destructive Git actions.
Do not revert user or other-agent changes.
Inspect nearest AGENTS.md for the owned scope before reporting.
Return a compact result under docs/Agents/ReportFormat.md, "Subagent results".
Include role-specific evidence and verdicts; for hot work identify the selected
compiled surface and H0/H1/C/D classification. Omit irrelevant/empty sections.
```
