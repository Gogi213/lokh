"""Static registration evidence for the current owner-local offline suites."""
from __future__ import annotations

from CMake.Root.CmakeFamilyRootGraphCommon import ROOT, parse_commands, read_required
from CMake.Root.CmakeFamilyRootProfilePolicy import _literal, _tree
from CMake.Syntax.CmakeFamilyLexer import words


def check_acceptance_sentinels(errors: list[str]) -> None:
    runner = read_required("tools/Testing/RunOffline.py", errors)
    try:
        budgets = _literal(_tree(runner, "tools/Testing/RunOffline.py"), "BUDGETS")
    except ValueError as exc:
        errors.append(f"offline registration inventory: {exc}")
        return
    if not isinstance(budgets, dict):
        errors.append("offline registration inventory: non-dictionary budgets")
        return
    from Family.Profile.CxetFamilyActivation import (
        offline_registration_inventory, validate_offline_helper,
    )
    helper = read_required("cmake/CxetOfflineTests.cmake", errors)
    if not validate_offline_helper(helper, errors):
        return
    for owner, budget in budgets.items():
        names = offline_registration_inventory(ROOT, owner, errors)
        if len(names) != budget:
            errors.append(f"owner {owner}: declared cases {len(names)} differ from canonical owner budget {budget}")
    helper_commands = parse_commands("cmake/CxetOfflineTests.cmake", helper, errors)
    for name in ("cxet_offline_cases", "cxet_add_offline_suite", "cxet_add_offline_typescript_suite", "cxet_add_offline_diagnostic"):
        declarations = [command for command in helper_commands if command.name == "function"
                        and words(command.body)[:1] == [name]]
        if len(declarations) != 1:
            errors.append(f"cmake/CxetOfflineTests.cmake: require one canonical {name} helper")
    # Keep runtime catalog/owner discrimination mandatory. A source count alone
    # never proves the executable advertised or ran the same cases.
    for required in ('"offline.${T_OWNER}.${name}"', '"offline-catalog.${T_OWNER}.${target}"',
                     '"owner:${T_OWNER};offline', '"${Python3_EXECUTABLE}"',
                     '"${CMAKE_SOURCE_DIR}/tools/Testing/CheckCaseCatalog.py"'):
        if required not in helper:
            errors.append(f"cmake/CxetOfflineTests.cmake: missing actual catalog/owner fence {required}")
