# Report format

Lead non-trivial reports with `be0h check: <result and concrete proposal>`.
Use concise prose; no empty sections or printed internal checklists. Before
edits announce only material assumptions/risks and actual delegated ownership.

## Result and evidence

- After changes give the result, changed files, actual commands/results and
  material limits. Separate completed implementation from executed verification.
  Unrequested runs do not prevent implementation completion; offer them once
  under `DevelopmentWorkflow.md`; after first approval, justified repeats stay
  within that package and task. Do not broaden checks implicitly.
- Read-only studies report a verdict, inspected paths/symbols, concrete findings
  and useful next changes in chat. They grant no file/state/archive writes.
- Evidence types are independent, not a ladder. Keep each selected gate and its
  exact exercised scope distinct; earlier snapshots do not verify later edits.

| Label | Required observation |
|---|---|
| `static-only` | Source/config/log/diff inspection; no build/test/runtime check ran |
| `schema proof` | Named schema/lint/format-check command and result |
| `build proof` | Named build command and result |
| `targeted-test proof` | Named targeted test command and result |
| `runtime proof` | Exact local binary/tool invocation and observed behavior |
| `browser proof` | Actual product user action, result and data origin |
| `model proof` | Exact selected model invocation and result |
| `performance proof` | Selected measurement, workload, environment and result |
| `live proof` | Exact selected exchange/network/trading/production-like exercise |

Use verified/tested/live-ready only for matching current evidence. Static
inspection can complete an implementation, never establish exercised behavior.
If TDD was selected, report observed RED/GREEN; never reconstruct a baseline.
Compiler/environment failures are BLOCKED, not behavioral RED.

For UI acceptance name the action and real-provider/replay/fixture/synthetic
origin. A screenshot alone does not prove provider use. If asked to retain an
owned process, report command/PID and stop instructions.

## Subagent results

Return a compact result that the primary can integrate without reconstructing
the investigation. Use these elements only when relevant; a narrow lookup may
be one sentence with an exact source anchor. Do not emit empty sections, require
a JSON schema, or create report files unless the task explicitly requests them.

- Outcome: the concrete answer, finding or implemented change; name inspected
  or changed paths and distinguish established facts from hypotheses.
- Evidence: exact paths and symbols, relevant callers, and commands/results for
  any checks actually run. State the inspected scope and evidence limits;
  source inspection is `static-only`, and unrun checks stay unrun.
- Boundaries: affected consumers, registrations, shared files and dependencies
  on other assignments. Describe an unchecked boundary as unresolved rather
  than implying that the whole call chain was inspected.
- Integration: remaining risks, material questions and concrete actions needed
  from the primary or another assigned owner. Findings do not authorize edits
  or additional checks.

Reviewers retain their role-specific verdict and, for every finding, severity,
an exact path/line anchor, the violated invariant and evidence limitations.
A CLEAR verdict covers only the stated inspected surface and evidence level.

Examples: a lookup returns the symbol and location; an implementation names its
changed owner and affected caller/registration; conflicting reports identify the
disputed claim and source anchors; a critical review returns its independent
verdict with the required finding evidence. These are response examples, not
additional workflow stages.

## Plans and reviews

- Plan creation is static-only. Report `done_unverified` separately from verified.
  Selected plan checks record exact command, evidence type, integer exit status
  and latest result; missing evidence remains visible.
- H reviews identify role, subject, verdict/findings, model/effort and read-only
  boundary. A finding needs severity, exact path/line and violated invariant.
- Read-only audits leave plan/task/status/archive recommendations in chat unless
  existing authority covers the selected writes. Findings grant no fix permission.
  `PlanWorkflow.md` owns plan state and independent static/schema/build/test/runtime/
  browser/model/performance/live evidence.

Severity: BLOCKER (must fix before use/merge), HIGH (likely production/live bug),
MEDIUM (important correctness/maintenance issue), LOW (cleanup), NOTE (observation).

## Subject-specific review

Load only the relevant existing guide in `Roles/`: `LowLatencyEngineer.md`
for hot paths/event semantics/recovery, `HotParserEngineer.md` for parsing,
`HotTransportEngineer.md` for session I/O, `ObservabilityEngineer.md` for
probes, and `NetworkPlacementEngineer.md` for placement evidence.
These are internal review lenses, not mandatory report fields. Missing
unrequested tests/baselines are evidence limits, not veto findings.
