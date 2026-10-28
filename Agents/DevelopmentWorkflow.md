# Development workflow

This file owns the CXET development and check-selection policy. App rules add
only domain constraints. Follow the active task, nearest `AGENTS.md`,
`GlobalContracts.md` and applicable hot-path rules.

## Implement the requested result

1. Identify the minimum agreed user outcome and its necessary prerequisites early.
   After sufficient investigation, progress toward that outcome; do not expand
   infrastructure or coordination without a concrete task, dependency or review.
   Establish the requested observable behavior and its canonical owner. Resolve
   routine details from current code; ask about material unresolved semantics.
   Carry the agreed result and constraints through later optimization, refactor,
   and verification stages. A faster startup must not weaken an agreed readiness
   or risk condition. Keep domain semantics with their existing contract owner.
   Before non-trivial behavior changes, establish the initial state, full event
   cycle, allowed decisions, refusal/recovery behavior and observable completion
   criteria. Walk through a normal scenario and a relevant failure or partial
   scenario. For finance, settle units/scales, rounding, account authority,
   reservations and the effects of partial fills and Unknown outcomes. Resolve
   facts from source first; discuss material choices with the user before
   dependent edits. This is an in-chat behavior agreement, not an extra artifact
   or a repeated approval of already settled decisions. Carry those decisions
   into worker capsules and later optimization.
   When useful for checking a material assumption, explain the existing behavior,
   intended change and preserved constraints briefly in chat. Skip this for
   obvious minor work. The portable `agent-workflow` card can retain decisions
   during substantial tasks; it adds no mandatory document or approval stage.
2. Before a non-trivial code edit, read the actual declaration of the changed
   type or function, an affected caller and a nearby analogous implementation.
   Derive namespaces, overloads and conventions from that code. Use available semantic
   navigation when its compilation database covers the touched scope; otherwise
   use bounded source search. Empty results from incomplete reference coverage
   do not prove there are no callers. Follow `GlobalContracts.md` for code style
   and reuse. Implement the smallest complete change and inspect its actual
   callers, registrations, source lists and operational instructions. Preserve
   unrelated edits, existing tests and production behavior outside the task.
3. Add a small useful regression test when it protects the changed behavior.
   Prefer the owning existing suite and meaningful outcomes or failure cases.
   Test-first is optional; use TDD only when the user requests it. Do not create
   tests for every method, artificial tests for prose, or APIs solely to make a
   test convenient. Coverage counts and sanitizer repetitions are not goals.
4. Inspect the integrated change and resolve concrete findings within scope.
   Finish the requested edits without waiting for unrequested check runs.
   Report implementation and executed verification separately. Unrun tests
   remain unrun; static inspection does not establish runtime or live readiness.

For Risk S local edits, use the existing lightweight path: inspect the affected
scope, make the requested change and report it. Do not add plan artifacts,
optional reviewer threads or unrelated domain rules. A small diff that affects
hot-path, contract, recovery or safety semantics still follows its actual risk.

Finish the affected declarations, callers, source lists, registrations and
operational recipes before the selected build. Stabilize owned shared headers
before a multi-target run; a passing intermediate target is not final-source
proof. Do not substitute documents or benchmark candidates for authorized
implementation. Add diagnostic collectors only for a concrete selected question;
prefer the existing cold stage/refusal report. Lead status with the user action
that now works and its remaining causal blocker, then give supporting evidence.

For identifier or path renames, inspect the entire affected defining scope and
remaining old references in its consumer closure. Classify intentional member
names and historical evidence separately. Reversible text replacement and a
whitespace-only check do not prove complete C++ symbol binding.

An existing implementation does not need to be removed to reconstruct a RED
history. Refactors preserve behavior and use existing tests; add focused
characterization only for a concrete relevant gap. New tests need their actual
registration closure, not a quota of scenarios. Preserve accurate executable
catalogs where existing infrastructure requires them; a foreign catalog mismatch
is not permission to adopt that suite or increase the task's coverage target.

## Select runs with the user

- `делай` / `implement` / `выполни план` authorizes requested edits and useful
  test additions, without compilation or test execution. Finish implementation
  independently of unrequested checks; a plan list or Goal grants no run permission.
- First approval is required before launching a check package. For `делай и проверь`,
  `проверь` or another verification request, present the smallest exact command
  package, working directories, purpose, targets/profile, resource limits and
  material side effects; wait for user selection before execution. A direct
  request to run an exact command supplies its first approval.
- The approved package remains authorized until task completion, cancellation or
  a scope change; an explicit pause suspends execution until the user resumes it.
  After the presented package, `проверяй, разрешаю` selects that package. Status
  questions, incidental messages and worker reports do not revoke approval.
  Respect any narrower user restriction, such as a single attempt.
- Approval covers justified repeats without a numeric attempt cap: repeat only
  after a concrete fix, a change to the exercised code or a resolved blocker.
  Before a repeat, show the exact command and reason and inspect the prior process
  and log. A failed invocation alone is not reason to retry. Stop after success
  until a subsequent affected code change requires that check again.
- Changed commands or targets, different profiles, or increased jobs/resources
  require new selection. Do not silently extend the package or escalate after
  failure. A listed but unapproved package remains unapproved.
- The primary coordinates launches and results. A delegated check must name its
  existing approved package and exact command; delegation does not expand consent
  or grant another standalone chat this task's authority. Keep independent
  critical reviewers within their read-only assignments.
- Static reading, searches and local read-only Git need no run consent, including
  in Recorder. Every Git write and formatter rewrite retains separate permission.
- ASan/UBSan/TSan, full suites/builds, baselines, benchmarks, services, browser,
  runtime/live/network, model and account/order actions retain their separate
  explicit selection. Package approval cannot add these actions implicitly;
  preserve narrower domain-specific action and retry restrictions.
- Classify the cause of failure before continuing. Environment/build failures
  are `BLOCKED`, not a behavioral RED. Missing tools or dependencies do not
  authorize bootstrap, package installation or replacing pinned tools.

Checks of personal workflow utilities follow the same user-selection policy.
Automatic learning authorizes no test, smoke, pressure-scenario or model-eval
runs. Study keeps product files read-only; personal writes follow active mode
and authority. Skills are tools, not additional execution or acceptance gates.

## Bounded reads and output

Discover paths and short matches before reading excerpts. Default each displayed
read or command summary to 40 lines / 8 KiB, whichever is reached first. This is
a display budget, not a limit on source inspection or retained evidence. Mark
truncation explicitly, identify the file/log and omitted range when known, then
reread the narrow range needed for the current question. Read wider context when
necessary for correctness; do not infer absence from a clipped search or omit
required contracts, callers, failure paths or review evidence to fit the budget.

Selected checks retain complete stdout/stderr logs, exact command, directory
and final exit status. Show a compact status and relevant diagnostic excerpts;
keep full logs available for targeted rereads. An error-only filter or an empty
excerpt never proves success: inspect the exit status and completion evidence,
including warnings or skipped work that affect the conclusion. Missing or
truncated retained evidence is inconclusive and must be reported explicitly.
Output handling never authorizes a check, a repeat or a larger check package.

## Independent ownership

Other standalone chats keep their own tasks. Contact one only for an actual
shared-file conflict, necessary dependency or concrete defect attribution.
When authorship is established, send the defect to the chat that introduced it
and continue independent work. A message does not transfer ownership or authorize
foreign edits. If an actual dependency blocks one part, report that part to the
user and continue the rest. Preserve the build lock; do not run a project-wide
queue, poll unrelated tasks or wait for another owner's entire verification.

## Safe execution of selected checks

Classify by effects, not command language or filename:

- Lightweight local checks include workflow validators and utility unit tests
  that do not compile, use or modify a native build/product tree, start services,
  or perform live/network/model/account actions. Run them directly in the declared
  source directory with their own temporary fixtures. They need no CXET compile
  lock, CMake cache, compiler selection or `RunOffline` wrapper. Preserve output
  and exit status; ordinary process limits may bound the selected check.
- Native build checks include compilation, CTest/native binaries using a prepared
  build tree, code generation in that tree and wrappers that configure or change it.
  They retain the owner cache, compiler/targets, containment and build-lock rules
  below. A Python or shell build wrapper is a native check.
- External services, model calls, browser and live/account actions keep their
  separate authorization and execution rules; they are not lightweight checks.

`CheckCxetFamilyRootGraph.py` and `CheckCxetFamilyOwnership.py` are optional
manual architectural audits. Run either only when the user explicitly requests
that checker or selects its exact command. Ordinary requests to verify changes
(`проверь`), build approval, and changes to includes or CMake registrations do
not select these audits. Do not automatically add or recommend them in routine
check packages, or require them before a build. Manual commands are documented
in `tools/Codex/README.md`.

These audits check CMake registration, source ownership and include
reachability, including registered test paths, without compiling C++. They do
not prove C++ type/template correctness or linking. Explicitly selected audits
retain the run-selection and repeat-consent rules above. Fix confirmed defects
within the authorized scope; report foreign or semantic blockers rather than
weakening the checks.

Before an authorized native build check, identify its owner, source root,
prepared private cache, compiler, targets and resource-contained runner. Use the
canonical lock and one build job unless a positive count was explicitly selected. A held lock,
missing containment, incompatible cache or unavailable dependency is `BLOCKED`;
continue independent edits rather than bypass the boundary.

New targets may need regeneration of that same private offline cache; select
that preparation command with the user before running it. Never reconfigure the
active product tree to obtain a test target. Do not change product selection,
clean artifacts, bootstrap tools, restart services, use `--force` or start an
unrestricted build to repair a check failure.

Keep each attempt's command, directory/profile, owned PID or tool session, log
and final exit status. Preserve failed logs. A partial log, percentage, old
executable or disappeared process is inconclusive. After interruption, inspect
process ownership and state, available output, the log, cache and the last
completed phase before proposing a new attempt. A canceled tool call does not
prove that its process stopped or that its action had no effect. Establish
whether the action completed, remains active or has an unknown outcome before
continuing; do not blindly repeat it. Apply the approved package's scope and
repeat rules above. Stop owned duplicate attempts and never kill another
session's processes.
After a suspected host/WSL restart, compare timestamps and available boot
evidence; an empty current-boot OOM log does not establish cause.
Product wrappers can update dependencies, frontend outputs and product selection;
establish those effects before a selected product build.

## Review and evidence

The primary inspects the final integrated change. `Subagents.md` owns the
independent review gates for actual H0/H1 code and substantive Capital
computational changes, including offline. Review the final affected change,
not every intermediate edit. Reopen review only for concrete finding repairs
or new material changes, and only on the affected surface.

Keep static, schema, build, targeted-test, runtime, browser, performance and live
proof separate. Existing family CI selects its own snapshot profiles; its
release, sanitizer and thread/fuzz gates do not authorize local runs or make
those runs an ordinary implementation completion criterion. This workflow
rewrite does not change CI. Report only commands and results actually observed;
registration counts and reviewer claims are not execution evidence.
