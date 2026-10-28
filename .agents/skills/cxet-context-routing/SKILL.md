---
name: cxet-context-routing
description: Select bounded CXET repository context before non-trivial multi-file work or review; use the local context map, lazy search and inspect changed-path mappings.
---

# CXET Context Routing

Use this skill before a non-trivial CXET task that may read or change more
than one repository file. It keeps context selection bounded while preserving
the existing `AGENTS.md` ownership and permission rules.

## Workflow

1. Call `cxet_context_map` with a short task hint. Pass an explicit `scope`
   when the task already identifies one; otherwise use the returned route or
   candidate scopes.
2. Read the returned route documents once per unchanged context and search only
   the selected roots. Common policy is only root AGENTS.md; load reporting at
   report time and Subagents.md for delegation/mandatory review. Capital retains
   its explicit review rules already offline. Do not follow every linked document
   or dump unrelated directories into context.
3. Choose one suitable search within the selected scope: bounded `rg` for text,
   Serena for C++ symbol relationships when its compilation coverage is available,
   or `cxet_context_search` for scoped excerpts. Routing selects the area; it does
   not require repeating the same query in every tool. Fall back only for a real
   coverage gap, unavailable tool or a new question. Output remains static-only.
   Start with paths or short matches; then read the relevant symbol or range.
   Use compact excerpts (normally up to 40 lines / 8 KiB), expanding only for a
   concrete missing dependency or invariant. Truncation means incomplete evidence:
   narrow the next read instead of repeating a larger dump. Do not truncate a
   required rule and then treat it as fully read. Load applicable policy before
   analysis or edits; a checker failure is not a substitute for that context.
4. After edits, inspect changed-path mappings and references. If the user
   selects `cxet_context_postcheck`, call it once with changed paths. Treat
   `unmapped` as a manifest review signal; returned commands are proposals,
   not permission to execute. No extra validator run is automatic.

## Boundaries

- The context tools never run builds, tests, Git, services, network calls,
  model calls, live exchange actions, or account/order operations.
- Actual checks still require the task-scoped authorization required by the
  repository `AGENTS.md`.
- If the MCP is unavailable, read `tools/Codex/CxetContextManifest.json` from
  the repository root. Select its matching scope, read `common.route_docs` and
  that scope's `route_docs`, and use `rg --files` or `rg` only within the scope's
  `roots`. Narrow the query before reading excerpts; do not compensate with a
  recursive full-repository read or start the server implicitly.
- Report `static-only` separately from test, build, runtime, browser, model,
  and live evidence.
