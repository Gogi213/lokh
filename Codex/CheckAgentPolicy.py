#!/usr/bin/env python3
"""Validate the repository-owned Codex model routing policy and native roles."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tomllib
from typing import Any

from AgentRouting import load_routing, managed_config
from PlanWorkflow import PlanError, validate_rule_index


ROOT = Path(__file__).resolve().parents[2]

POLICY_TEXT_FILES = (
    "AGENTS.md", "docs/Agents/DevelopmentWorkflow.md", "docs/Agents/Subagents.md",
    "docs/Agents/PlanWorkflow.md", "docs/Agents/Superpowers.md", "docs/Agents/README.md",
    "docs/Agents/RuleIndex.json", "tools/Codex/SkillEvals.yaml",
)
CANONICAL_RULE_ROUTES = {
    "global-entrypoint": "AGENTS.md",
    "development-workflow": "docs/Agents/DevelopmentWorkflow.md",
    "global-contracts": "docs/Agents/GlobalContracts.md",
    "role-routing": "docs/Agents/RoleRouter.md",
    "code-simplicity-role": "docs/Agents/Roles/CodeSimplicityEngineer.md",
    "hot-path-fast-lane": "docs/Agents/HotPathFastLane.md",
    "subagents": "docs/Agents/Subagents.md",
    "durable-plans": "docs/Agents/PlanWorkflow.md",
    "plan-mode-goals": "docs/Agents/PlanWorkflow.md",
    "reporting": "docs/Agents/ReportFormat.md",
    "superpowers": "docs/Agents/Superpowers.md",
}
LEGACY_MODEL_RE = re.compile(
    r"\b(?:gpt[-_ ]?5(?:\.\d+)?|gpt[-_ ]?6[-_ ](?:sol|luna))\b",
    re.IGNORECASE,
)
OBSOLETE_ROUTING_RE = re.compile(
    r"\b(?:Sol (?:is )?(?:used|allowed) only (?:on|with) explicit user request|"
    r"Sol requires an explicit user request|"
    r"(?:routine|ordinary) primary[^.\n]{0,100}terra[^.\n]{0,30}xhigh)\b",
    re.IGNORECASE,
)
FORBIDDEN_EFFORT_RE = re.compile(
    r"\b(?:gpt[-_ ]?6\.1[-_ ]terra|reasoning[_ ]effort)\b"
    r"[\s`:=\"']*(?:xhigh/)?ultra\b",
    re.IGNORECASE,
)
CURRENT_MESSAGE_AUTH_RE = re.compile(
    r"\bcurrent\s+user\s+(?:message|request)\s+(?:explicitly\s+)?"
    r"(?:allow\w*|authoriz\w*|ask\w*|grant\w*)\b"
    r"|\buser(?:'s)?\s+(?:explicit(?:ly)?\s+)?"
    r"(?:ask\w*|consent|permission|authoriz\w*)[^.!?]{0,160}"
    r"\bin\s+the\s+current\s+message\b"
    r"|\bexplicit\s+current[-\s]+message\s+permission\b"
    r"|текущее\s+сообщение\s+пользователя\s+(?:разреш\w*|авториз\w*)",
    re.IGNORECASE,
)
BLANKET_FAST_BAN_RE = re.compile(
    r"\bFast\s+and\s+priority\s+(?:service\s+tiers\s+)?are\s+forbidden\b",
    re.IGNORECASE,
)
UNAPPROVED_PACKAGE_RE = re.compile(
    r"\b(?:Run|Reuse)\s+(?:a|any|the)\s+(?:proposed|unapproved)\s+"
    r"(?:check\s+)?package\s+without\s+(?:first\s+)?(?:user\s+)?(?:approval|selection)\b",
    re.IGNORECASE,
)
OBSOLETE_RUN_CONSENT_RE = re.compile(
    r"\b(?:By default each build or test invocation needs separate consent|"
    r"One confirmation authorizes one invocation|single[- ]launch consent|per[- ]launch consent)\b",
    re.IGNORECASE,
)
PACKAGE_EXPANSION_RE = re.compile(
    r"\b(?:changed commands or targets|increased jobs/resources)\s+"
    r"(?:do not require|need no)\s+(?:new\s+)?(?:selection|approval|consent)\b",
    re.IGNORECASE,
)
OBSOLETE_WORKER_CAP_RE = re.compile(
    r"\b(?:at most|no more than)\s+(?:three|3)\s+(?:(?:concurrent|recorder)\s+){0,2}workers\b",
    re.IGNORECASE,
)
READ_ONLY_GIT_BAN_RE = re.compile(
    r"\b(?:Do not run any Git command|This ban includes read-only commands)\b",
    re.IGNORECASE,
)


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"{relative}: required policy file is missing")
    return path.read_text(encoding="utf-8")


def _nested(value: Any, keys: tuple[str, ...], relative: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise ValueError(f"{relative}: missing TOML key {'/'.join(keys)}")
        current = current[key]
    return current


def _expect(relative: str, field: str, actual: Any, expected: Any) -> None:
    if type(actual) is not type(expected) or actual != expected:
        raise ValueError(f"{relative}: {field} mismatch: expected {expected!r}, got {actual!r}")


def _validate_config(root: Path, policy: dict[str, Any]) -> None:
    relative = ".codex/config.toml"
    try:
        config = tomllib.loads(_read(root, relative))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{relative}: invalid TOML: {error}") from error
    # Project defaults may set effort; explicit user selectors remain unrestricted.
    for key in ("model", "model_reasoning_effort", "plan_mode_reasoning_effort"):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()):
            raise ValueError(f"{relative}: {key} must be a nonempty string when present")
    for keys, expected in managed_config(policy).items():
        _expect(relative, "/".join(keys), _nested(config, keys, relative), expected)
    # These repository features are required locally but are not synced to home.
    for feature in ("goals", "hooks"):
        keys = ("features", feature)
        _expect(relative, "/".join(keys), _nested(config, keys, relative), True)
    # Service tier and positive concurrency are user-controlled, not managed values.
    if config.get("service_tier") not in (None, "default", "fast", "priority"):
        raise ValueError(f"{relative}: unsupported service_tier: {config.get('service_tier')!r}")
    thread_limit = config["agents"].get("max_concurrent_threads_per_session")
    if thread_limit is not None and (type(thread_limit) is not int or thread_limit < 1):
        raise ValueError(f"{relative}: agents/max_concurrent_threads_per_session must be a positive integer")


def _validate_agents(root: Path, policy: dict[str, Any]) -> None:
    directory = root / ".codex/agents"
    if not directory.is_dir():
        raise ValueError(".codex/agents: required directory is missing")
    actual = {path.name for path in directory.glob("*.toml")}
    expected = set(policy["nativeRoles"])
    if actual != expected:
        raise ValueError(f".codex/agents: role inventory mismatch: expected {sorted(expected)}, got {sorted(actual)}")
    for filename, role in policy["nativeRoles"].items():
        relative = f".codex/agents/{filename}"
        try:
            document = tomllib.loads(_read(root, relative))
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"{relative}: invalid TOML: {error}") from error
        for field, key in (("name", "name"), ("model", "model"),
                           ("model_reasoning_effort", "effort"), ("sandbox_mode", "sandbox")):
            _expect(relative, field, document.get(field), role[key])
        instructions = document.get("developer_instructions")
        text = " ".join(instructions.split()) if isinstance(instructions, str) else ""
        if not text:
            raise ValueError(f"{relative}: missing role instructions")
        if role["name"] in {"mechanical_luna", "mechanical_luna_broad"}:
            if (re.search(r"\bLaunch only when\b[^.]{0,160}\bauthorizes implementation\b", text)
                    or "Read-only tasks may launch without implementation authorization." not in text):
                raise ValueError(f"{relative}: read-only launch must not require implementation authorization")
            if "Editing requires explicit implementation authorization for the active task." not in text:
                raise ValueError(f"{relative}: missing editing authorization fence")


def _validate_skill_evals(root: Path, policy: dict[str, Any]) -> None:
    relative = "tools/Codex/SkillEvals.yaml"
    try:
        document = json.loads(_read(root, relative))
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{relative}: expected JSON-compatible YAML: {error}"
        ) from error
    _expect(relative, "model", document.get("model"), policy["routes"]["patch"]["model"])
    _expect(relative, "reasoningEffort", document.get("reasoningEffort"), policy["routes"]["patch"]["effort"])


def policy_text_paths(root: Path) -> list[str]:
    """Inventory live policy owners from the existing rule index, not archives."""
    root = Path(root).resolve()
    try:
        index = validate_rule_index(root)
    except PlanError as error:
        raise ValueError(f"docs/Agents/RuleIndex.json: {error}") from error
    globs = index["policyGlobs"]
    paths = set(POLICY_TEXT_FILES)
    for pattern in globs:
        if pattern == "apps/**/AGENTS.md":
            candidates = []
            for directory, folders, files in os.walk(root / "apps", followlinks=False):
                folders[:] = sorted(folder for folder in folders
                                    if folder not in {".git", "build", "node_modules"})
                if "AGENTS.md" in files:
                    candidates.append(Path(directory) / "AGENTS.md")
        else:
            candidates = root.glob(pattern)
        for path in candidates:
            relative = path.relative_to(root)
            if any(part in {".git", "build", "node_modules"} for part in relative.parts):
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError(f"{relative}: policy path escapes repository")
            if path.is_file():
                paths.add(relative.as_posix())
    rules = index.get("rules")
    if not isinstance(rules, list):
        raise ValueError("docs/Agents/RuleIndex.json: rules must be a list")
    for rule in rules:
        if not isinstance(rule, dict) or not isinstance(rule.get("path"), str):
            raise ValueError("docs/Agents/RuleIndex.json: malformed rule route")
        if not {"id", "path", "triggers"}.issubset(rule) or set(rule) - {"id", "path", "triggers", "requiredText"}:
            raise ValueError("docs/Agents/RuleIndex.json: invalid rule route fields")
        path = Path(rule["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("docs/Agents/RuleIndex.json: unsafe rule path")
        paths.add(path.as_posix())
    for relative in paths:
        if not (root / relative).resolve().is_relative_to(root):
            raise ValueError(f"{relative}: policy path escapes repository")
    return sorted(paths)


def _config_policy_strings(root: Path) -> list[str]:
    """Inspect active TOML strings except user selections; comments are not scanned."""
    relative = ".codex/config.toml"
    try:
        config = tomllib.loads(_read(root, relative))
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{relative}: invalid TOML: {error}") from error
    selectors = {"model", "model_reasoning_effort", "plan_mode_reasoning_effort"}
    result: list[str] = []

    def visit(value: Any, *, root_table: bool = False, profile_table: bool = False) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if (root_table or profile_table) and key in selectors:
                    continue
                if root_table and key == "profile" and isinstance(child, str):
                    continue
                result.append(key)
                if root_table and key == "profiles" and isinstance(child, dict):
                    # Profile names are user identifiers; all non-selector fields
                    # of each profile remain subject to normal policy scanning.
                    for profile in child.values():
                        visit(profile, profile_table=isinstance(profile, dict))
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            result.append(value)

    visit(config, root_table=True)
    return result


def _validate_policy_text(root: Path, policy: dict[str, Any]) -> None:
    texts = {relative: _read(root, relative) for relative in policy_text_paths(root)}
    texts.update(
        {
            f".codex/agents/{filename}": _read(root, f".codex/agents/{filename}")
            for filename in policy["nativeRoles"]
        }
    )
    policy_texts = list(texts.items())
    policy_texts.extend((".codex/config.toml", value) for value in _config_policy_strings(root))
    for relative, text in policy_texts:
        if relative == "docs/Agents/Superpowers.md" and (
            "live trading/runtime binaries not covered by an exact declared non-account gate"
            in " ".join(text.split()).casefold()
        ):
            raise ValueError(f"{relative}: plan-only runtime permission conflicts with separate task authorization")
        if LEGACY_MODEL_RE.search(text):
            raise ValueError(f"{relative}: legacy model routing is forbidden")
        if OBSOLETE_ROUTING_RE.search(text):
            raise ValueError(f"{relative}: obsolete model routing conflicts with current policy")
        if FORBIDDEN_EFFORT_RE.search(text):
            raise ValueError(f"{relative}: forbidden effort in model routing")
        if CURRENT_MESSAGE_AUTH_RE.search(text):
            raise ValueError(f"{relative}: current-message authorization conflicts with persisted active-task scope")
        if BLANKET_FAST_BAN_RE.search(text):
            raise ValueError(f"{relative}: blanket Fast tier ban conflicts with manual selection")
        if UNAPPROVED_PACKAGE_RE.search(text):
            raise ValueError(f"{relative}: unapproved package conflicts with first user approval")
        if OBSOLETE_RUN_CONSENT_RE.search(text):
            raise ValueError(f"{relative}: per-attempt consent conflicts with the approved task package")
        if PACKAGE_EXPANSION_RE.search(text):
            raise ValueError(f"{relative}: package expansion requires new selection")
        if OBSOLETE_WORKER_CAP_RE.search(text):
            raise ValueError(f"{relative}: obsolete worker cap conflicts with the configured session limit")
        if READ_ONLY_GIT_BAN_RE.search(text):
            raise ValueError(f"{relative}: local read-only Git is allowed by canonical policy")
    relative = "docs/Agents/RuleIndex.json"
    try:
        index = json.loads(texts[relative])
    except json.JSONDecodeError as error:
        raise ValueError(f"{relative}: invalid rule index: {error}") from error
    rules = index.get("rules", []) if isinstance(index, dict) else []
    for rule_id, path in CANONICAL_RULE_ROUTES.items():
        if not isinstance(rules, list) or not any(
            isinstance(rule, dict) and rule.get("id") == rule_id
            and rule.get("path") == path for rule in rules
        ):
            raise ValueError(f"{relative}: missing canonical {rule_id} route")


def validate_policy(root: Path = ROOT) -> None:
    root = Path(root).resolve()
    policy = load_routing(root)
    _validate_config(root, policy)
    _validate_policy_text(root, policy)
    _validate_agents(root, policy)
    _validate_skill_evals(root, policy)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        validate_policy(_parser().parse_args(argv).root)
    except (OSError, ValueError) as error:
        print(f"agent policy: FAIL: {error}", file=sys.stderr)
        return 1
    print("agent policy: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
