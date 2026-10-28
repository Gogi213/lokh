---
name: cxet-exchange-readiness
description: Trace an exchange from registration to trader readiness. Use for onboarding, missing capabilities, selected-wire questions, partial venue support, or readiness claims.
---

# CXET Exchange Readiness

Use this skill for end-to-end exchange readiness; use the parser, transport, or
runtime skill when only one boundary is under review.

## Workflow

1. Read the root and every affected nested `AGENTS.md`, `docs/Agents/RoleRouter.md`, and the exchange readiness, parser, transport, and runtime role guidance needed by the task.
2. Use the repo-local readiness helper when available; treat its output as static-only source indexing, not build or live proof.
3. Trace the exact product chain:

   ```text
   register_all / exchange config
   -> ExchangeProductConnector and ObjectConfig
   -> selected public/private/order wire and RoutePlan
   -> registered normalized runtime/user/order callbacks
   -> account and trading-control hooks
   -> Parser-owned native session readiness and Trader prepared order path
   ```

4. Separate public market-data support, private user data, account reconciliation, order entry, and trader readiness. One green section never proves the others.
5. Keep endpoints, subscribe grammar, auth, parsing quirks, and capability policy in exchange-owned code. Shared code may contain only generic bounded contracts.
6. Fail closed on missing parser, schema, route, account hook, session proof, or selected-wire coverage. Do not add compatibility or transport fallback to make a capability appear ready.
7. Report static, build/test, runtime, and live evidence separately and name the narrow missing proof.

## Review

Select `exchange_normalizer_engineer` and `exchange_readiness_engineer`; add `hot_parser_engineer`, `hot_transport_engineer`, `trader_runtime_engineer`, and `low_latency_engineer` when their surfaces are involved.
