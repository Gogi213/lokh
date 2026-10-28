---
name: cxet-runtime-contract
description: Audit CXET public runtime contracts and ownership boundaries. Use for public headers, cross-module APIs, ABI/schema, linkage, or dependency changes.
---

# CXET Runtime Contract

Use this skill for public API, ABI, schema, linkage, and ownership boundaries;
use exchange or hot-path skills for isolated venue or latency work.

## Workflow

1. Read the root and every affected nested `AGENTS.md`, then select `architect` and the specialist that owns the affected runtime surface.
2. Identify the current producer, consumer, build target, linkage boundary, and every public header or wire/storage layout involved.
3. Classify the change as core reusable API, exchange-owned policy, app runtime, strategy, recorder, parser product, or diagnostic code. Keep dependency direction from apps toward CXETCPP.
4. For ABI or schema-sensitive types, inspect size, alignment, field order, layout, integer scaling, timestamps, sequence identity, lifetime, and all consumers. Do not rely on a struct filename as layout proof.
5. Prove H0/H1/C/D placement and low-build inclusion for hot surfaces before applying hot-path restrictions or making latency claims.
6. Keep app-only UI, persistence, control policy, strategy policy, and experiments out of `src/src`. Do not create a shared abstraction until at least one stable reusable contract is explicit.
7. Follow the single-current rule in `docs/Agents/GlobalContracts.md`; update every current producer and consumer atomically. Reject invalid layouts rather than adding legacy readers or numeric version gates.
8. Report public API impact, dependency impact, current layout, required consumers to update, and evidence level.
9. Enforce the native boundary: no `simdjson`, Boost, `std::string_view`, padded
   JSON adapters, or direct libc string/memory calls outside the primitive
   backend/oracle tests. Keep exchange schemas and policy atomic and exchange-owned.

## Hard Gates

- Do not invent a public schema library target or API owned by another task.
- Do not expose transport internals merely to make an app compile.
- Do not claim ABI, build, runtime, or live compatibility without matching proof.
