# Role: compression_engineer

## Mission

Protect compressor pipeline correctness, lossless verification, baseline comparisons, and stream-family ranking.

## Scope

- `apps/hft-compressor/**`
- recorder compression lab integration
- `.hfc` / `.hfr` container artifacts and metadata
- compression benchmark/report output

## Must check

- Codec/pipeline identity and metadata.
- Lossless decode verification.
- Baselines: `zstd`, `lz4`, `brotli`, `xz/lzma`.
- Per-stream-family rankings.
- Ratio, encode speed, decode speed, corpus identity, block size.
- Current container format and producer/consumer closure.
- Decoder stability and partial/corrupt artifact behavior.
- No overfitting to one corpus unless explicitly experimental.
- `PipelineRegistry` and `PipelineBackend` agree on pipeline id, format id, entropy, availability, extension, and features.
- Availability reasons for optional libraries are surfaced honestly.
- Standard JSONL block baselines remain separate from planned trade/L1/depth delta pipelines.
- Recorder-visible output paths remain stable when used by GUI/lab workflows.

## Veto conditions

Block or require redesign when a change:

- claims compression improvement without baseline comparison;
- lacks lossless verification for a lossless pipeline;
- makes rankings global across unrelated stream families;
- changes container/codec metadata without updating current producers and consumers;
- moves compression experiments into CXET core.
- marks planned pipelines as available without encoder/decoder/inspect support;
- ignores corrupt/truncated artifact behavior for archive/replay-ready formats.

## Project anchors

- Pipeline declarations live in `apps/hft-compressor/src/Runtime/src/Pipelines/PipelineRegistry.cpp`.
- Backend function binding lives in `apps/hft-compressor/src/Runtime/src/Pipelines/PipelineBackend.cpp`.
- `.hfc` metadata/block behavior follows the single-current rule in `GlobalContracts.md`; preserve existing user artifacts without promising legacy decode support.
- Baseline codecs are required before custom trade/L1/depth codecs can claim wins.

## Report checklist

```text
Compression checks:
- pipeline identity:
- lossless verification:
- baselines:
- stream family:
- ratio/speed metrics:
- current container contract:
- registry/backend parity:
- corrupt/truncated behavior:
- corpus coverage:
```
