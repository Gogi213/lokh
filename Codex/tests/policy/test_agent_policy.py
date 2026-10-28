#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path
import shutil
import json
import re
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[4]
TOOLS = ROOT / "tools" / "Codex"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import AgentRouting  # noqa: E402
import CheckAgentPolicy  # noqa: E402


class AgentPolicyTests(unittest.TestCase):
    def test_current_repository_policy_is_valid(self) -> None:
        CheckAgentPolicy.validate_policy(ROOT)

    def test_routing_roles_and_managed_settings(self) -> None:
        policy = AgentRouting.load_routing(ROOT)
        self.assertEqual(policy["models"], {
            "gpt-6.1-terra": ["high", "xhigh", "max"],
            "gpt-6.1-sol": ["high", "xhigh"],
            "gpt-6-astra": ["medium", "high"],
        })
        self.assertEqual(policy["primary"], {"model": "gpt-6.1-sol", "effort": "high"})
        self.assertEqual(policy["defaultWorker"], {"model": "gpt-6.1-sol", "effort": "high"})
        self.assertEqual(policy["routes"], {
            "research": {"model": "gpt-6.1-sol", "effort": "high"},
            "design": {"model": "gpt-6.1-sol", "effort": "xhigh"},
            "patch": {"model": "gpt-6.1-sol", "effort": "high", "allowedEfforts": ["high", "xhigh"]},
            "integration": {"model": "gpt-6.1-sol", "effort": "high"},
            "review": {"model": "gpt-6.1-sol", "effort": "xhigh"},
            "mechanical": {"model": "gpt-6.1-terra", "effort": "high"},
            "escalation": {"model": "gpt-6-astra", "effort": "medium", "allowedEfforts": ["medium", "high"]},
        })
        for filename in ("researcher-sol.toml", "planner-sol.toml"):
            self.assertEqual(policy["nativeRoles"][filename]["sandbox"], "read-only")
        managed = AgentRouting.managed_config(policy)
        self.assertNotIn(("features", "goals"), managed)
        self.assertNotIn(("features", "hooks"), managed)
        self.assertNotIn(("service_tier",), managed)
        self.assertNotIn(("agents", "max_concurrent_threads_per_session"), managed)
        for key in ("model", "model_reasoning_effort", "plan_mode_reasoning_effort"):
            self.assertNotIn((key,), managed)

    def test_routing_rejects_bad_effort_and_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / AgentRouting.ROUTING_PATH
            original = path.read_text(encoding="utf-8")
            policy = json.loads(original)
            policy["routes"]["research"]["effort"] = "ultra"
            path.write_text(json.dumps(policy), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid model or effort"):
                AgentRouting.load_routing(root)
            path.write_text(original.replace('"primary":', '"primary": {}, "primary":', 1), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate key"):
                AgentRouting.load_routing(root)

    def test_coordinated_role_and_toml_drift_violates_route_semantics(self) -> None:
        cases = (
            ("researcher-sol.toml", "model", "gpt-6.1-terra"),
            ("planner-sol.toml", "model", "gpt-6.1-terra"),
            ("architect-reviewer.toml", "model", "gpt-6.1-terra"),
            ("code-simplicity-engineer.toml", "name", "other_simplicity_engineer"),
            ("code-simplicity-engineer.toml", "model", "gpt-6.1-terra"),
            ("code-simplicity-engineer.toml", "effort", "high"),
            ("code-simplicity-engineer.toml", "sandbox", "read-only"),
            ("low-latency-engineer.toml", "sandbox", "workspace-write"),
            ("mechanical-luna.toml", "model", "gpt-6.1-sol"),
            ("mechanical-luna-broad.toml", "effort", "xhigh"),
        )
        toml_fields = {"name": "name", "model": "model", "effort": "model_reasoning_effort", "sandbox": "sandbox_mode"}
        for filename, field, replacement in cases:
            with self.subTest(role=filename, field=field), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                routing_path = root / AgentRouting.ROUTING_PATH
                policy = json.loads(routing_path.read_text(encoding="utf-8"))
                role = policy["nativeRoles"][filename]
                previous = role[field]
                role[field] = replacement
                routing_path.write_text(json.dumps(policy), encoding="utf-8")
                path = root / ".codex/agents" / filename
                key = toml_fields[field]
                path.write_text(path.read_text(encoding="utf-8").replace(
                    f'{key} = "{previous}"', f'{key} = "{replacement}"', 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"nativeRoles.{filename} must match"):
                    CheckAgentPolicy.validate_policy(root)

    def test_primary_and_default_worker_must_follow_routes(self) -> None:
        for field, replacement, expected in (
            ("primary", {"model": "gpt-6.1-terra", "effort": "xhigh"}, "primary must match"),
            ("defaultWorker", {"model": "gpt-6.1-terra", "effort": "high"}, "defaultWorker must use"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / AgentRouting.ROUTING_PATH
                policy = json.loads(path.read_text(encoding="utf-8"))
                policy[field] = replacement
                path.write_text(json.dumps(policy), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected):
                    AgentRouting.load_routing(root)

    def test_required_native_role_cannot_be_removed(self) -> None:
        for filename in ("planner-sol.toml", "code-simplicity-engineer.toml", "mechanical-luna.toml"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / AgentRouting.ROUTING_PATH
                policy = json.loads(path.read_text(encoding="utf-8"))
                del policy["nativeRoles"][filename]
                path.write_text(json.dumps(policy), encoding="utf-8")
                (root / ".codex/agents" / filename).unlink()
                with self.assertRaisesRegex(ValueError, f"nativeRoles.{filename} must match"):
                    CheckAgentPolicy.validate_policy(root)

    def test_skill_evals_follow_patch_route(self) -> None:
        for field, replacement in (("model", "gpt-6.1-terra"), ("reasoningEffort", "xhigh")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "tools/Codex/SkillEvals.yaml"
                document = json.loads(path.read_text(encoding="utf-8"))
                document[field] = replacement
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"SkillEvals.*{field} mismatch"):
                    CheckAgentPolicy.validate_policy(root)

    def test_sol_research_and_design_are_allowed_but_obsolete_ban_is_not(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            nested = root / "apps/example/AGENTS.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("Use gpt-6.1-sol high for research and xhigh for design.\n")
            CheckAgentPolicy.validate_policy(root)
            nested.write_text("Sol requires an explicit user request.\n")
            with self.assertRaisesRegex(ValueError, "obsolete model routing"):
                CheckAgentPolicy.validate_policy(root)

    def test_recorder_router_is_in_live_policy_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "apps/hft-recorder/docs/Agents/RoleRouter.md"
            path.write_text(path.read_text() + "\nUse GPT-6 Luna max for mechanical work.\n")
            with self.assertRaisesRegex(ValueError, "RoleRouter.*legacy model"):
                CheckAgentPolicy.validate_policy(root)

    def test_new_app_skill_is_checked_without_global_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "apps/hft-recorder/tools/Codex/skills/local-case/SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text("Sol requires an explicit user request.\n")
            with self.assertRaisesRegex(ValueError, "local-case.*obsolete model routing"):
                CheckAgentPolicy.validate_policy(root)

    def test_astra_high_escalation_and_terra_max_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            nested = root / "apps/example/AGENTS.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "Use gpt-6.1-terra max for critical work and gpt-6-astra high for escalation.\n",
                encoding="utf-8",
            )
            CheckAgentPolicy.validate_policy(root)

    def test_approved_task_package_reuse_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "apps/trader/AGENTS.md"
            path.write_text(path.read_text() +
                            "\nReuse a selection within the task after first approval of the exact package.\n")
            CheckAgentPolicy.validate_policy(root)

    def test_unapproved_packages_are_rejected(self) -> None:
        for rule in ("Run any proposed package without first user approval.",
                     "Reuse the unapproved check package without user selection."):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "apps/trader/AGENTS.md"
                path.write_text(path.read_text() + "\n" + rule + "\n")
                with self.assertRaisesRegex(ValueError, "unapproved package"):
                    CheckAgentPolicy.validate_policy(root)

    def test_obsolete_per_attempt_consent_is_rejected(self) -> None:
        for rule in ("One confirmation authorizes one invocation.",
                     "Use single-launch consent for each check."):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "apps/trader/AGENTS.md"
                path.write_text(path.read_text() + "\n" + rule + "\n")
                with self.assertRaisesRegex(ValueError, "per-attempt consent"):
                    CheckAgentPolicy.validate_policy(root)

    def test_nested_rules_cannot_expand_an_approved_package(self) -> None:
        for rule in ("Changed commands or targets need no new selection.",
                     "Increased jobs/resources do not require new approval."):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "apps/trader/AGENTS.md"
                path.write_text(path.read_text() + "\n" + rule + "\n")
                with self.assertRaisesRegex(ValueError, "package expansion"):
                    CheckAgentPolicy.validate_policy(root)

    def test_first_package_approval_and_check_classification_are_required(self) -> None:
        for contract in ("First approval is required before launching a check package",
                         "The approved package remains authorized until task completion",
                         "Classify by effects", "Lightweight local checks", "Native build checks"):
            with self.subTest(contract=contract), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "docs/Agents/DevelopmentWorkflow.md"
                text = path.read_text()
                path.write_text(text.replace(contract, "Removed contract"))
                with self.assertRaisesRegex(ValueError, "DevelopmentWorkflow.*missing preserved anchors|missing mandatory routing pointers"):
                    CheckAgentPolicy.validate_policy(root)

    def test_nested_worker_cap_is_rejected(self) -> None:
        for rule in ("Use at most three workers concurrently.",
                     "Use no more than 3 concurrent workers.",
                     "Use at most three recorder workers concurrently."):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "apps/trader/AGENTS.md"
                path.write_text(path.read_text() + "\n" + rule + "\n")
                with self.assertRaisesRegex(ValueError, "obsolete worker cap"):
                    CheckAgentPolicy.validate_policy(root)

    def test_policy_glob_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/RuleIndex.json"
            document = json.loads(path.read_text())
            document["policyGlobs"].append("../outside/*.md")
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "unsafe rule-index policy glob"):
                CheckAgentPolicy.validate_policy(root)

    def test_rule_index_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/RuleIndex.json"
            document = json.loads(path.read_text())
            document["obsoleteField"] = True
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "rule-index"):
                CheckAgentPolicy.policy_text_paths(root)

    def test_missing_development_workflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            (root / "docs/Agents/DevelopmentWorkflow.md").unlink(missing_ok=True)
            with self.assertRaisesRegex(ValueError, "DevelopmentWorkflow"):
                CheckAgentPolicy.validate_policy(root)

    def test_missing_code_simplicity_guide_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            (root / "docs/Agents/Roles/CodeSimplicityEngineer.md").unlink()
            with self.assertRaisesRegex(ValueError, "rule owner does not exist:.*CodeSimplicityEngineer"):
                CheckAgentPolicy.validate_policy(root)

    def test_missing_canonical_policy_routes_are_rejected(self) -> None:
        for rule_id in CheckAgentPolicy.CANONICAL_RULE_ROUTES:
            with self.subTest(route=rule_id), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "docs/Agents/RuleIndex.json"
                document = json.loads(path.read_text(encoding="utf-8"))
                document["rules"] = [rule for rule in document["rules"]
                                     if rule["id"] != rule_id]
                path.write_text(json.dumps(document), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, rule_id):
                    CheckAgentPolicy.validate_policy(root)

    def test_root_must_route_canonical_policy_owners(self) -> None:
        for relative in ("docs/Agents/DevelopmentWorkflow.md", "docs/Agents/PlanWorkflow.md",
                         "docs/Agents/Subagents.md", "docs/Agents/GlobalContracts.md",
                         "docs/Agents/HotPathFastLane.md", "docs/Agents/RoleRouter.md",
                         "docs/Agents/ReportFormat.md", "docs/Agents/Superpowers.md"):
            with self.subTest(owner=relative), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "AGENTS.md"
                path.write_text(path.read_text(encoding="utf-8").replace(
                    relative, "docs/Agents/MissingOwner.md"), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "AGENTS.*missing preserved anchors|missing mandatory routing pointers"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_requires_optional_test_first_and_selected_runs(self) -> None:
        for marker in ("Test-first is optional",
                       "wait for user selection before execution"):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "docs/Agents/DevelopmentWorkflow.md"
                path.write_text(path.read_text(encoding="utf-8").replace(marker, ""),
                                encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "DevelopmentWorkflow.*missing preserved anchors|missing mandatory routing pointers"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_requires_independent_chat_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/DevelopmentWorkflow.md"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "A message does not transfer ownership", "A message transfers ownership"),
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DevelopmentWorkflow.*missing preserved anchors|missing mandatory routing pointers"):
                CheckAgentPolicy.validate_policy(root)

    def test_root_can_route_policy_without_duplicating_owner_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "AGENTS.md"
            text = " ".join(path.read_text(encoding="utf-8").split())
            for marker in ("Fast mode may be selected manually",
                           "Plan mode does not create or mutate a Goal",
                           "Messages do not transfer ownership"):
                text = text.replace(marker, "See the canonical owner")
            path.write_text(text, encoding="utf-8")
            CheckAgentPolicy.validate_policy(root)

    def test_subagents_keeps_manual_fast_and_independent_review_guards(self) -> None:
        for marker in (
            "Fast mode may be selected manually",
            "`code_simplicity_engineer`",
            "For the final integrated H0/H1 code change, run two independent read-only reviews",
            "`strategy_quant` + `low_latency_engineer` pair already during its offline stage",
        ):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / "docs/Agents/Subagents.md"
                # Match the normalized canonical wording even across wrapped lines.
                text = path.read_text(encoding="utf-8")
                path.write_text(text.replace(marker, ""), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Subagents.*missing preserved anchors|missing mandatory routing pointers"):
                    CheckAgentPolicy.validate_policy(root)

    def test_optional_tdd_history_is_not_a_required_policy_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/DevelopmentWorkflow.md"
            text = path.read_text(encoding="utf-8")
            for marker in ("RED", "GREEN", "REFACTOR"):
                text = text.replace(marker, "optional-history")
            path.write_text(text, encoding="utf-8")
            CheckAgentPolicy.validate_policy(root)

    def test_configuration_and_roles_use_requested_model_and_effort(self) -> None:
        config = tomllib.loads((ROOT / ".codex/config.toml").read_text(encoding="utf-8"))
        self.assertNotIn("model", config)
        self.assertEqual(config["model_reasoning_effort"], "high")
        self.assertEqual(config["plan_mode_reasoning_effort"], "high")
        self.assertIn(config["service_tier"], ("default", "fast", "priority"))
        self.assertIs(config["features"]["fast_mode"], True)
        self.assertIs(config["features"].get("goals"), True)
        self.assertIs(config["features"].get("hooks"), True)
        self.assertEqual(config["agents"]["default_subagent_model"], "gpt-6.1-sol")
        self.assertEqual(config["agents"]["default_subagent_reasoning_effort"], "high")
        thread_limit = config["agents"]["max_concurrent_threads_per_session"]
        self.assertIs(type(thread_limit), int)
        self.assertGreater(thread_limit, 0)
        policy = AgentRouting.load_routing(ROOT)
        for filename, expected in policy["nativeRoles"].items():
            with self.subTest(role=filename):
                role = tomllib.loads((ROOT / ".codex/agents" / filename).read_text(encoding="utf-8"))
                self.assertEqual(role["model"], expected["model"])
                self.assertEqual(role["model_reasoning_effort"], expected["effort"])
                self.assertEqual(role["sandbox_mode"], expected["sandbox"])

    def test_thread_limit_accepts_positive_configured_ceiling(self) -> None:
        for limit in (1, 20, 200):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                current = tomllib.loads(path.read_text())["agents"]["max_concurrent_threads_per_session"]
                path.write_text(path.read_text().replace(
                    f"max_concurrent_threads_per_session = {current}",
                    f"max_concurrent_threads_per_session = {limit}",
                ))
                CheckAgentPolicy.validate_policy(root)

    def test_thread_limit_rejects_nonpositive_and_noninteger_values(self) -> None:
        for limit in ("0", "-1", "true", "1.5", '"200"'):
            with self.subTest(limit=limit), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                current = tomllib.loads(path.read_text())["agents"]["max_concurrent_threads_per_session"]
                path.write_text(path.read_text().replace(
                    f"max_concurrent_threads_per_session = {current}",
                    f"max_concurrent_threads_per_session = {limit}",
                ))
                with self.assertRaisesRegex(ValueError, "max_concurrent_threads_per_session must be a positive integer"):
                    CheckAgentPolicy.validate_policy(root)

    def test_explicit_primary_selection_is_optional_and_unrestricted(self) -> None:
        cases = (
            "",  # All three keys absent.
            'model = "gpt-6.1-sol"\n',
            'model = "gpt-6-astra"\nmodel_reasoning_effort = "low"\n',
            'model = "gpt-6-luna"\nplan_mode_reasoning_effort = "ultra"\n',
            'model = "gpt-5.6-sol"\nmodel_reasoning_effort = "ultra"\n',
            'model = "unknown-future-model"\nplan_mode_reasoning_effort = "future-effort"\n',
            'model_reasoning_effort = "low"\n',
            'plan_mode_reasoning_effort = "ultra"\n',
            'model = """gpt-6-luna""" # old name is still a valid user choice\n',
            '# model = "gpt-5"\nmodel = "future-model"\n',
        )
        for selection in cases:
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                self._set_primary_selection(path, selection)
                CheckAgentPolicy.validate_policy(root)

    def test_invalid_primary_values_are_rejected(self) -> None:
        for key in ("model", "model_reasoning_effort", "plan_mode_reasoning_effort"):
            for value in ('""', '"   "', "1", "true", "[]"):
                with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as directory:
                    root = self._copy_policy(directory)
                    path = root / ".codex/config.toml"
                    self._set_primary_selection(path, f"{key} = {value}\n")
                    with self.assertRaisesRegex(ValueError, f"{key} must be a nonempty string"):
                        CheckAgentPolicy.validate_policy(root)

    def test_user_config_comments_do_not_bypass_role_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            config = root / ".codex/config.toml"
            config.write_text('model = """gpt-6-luna""" # user selection\n'
                              + config.read_text(encoding="utf-8"), encoding="utf-8")
            role = root / ".codex/agents/architect-reviewer.toml"
            role.write_text(role.read_text(encoding="utf-8").replace(
                'model = "gpt-6.1-sol"', 'model = "gpt-6-luna"'), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "legacy model"):
                CheckAgentPolicy.validate_policy(root)

    def test_primary_selectors_are_not_text_scanned_in_any_toml_string_form(self) -> None:
        fields = ("model", "model_reasoning_effort", "plan_mode_reasoning_effort")
        values = (
            '"Do not run any Git command"',
            "'Do not run any Git command'",
            '"""\nDo not run any Git command\n"""',
            "'''\nDo not run any Git command\n'''",
        )
        for field in fields:
            for value in values:
                with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                    root = self._copy_policy(directory)
                    path = root / ".codex/config.toml"
                    self._set_primary_selection(path, f'"{field}" = {value} # selected by the user\n')
                    CheckAgentPolicy.validate_policy(root)

    def test_routing_guards_apply_to_other_config_values_but_not_root_selectors(self) -> None:
        cases = (
            ("Use GPT-6 Luna xhigh for work.", "legacy model"),
            ("Sol requires an explicit user request.", "obsolete model routing"),
            ("Use GPT-6.1 Terra ultra for work.", "forbidden effort"),
        )
        for phrase, error in cases:
            for selector in ("model", "model_reasoning_effort", "plan_mode_reasoning_effort"):
                with self.subTest(phrase=phrase, selector=selector), tempfile.TemporaryDirectory() as directory:
                    root = self._copy_policy(directory)
                    path = root / ".codex/config.toml"
                    self._set_primary_selection(path, f'{selector} = "{phrase}"\n')
                    CheckAgentPolicy.validate_policy(root)
            for key in ("custom", "developer_instructions"):
                with self.subTest(phrase=phrase, key=key), tempfile.TemporaryDirectory() as directory:
                    root = self._copy_policy(directory)
                    path = root / ".codex/config.toml"
                    path.write_text(f'{key} = "{phrase}"\n' + path.read_text(encoding="utf-8"),
                                    encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, error):
                        CheckAgentPolicy.validate_policy(root)

    def test_user_profile_and_its_selectors_are_not_text_scanned(self) -> None:
        cases = (
            ("gpt-5", "gpt-6-luna", "low", "ultra"),
            ("future-profile", "unknown-future-model", "future-effort", "ultra"),
            ("Do not run any Git command", "Use GPT-6 Luna xhigh for work.",
             "Do not run any Git command", "Sol requires an explicit user request."),
        )
        for name, model, effort, plan_effort in cases:
            with self.subTest(profile=name), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                config = path.read_text(encoding="utf-8")
                path.write_text(
                    f'profile = "{name}"\n' + config
                    + f'\n[profiles."{name}"]\nmodel = "{model}"\n'
                    + f'model_reasoning_effort = "{effort}"\n'
                    + f'plan_mode_reasoning_effort = "{plan_effort}"\n',
                    encoding="utf-8")
                CheckAgentPolicy.validate_policy(root)

    def test_profile_non_selector_fields_remain_text_scanned(self) -> None:
        cases = (
            ("Use GPT-6 Luna xhigh for work.", "legacy model"),
            ("Sol requires an explicit user request.", "obsolete model routing"),
            ("Use GPT-6.1 Terra ultra for work.", "forbidden effort"),
            ("Do not run any Git command", "local read-only Git is allowed"),
        )
        for phrase, error in cases:
            with self.subTest(phrase=phrase), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                config = path.read_text(encoding="utf-8")
                path.write_text('profile = "gpt-5"\n' + config
                                + '\n[profiles."gpt-5"]\nmodel = "gpt-6-luna"\n'
                                + f'developer_instructions = "{phrase}"\n', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, error):
                    CheckAgentPolicy.validate_policy(root)

    def test_permission_guards_scan_other_active_config_values(self) -> None:
        cases = (
            'custom = "Do not run any Git command"\n',
            '[custom]\nmodel = "Do not run any Git command"\n',
            '[custom]\nvalues = ["Do not run any Git command"]\n',
            '[custom]\n"Do not run any Git command" = true\n',
        )
        for addition in cases:
            with self.subTest(addition=addition), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/config.toml"
                path.write_text(addition + path.read_text(encoding="utf-8"), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "local read-only Git is allowed"):
                    CheckAgentPolicy.validate_policy(root)

    def test_permission_guards_scan_policy_docs_but_not_config_comments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            config = root / ".codex/config.toml"
            config.write_text('# Do not run any Git command\n'
                              + config.read_text(encoding="utf-8"), encoding="utf-8")
            CheckAgentPolicy.validate_policy(root)
            nested = root / "apps/example/AGENTS.md"
            nested.parent.mkdir(parents=True)
            nested.write_text("Do not run any Git command.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "local read-only Git is allowed"):
                CheckAgentPolicy.validate_policy(root)

    def test_legacy_models_in_role_are_rejected(self) -> None:
        for model in ("gpt-" + "5.6-sol", "gpt-6-sol", "gpt-6-luna"):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                role = root / ".codex/agents/architect-reviewer.toml"
                role.write_text(
                    role.read_text(encoding="utf-8").replace("gpt-6.1-sol", model),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "legacy model"):
                    CheckAgentPolicy.validate_policy(root)

    def test_role_model_must_match_canonical_routing(self) -> None:
        for model in ("gpt-6.1-other", "gpt-6-astra", "gpt-6.1-terra"):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                role = root / ".codex/agents/hot-parser-engineer.toml"
                role.write_text(
                    role.read_text(encoding="utf-8").replace("gpt-6.1-sol", model),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "model mismatch"):
                    CheckAgentPolicy.validate_policy(root)

    def test_critical_reviewer_effort_must_match_routing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            role = root / ".codex/agents/hot-parser-engineer.toml"
            role.write_text(
                role.read_text(encoding="utf-8").replace(
                    'model_reasoning_effort = "xhigh"', 'model_reasoning_effort = "medium"'
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "model_reasoning_effort mismatch"):
                CheckAgentPolicy.validate_policy(root)

    def test_wrong_efforts_are_rejected_in_mechanical_role(self) -> None:
        for effort in ("xhigh", "ultra"):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                path = root / ".codex/agents/mechanical-luna-broad.toml"
                path.write_text(path.read_text(encoding="utf-8").replace(
                    'model_reasoning_effort = "high"', f'model_reasoning_effort = "{effort}"'),
                    encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "model_reasoning_effort mismatch|forbidden effort"):
                    CheckAgentPolicy.validate_policy(root)

    def test_manually_selected_fast_tiers_are_allowed(self) -> None:
        for tier in ("fast", "priority"):
            with self.subTest(tier=tier), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                config = root / ".codex/config.toml"
                config.write_text(
                    config.read_text(encoding="utf-8").replace(
                        'service_tier = "default"', f'service_tier = "{tier}"'
                    ),
                    encoding="utf-8",
                )
                CheckAgentPolicy.validate_policy(root)

    def test_unsupported_service_tiers_are_rejected(self) -> None:
        for tier in ("ultrafast", "flex", "unknown"):
            with self.subTest(tier=tier), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                config = root / ".codex/config.toml"
                config.write_text(
                    config.read_text(encoding="utf-8").replace(
                        'service_tier = "default"', f'service_tier = "{tier}"'
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "unsupported service_tier"):
                    CheckAgentPolicy.validate_policy(root)

    def test_nested_rule_cannot_forbid_manually_selected_fast_tiers(self) -> None:
        for rule in (
            "Fast and priority service tiers are forbidden.",
            "Fast and priority service tiers\nare forbidden.",
        ):
            with self.subTest(rule=rule), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                nested = root / "apps/example/AGENTS.md"
                nested.parent.mkdir(parents=True)
                nested.write_text(rule + "\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, r"apps/example/AGENTS\.md:.*(?:Fast|fast)"
                ):
                    CheckAgentPolicy.validate_policy(root)

    def test_disabled_fast_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            config = root / ".codex/config.toml"
            config.write_text(
                config.read_text(encoding="utf-8").replace("fast_mode = true", "fast_mode = false"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "features/fast_mode mismatch"):
                CheckAgentPolicy.validate_policy(root)

    def test_disabled_goal_or_hook_feature_is_rejected(self) -> None:
        for feature in ("goals", "hooks"):
            with self.subTest(feature=feature), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                config = root / ".codex/config.toml"
                text = config.read_text(encoding="utf-8")
                self.assertIn(f"{feature} = true", text)
                config.write_text(text.replace(f"{feature} = true", f"{feature} = false"),
                                  encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"features/{feature} mismatch"):
                    CheckAgentPolicy.validate_policy(root)

    def test_missing_plan_mode_goal_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/RuleIndex.json"
            document = json.loads(path.read_text(encoding="utf-8"))
            document["rules"] = [rule for rule in document["rules"]
                                 if rule["id"] != "plan-mode-goals"]
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "plan-mode-goals"):
                CheckAgentPolicy.validate_policy(root)

    def test_missing_goal_permission_boundary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            path = root / "docs/Agents/PlanWorkflow.md"
            text = path.read_text(encoding="utf-8")
            self.assertIn("Goal does not grant permission", text)
            path.write_text(text.replace("Goal does not grant permission", "Goal permission"),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PlanWorkflow.md"):
                CheckAgentPolicy.validate_policy(root)

    def test_nested_agent_legacy_routing_is_rejected(self) -> None:
        for policy in (
            "Use GPT-6 Luna xhigh for mechanical work.",
            "Use GPT-6 Sol medium for critical reviews.",
            "Use GPT-6.1 Terra ultra for primary work.",
        ):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                nested = root / "apps/example/deep/AGENTS.md"
                nested.parent.mkdir(parents=True)
                nested.write_text(policy, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "apps/example/deep/AGENTS.md:.*(?:legacy model|forbidden effort)"):
                    CheckAgentPolicy.validate_policy(root)

    def test_current_message_only_authorization_is_rejected(self) -> None:
        for policy in (
            "Do not run tests unless the current user message explicitly asks for them.",
            "Editing workers require the current user request explicitly authorizes implementation.",
            "Subagents must not run Git unless the current user message explicitly\ngrants that exact action.",
            "Только текущее сообщение пользователя разрешает проверки.",
            "Do not run any Git command unless the user explicitly asks for that exact action in the current message.",
            "Do not run checks without the user's explicit consent in the current message.",
        ):
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                nested = root / "apps/example/AGENTS.md"
                nested.parent.mkdir(parents=True)
                nested.write_text(policy, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "apps/example/AGENTS.md:.*current-message authorization"):
                    CheckAgentPolicy.validate_policy(root)

    def test_active_role_rejects_hyphenated_current_message_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            relative = "docs/Agents/Roles/RecorderCorpusEngineer.md"
            role = root / relative
            role.write_text(
                role.read_text(encoding="utf-8")
                + "\nVeto Git inside apps/hft-recorder without explicit current-message permission.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError, r"docs/Agents/Roles/RecorderCorpusEngineer\.md:.*current-message authorization"
            ):
                CheckAgentPolicy.validate_policy(root)

    def test_mandatory_app_routers_reject_blanket_fast_bans(self) -> None:
        for relative, rule in (
            ("apps/hft-parser/docs/agents/ROLE_ROUTER.md",
             "Fast and priority service tiers are forbidden."),
        ):
            with self.subTest(router=relative), tempfile.TemporaryDirectory() as directory:
                root = self._copy_policy(directory)
                router = root / relative
                router.write_text(router.read_text(encoding="utf-8") + "\n" + rule + "\n",
                                  encoding="utf-8")
                with self.assertRaisesRegex(
                    ValueError, relative.replace(".", r"\.") + r":.*(?:Fast|fast)"
                ):
                    CheckAgentPolicy.validate_policy(root)

    def test_persisted_authority_and_forbidden_effort_mentions_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            nested = root / "apps/example/AGENTS.md"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                "Use GPT-6.1 Terra high for mechanical_luna; Terra max is allowed for critical work.\n"
                "Checks require explicit active-task authorization; status questions do not revoke it.\n"
                "Git and account actions require separate task-scoped permission.\n"
                "Preserve max_position_usdt semantics.\n",
                encoding="utf-8",
            )
            CheckAgentPolicy.validate_policy(root)

    def test_historical_agents_are_not_active_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_policy(directory)
            history = root / "docs/agent-plans/archive/example/AGENTS.md"
            history.parent.mkdir(parents=True)
            history.write_text("Use GPT-6 Luna max.", encoding="utf-8")
            CheckAgentPolicy.validate_policy(root)

    def test_workflow_rejects_plan_only_runtime_permission(self) -> None:
        permission = (
            "Live trading/runtime binaries not covered by an exact declared "
            "non-account gate in a current execute/verify plan invocation."
        )
        for text in (permission, permission.replace(" ", "\n")):
            with self.subTest(permission=text), tempfile.TemporaryDirectory() as directory:
                root = self._copy_workflow_policy(directory)
                path = root / "docs/Agents/Superpowers.md"
                path.write_text(path.read_text(encoding="utf-8") + "\n" + text,
                                encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Superpowers.*plan-only runtime"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_requires_separate_runtime_permission(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_workflow_policy(directory)
            path = root / "docs/Agents/Superpowers.md"
            path.write_text("Use DevelopmentWorkflow.md and PlanWorkflow.md.\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Superpowers.*missing preserved anchors|missing mandatory routing pointers"):
                CheckAgentPolicy.validate_policy(root)

    def test_workflow_rejects_implementation_only_read_launch(self) -> None:
        for filename in ("mechanical-luna.toml", "mechanical-luna-broad.toml"):
            with self.subTest(role=filename), tempfile.TemporaryDirectory() as directory:
                root = self._copy_workflow_policy(directory)
                path = root / ".codex/agents" / filename
                path.write_text(path.read_text(encoding="utf-8").replace(
                    "Read-only tasks may launch without implementation authorization.",
                    "Launch only when the active request explicitly authorizes implementation."
                ), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mechanical.*read-only launch"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_requires_mechanical_edit_authority(self) -> None:
        for filename in ("mechanical-luna.toml", "mechanical-luna-broad.toml"):
            with self.subTest(role=filename), tempfile.TemporaryDirectory() as directory:
                root = self._copy_workflow_policy(directory)
                path = root / ".codex/agents" / filename
                path.write_text(path.read_text(encoding="utf-8").replace(
                    "Editing requires explicit implementation authorization for the active task.",
                    "Editing is allowed for any task."
                ), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "mechanical.*editing authorization"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_accepts_scoped_reading_and_persisted_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_workflow_policy(directory)
            CheckAgentPolicy.validate_policy(root)

    def test_workflow_requires_canonical_conflict_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_workflow_policy(directory)
            path = root / "docs/Agents/README.md"
            path.write_text("If root and local rules conflict, use the stricter rule.\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "README.*missing preserved anchors|missing mandatory routing pointers"):
                CheckAgentPolicy.validate_policy(root)

    def test_workflow_policy_owners_must_exist(self) -> None:
        for relative in ("docs/Agents/PlanWorkflow.md", "docs/Agents/Superpowers.md",
                         "docs/Agents/README.md"):
            with self.subTest(path=relative), tempfile.TemporaryDirectory() as directory:
                root = self._copy_workflow_policy(directory)
                (root / relative).unlink()
                with self.assertRaisesRegex(ValueError, "rule owner does not exist|required policy file is missing"):
                    CheckAgentPolicy.validate_policy(root)

    def test_workflow_audit_is_not_active_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self._copy_workflow_policy(directory)
            report = root / "docs/Agents/WorkflowAudit20261004.md"
            report.write_text(
                "Historical model: gpt-6-astra; gpt-5.6-sol.\n"
                "Historical rule: current user message explicitly authorizes edits.\n"
                "Historical conflict: Launch only when the active request explicitly "
                "authorizes implementation.\n", encoding="utf-8")
            CheckAgentPolicy.validate_policy(root)

    @classmethod
    def _copy_workflow_policy(cls, directory: str) -> Path:
        root = cls._copy_policy(directory)
        (root / "docs/Agents/Superpowers.md").write_text(
            "Use DevelopmentWorkflow.md and PlanWorkflow.md.\n"
            "Runtime/live actions require separate exact task-scoped authorization "
            "even when listed in a plan.\n", encoding="utf-8")
        (root / "docs/Agents/README.md").write_text(
            "Resolve conflicts using explicit user instructions and the canonical owner.\n"
            "Apply the stricter compatible safety constraint.\n", encoding="utf-8")
        for filename in ("mechanical-luna.toml", "mechanical-luna-broad.toml"):
            path = root / ".codex/agents" / filename
            text = path.read_text(encoding="utf-8")
            instructions = tomllib.loads(text)["developer_instructions"]
            path.write_text(text.replace(instructions,
                "\nRead-only tasks may launch without implementation authorization.\n"
                "Editing requires explicit implementation authorization for the active task.\n"
                "For study, review, diagnosis, planning, or status work, do not edit.\n"
                "Checks, runtime/live and Git writes need exact active-task authority.\n"
            ), encoding="utf-8")
        return root

    @staticmethod
    def _set_primary_selection(path: Path, selection: str) -> None:
        prefix, separator, tables = path.read_text(encoding="utf-8").partition("\n[")
        defaults = re.sub(r"^(?:model|model_reasoning_effort|plan_mode_reasoning_effort)\s*=.*\n?",
                          "", prefix, flags=re.MULTILINE)
        path.write_text(selection + defaults + separator + tables, encoding="utf-8")

    @staticmethod
    def _copy_policy(directory: str) -> Path:
        root = Path(directory)
        (root / ".codex").mkdir(parents=True)
        (root / "docs/Agents").mkdir(parents=True)
        (root / "tools/Codex").mkdir(parents=True)
        shutil.copy2(ROOT / ".codex/config.toml", root / ".codex/config.toml")
        shutil.copytree(ROOT / ".codex/agents", root / ".codex/agents")
        shutil.copytree(ROOT / "docs/Agents/Roles", root / "docs/Agents/Roles")
        for relative in (
            "AGENTS.md",
            "docs/Agents/Subagents.md",
            "docs/Agents/PlanWorkflow.md",
            "docs/Agents/Superpowers.md",
            "docs/Agents/README.md",
            "docs/Agents/RuleIndex.json",
            "tools/Codex/SkillEvals.yaml",
            "tools/Codex/AgentRouting.json",
            "apps/hft-parser/docs/agents/ROLE_ROUTER.md",
        ):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        workflow = ROOT / "docs/Agents/DevelopmentWorkflow.md"
        if workflow.is_file():
            shutil.copy2(workflow, root / "docs/Agents/DevelopmentWorkflow.md")
        for source in (ROOT / "apps").rglob("AGENTS.md"):
            if any(part in {".git", "build", "hft-trader"} for part in source.relative_to(ROOT).parts):
                continue
            destination = root / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for relative in CheckAgentPolicy.policy_text_paths(ROOT):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        return root


if __name__ == "__main__":
    unittest.main()
