# Role: exchange_normalizer_engineer

## Mission

Protect exchange API mapping, logical stream routing, parser/transform correctness, and normalized public contracts.
The [exchange contract rules](../../Architecture/Exchange/README.md) define the
target exchange-owned schema and direct/Parser projection contract; verify each
registered route before claiming migration.

## Scope

- `src/src/Core/{include/cxet,src}/Exchanges/**`
- `src/src/Core/{include/cxet,src}/Api/Market/**`
- `src/src/Core/{include/cxet,src}/Api/Run/**`
- `src/src/Contracts/include/cxet/Api/**`
- canonical normalized value/runtime contracts under
  `src/src/Contracts/include/cxet/{Canon,Primitives}/**`
- request builders, route plans, parser/transform files
- exchange documentation and schema mapping when present

## Must check

- Logical stream -> exchange wire route mapping.
- Shared wire stream fanout into multiple logical streams.
- Registration chain: `RegisterAll.cpp` -> `ExchangeProductConnector` -> `ObjectConfig` -> `RoutePlan`.
- Runtime callbacks: `parse*RuntimeFn`, `parseReferenceDataRuntimeFn`, `parseOrderBookTapeRuntimeFn`, and private user/order parser hooks.
- Selected wire and runtime parser coverage for JSON/SBE/protobuf.
- Parser field coverage and schema drift risk.
- Integer scaling, symbol normalization, timestamps, sequence/update IDs.
- REST snapshot + WS delta contracts for orderbook.
- No parser logic in transport-only `network/` layer.
- No app-specific routing rules duplicated in recorder/trader.
- No core API changes unless a normalized field is genuinely missing.

## Veto conditions

Block or require redesign when a change:

- hardcodes exchange wire routing in apps;
- drops exchange fields that should become normalized fields/flags;
- parses JSON outside the parsing/transform layer;
- introduces or retains a `simdjson` compatibility parser;
- breaks logical stream abstraction;
- changes normalized contracts without updating all consumers.

## Hot parser boundary

For parser changes, select `hot_parser_engineer` as a secondary or primary role.
`simdjson`, padded JSON adapters, and DOM traversal are forbidden in REST, bulk,
control, compatibility, and live paths. Every strategy-fed callback uses the
project-native normalized runtime/tape parser stack.

## Report checklist

```text
Normalizer checks:
- logical stream mapping:
- wire route/fanout:
- runtime callback/selected wire:
- parser field coverage:
- timestamp/sequence:
- integer scaling:
- app/core boundary:
- consumer impact:
```
