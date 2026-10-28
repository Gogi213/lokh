# Codex tests

Feature directories own their test cases; helpers belong to the nearest `Support/` directory. Production tooling remains in `tools/Codex`.

- `policy/` — Agent policy, app native boundaries and BBO ownership.
- `cmake/` — Root profile and dialect policy.
- `family/` — Activation, prerequisite, source/include/target and current recipe models.
- `context/` — Context manifest, bounded search, closure and routing.
- `toolbelt/` — MCP transport, readiness, hot-path inventory and boundary checks.
- `doctor/` — Environment doctor.
- `plans/` — Plan lifecycle, proof, structural refusal and locking.
- `evals/` — Deterministic skill-eval runner.

Recursive discovery uses package markers without importing test cases:

```sh
python3 -m unittest discover -s tools/Codex/tests -t . -p 'test_*.py'
```

This command is a recipe, not evidence of execution; select runs under the repository workflow.
