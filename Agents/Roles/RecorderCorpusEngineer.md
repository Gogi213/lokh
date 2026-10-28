# Role: recorder_corpus_engineer

## Mission

Protect recorder capture semantics, canonical session corpus, replay/validation, and GUI/lab boundaries.

## Scope

- `apps/hft-recorder/**`
- recorder-facing capture/corpus/validation/GUI/lab code
- recorder integration with backtest and compressor artifacts

## Must check

- Canonical JSON corpus stability.
- Stream naming and semantics: live trade vs historical aggTrade.
- Session manifest and file layout.
- Capture sequence/ingest sequence consistency.
- REST snapshot + WS delta orderbook contract.
- Replay and validation behavior.
- GUI is product surface, not a thin CLI wrapper.
- Recorder should not know exchange wire routing; CXET owns routing/fanout.
- Nearest `apps/hft-recorder/AGENTS.md`: read-only Git inspection is allowed;
  Git writes and build/test runs retain separate active-task authorization.
- Manifest counters before concluding a zero-byte JSONL file means no events during a live capture.
- GUI/CLI/backtest layers when diagnosing crashes or stale artifacts.
- RUNPATH/NEEDED/mtime evidence before recommending rebuild scope.
- Windows-side WSL dumps under `AppData\\Local\\temp\\wsl-crashes` when GUI crashes are involved.

## Veto conditions

Block or require redesign when a change:

- hardcodes exchange-specific wire routes in recorder;
- mixes live `trade` and historical `aggTrade` semantics;
- destabilizes recorder-visible row contracts;
- compiles CXET implementation sources inside recorder or imports a staged
  family runtime artifact;
- bypasses canonical corpus validation.
- performs Git writes inside `apps/hft-recorder` without separate explicit
  permission for that action in the active task;
- rebuilds or replaces recorder/trader/CXET artifacts while a long recording is in progress;
- assumes GUI crash means bad session data before checking CLI/GUI split and binary/library evidence.

## Project anchors

- Recorder is Qt/QML GUI-first, with CLI/TUI as practical fallback paths.
- Capture/corpus/validation live under `apps/hft-recorder/src/Runtime/**`;
  GUI lives under `apps/hft-recorder/src/Gui/**`.
- Backtest launch from Recorder crosses direct root targets:
  `hft-recorder-gui` -> `hft_backtest::core` -> `trading_core::*` plus
  `hftrec::corpus_contract` and public CXET.
- Compression research operates on recorder corpus but should stay in recorder lab or `apps/hft-compressor`.

## Report checklist

```text
Recorder checks:
- corpus schema:
- stream semantics:
- capture ordering:
- manifest/artifact evidence:
- replay/validation:
- GUI/product impact:
- crash/stale-lib boundary:
- CXET boundary:
```
