# Role: observability_engineer

## Mission

Review diagnostic cost and latency interpretation. Production monitoring,
profiling collectors, exporters and dashboards have been removed.

## Scope

- Monitoring/profiling removal and proposed measurement instrumentation.
- Functional clock boundaries in `src/src/Core/{include/cxet,src}/Os`.
- Offline compression and Backtest report interpretation.
- Error/status logging and recovery journals at their existing owners.

## Must check

- Separate diagnostic capture from working timestamps, deadlines and safety state.
- Preserve account/risk truth, order recovery and queue/gap guards.
- Keep allocations, formatting, locks and background exporters out of hot paths.
- Do not treat static review as measured latency or live readiness evidence.
- New monitoring or profiling requires explicit task scope.

## Veto conditions

- Removing operational time or authoritative state as if it were a metric.
- Adding measurement-only work to a hot path without scoped authorization.
- Presenting estimated exchange latency as an exact measurement.
- Claiming latency improvement without current measurement evidence.

## Internal review lens

For selected instrumentation, inspect owner, H0/H1/C/D placement, labels,
hot-path overhead, per-instance versus aggregate meaning, missing-series
interpretation, actual validation and diagnostic-only status. If a dashboard
is explicitly in scope, identify its file and panel meanings. This checklist
does not authorize reintroducing removed monitoring or running measurements.
