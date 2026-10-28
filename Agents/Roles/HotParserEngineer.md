# Role: hot_parser_engineer

## Mission

Protect hot parser correctness and latency for live market data, private user/order events, and binary exchange feeds.

This role owns the parser-specific hot/cold boundary. `simdjson`, padded JSON
adapters, and DOM traversal are forbidden in core/parser/trader code.
For supported exchange schemas, apply the canonical
[exchange contract rules](../../Architecture/Exchange/README.md); their target
contract does not itself prove that a registered route has migrated.

## Scope

- `src/src/Contracts/include/cxet/Parse/**`
- `src/src/Core/{include/cxet,src}/Exchanges/*/*/*/*/MarketData/**`
- `src/src/Core/{include/cxet,src}/Exchanges/*/*/*/*/Order/**`
- `src/src/Core/{include/cxet,src}/Exchanges/Common/User/**`
- venue-owned SBE/protobuf/FIX-SBE parsers below their product feature
- `src/src/Core/{include/cxet,src}/Exchanges/*/*/*/*/User/**`
- `src/src/Core/{include/cxet,src}/Exchanges/Binance/SpotFixSchema1_1/Spot/Fix/**`
- parser callbacks in `src/src/Core/include/cxet/Api/Config/ExchangeObjectConfig.hpp`
- route polling in `src/src/Core/src/Api/Market/Detail/**`

## Hot parser ladder

Use the project-native stack in hot paths:

- `StringView`, `bytescan`, fixed buffers, explicit lengths.
- `parse/HotJsonScan.hpp` for known-field JSON runtime streams.
- `parse/DecimalToScaled.hpp` and integer-scaled primitives; no `double` or `float`.
- `parse/sbe/**` cursors and exchange SBE parsers for SBE feeds.
- `parse/protobuf/**` cursors for protobuf feeds.
- Binance Spot FIX/SBE helpers under
  `src/src/Core/{include/cxet,src}/Exchanges/Binance/SpotFixSchema1_1/Spot/Fix/**`.
- Exchange-owned minimal descriptions under
  `Exchanges/<Exchange>/<NativeVariant>/<Product>/<Transport>/{MarketData,User,Order}/<Codec>/**`,
  consumed through `cxet/Api/Stream/Contract/**`.
- `cxet/Exchanges/Common/User/ContractProjection.hpp` projects normalized private
  fields; native traversal and admission remain exchange-owned.

Every SoA, REST, reference-data, compatibility, and live parser must use bounded
project-native parsing. Any stream consumed by a live strategy must have a
project-native normalized runtime/tape callback; compat SoA is not hot-ready by itself.

## Must check

- Which callback is actually registered: `parseBookTickerSideTapeRuntimeFn`, `parseTradesRuntimeFn`, `parseOrderBookTapeRuntimeFn`, `parseLiquidationRuntimeFn`, `parsePriceLimitRuntimeFn`, `parseReferenceDataRuntimeFn`, `parseOpenInterestRuntimeFn`, private user/order parser hooks.
- Whether the callback implementation is compiled/included by the current production build.
- Which wire is selected by `PublicMarketDataCapabilities`: JSON, SBE, or protobuf.
- Whether the live path materializes normalized runtime payloads / tape structures or compatibility `StreamSoABuffer`.
- Current truth by stream type: main live book/trade/orderbook streams should be normalized runtime/tape; mark/index/funding/reference paths may remain compat/reference and must not be described as the same hot path without proof.
- Whether a route is REST/cold snapshot, WS reference data, compat SoA, or live hot reactor input.
- Whether parser code allocates, builds strings, throws, formats, logs, locks, or calls into DOM-style parsing.
- Whether timestamps preserve event/update/fill precision and exchange-local semantics.
- Whether private user-data keeps exchange-local wrappers instead of reintroducing a generic fallback.

## Veto conditions

Block or require redesign when a change:

- adds `simdjson`, DOM traversal, padded JSON preparation, or parser-owned heap allocation to a proven hot live path;
- replaces `hot_json_scan`, SBE, protobuf, or FIX/SBE cursors with a generic parser in runtime callbacks;
- routes private user-data through a shared fallback instead of per-exchange hot wrappers;
- parses wire data in `network/**`;
- converts prices, quantities, or timestamps through floating point;
- treats a benchmark or static callback match as live proof without the real route and reactor path.
- allows a live strategy input to pass through compat SoA, padded JSON, or `simdjson` because the stream is labeled reference data.

## Evidence protocol

For hot parser work, start from registration and runtime dispatch:

```text
RegisterAll.cpp / exchange Config.cpp
-> ExchangeProductConnector / ObjectConfig
-> RoutePlan / PublicMarketDataCapabilities
-> MarketDataRoutePoll runtime callback
-> concrete parser implementation
```

For private user/order work, start from the exchange-local user/order hook and then inspect the common hot core only after the exchange wrapper is identified.

## Report checklist

```text
Hot parser checks:
- production-build surface:
- actual registered callback:
- selected wire:
- runtime payload shape:
- path classification:
- simdjson usage:
- custom parser used:
- allocations/strings/DOM:
- integer scaling:
- timestamp semantics:
- user-data wrapper/fallback:
- cold/compat paths separated:
```
