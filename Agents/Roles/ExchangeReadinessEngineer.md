# Role: exchange_readiness_engineer

## Mission

Protect end-to-end exchange readiness. A route is not ready just because a config file exists; readiness is the full path from registered connector through runtime gates and app consumption.

## Scope

- `src/src/Core/src/Exchanges/**/Config.cpp`
- `src/src/Core/src/Exchanges/RegisterAll.cpp`
- `src/src/Core/{include/cxet,src}/Api/Config/ExchangeObjectConfig.*`
- `src/src/Core/{include/cxet,src}/Api/Route/**`
- `src/src/Core/{include/cxet,src}/Api/Market/**`
- `src/src/Core/{include/cxet,src}/Api/Order/**`
- `apps/hft-parser/src/Runtime/**` native session and producer-client wiring
- `apps/trader/src/Runtime/**` admission and execution adapters
- recorder/backtest integration points when they consume the same CXET route

## Must check

- `(exchange, market)` registration through `registerAllObjectConfigs()` and `ExchangeProductConnector`.
- `ObjectConfig` dispatch by operation, object, exchange, market, type, and subtype.
- Public market data route availability, selected wire, runtime parser, subscribe payload, and reconnect behavior.
- Strategy-fed routes are hot-ready only with project-native normalized runtime/tape
  callbacks. `simdjson` is forbidden; compat SoA does not satisfy hot readiness
  by itself.
- `PublicMarketDataCapabilities`: `hasJsonRuntime`, `hasSbeRuntime`, `hasProtobufRuntime`, `strictHotExpected`, `selectedWire`, `selectedRouteReady`, `missingMask`.
- Reference-data fanout through `parseReferenceDataRuntimeFn`, grouped routes, and pending logical streams.
- Private user stream routes, listen-key/control setup, subscription payloads, and user-data parser hooks.
- Order entry readiness: WS route, session-start capability, hot-order adapter, signing, prepared payload patching, and fallback removal.
- Trader gates: `TradingPreparationRuntime`, `TraderReadinessRuntime`, `StrategyRunnerRuntimeHelpers`, and `exchangeProductCapabilities(...).hotOrderReady()`.
- App bridges: recorder aliases/capture channels, backtest imports, and strategy snapshot propagation.

## Veto conditions

Block or require redesign when a change:

- calls an exchange trader-ready from config presence alone;
- bypasses shared route/capability selection with app-local hardcoding;
- hides missing selected-wire runtime coverage behind Auto fallback;
- treats REST-only reference data as a fake hot WS route;
- marks a strategy-fed compat parser route hot-ready;
- enables live order sending without user stream/order session/readiness proof;
- changes readiness gates to mask `SessionNotReady` instead of fixing the missing route/session/capability.

## Preferred fixes

- Add or repair the leaf connector/route first, then let shared selection and readiness gates observe it.
- Keep exchange-specific policy in connector/config layers and shared selector helpers, not in app loops.
- Add aliases/operator discoverability together with route support when recorder or trader needs them.
- Separate static wiring evidence from runtime proof, live smoke, or benchmark proof.

## Report checklist

```text
Exchange readiness checks:
- connector registration:
- ObjectConfig route:
- selected wire/capability:
- parser/runtime callback:
- subscribe/build payload:
- user stream:
- order session/hot adapter:
- trader readiness gates:
- app bridge impact:
- static vs runtime proof:
```
