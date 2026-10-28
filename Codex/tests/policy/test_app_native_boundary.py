#!/usr/bin/env python3
"""Focused utility fixtures for Parser/Trader native implementation ownership."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from Family.Sources.CxetFamilyAppNativeBoundary import (  # noqa: E402
    APP_NATIVE_BOUNDARY_ROOTS,
    app_native_source_errors,
    validate_app_native_boundary,
    validate_app_native_boundary_microcases,
)


class AppNativeBoundaryTests(unittest.TestCase):
    def test_source_microcases(self) -> None:
        errors: list[str] = []
        validate_app_native_boundary_microcases(errors)
        self.assertEqual(errors, [])

    def test_all_app_src_paths_are_guarded_regardless_of_profile_or_name(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for relative in APP_NATIVE_BOUNDARY_ROOTS:
                (root / relative).mkdir(parents=True)
            fixtures = (
                "apps/hft-parser/src/Runtime/History/Legacy/Bad.CXXM",
                "apps/hft-parser/src/Process/Config/Bad.INC",
                "apps/trader/src/Projection/Diagnostic/Bad.hpp",
            )
            for relative in fixtures:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('#include "cxet/Network/Grpc/GrpcClient.hpp"\n',
                                encoding="utf-8")
            # Fixtures outside production src (and prose within it) are not
            # production implementation. No runtime subtree is exempted.
            test_path = root / "apps/trader/tests/NativeFixture.cpp"
            test_path.parent.mkdir(parents=True)
            test_path.write_text('#include "cxet/Exchanges/Finam/X.hpp"',
                                 encoding="utf-8")
            (root / "apps/trader/src/README.md").write_text(
                '#include "cxet/Exchanges/Finam/X.hpp"', encoding="utf-8")
            errors: list[str] = []
            validate_app_native_boundary(root, errors)
            self.assertEqual(len(errors), len(fixtures), errors)
            for relative in fixtures:
                self.assertTrue(any(error.startswith(relative + ":")
                                    for error in errors), errors)

    def test_diagnostic_label_does_not_exempt_a_runtime_call(self) -> None:
        source = b'''switch (value) {
          case RouteTransport::Grpc: nativeOwner.start(); return "grpc";
        }'''
        self.assertTrue(app_native_source_errors(source))

    def test_alias_chain_keeps_native_branch_visible(self) -> None:
        source = b'''using Local = Mode;
          using Mode = cxet::api::RouteTransport;
          if (selected == Local::Rest) open();'''
        self.assertTrue(app_native_source_errors(source))

    def test_generic_binding_values_and_ipc_decisions_remain_legal(self) -> None:
        source = b'''#include "cxet/Runtime/Native/NativeCredentialRuntime.hpp"
          const Product product{canon::kExchangeIdFinam, market};
          if (frame.protocol == ipc::Protocol::Request) publish(frame);
          diagnostic.transportRaw = selected.transportRaw;
          diagnostic.apiProtocolProfileRaw = product.apiProtocolProfileRaw;
          return owner.ready();'''
        self.assertEqual(app_native_source_errors(source), [])

    def test_large_returned_callback_and_binding_are_not_large_decisions(self) -> None:
        body = b"value += amount;" * 1100
        sources = (
            b"return [&](auto value) noexcept -> bool {" + body + b"return true;};",
            b"return Binding{.first = [] {" + body + b"return true;},"
            b".second = [] {" + body + b"return false;}};",
            b"return invoke([] {" + body + b"return true;}());",
            b"return [] {return [] {" + body + b"return true;};};",
        )
        for source in sources:
            with self.subTest(source=source[:60]):
                self.assertEqual(app_native_source_errors(source), [])

    def test_native_decisions_inside_large_nested_callback_are_checked(self) -> None:
        body = b"value += amount;" * 1100
        source = (b"return Binding{.callback = [] {" + body +
                  b"return [&] {if (exchange == canon::kExchangeIdFinam) "
                  b"grpcClient.start(); return route.transport == RouteTransport::Grpc;};}};")
        errors = app_native_source_errors(source)
        self.assertTrue(any("explicit protocol decision" in error for error in errors), errors)
        self.assertTrue(any("explicit venue/native decision" in error for error in errors), errors)
        self.assertFalse(any("scan bound" in error for error in errors), errors)

    def test_callback_capture_aggregate_fields_and_invocation_arguments_are_checked(self) -> None:
        body = b"value += amount;" * 1100
        predicate = b"route.transport == RouteTransport::Grpc"
        sources = (
            b"return [selected = " + predicate + b"] {" + body + b"return selected;};",
            b"return Binding{.callback = [] {" + body + b"return true;},.selected = " + predicate + b"};",
            b"return invoke([] {" + body + b"return true;}(), " + predicate + b");",
            b"return table[index](Value{" + predicate + b"});",
            b"return table[index] < Value{" + predicate + b"};",
        )
        for source in sources:
            with self.subTest(source=source[:60]):
                errors = app_native_source_errors(source)
                self.assertTrue(any("explicit protocol decision" in error for error in errors), errors)
                self.assertFalse(any("scan bound" in error for error in errors), errors)

    def test_large_actual_return_expression_retains_scan_bound(self) -> None:
        for expression in (b"value || " * 2100 + b"value",
                           b"Value{" + b"value," * 2100 + b"value}"):
            errors = app_native_source_errors(b"return " + expression + b";")
            self.assertIn("app native boundary return exceeds 4096 token scan bound", errors)

    def test_callback_result_native_evidence_reaches_outer_predicate(self) -> None:
        bodies = (
            b"[] {return RouteTransport::Grpc;}()",
            b"(([] {return RouteTransport::Grpc;}))()",
            b"[] {return [] {return RouteTransport::Grpc;}();}()",
            b"[] {using Wire = RouteTransport; return Wire::Grpc;}()",
            b"invoke([] {return RouteTransport::Grpc;})",
            b"[] {" + b"value += amount;" * 1100 + b"return RouteTransport::Grpc;}()",
        )
        for expression in bodies:
            with self.subTest(expression=expression[:60]):
                errors = app_native_source_errors(b"return " + expression + b" == route.transport;")
                self.assertTrue(any("explicit protocol decision" in error for error in errors), errors)
                self.assertFalse(any("scan bound" in error for error in errors), errors)

    def test_callback_literal_display_keeps_its_conditional_exemption(self) -> None:
        source = b'return [] {return mode == RouteTransport::Grpc ? "grpc" : "rest";};'
        self.assertEqual(app_native_source_errors(source), [])

    def test_callback_result_venue_evidence_reaches_outer_native_predicate(self) -> None:
        source = b"return [] {return canon::kExchangeIdFinam;}() == nativeOwner.exchange;"
        errors = app_native_source_errors(source)
        self.assertTrue(any("explicit venue/native decision" in error for error in errors), errors)

    def test_large_actual_condition_retains_scan_bound(self) -> None:
        source = b"if (" + b"value && " * 2100 + b"route.transport == RouteTransport::Grpc) run();"
        self.assertIn("app native boundary decision exceeds 4096 token scan bound",
                      app_native_source_errors(source))


if __name__ == "__main__":
    unittest.main()
