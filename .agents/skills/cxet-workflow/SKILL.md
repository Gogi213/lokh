---
name: cxet-workflow
description: Create or execute a CXET durable plan for explicit cross-session work. Use when the user requests a durable plan or its execution.
---

# CXET workflow

Use this skill only when a durable cross-session plan is explicitly needed;
ordinary tasks stay in chat.

Read the root and nearest nested `AGENTS.md`, then
`docs/Agents/PlanWorkflow.md`.

- Use a file-backed plan only when the user explicitly asks for one or work
  must continue across sessions. Ordinary work uses an in-chat plan.
- Select an explicit plan ID, or the only active compatible plan. Never choose
  by recency.
- Follow the native Goal handoff in `PlanWorkflow.md`: prepare the objective
  while planning; use `get_goal` and, when eligible, `create_goal` only after
  execution is authorized and the active mode permits mutations. Goal does
  not grant permission or replace the selected plan/state evidence.
- Global lightweight reminders are allowed; do not use hooks as execution or
  permission authority, or add permission manifests, leases, receipts, gate
  runners or reviewer-attestation transport.
- `составь план` may write only the selected plan artifacts.
- `выполни план` may implement its tasks without check execution. Put proposed
  runs in a separate optional block. Follow command-package approval and
  task-scoped repeat rules in `DevelopmentWorkflow.md`; a list or an active
  Goal does not authorize a run. Implementation-only work may
  finish with unrun checks under `PlanWorkflow.md`.
- Preserve unrelated dirty changes and record only checks that actually ran.
- Git, full builds, benchmarks, runtime/live/network, browser, model, and
  account/order actions still require separate current permission.
