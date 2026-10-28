"""The root compile entrypoint delegates only to the canonical owner driver."""
from __future__ import annotations

from CMake.Policy.CmakeFamilySelectorPolicy import validate_compile_selector_authority
from CMake.Root.CmakeFamilyRootGraphCommon import read_required
from CMake.Root.CmakeFamilyRootProfilePolicy import resolve_root_profile_caches


def check_root_compile(text: str, errors: list[str]) -> None:
    validate_compile_selector_authority(text, errors)
    driver = read_required("tools/Build/CompileTargets.py", errors)
    offline = read_required("tools/Testing/RunOffline.py", errors)
    owners = read_required("tools/Build/ActiveBuild.py", errors)
    resolve_root_profile_caches(driver, errors, offline_text=offline, owners_text=owners)
