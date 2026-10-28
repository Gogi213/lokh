"""Fail-closed property-effect policy for CXET family targets."""

from __future__ import annotations

from CMake.Policy.CmakeFamilyCommandPolicy import safe_compile_option
from Family.Targets.CxetFamilyBuildPolicy import exact_liburing_property


_LAUNCH_OR_TOOL_PROPERTIES = frozenset({
    "CROSSCOMPILING_EMULATOR",
    "RULE_LAUNCH_COMPILE",
    "RULE_LAUNCH_CUSTOM",
    "RULE_LAUNCH_LINK",
    "UNITY_BUILD_CODE_AFTER_INCLUDE",
    "UNITY_BUILD_CODE_BEFORE_INCLUDE",
})


def evaluate_target_property_effect(
    instance,
    target: str,
    mutation,
    declaration,
    contexts: dict[str, object],
    approved_external: frozenset[str],
    *,
    build_dependency_error,
) -> tuple[bool, str | None]:
    """Handle ownership-capable TARGET properties before link parsing."""
    if target in approved_external:
        return True, None if exact_liburing_property(instance, mutation) else (
            f"unapproved external target property {mutation.name} on {target}")
    if mutation.name in {"INCLUDE_DIRECTORIES", "INTERFACE_INCLUDE_DIRECTORIES"}:
        return True, (
            f"first-party include property {mutation.name} is unsupported; "
            "use reviewed target_include_directories")
    if mutation.name in {"COMPILE_OPTIONS", "INTERFACE_COMPILE_OPTIONS"}:
        bad = [
            value for value in mutation.values
            if not safe_compile_option(value)
        ]
        return True, (
            f"ownership-capable compile options {bad}" if bad else None)
    if mutation.name in {"COMPILE_FLAGS", "INTERFACE_COMPILE_FLAGS"}:
        return True, f"unsupported opaque compile property {mutation.name}"
    if mutation.name == "MANUALLY_ADDED_DEPENDENCIES":
        bad = [
            dependency for dependency in mutation.values
            if build_dependency_error(
                instance, target, dependency, contexts) is not None
        ]
        return True, (
            f"unapproved property build dependencies {bad}" if bad else None)
    if "PRECOMPILE_HEADERS" in mutation.name:
        return True, f"unsupported precompile-header property {mutation.name}"
    if (mutation.name in _LAUNCH_OR_TOOL_PROPERTIES or
            mutation.name.endswith("_COMPILER_LAUNCHER") or
            mutation.name.endswith("_LINKER_LAUNCHER")):
        return True, f"unsupported tool-launch property {mutation.name}"
    return False, None
