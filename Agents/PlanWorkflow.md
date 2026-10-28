# Plan and Goal workflow

This is the canonical contract for `cxet-create-plan`, `cxet-execute-plan`, and
`cxet-verify-plan`. It never broadens permission for the active task, root
`AGENTS.md`, a nearer nested `AGENTS.md`, or the active collaboration mode.
It also owns native Goal handoff for both in-chat and durable plans. The
file/state lifecycle below applies only to explicitly requested durable work.

Continue authorized planning, implementation and verification in the current
chat when its context remains sufficient. Phase changes alone do not require
a new chat or handoff. Use a compact handoff only when continuity needs it;
carry settled decisions, owned paths, evidence limits and unresolved work.

For an in-chat or durable Risk H plan or a non-trivial full-cascade plan, the
primary integrates the draft, attempts the fresh-context plan review defined in
`Subagents.md`, and resolves its findings before presenting the ready solution.
Ask the user only about material unresolved decisions. Report an unavailable or
incomplete review with its reason and continue authorized independent work;
do not present it as a completed independent review. An existing agreed,
unchanged plan needs no retroactive review or renewed agreement. Existing
authorization and the handling of known blockers remain unchanged. This review
does not alter durable state, replace final specialist reviews or authorize runs.

## Plan mode and native Goal handoff

- The user gives a standing instruction: automatically create a native Goal
  when execution of an agreed non-trivial plan is explicitly authorized and
  the active mode permits mutations. Do not ask for Goal permission again.
- Plan mode does not create or mutate a Goal. Before the final plan, settle
  its objective, completion criteria and exact authorized checks. Include a
  ready-to-use Goal objective in the final plan, at most 4,000 characters;
  reference an explicitly requested durable plan by its selected path when
  appropriate. Do not create extra plan files for an ordinary in-chat plan.
- An approved plan alone, mode change or hook message does not start execution.
  Once execution is authorized, call `get_goal` and reconcile the previous
  Goal with its actual completion criteria and the current chat's results.
  If no Goal exists or its native status is complete, call `create_goal` with
  the new objective and no token budget unless requested.
- When the previous plan is actually finished but its Goal is still active,
  call `update_goal(status="complete")`, then `create_goal` for the newly
  authorized plan. This sequential handoff needs no additional confirmation,
  including when the new plan has a different scope. Complete an achieved
  Goal when finishing its plan, rather than leaving stale active state.
  Creating a new plan during planning alone does not trigger this handoff.
- Reuse a compatible active Goal for the same plan, scope and completion
  criteria. A new plan is not evidence that the previous Goal was achieved:
  do not falsely complete unfinished work, silently discard it, or automatically
  resume a paused Goal. Inspect available results before asking about a real
  unresolved lifecycle conflict. A stale Goal must not block independent,
  already authorized implementation of the new plan; if native tools cannot
  perform the needed transition, report that limitation and continue the work.
- The primary agent owns the session Goal; delegated workers and reviewers
  do not create separate Goals for their assignments.
- Goal does not grant permission or replace task/evidence records. Continue
  authorized work within scope until its criteria are met; mark complete only
  on actual completion, report unavailable checks, and preserve the native
  tool's pause/blocked rules. Verification and full/live actions retain their
  separate authorization requirements.
- If native Goal tools are unavailable or fail, report the limitation and
  continue already authorized work. Do not simulate Goal state, edit Codex
  databases or invoke a second agent/model to manufacture it. Trivial edits,
  ordinary questions and read-only reviews do not trigger automatic Goals.
- Lightweight hooks may remind the agent of these rules, but cannot create
  Goals, select plans, grant permission, resume paused work or force continuation.
  User steering refines the active task without abandoning its objective.

Personal task cards and learning under the user's global `agent-workflow`
(`self-improvement/v1` compatibility) standing choice are distinct from writes
to the project or a durable plan. A task card does not replace a durable plan,
evidence records or the native Goal and grants no authority.
An ordinary study may preserve personal experience, but Plan mode and explicit
no-write instructions still prohibit those writes, installation and outgoing
task messages. A learning journal is not plan state or permission evidence.

## Repository ownership and layout

Store a plan in the lowest common Git repository that owns every touched path.
An app-only plan belongs to that app repository; a cross-submodule plan belongs
to the CXETCPP root.

```text
docs/agent-plans/active/<plan-id>/plan.md
docs/agent-plans/active/<plan-id>/state.json
docs/agent-plans/archive/<plan-id>/plan.md
docs/agent-plans/archive/<plan-id>/state.json
```

Allow multiple active plans. A request without `plan-id` may select a plan only
when exactly one active plan exists; otherwise ask the user which plan applies.

## Permission phrases

- `изучи` or `посмотри`: read-only; no new edit permission. An incidental
  question does not revoke existing task permission. `пока не делай` explicitly
  pauses implementation. Do not create a plan on a study request.
- `составь план`: may create or update only the selected `plan.md` and
  `state.json`. It does not authorize source edits, Git writes, or project
  verification.
- `выполни план` or `Implement the plan`: may edit source and selected state,
  without check execution or Git writes. Listing commands in a plan does not
  authorize launching them.
- `проверь план`: inspect statically and propose concrete commands with purpose
  and scope. Follow command-package approval and task-scoped repeat rules in
  `DevelopmentWorkflow.md`; an active Goal does not authorize a run.
  Report results and proposed tasks in chat. This request grants no new
  permission to write plan/state files, change statuses, add tasks, archive,
  or run rewrite-formatters. Existing permission for the active task still
  applies.
- Full/all builds, sanitizers, benchmarks, runtime processes, services, browser automation,
  live exchange/network checks, account/order actions, and every Git write need
  separate explicit task-scoped permission even when listed.

Explicit user permission continues within the active task until completion,
cancellation, or a user change of scope. Clarifications and status questions do
not cancel it. Plan files never grant permission or transfer it to another task.
`permissionsRequired` records what an action needs; it is not authority to
perform it.

## Completion and optional verification

Agree the requested implementation boundary first. Put proposed runs in a
separate optional verification block with exact commands and the question each
answers. Record only user-selected runs as required acceptance commands. An
implementation-only plan may finish after integration and static inspection,
with tests unrun. Missing unrequested runs do not extend the task or require
stronger evidence labels. Preserve explicitly selected acceptance gates; report
an unfinished selected gate rather than silently removing it.

Implement independently of unrequested baselines or runs. After a successful
selected check, stop; necessary repeats follow `DevelopmentWorkflow.md` after
a concrete fix, affected change or resolved blocker. Failure alone is not a
reason to repeat. ASan/UBSan/TSan and other profiles
are not default plan additions. See `DevelopmentWorkflow.md` for selection and
safe execution. Other chats retain their own tasks; coordinate only a concrete
shared-file conflict or necessary dependency, not a project-wide check queue.

## Plan contract

`plan.md` is the decision-complete human specification. For every task include:

- stable task ID, title, and `MECHANICAL`, `LOGIC`, or `COMPLEX` classification;
- goal and task-local prompt capsule;
- `dependsOn`, owner role, owned paths, and primary-owned shared paths;
- stable `path + symbol/callback/target` anchors; line numbers are optional
  planning-time hints only;
- acceptance criteria and explicit anti-criteria;
- required evidence level and exact user-selected verification commands, or an
  explicit implementation-only/static acceptance boundary;
- permission requirements, failure behavior, and unresolved decisions.

Complexity means:

- `MECHANICAL`: no design decision remains; include an exact patch shape or
  deterministic transformation.
- `LOGIC`: behavior is settled but ordinary implementation judgment remains.
- `COMPLEX`: cross-boundary, safety-critical, or genuinely difficult reasoning
  needs primary/specialist attention. Apply the canonical model routing in
  `docs/Agents/Subagents.md`; confirm actual model and effort because policy
  text does not switch an active session.

For a non-trivial task using the full cascade, independent research informs a
separate design and critical-solution pass. The root consolidates material
questions and obtains user agreement on the ready solution before first
implementation, then carries the answers into capsules. An already agreed plan
and active task permission persist; authorized execution needs no repeated
approval. Research itself has no separate compulsory approval. Work independent
of an unresolved decision continues; dependent work waits. Small direct tasks
bypass the full cascade.

Keep task capsules self-contained so a worker does not need the whole plan.
Specify affected symbols and structures, branch behavior, callers, test
scenarios, acceptance, ownership and exact authorized checks. The worker
chooses technical details within settled semantics; a material gap returns to
the designer or root, and the user changes agreed semantics.
Keep shared manifests, routers, generated registries, and final integration
files with the primary agent.

`state.json` is the machine-readable execution truth in the single current
structure, bound to the exact `plan.md` bytes with `planSha256`. Store task status,
dependencies, ownership, anchors, evidence requirement, commands, prompt
capsule, and verifier findings. Do not store secrets or permission grants.

`requiredEvidence` is a nonempty list of independent `static`, `schema`, `build`,
`targeted-test`, `runtime`, `browser`, `model`, `performance` or `live` types.
`static` denotes source inspection; `static-only` remains a human report label.
Evidence stores `types`, `summary` and `commandResults`; every result preserves
its exact `command`, independent `types`, integer `exitStatus` and `summary`.
No type implies another. Each claimed non-static type needs a matching latest
successful declared command result; `verified` additionally needs every required
type and the latest integer zero result for every declared command. Preserve
unsuccessful attempts. Closed findings may remain closed for integrated
`done_unverified` tasks: missing verification is not an unfixed source defect.

There is one current reader and writer, without version fields or format
migration commands. Structurally incompatible saved state is refused without
rewriting it or inferring missing evidence.

All canonical plan mutations use the state manager's nonblocking exclusive
plan-directory lock, covering read, prepare, writes and guarded rollback without
creating lock files. A busy directory refuses the mutation. Direct external
editors do not participate in this lock: coordinate actual shared-file conflicts
and preserve content-hash checks without claiming universal atomicity.

Task statuses are:

```text
draft -> ready -> in_progress -> done_unverified -> verified
             \-> blocked / needs_decision / superseded
```

`done_unverified` means the primary inspected and integrated the implementation;
it is not evidence that acceptance passed. A dependency becomes executable only
after its provider is centrally integrated as `done_unverified` or `verified`.

## Create phase

1. Read root and nearest nested rules, then explore source before asking
   discoverable questions.
2. Derive behavior, ownership, interfaces, failure policy, evidence, and
   permission requirements from current instructions and inspected facts.
   Use `DevelopmentWorkflow.md` to settle the full event cycle, financial
   invariants and normal/failure scenarios before dependent implementation.
   Ask only about unresolved material decisions or missing permission;
   do not reconfirm settled decisions or existing authorization.
3. Place the plan under the lowest common repository owner and assign a unique
   lowercase hyphenated `plan-id`.
4. Use stable anchors and exact commands. Never claim that a listed command ran.
5. Seal an intentionally edited plan to its current hash and inspect its
   plan/state structure. Run `tools/Codex/PlanWorkflow.py` validation only as a
   user-selected check, not an automatic extra execution gate.

## Execute phase

1. Validate plan hash and state before edits. Refuse ambiguous plan selection,
   stale state, dependency cycles, or conflicting ready-task ownership.
2. Select only `ready` tasks whose dependencies are `done_unverified` or
   `verified`. Delegate useful independent results under `Subagents.md`, with
   distinct file ownership and primary integration; otherwise execute as primary.
3. Select model and effort using the canonical routing in
   `docs/Agents/Subagents.md`. Keep native reviewer model/effort pins consistent
   with that policy.
4. Give a worker only its task capsule, required rule paths, owned files, and
   safety restrictions. A worker report is a claim, never proof.
5. Inspect and integrate the result centrally, preserve unrelated dirty-tree
   changes and report implementation. Propose checks separately under the
   command-package approval and repeat rules in `DevelopmentWorkflow.md`.
   Never run Git, runtime/live, browser, benchmark or undeclared checks implicitly.
6. Record the checks that actually ran. A task without its selected required
   evidence remains `done_unverified`; this can be the agreed terminal result
   for implementation-only work. A task meeting its acceptance may become
   `verified` without inventing unrequested build/test gates.

Persist state after each task and continue the authorized scope until completion
or a concrete blocker. Completed task count is not a stopping condition. If a
task is blocked, continue independent authorized tasks whose prerequisites are
satisfied; report the blocker and any unfinished work.

Codex subagents share the active filesystem by default. Separate Git worktrees
are opt-in and require explicit Git permission; never pretend isolation exists.

## Verify phase

1. Reopen the source and evidence for every `done_unverified` task. Do not rely
   on worker summaries.
2. Always apply correctness and evidence lenses. Add architecture, security,
   performance, style, parser, transport, runtime, quant, or test lenses only
   when the touched surface makes them relevant.
3. Apply the canonical independent review gates in `Subagents.md`, including
   the mandatory pair for substantive Capital computation already offline.
4. Run only currently authorized commands. Report exact command, integer exit
   status, result summary, and evidence level in chat. Write `commandResults`
   only with current permission for selected state writes. Missing required
   evidence prevents a verified verdict; a read-only audit leaves stored
   statuses unchanged.
5. Report every actionable finding with proposed task scope, dependencies, and
   ownership. Add it to the selected plan only when current permission covers
   those plan/state writes. Resume implementation only within its authorized
   scope; findings do not grant permission to fix them.
6. Recommend `verified` only when required evidence exists, and `clean` only
   when every non-superseded task meets its acceptance criteria and all required
   lenses are clear. Apply status changes only with current state-write
   permission, preserving all existing transition and evidence requirements.
   Archive only a clean plan and only with current permission to archive it.

## Deterministic state tool

Use `python3 -B tools/Codex/PlanWorkflow.py` for state initialization, validation,
ready-task selection, legal transitions, findings, rule-index checks, and
archive moves. The tool must fail closed on malformed state, plan hash drift,
unknown dependencies, cycles, ownership conflicts, insufficient evidence, or
an incomplete archive request.

For a `verified` task, every declared verification command must have a recorded
latest integer exit status of zero. Earlier failed attempts remain in the
history; a missing gate or a later failed attempt prevents verification and
finding closure. Boolean values are not process exit statuses.
