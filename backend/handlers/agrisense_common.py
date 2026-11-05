"""
AgriSense - Common Layer Forwarding Module for IDE Resolution & Local Handlers
Re-exports all definitions from backend/common_layer/python/agrisense_common.py
"""
import importlib.util
import os

_common_file = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../common_layer/python/agrisense_common.py")
)

_spec = importlib.util.spec_from_file_location("_layer_agrisense_common", _common_file)
if _spec and _spec.loader:
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    TOMATO_CLASSES = _mod.TOMATO_CLASSES
    TREATMENT_RECOMMENDATIONS = _mod.TREATMENT_RECOMMENDATIONS
    decimalize_floats = _mod.decimalize_floats
    floatify_decimals = _mod.floatify_decimals
    format_response = _mod.format_response
    format_error = _mod.format_error

__all__ = [
    "TOMATO_CLASSES",
    "TREATMENT_RECOMMENDATIONS",
    "decimalize_floats",
    "floatify_decimals",
    "format_response",
    "format_error",
]
