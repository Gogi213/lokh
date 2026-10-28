#!/usr/bin/env python3
"""Fail closed on the canonical direct-source CXET family root graph."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_isolated_checker_imports() -> None:
    if not (sys.flags.isolated and sys.flags.no_site):
        print(
            "cxet family checker requires /usr/bin/python3 -I -S",
            file=sys.stderr,
        )
        raise SystemExit(2)
    sys.path.append(Path(__file__).resolve(strict=True).parent.as_posix())


_bootstrap_isolated_checker_imports()

from CMake.Policy.CmakeFamilyEffectPolicy import validate_effect_policy_microcases
from CMake.Policy.CmakeFamilyIncludeDirectories import (
    validate_target_include_directory_microcases,
)
from CMake.Policy.CmakeFamilyFallbackPolicy import check_no_family_fallback
from CMake.Root.CmakeFamilyRootPolicy import validate_root_ownership_effect_microcases
from CMake.Root.CmakeFamilyRootProfilePolicy import (
    resolve_root_profile_caches, validate_root_profile_evidence_microcases,
)


from CMake.Root.CmakeFamilyRootGraphCommon import APP_CONTRACTS, CANONICAL_ALIASES, FAMILY_DIRS, PROVIDER_ONLY_CONTRACTS, ROOT, ROOT_CMAKE, ROOT_COMPILE, generated_path, read_required, validate_generated_path_microcases
from CMake.Root.CmakeFamilyRootComposition import check_aliases, check_app_contract, check_provider_guards, check_root_graph, validate_provider_first_microcases
from CMake.Root.CmakeFamilyRootEntrypoints import (
    check_root_compile,
)
from CMake.Root.CmakeFamilyAcceptanceSentinels import check_acceptance_sentinels



def main() -> int:
    errors: list[str] = []
    validate_generated_path_microcases(errors)
    validate_effect_policy_microcases(errors)
    validate_root_ownership_effect_microcases(errors)
    validate_target_include_directory_microcases(errors)
    validate_provider_first_microcases(errors)
    validate_root_profile_evidence_microcases(errors)
    root_cmake = read_required(ROOT_CMAKE, errors)
    core_cmake = read_required("src/src/CMakeLists.txt", errors)
    root_compile = read_required(ROOT_COMPILE, errors)
    driver = read_required("tools/Build/CompileTargets.py", errors)
    offline = read_required("tools/Testing/RunOffline.py", errors)
    owners = read_required("tools/Build/ActiveBuild.py", errors)
    owner_graph = read_required("cmake/CxetCompileGraph.cmake", errors)
    profile_caches = resolve_root_profile_caches(driver, errors, offline_text=offline, owners_text=owners)

    check_root_graph(root_cmake, core_cmake, profile_caches, errors, owner_graph_text=owner_graph)
    check_root_compile(root_compile, errors)

    loaded: dict[str, str] = {}
    for relative in sorted(
            set(APP_CONTRACTS) | set(PROVIDER_ONLY_CONTRACTS) |
            set(CANONICAL_ALIASES)):
        loaded[relative] = read_required(relative, errors)
    for relative, providers in APP_CONTRACTS.items():
        check_app_contract(relative, loaded[relative], providers, errors)
    for relative, providers in PROVIDER_ONLY_CONTRACTS.items():
        check_provider_guards(
            relative, loaded[relative], providers, errors)
    for relative, aliases in CANONICAL_ALIASES.items():
        check_aliases(relative, loaded[relative], aliases, errors)

    check_acceptance_sentinels(errors)
    check_no_family_fallback(
        ROOT, FAMILY_DIRS, read_required, generated_path, errors)

    if errors:
        print("CXET family root graph check: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "CXET family root graph check: PASS "
        "(single root composition, direct providers, no sibling fallback)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
