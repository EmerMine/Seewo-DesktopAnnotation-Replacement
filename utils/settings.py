"""用户设置（config.json）的加载、保存与旧版扁平结构迁移。"""
import json
import copy

from .paths import get_config_path
from .config import DEFAULT_SETTINGS

_LEGACY_GENERAL_KEYS = {"ink_product", "theme", "style", "auto_check_update", "update_never_remind", "update_skipped_version", "suppress_ifeo_warning"}
_LEGACY_NONE_KEYS = {"none_show_disabled_msg", "none_msg_duration"}
_LEGACY_ICA_KEYS = {"ica_profiles", "ica_active_profile_id", "ica_exe_path", "ica_auto_pen", "ica_unhide_scheme"}
_LEGACY_ICCCE_KEYS = {"show_loading_window", "auto_pen", "thorough_hide", "loading_duration"}


def _is_legacy_flat(data):
    if not isinstance(data, dict):
        return False
    if "general" in data and "none" in data and "ica_series" in data and "iccce" in data and "custom" in data:
        return False
    return bool(set(data.keys()) & (_LEGACY_GENERAL_KEYS | _LEGACY_NONE_KEYS | _LEGACY_ICA_KEYS | _LEGACY_ICCCE_KEYS))


def _migrate_legacy_flat(data):
    result = {
        "general": {},
        "none": {},
        "ica_series": {},
        "iccce": {},
    }
    for k in list(_LEGACY_GENERAL_KEYS):
        if k in data:
            result["general"][k] = data.pop(k)
    for k in list(_LEGACY_NONE_KEYS):
        if k in data:
            result["none"][k] = data.pop(k)
    for k in list(_LEGACY_ICCCE_KEYS):
        if k in data:
            result["iccce"][k] = data.pop(k)
    ica_flat = {}
    for k in list(_LEGACY_ICA_KEYS):
        if k in data:
            ica_flat[k] = data.pop(k)
    if ica_flat:
        result["ica_series"]["ica_profiles"] = ica_flat.get("ica_profiles", [
            {"id": "p1", "name": "方案 1", "exe_path": ica_flat.get("ica_exe_path", ""),
             "window_title": "", "auto_pen": ica_flat.get("ica_auto_pen", False),
             "unhide_scheme": ica_flat.get("ica_unhide_scheme", "scheme1")},
        ])
        result["ica_series"]["ica_active_profile_id"] = ica_flat.get("ica_active_profile_id", "p1")
    for k, v in data.items():
        result[k] = v
    return result


def _deep_merge(defaults, overrides):
    result = {}
    for k, v in defaults.items():
        if isinstance(v, dict) and isinstance(overrides.get(k), dict):
            result[k] = _deep_merge(v, overrides[k])
        else:
            result[k] = overrides.get(k, v)
    for k, v in overrides.items():
        if k not in defaults:
            result[k] = v
    return result


def load_settings():
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    if _is_legacy_flat(data):
        data = _migrate_legacy_flat(data)
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except OSError:
            pass
    return _deep_merge(copy.deepcopy(DEFAULT_SETTINGS), data)


def save_settings(settings):
    config_path = get_config_path()
    if _is_legacy_flat(settings):
        settings = _migrate_legacy_flat(settings)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)
