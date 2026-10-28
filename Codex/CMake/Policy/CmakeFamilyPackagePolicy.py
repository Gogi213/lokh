"""Compatibility facade for the central build-effect variable policy."""

from __future__ import annotations


from CMake.Policy.CmakeFamilyEffectPolicy import effect_variable


def package_shadow_variable(variable: str) -> bool:
    return effect_variable(variable)
