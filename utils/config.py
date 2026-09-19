"""默认配置（default_config.json）加载与全局常量定义。"""
import sys
import os
import json
import tempfile

from .paths import get_data_dir


def _load_default_config():
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "default_config.json"))
        candidates.append(os.path.join(os.getcwd(), "default_config.json"))
        internal = os.path.join(os.getcwd(), "_internal", "default_config.json")
        candidates.append(internal)
    else:
        # 包目录的上一级才是项目根
        candidates.append(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "default_config.json"))
        candidates.append(os.path.join(os.getcwd(), "default_config.json"))
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return {}


_config = _load_default_config()


VERSION = _config.get("version")

DEFAULT_SETTINGS = _config.get("default_settings", {
    "general": {
        "ink_product": "none",
        "theme": "system",
        "style": "windowsvista",
        "auto_check_update": True,
        "update_never_remind": False,
        "update_skipped_version": None,
        "suppress_ifeo_warning": False,
    },
    "none": {
        "none_show_disabled_msg": True,
        "none_msg_duration": 2,
    },
    "ica_series": {
        "ica_profiles": [
            {"id": "p1", "name": "方案 1", "exe_path": "", "window_title": "", "auto_pen": False, "unhide_scheme": "scheme1"},
        ],
        "ica_active_profile_id": "p1",
    },
    "iccce": {
        "show_loading_window": True,
        "auto_pen": False,
        "thorough_hide": False,
        "loading_duration": 3,
    },
    "custom": {
        "exe_path": "",
        "show_loading_window": True,
        "loading_duration": 3,
    },
})

SHORTCUT_NAME = _config.get("shortcut_name", "希沃批注替换设置.lnk")

_icc_cfg = _config.get("icc", {})
ICC_PROTOCOL_KEY = _icc_cfg.get("protocol_key", r"icc")
ICC_COMMAND_KEY = _icc_cfg.get("command_key", r"icc\shell\open\command")
ICC_STATUS_OK = _icc_cfg.get("status_ok", "ok")
ICC_STATUS_NO_PROTOCOL = _icc_cfg.get("status_no_protocol", "no_protocol")
ICC_STATUS_BROKEN = _icc_cfg.get("status_broken", "broken")
ICC_MIN_AUTO_PEN_VERSION = tuple(_icc_cfg.get("min_auto_pen_version", [1, 7, 18, 7]))

_da_cfg = _config.get("desktop_annotation", {})
DESKTOP_ANNOTATION_DIR = _da_cfg.get("dir", r"C:\Program Files (x86)\Seewo\MiniApps\DesktopAnnotation")
_DESKTOP_ANNOTATION_EXE_NAME = _da_cfg.get("exe_name", "DesktopAnnotation.exe")
_DESKTOP_ANNOTATION_BACKUP_NAME = _da_cfg.get("backup_name", "DesktopAnnotationBackup.exe")
_DESKTOP_ANNOTATION_BAT_NAME = _da_cfg.get("bat_name", "Seewo-DesktopAnnotation-Replacement.bat")
_DA_ORIGINAL_PREFIX = os.path.splitext(_DESKTOP_ANNOTATION_EXE_NAME)[0]
_DA_BACKUP_PREFIX = os.path.splitext(_DESKTOP_ANNOTATION_BACKUP_NAME)[0]
_LEN_DA_PREFIX = len(_DA_ORIGINAL_PREFIX)
_LEN_DA_BACKUP_PREFIX = len(_DA_BACKUP_PREFIX)
DESKTOP_ANNOTATION_EXE = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_EXE_NAME)
DESKTOP_ANNOTATION_BACKUP = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_BACKUP_NAME)
DESKTOP_ANNOTATION_BAT = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_BAT_NAME)
_DA_LOG_FILE = os.path.join(tempfile.gettempdir(), "sar_desktop_annotation.log")

IFEO_BASE_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options"
_IFEO_TARGET_NAMES = ("DesktopAnnotation.exe", "DesktopAnnotationBackup.exe")

_apps_cfg = _config.get("apps", {})
_APPS_EXE_NAME = _apps_cfg.get("exe_name", "DesktopAnnotation.exe")
APPS_EXE_SHA256 = _apps_cfg.get("exe_sha256", "")

_repair_cfg = _config.get("repair", {})
REPAIR_EXE_PNG_URL = _repair_cfg.get("exe_png_url", "")
REPAIR_URL_MAP = _repair_cfg.get("url", {})

_install_cfg = _config.get("install_status", {})
INSTALL_STATUS_INSTALLED = _install_cfg.get("installed", "installed")
INSTALL_STATUS_NOT_INSTALLED = _install_cfg.get("not_installed", "not_installed")
INSTALL_STATUS_CORRUPTED = _install_cfg.get("corrupted", "corrupted")

LOCAL_APPS_EXE = os.path.join(get_data_dir(), "apps", _APPS_EXE_NAME)
