---
name: cxet-audit-plan
description: Audit an existing CXET durable plan statically and run only user-selected commands. Use when the user asks to verify or review a selected plan.
---

# CXET plan audit

Use this skill only for auditing an existing plan; do not use it to create or
implement a plan.

Read the root and nearest nested `AGENTS.md`, then
`docs/Agents/PlanWorkflow.md`.

- Resolve the explicit plan ID, or the only active compatible plan.
- Validate the current plan/state pair and its sealed plan hash.
- Reopen the implementation instead of trusting worker summaries.
- Propose concrete relevant command packages and obtain user approval before
  their first run. Follow task-scoped repeat rules in `DevelopmentWorkflow.md`;
  proposed checks alone do not authorize a launch. Static
  source/evidence inspection is read-only.
- Report the command, integer exit status, evidence level, concise result, and
  proposed tasks for actionable findings in chat; never fabricate passed evidence.
- Write results, add tasks, change statuses, or archive only when current
  authorization covers the corresponding selected plan/state changes.
  A read-only audit grants no new write permission. Without existing write
  authorization, leave stored files unchanged. Findings grant no new permission
  for source fixes.
- Global lightweight reminders are allowed; do not use hooks as audit or
  permission authority, or use manifests, leases, receipts, gate runners, or imported
  reviewer attestations.
- Git, full builds, benchmarks, runtime/live/network, browser, model, and
  account/order actions require separate current permission.
