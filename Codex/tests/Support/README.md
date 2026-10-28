# Codex test support

Shared fixture state and module-loading helpers live here. Fixture classes do not inherit `unittest.TestCase` and define no case methods, so each case is discovered only in its feature module.

Keep implementation imports pointed at the canonical production owner. Add support only for fixtures used by more than one feature module.
