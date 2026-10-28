"""Load the single repository-owned Codex routing policy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROUTING_PATH = "tools/Codex/AgentRouting.json"
ROUTES = frozenset({"research", "design", "patch", "integration", "review", "mechanical", "escalation"})


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"{ROUTING_PATH}: duplicate key {key!r}")
        result[key] = value
    return result


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{ROUTING_PATH}: {label} must have fields {sorted(fields)}")
    return value


def load_routing(root: Path) -> dict[str, Any]:
    """Return a validated policy or raise ValueError; never fall back on defaults."""
    try:
        policy = json.loads((Path(root) / ROUTING_PATH).read_text(encoding="utf-8"),
                            object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{ROUTING_PATH}: cannot load routing: {error}") from error
    _object(policy, {"models", "primary", "defaultWorker", "routes", "nativeRoles"}, "policy")
    models = policy["models"]
    if not isinstance(models, dict) or not models:
        raise ValueError(f"{ROUTING_PATH}: models must be a nonempty object")
    for model, efforts in models.items():
        if (not model or not isinstance(efforts, list) or not efforts
                or any(not isinstance(effort, str) or not effort for effort in efforts)
                or len(set(efforts)) != len(efforts)):
            raise ValueError(f"{ROUTING_PATH}: invalid effort list for {model!r}")

    def selection(value: Any, label: str, *, alternatives: bool = False) -> None:
        fields = {"model", "effort"} | ({"allowedEfforts"} if alternatives else set())
        entry = _object(value, fields, label)
        model, effort = entry["model"], entry["effort"]
        if not isinstance(model, str) or model not in models or effort not in models[model]:
            raise ValueError(f"{ROUTING_PATH}: invalid model or effort for {label}")
        if alternatives:
            allowed = entry["allowedEfforts"]
            if (not isinstance(allowed, list) or not allowed or effort not in allowed
                    or any(not isinstance(item, str) or item not in models[model] for item in allowed)
                    or len(set(allowed)) != len(allowed)):
                raise ValueError(f"{ROUTING_PATH}: invalid allowedEfforts for {label}")

    selection(policy["primary"], "primary")
    selection(policy["defaultWorker"], "defaultWorker")
    routes = _object(policy["routes"], set(ROUTES), "routes")
    for name, route in routes.items():
        selection(route, f"routes.{name}", alternatives=name in {"patch", "escalation"})
    roles = policy["nativeRoles"]
    if not isinstance(roles, dict) or not roles:
        raise ValueError(f"{ROUTING_PATH}: nativeRoles must be a nonempty object")
    names: set[str] = set()
    for filename, role in roles.items():
        if not filename.endswith(".toml") or Path(filename).name != filename:
            raise ValueError(f"{ROUTING_PATH}: invalid role filename {filename!r}")
        _object(role, {"name", "model", "effort", "sandbox"}, f"nativeRoles.{filename}")
        name = role["name"]
        if not isinstance(name, str) or not name.isidentifier() or name in names:
            raise ValueError(f"{ROUTING_PATH}: invalid or duplicate role name {name!r}")
        names.add(name)
        if not isinstance(role["sandbox"], str) or role["sandbox"] not in {"read-only", "workspace-write"}:
            raise ValueError(f"{ROUTING_PATH}: invalid sandbox for {filename}")
        selection({"model": role["model"], "effort": role["effort"]}, f"nativeRoles.{filename}")

    if policy["primary"] != routes["integration"]:
        raise ValueError(f"{ROUTING_PATH}: primary must match routes.integration")
    worker, patch = policy["defaultWorker"], routes["patch"]
    if worker["model"] != patch["model"] or worker["effort"] not in patch["allowedEfforts"]:
        raise ValueError(f"{ROUTING_PATH}: defaultWorker must use routes.patch model and allowed effort")

    # These named native roles have stable semantics; compare them to their route
    # instead of hard-coding another copy of the model matrix.
    role_routes = {
        "researcher-sol.toml": ("researcher_sol", "research", "read-only"),
        "planner-sol.toml": ("planner_sol", "design", "read-only"),
        "architect-reviewer.toml": ("architect_reviewer", "review", "read-only"),
        "code-simplicity-engineer.toml": ("code_simplicity_engineer", "review", "workspace-write"),
        "hot-parser-engineer.toml": ("hot_parser_engineer", "review", "read-only"),
        "hot-transport-engineer.toml": ("hot_transport_engineer", "review", "read-only"),
        "low-latency-engineer.toml": ("low_latency_engineer", "review", "read-only"),
        "strategy-quant.toml": ("strategy_quant", "review", "read-only"),
        "trader-runtime-engineer.toml": ("trader_runtime_engineer", "review", "read-only"),
        "mechanical-luna.toml": ("mechanical_luna", "mechanical", "workspace-write"),
        "mechanical-luna-broad.toml": ("mechanical_luna_broad", "mechanical", "workspace-write"),
    }
    for filename, (name, route_name, sandbox) in role_routes.items():
        role = roles.get(filename)
        route = routes[route_name]
        if (role is None or role["name"] != name or role["model"] != route["model"]
                or role["effort"] != route["effort"] or role["sandbox"] != sandbox):
            raise ValueError(f"{ROUTING_PATH}: nativeRoles.{filename} must match routes.{route_name} and its role semantics")
    return policy


def managed_config(policy: dict[str, Any]) -> dict[tuple[str, ...], str | bool]:
    """Owned worker/feature keys; the primary selection belongs to the user."""
    worker = policy["defaultWorker"]
    return {
        ("agents", "enabled"): True,
        ("agents", "default_subagent_model"): worker["model"],
        ("agents", "default_subagent_reasoning_effort"): worker["effort"],
        ("features", "fast_mode"): True,
    }
