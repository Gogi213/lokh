---
name: cxet-hot-path-audit
description: Trace the compiled CXET tick-to-trade path. Use for latency, allocations, locks, queues, market pump, strategy cycle, order send, or performance claims.
---

# CXET Hot Path Audit

Use this skill for the whole compiled tick-to-trade or latency surface; use the
parser or transport skill for an isolated parser or I/O boundary.

## Workflow

1. Read the repository root `AGENTS.md`, the nearest nested `AGENTS.md`, and `docs/Agents/HotPathFastLane.md`.
2. Inspect existing surface evidence. When the user requests a helper run,
   propose this command and wait for its selection:

   ```bash
   python3 tools/Codex/CxetToolbelt.py hotpath --surface all --format summary
   ```

3. Prove the touched translation unit is present in the current low-build compile commands, or prove header inclusion from one of those units. If the artifact is missing or profile-mismatched, report `surface unavailable`; do not infer a fallback surface.
4. Classify every relevant step as H0, H1, C, or D.
5. Trace the full path:

   ```text
   route/config -> selected wire -> registered runtime callback
   -> nonblocking market poll -> normalized runtime/tape publication
   -> Parser-owned typed publication -> direct Trader consumer -> inline runCycle
   -> intent/preflight -> prepared payload patch -> terminal TLS/socket write
   ```

6. Inspect allocations, growth, locks, waits, syscalls, formatting, floating point, copies, lifetimes, atomics, false sharing, buffer bounds, metrics, and fallback behavior only on the proven path.
7. Reject `simdjson`, Boost, `std::string_view`, padded JSON adapters, and direct
   libc string/memory calls outside the project primitive backend/oracle tests.
8. Rank unmeasured results as `candidate`, not `speedup`. Explain the evidence
   needed for a measured claim; unrequested baselines do not block edits.

## Permission And Review

- `изучи` or `посмотри`: remain read-only.
- `делай`: edit, but do not run verification.
- `делай и проверь`: propose concrete commands with purpose and scope; wait for
  selection under the command-package approval and task-scoped repeat rules
  in `DevelopmentWorkflow.md`.
- Full builds, sanitizers, benchmarks, runtime, live exchange, account and order
  actions need their own exact task-scoped selection.
- Final actual H0/H1 code changes require `low_latency_engineer` and one relevant
  independent specialist under `Subagents.md`; unchanged CLEAR needs no repeat.

## Output

Lead with severity findings and exact file/symbol evidence. Include low-build surface, H0/H1/C/D classification, caller chain, suspected cost, correctness risk, evidence level, and the narrow verification needed. Keep static, build/test, runtime, and live proof separate.
