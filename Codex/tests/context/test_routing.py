"""Routing regressions."""
from tools.Codex.tests.Support.context import (
    ContextFixture,
    REPO_ROOT,
    TOOLS_DIR,
    importlib,
    json,
    load_module,
    mock,
    pathlib,
    subprocess,
    sys,
    tempfile,
    unittest,
)

class RoutingTests(ContextFixture, unittest.TestCase):
    def test_product_contexts_keep_separate_ownership_roots(self):
        expected = {
            "trader": "apps/trader/src",
            "hft-parser": "apps/hft-parser/src",
            "vetron": "apps/vetron/src",
        }
        for scope, root in expected.items():
            with self.subTest(scope=scope):
                payload = self.index.build_context_map(REPO_ROOT, "context routing", scope)
                self.assertEqual(payload["route_status"], "selected")
                self.assertIn(root, payload["roots"])

    def test_ordinary_contexts_do_not_preload_agent_report_or_plan_policy(self):
        manifest = self.index._load_manifest_file(REPO_ROOT)
        self.assertEqual(manifest["common"]["route_docs"], ["AGENTS.md"])
        deferred_docs = {
            "docs/Agents/Subagents.md",
            "docs/Agents/ReportFormat.md",
            "docs/Agents/PlanWorkflow.md",
        }
        for scope in manifest["scopes"]:
            # Capital retains its offline review gate; CI owns workflow policy.
            if scope in {"capital", "ci"}:
                continue
            with self.subTest(scope=scope):
                payload = self.index.build_context_map(REPO_ROOT, "scoped study", scope)
                self.assertEqual(payload["common_route_docs"], ["AGENTS.md"])
                self.assertTrue(deferred_docs.isdisjoint(payload["route_docs"]))
                self.assertIn("AGENTS.md", payload["route_docs"])

    def test_capital_routes_both_names_and_loads_inherited_policy(self):
        manifest = self.index._load_manifest_file(REPO_ROOT)
        self.assertIn(
            "docs/Agents/Subagents.md",
            manifest["scopes"]["capital"]["route_docs"],
        )
        required_docs = {
            "AGENTS.md",
            "apps/AGENTS.md",
            "apps/trading-core/AGENTS.md",
            "apps/trading-core/capital/AGENTS.md",
            "apps/trading-core/capital/README.md",
            "docs/Agents/GlobalContracts.md",
            "docs/Agents/DevelopmentWorkflow.md",
            "docs/Agents/HotPathFastLane.md",
            "docs/Agents/Subagents.md",
        }
        for hint in ("изучи capital", "изучи капитал", "Capital", "apps/trading-core/capital/"):
            with self.subTest(hint=hint):
                payload = self.index.build_context_map(REPO_ROOT, hint)
                self.assertEqual(payload["route_status"], "selected")
                self.assertEqual(payload["scope"], "capital")
                self.assertEqual(payload["evidence"], "static-only")
                self.assertIn("apps/trading-core/capital", payload["roots"])
                self.assertIn(
                    "apps/trading-core/src/Core/include/trading_core/Execution",
                    payload["roots"],
                )
                self.assertTrue(required_docs.issubset(payload["route_docs"]))
                self.assertNotIn("apps/trader/src", payload["roots"])
                self.assertNotIn("src/src/Core", payload["roots"])
                self.assertLessEqual(
                    len(self.index.render_payload(payload, "summary").encode("utf-8")),
                    6144,
                )

    def test_capital_explicit_scope_and_postcheck_cover_nested_sources(self):
        payload = self.index.build_context_map(
            REPO_ROOT, "risk execution account", "capital"
        )
        self.assertEqual(payload["scope"], "capital")
        paths = [
            "apps/trading-core/capital/AGENTS.md",
            "apps/trading-core/capital/README.md",
            "apps/trading-core/capital/include/capital/Decision/PairSizingDecision.hpp",
            "apps/trading-core/capital/src/Risk/PairAssessment.cpp",
        ]
        postcheck = self.index.build_postcheck(REPO_ROOT, paths, "capital")
        self.assertEqual(postcheck["status"], "ok")
        self.assertEqual(postcheck["unmapped"], [])
        self.assertEqual({row["path"] for row in postcheck["mapped"]}, set(paths))
        for row in postcheck["mapped"]:
            self.assertIn("capital", row["scopes"])

    def test_context_map_routes_transport_without_loading_excerpts(self):
        payload = self.index.build_context_map(
            REPO_ROOT,
            "проверь WebSocket reconnect и framing в transport",
        )
        self.assertEqual(payload["evidence"], "static-only")
        self.assertEqual(payload["route_status"], "selected")
        self.assertEqual(payload["scope"], "transport")
        self.assertIn("route_docs", payload)
        self.assertIn("roots", payload)
        self.assertIn("static_checks", payload)
        self.assertNotIn("excerpts", payload)
        self.assertLessEqual(
            len(self.index.render_payload(payload, "summary").encode("utf-8")),
            6144,
        )

    def test_ci_context_includes_canonical_skills_and_gate_checks(self):
        payload = self.index.build_context_map(
            REPO_ROOT,
            "проверь GitHub Actions Codex skills policy",
            "ci",
        )
        self.assertIn("tools/Ci", payload["roots"])
        self.assertIn(".agents/skills", payload["roots"])
        self.assertIn(
            "python3 tools/Codex/CxetContextIndex.py validate",
            payload["static_checks"],
        )
        self.assertNotIn("bash tools/Codex/InstallSkills.sh", payload["static_checks"])

    def test_ci_postcheck_maps_active_trading_core_capital_and_vetron_policy_owners(self):
        paths = [
            "apps/trading-core/AGENTS.md",
            "apps/trading-core/capital/AGENTS.md",
            "apps/vetron/AGENTS.md",
        ]
        payload = self.index.build_postcheck(REPO_ROOT, paths, "ci")
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["unmapped"], [])
        self.assertEqual({row["path"] for row in payload["mapped"]}, set(paths))
        for row in payload["mapped"]:
            self.assertEqual(row["scopes"], ["ci"])

    def test_ci_postcheck_maps_active_router_and_execution_safety_owners(self):
        paths = [
            "apps/hft-parser/docs/agents/ROLE_ROUTER.md",
            "tools/Build/tests/compile/test_containment.py",
            "tools/Testing/RunOffline.py",
            "tools/Testing/tests/offline/test_containment.py",
        ]
        paths.extend(path.relative_to(REPO_ROOT).as_posix() for path in sorted(
            (REPO_ROOT / "apps/hft-parser/docs/agents/roles").glob("*.md")))
        payload = self.index.build_postcheck(REPO_ROOT, paths, "ci")
        self.assertEqual(payload["unmapped"], [])
        self.assertEqual({row["path"] for row in payload["mapped"]}, set(paths))
        self.assertEqual(payload["status"], "ok")

    def test_ambiguous_context_map_returns_candidates_without_broad_context(self):
        for hint in ("проверь session", "capital api"):
            with self.subTest(hint=hint):
                payload = self.index.build_context_map(REPO_ROOT, hint)
                self.assertEqual(payload["route_status"], "ambiguous")
                self.assertGreaterEqual(len(payload["candidates"]), 2)
                self.assertLessEqual(len(payload["candidates"]), 3)
                self.assertNotIn("roots", payload)
                self.assertNotIn("excerpts", payload)

    def test_postcheck_maps_paths_and_reports_unmapped_paths(self):
        payload = self.index.build_postcheck(
            REPO_ROOT,
            [
                "src/src/Core/include/cxet/Network/Ws/Client/WsClient.hpp",
                "some/unmapped/file.txt",
            ],
        )
        self.assertEqual(payload["evidence"], "static-only")
        self.assertEqual(payload["unmapped"], ["some/unmapped/file.txt"])
        mapped = {item["path"]: item for item in payload["mapped"]}
        self.assertIn(
            "src/src/Core/include/cxet/Network/Ws/Client/WsClient.hpp",
            mapped,
        )
        self.assertIn("transport", mapped["src/src/Core/include/cxet/Network/Ws/Client/WsClient.hpp"]["scopes"])

    def test_cli_validate_and_map_are_static_only(self):
        validate = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "CxetContextIndex.py"), "validate"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        self.assertIn("valid", validate.stdout)

        mapped = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "CxetContextIndex.py"),
                "map",
                "--task-hint",
                "transport WebSocket",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        )
        payload = json.loads(mapped.stdout)
        self.assertEqual(payload["evidence"], "static-only")
        self.assertEqual(payload["scope"], "transport")

    def test_mcp_exposes_context_tools_and_keeps_them_static_only(self):
        mcp = load_module("cxet_mcp_server_context_test", TOOLS_DIR / "CxetMcpServer.py")
        names = {descriptor["name"] for descriptor in mcp.tool_descriptors()}
        self.assertTrue(
            {
                "cxet_context_map",
                "cxet_context_search",
                "cxet_context_postcheck",
            }.issubset(names)
        )
        mapped = mcp.call_tool(
            "cxet_context_map",
            {"task_hint": "WebSocket framing", "format": "summary"},
        )
        checked = mcp.call_tool(
            "cxet_context_postcheck",
            {
                "changed_paths": [
                    "src/src/Core/include/cxet/Network/Ws/Client/WsClient.hpp"
                ],
                "format": "summary",
            },
        )
        self.assertIn("static-only", mapped["content"][0]["text"])
        self.assertIn("static-only", checked["content"][0]["text"])


if __name__ == '__main__':
    unittest.main()
