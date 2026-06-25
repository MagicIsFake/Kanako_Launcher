# core/patches.py
import minecraft_launcher_lib

def _normalize_arg_item(item):
    """Normalize a single argument dict: rename non-standard keys to standard ones."""
    if not isinstance(item, dict):
        return item
    item = item.copy()
    if "values" in item and "value" not in item:
        item["value"] = item.pop("values")
    if "compatibilityRules" in item and "rules" not in item:
        item["rules"] = item.pop("compatibilityRules")
    return item

_original_get_arguments = minecraft_launcher_lib.command.get_arguments

def _safe_get_arguments(argument_list, data, path, options, classpath):
    adapted_list = [_normalize_arg_item(i) for i in argument_list]
    return _original_get_arguments(adapted_list, data, path, options, classpath)

def apply_monkey_patches():
    """Hàm này bắt buộc phải gọi đầu tiên trước khi chạy game"""
    minecraft_launcher_lib.command.get_arguments = _safe_get_arguments