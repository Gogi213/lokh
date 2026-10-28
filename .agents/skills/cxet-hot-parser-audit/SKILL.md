---
name: cxet-hot-parser-audit
description: Audit registered CXET parsers and wire boundaries. Use for parser registration, normalized runtime/tape payloads, native hot parsing, or parser-readiness claims.
---

# CXET Hot Parser Audit

Use this skill when parser registration, wire selection, or payload boundaries
are the subject; use the hot-path skill for the whole tick-to-trade route.
For supported exchange schemas, apply the canonical
[exchange contracts](../../../docs/Architecture/Exchange/README.md) while
checking actual registered callbacks and consumers.

## Workflow

1. Read root and nearest `AGENTS.md`, `docs/Agents/HotPathFastLane.md`, and `docs/Agents/Roles/HotParserEngineer.md`.
2. Inspect existing registration/surface evidence. For a requested helper run,
   propose this command and wait for user selection:

   ```bash
   python3 tools/Codex/CxetToolbelt.py hotpath --surface parser --format summary
   ```

3. Start from registration, never from a parser filename:

   ```text
   register_all / exchange config
   -> ExchangeProductConnector / ObjectConfig
   -> selected wire and RoutePlan
   -> MarketDataRoutePoll or private/order session hook
   -> concrete parser
   -> normalized runtime/tape/user/order payload
   -> consumer
   ```

4. Prove low-build inclusion and classify H0/H1/C/D.
5. For every strategy-fed stream, require a project-native normalized runtime/tape callback. `simdjson`, padded JSON, and DOM traversal are forbidden; compat `StreamSoABuffer` does not satisfy hot readiness by itself.
6. Check fixed capacity, no parser-owned allocation, integer scaling, timestamp/sequence semantics, bounded unescape, exchange-local private wrappers, and absence of generic parser fallback.
7. Treat static token matches as review candidates only. A nearby compat parser is not evidence about the selected live callback.

## Veto And Output

Veto concrete violations involving `simdjson`, padded JSON, DOM traversal,
generic private fallback, floating-point conversion, unbounded parsing or an
unproven callback selection. Report callback, wire, payload, consumer, path
class and evidence limits. Proposed tests need user-selected commands under
`DevelopmentWorkflow.md`; absent unrequested runs are not vetoes.
