import sys
import os
import re
import time
import json
import copy
import glob
import hashlib
import base64
import urllib.request
import subprocess
import tempfile
import ctypes
import struct
import winreg
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

try:
    from PIL import Image as _PILImage
    import numpy as _numpy
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False


def _load_default_config():
    candidates = []
    if getattr(sys, 'frozen', False):
        candidates.append(os.path.join(os.path.dirname(sys.executable), "default_config.json"))
        candidates.append(os.path.join(os.getcwd(), "default_config.json"))
        internal = os.path.join(os.getcwd(), "_internal", "default_config.json")
        candidates.append(internal)
    else:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_config.json"))
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
_DESKTOP_ANNOTATION_BAT_NAME = _da_cfg.get("bat_name", "Seewo-DeskopAnnotation-Replacement.ps1")
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


_DEBUG_FORCED = False


def set_debug_mode(enabled: bool):
    """强制启用或禁用调试模式（由命令行参数 ``-debug`` 调用）。"""
    global _DEBUG_FORCED
    _DEBUG_FORCED = bool(enabled)


def _is_debug():
    """检测当前是否处于调试模式。

    触发条件（任一满足即为 True）：
      - 调试器已附加（pdb / pydevd / VS Code 调试器等，``sys.gettrace()`` 非 None）
      - 通过 ``set_debug_mode(True)`` 强制启用（例如 ``-debug`` 命令行参数）
    """
    return sys.gettrace() is not None or _DEBUG_FORCED


def _debug_log(msg):
    """调试日志输出：仅在调试模式下带时间戳输出到 stderr。"""
    if _is_debug():
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] [DEBUG] {msg}", file=sys.stderr, flush=True)


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


LOCAL_APPS_EXE = os.path.join(get_base_dir(), "apps", _APPS_EXE_NAME)


def get_data_dir():
    cwd = os.getcwd()
    internal = os.path.join(cwd, "_internal")
    return internal if os.path.isdir(internal) else cwd


def get_config_path():
    return os.path.join(get_data_dir(), "config.json")


def _is_win11():
    ver = sys.getwindowsversion()
    return ver.build >= 22000


def get_icon_path():
    return os.path.join(get_data_dir(), "resources", "icon.ico")


def get_shield_icon_path():
    filename = "win11.ico" if _is_win11() else "win10.ico"
    return os.path.join(get_data_dir(), "resources", "admin", filename)


def _log(msg, level="info"):
    try:
        log_path = os.path.join(get_data_dir(), "sar.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level.upper()}] {msg}\n")
    except Exception:
        pass


def _scan_original_da_files(dir_path):
    """返回目录中所有以 DesktopAnnotation 开头但不以 DesktopAnnotationBackup 开头的文件路径。"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    try:
        for name in os.listdir(dir_path):
            if name.startswith(_DA_ORIGINAL_PREFIX) and not name.startswith(_DA_BACKUP_PREFIX):
                result.append(os.path.join(dir_path, name))
    except OSError:
        pass
    return result


def _scan_backup_da_files(dir_path):
    """返回目录中所有以 DesktopAnnotationBackup 开头的文件路径。"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    try:
        for name in os.listdir(dir_path):
            if name.startswith(_DA_BACKUP_PREFIX):
                result.append(os.path.join(dir_path, name))
    except OSError:
        pass
    return result


def _find_primary_exe(paths):
    """从文件路径列表中找到 .exe 文件，找不到返回 None。"""
    for p in paths:
        if p.lower().endswith(".exe"):
            return p
    return None


_THEME_TO_SCHEME = {
    "dark": Qt.ColorScheme.Dark,
    "light": Qt.ColorScheme.Light,
    "system": Qt.ColorScheme.Unknown,
}


def apply_style(style_name):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(style_name) # type: ignore
    app.setPalette(QPalette()) # type: ignore


def apply_theme(theme):
    scheme = _THEME_TO_SCHEME.get(theme, Qt.ColorScheme.Unknown)
    QApplication.styleHints().setColorScheme(scheme) # type: ignore
    QApplication.instance().setPalette(QPalette()) # type: ignore


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


def run_protocol(uri):
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(
                ["cmd", "/c", "start", "", uri],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    except Exception:
        pass


def sha256_file(path):
    """计算文件 SHA-256 哈希（十六进制小写字符串）。文件不存在返回 None。"""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def kill_process_by_path(exe_path):
    """强制结束所有命令行与 exe_path 匹配的进程（taskkill /IM 不支持完整路径匹配，
    这里用 wmic 列出命令行后筛选）。忽略找不到进程的情况。"""
    if not os.path.exists(exe_path):
        return
    try:
        result = subprocess.run(
            ["wmic", "process", "where",
             f"name='{os.path.basename(exe_path)}'",
             "get", "processid,commandline", "/format:csv"],
            capture_output=True, text=True, encoding="mbcs", errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return
    exe_lower = exe_path.lower().replace("/", "\\")
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Node") or line.lower().startswith("commandline"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        cmdline = ",".join(parts[1:-1]).lower().replace("/", "\\")
        pid = parts[-1].strip()
        if not pid or not pid.isdigit():
            continue
        if exe_lower in cmdline:
            try:
                subprocess.run(
                    ["taskkill", "/f", "/pid", pid],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass


START_MENU_LNK = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                              r"Microsoft\Windows\Start Menu\Programs", SHORTCUT_NAME)
DESKTOP_LNK = os.path.join(os.path.expanduser("~"), "Desktop", SHORTCUT_NAME)


def shortcut_exists(kind):
    if kind == "start_menu":
        return os.path.exists(START_MENU_LNK)
    if kind == "desktop":
        return os.path.exists(DESKTOP_LNK)
    return False


def _ps_quote(s):
    """将任意字符串安全嵌入 PowerShell 单引号字符串（把 ' 替换成 ''）。"""
    return s.replace("'", "''")


def create_shortcut(kind):
    """在开始菜单或桌面创建快捷方式。

    根据运行模式自动选择目标：
      - 源码模式 (sys.frozen=False): TargetPath=pythonw.exe, Arguments='"main.py" -settings'
      - 打包模式 (sys.frozen=True):  TargetPath=Annotation.exe, Arguments='-settings'
    """
    if kind == "start_menu":
        lnk = START_MENU_LNK
    elif kind == "desktop":
        lnk = DESKTOP_LNK
    else:
        return False

    base = get_base_dir()

    if getattr(sys, 'frozen', False):
        target = os.path.join(base, "Annotation.exe")
        arguments = "-settings"
        icon = target
    else:
        target = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        main_py = os.path.join(base, "main.py")
        arguments = f'"{main_py}" -settings'
        icon_path = get_icon_path()
        icon = icon_path if os.path.exists(icon_path) else sys.executable

    workdir = base

    ps_script = (
        "$wsh = New-Object -ComObject WScript.Shell;"
        f"$s = $wsh.CreateShortcut('{_ps_quote(lnk)}');"
        f"$s.TargetPath = '{_ps_quote(target)}';"
        f"$s.Arguments = '{_ps_quote(arguments)}';"
        f"$s.WorkingDirectory = '{_ps_quote(workdir)}';"
        f"$s.IconLocation = '{_ps_quote(icon)},0';"
        "$s.Save()"
    )

    try:
        encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
        subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"快捷方式创建失败 (exit={e.returncode}): "
            f"{e.stderr.decode('mbcs', errors='ignore').strip() or e.stdout.decode('mbcs', errors='ignore').strip()}"
        ) from e
    except Exception as e:
        raise RuntimeError(str(e)) from e


def delete_shortcut(kind):
    if kind == "start_menu":
        lnk = START_MENU_LNK
    elif kind == "desktop":
        lnk = DESKTOP_LNK
    else:
        return
    if os.path.exists(lnk):
        os.remove(lnk)


def _critical(text):
    msg = QMessageBox(QMessageBox.Critical, "希沃批注替换", text) # type: ignore
    msg.setWindowIcon(QIcon(get_icon_path()))
    msg.exec()


def check_icc_ce_url_protocol():
    """检测 icc:// URL 协议是否已正确注册。

    返回值：
      - ICC_STATUS_OK          协议存在且命令路径有效
      - ICC_STATUS_NO_PROTOCOL 注册表 HKEY_CLASSES_ROOT\\icc 不存在
      - ICC_STATUS_BROKEN      协议存在但命令中的可执行文件路径无效
    """
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ICC_PROTOCOL_KEY)
    except FileNotFoundError:
        return ICC_STATUS_NO_PROTOCOL
    except Exception:
        return ICC_STATUS_NO_PROTOCOL

    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ICC_COMMAND_KEY)
        cmd, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
    except FileNotFoundError:
        return ICC_STATUS_BROKEN
    except Exception:
        return ICC_STATUS_BROKEN

    exe_path = _extract_exe_from_command(cmd)
    if exe_path and os.path.exists(exe_path):
        return ICC_STATUS_OK
    return ICC_STATUS_BROKEN


def get_icc_ce_exe_path():
    """从注册表读取 ICC-CE 可执行文件路径。找不到或损坏时返回 None。"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ICC_COMMAND_KEY)
        cmd, _ = winreg.QueryValueEx(key, "")
        winreg.CloseKey(key)
    except Exception:
        return None
    return _extract_exe_from_command(cmd)


def check_ifeo_hijack():
    """检测 IFEO 注册表中是否存在 DesktopAnnotation 相关的劫持项。

    同时检查 HKEY_LOCAL_MACHINE 和 HKEY_CURRENT_USER，使用 KEY_WOW64_64KEY
    避免 32 位 Python 在 64 位系统上访问 WOW6432Node 的重定向问题。

    返回值: list of dict，每项含 hive ("HKLM"/"HKCU")、name (子键名)、
            has_debugger (bool)、debugger (str|None)。
            列表为空表示未检测到劫持。
    """
    hijacks = []
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    for hive, hive_name in (
        (winreg.HKEY_LOCAL_MACHINE, "HKLM"),
        (winreg.HKEY_CURRENT_USER, "HKCU"),
    ):
        try:
            base = winreg.OpenKey(hive, IFEO_BASE_KEY, 0, access)
        except FileNotFoundError:
            continue
        except PermissionError:
            continue
        try:
            for target_name in _IFEO_TARGET_NAMES:
                try:
                    subkey = winreg.OpenKey(base, target_name, 0, access)
                except FileNotFoundError:
                    continue
                except PermissionError:
                    continue
                debugger_val = None
                try:
                    debugger_val, _ = winreg.QueryValueEx(subkey, "Debugger")
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
                # 检查是否有任意非默认值（有值的 key 才认为是劫持）
                value_count = 0
                try:
                    value_count, _, _ = winreg.QueryInfoKey(subkey)
                except OSError:
                    pass
                winreg.CloseKey(subkey)
                if debugger_val is not None or value_count > 0:
                    hijacks.append({
                        "hive": hive_name,
                        "name": target_name,
                        "has_debugger": debugger_val is not None,
                        "debugger": debugger_val,
                    })
        finally:
            winreg.CloseKey(base)
    return hijacks


def remove_ifeo_hijacks_async():
    """删除所有 DesktopAnnotation 相关的 IFEO 劫持项。

    HKCU 项直接删除（无需管理员权限），HKLM 项通过生成临时 PowerShell 脚本以管理员
    权限异步执行（ShellExecuteW runas 不阻塞）。调用方无需等待完成。
    """
    access = winreg.KEY_ALL_ACCESS | winreg.KEY_WOW64_64KEY
    # 1) 先处理 HKCU（不需要管理员权限）
    hkcu_removed = []
    for target_name in _IFEO_TARGET_NAMES:
        try:
            base = winreg.OpenKey(winreg.HKEY_CURRENT_USER, IFEO_BASE_KEY, 0, access)
        except FileNotFoundError:
            continue
        try:
            try:
                winreg.DeleteKey(base, target_name)
                hkcu_removed.append(target_name)
            except FileNotFoundError:
                pass
        except OSError:
            pass
        finally:
            winreg.CloseKey(base)

    # 2) HKLM 需要管理员权限 — 生成 PowerShell 脚本并以 runas 启动
    #    使用 PowerShell 5.1 的 Remove-Item -Path 'HKLM:\...' 语法，等价于 reg delete
    ps1_lines = [
        "$ErrorActionPreference = 'Stop'",
    ]
    for target_name in _IFEO_TARGET_NAMES:
        hive_path = f"HKLM:\\{IFEO_BASE_KEY}\\{target_name}"
        ps1_lines.append(
            f"Remove-Item -Path '{hive_path}' -Recurse -Force -ErrorAction SilentlyContinue"
        )
    _run_elevated("\r\n".join(ps1_lines) + "\r\n")

    return hkcu_removed


def get_file_version(path):
    """读取 Windows 可执行文件的 FILEVERSION，返回 (major, minor, patch, build) 元组。

    使用 ctypes 调用 GetFileVersionInfo 系列 Win32 API，无需 pywin32 依赖。
    读取失败时返回 None。
    """
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path, None, size, buf):
            return None

        # 读取 Translation 块（LANGID + CODEPAGE 对）
        res_ptr = ctypes.c_void_p()
        res_len = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            buf, r"\VarFileInfo\Translation", ctypes.byref(res_ptr), ctypes.byref(res_len)
        ):
            return None
        # 取第一对 (LANGID, CODEPAGE)，各占 2 字节，共 4 字节
        data = ctypes.string_at(res_ptr, res_len.value)
        lang_id, codepage = struct.unpack_from("<HH", data, 0)

        query = f"\\StringFileInfo\\{lang_id:04x}{codepage:04x}\\FileVersion"
        if not ctypes.windll.version.VerQueryValueW(
            buf, query, ctypes.byref(res_ptr), ctypes.byref(res_len)
        ):
            return None
        # 注意：res_len 是字符数，含末尾 null
        version_str = ctypes.wstring_at(res_ptr, res_len.value - 1)
        return _parse_version_tuple(version_str)
    except Exception:
        return None


def _parse_version_tuple(s):
    """将 "1.7.18.7" 或 "1, 7, 18, 7" 等格式解析为 (1, 7, 18, 7)。"""
    if not s:
        return None
    parts = re.split(r"[.,\s]+", s.strip())
    result = []
    for p in parts:
        m = re.match(r"(\d+)", p)
        if m:
            result.append(int(m.group(1)))
    if not result:
        return None
    while len(result) < 4:
        result.append(0)
    return tuple(result[:4])


def _version_tuple_to_string(ver):
    """将 (1, 0, 0, 133) 转为 "1.0.0.133"。"""
    if ver is None:
        return None
    return ".".join(str(p) for p in ver)


def _version_string_to_tuple(s):
    """将 JSON 键 "1.0.0.133" 转为版本元组。"""
    parts = s.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _get_latest_version_key(url_map):
    """从版本→URL列表的映射中，按语义版本号比较选取最大的版本键。"""
    if not url_map:
        return None
    best_key = None
    best_tuple = None
    for key in url_map:
        t = _version_string_to_tuple(key)
        if t is None:
            continue
        if best_tuple is None or t > best_tuple:
            best_tuple = t
            best_key = key
    return best_key


def get_desktop_annotation_version():
    """读取希沃桌面批注 exe 的版本号。

    优先扫描 DESKTOP_ANNOTATION_DIR 中所有 DesktopAnnotationBackup*.exe；
    若不存在或读取失败，再扫描 DesktopAnnotation*.exe（排除 Backup*）。
    返回 (version_tuple, source_path)；若均读取失败则返回 (None, None)。
    """
    for paths in (_scan_backup_da_files(DESKTOP_ANNOTATION_DIR),
                  _scan_original_da_files(DESKTOP_ANNOTATION_DIR)):
        primary = _find_primary_exe(paths)
        if primary and os.path.exists(primary):
            ver = get_file_version(primary)
            if ver is not None:
                return ver, primary
    return None, None


def get_repair_urls_for_version(ver_tuple):
    """根据版本元组查找修复安装包的下载链接列表。

    优先匹配完全对应的版本；若找不到则回退到最新版本；
    若映射表本身为空则回退到默认 REPAIR_EXE_PNG_URL。
    返回 list[str]（可能为空列表）。
    """
    url_map = REPAIR_URL_MAP
    if not url_map:
        return [REPAIR_EXE_PNG_URL] if REPAIR_EXE_PNG_URL else []

    if ver_tuple is not None:
        key = _version_tuple_to_string(ver_tuple)
        matched = url_map.get(key)
        if matched:
            return list(matched)

    latest_key = _get_latest_version_key(url_map)
    if latest_key:
        return list(url_map[latest_key])

    return [REPAIR_EXE_PNG_URL] if REPAIR_EXE_PNG_URL else []


def _icc_auto_pen_available():
    """返回 (是否可用, ICC-CE 文件版本元组 或 None)。

    仅当能读到有效版本且版本 < ICC_MIN_AUTO_PEN_VERSION 时才认为不可用；
    若 exe 不存在或版本未知，返回 (True, None)，让用户可自行尝试。
    """
    exe = get_icc_ce_exe_path()
    if not exe or not os.path.exists(exe):
        return True, None
    ver = get_file_version(exe)
    if ver is None:
        return True, None
    return ver >= ICC_MIN_AUTO_PEN_VERSION, ver


def _extract_exe_from_command(cmd):
    """从注册表命令字符串中提取可执行文件路径。

    典型命令格式：
      "C:\\Program Files\\ICC-CE\\ICC-CE.exe" "%1"
      C:\\Path\\To\\App.exe %1
    """
    if not cmd:
        return None
    s = cmd.strip()
    if s.startswith('"'):
        end = s.find('"', 1)
        if end == -1:
            return None
        return s[1:end]
    space = s.find(' ')
    return s[:space] if space != -1 else s


def _get_entry_command():
    """返回写进启动脚本（.ps1）的命令字符串（供希沃调用，应直接启动批注软件）。

    返回值是 PowerShell 5.1 可直接执行的表达式：
    - 打包模式：``& "C:\\...\\Annotation.exe" -run_annotation_app``
    - 源码模式：``& "C:\\...\\pythonw.exe" "D:\\...\\main.py" -run_annotation_app``

    前导 ``&`` 是 PowerShell 的调用运算符，用于显式启动被引号包围的可执行文件路径。
    """
    base = get_base_dir()
    if getattr(sys, "frozen", False):
        exe = os.path.join(base, "Annotation.exe")
        return f'& "{exe}" -run_annotation_app'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    main_py = os.path.join(base, "main.py")
    return f'& "{pythonw}" "{main_py}" -run_annotation_app'


def _parse_bat_entry(bat_path):
    """从启动脚本（.ps1 或遗留 .bat）中提取入口命令的所有路径段。找不到返回空列表。

    兼容两种语法：
      - PowerShell .ps1：首行形如 ``& "C:\\...\\Annotation.exe" -run_annotation_app``
      - 遗留 .bat：首行形如 ``"C:\\...\\Annotation.exe" -run_annotation_app``（被 ``@echo off`` / ``rem`` 头跳过后）

    兼容 UTF-8 BOM（PowerShell 5.1 ``Set-Content -Encoding UTF8`` 默认添加）：读取后剥离
    文件开头的 ``\\ufeff`` BOM 字符，避免其与首字符（如 ``&``）粘连导致 token 解析错误。

    典型输出：
      打包模式：["C:\\...\\Annotation.exe"]
      源码模式：["C:\\...\\pythonw.exe", "D:\\...\\main.py"]
    """
    if not os.path.exists(bat_path):
        return []
    # 优先以 UTF-8 解码（自动剥离 BOM）；失败则回退到 mbcs（Windows ANSI）
    content = None
    for encoding in ("utf-8-sig", "mbcs"):
        try:
            with open(bat_path, "r", encoding=encoding, errors="ignore") as f:
                content = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if content is None:
        return []
    # 兜底剥离可能残留的 BOM 字符（mbcs 解码时 UTF-8 BOM 会变成中文乱码）
    if content and content[0] == '\ufeff':
        content = content[1:]
    first_line = None
    for line in content.splitlines():
        line = line.strip()
        # 跳过空行、bat 头、PowerShell 注释 (#)、rem 注释、BOM 残留字符
        if not line or line.startswith("@") or line.startswith("rem") or line.startswith("#"):
            continue
        # 跳过首字符为 BOM 残留（如 '锘'）的行
        if line.startswith('\ufeff'):
            line = line[1:].lstrip()
            if not line:
                continue
        first_line = line
        break
    if not first_line:
        return []
    return _split_command_paths(first_line)


def _split_command_paths(cmd):
    """从命令字符串中提取所有被引号包围或空格分隔的路径参数（过滤 -flag 形式的非路径 token）。

    同时跳过 PowerShell 的调用运算符 ``&``（独立出现的单个 & 字符）。
    """
    paths = []
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if c in (' ', '\t'):
            i += 1
            continue
        if c == '"':
            end = cmd.find('"', i + 1)
            if end == -1:
                break
            paths.append(cmd[i + 1:end])
            i = end + 1
        else:
            j = i
            while j < n and cmd[j] not in (' ', '\t'):
                j += 1
            token = cmd[i:j]
            # 跳过 PowerShell 调用运算符 & 与 -flag 形式的参数
            if token != '&' and not token.startswith('-'):
                paths.append(token)
            i = j
    return paths


def _build_install_ps1():
    """生成安装阶段的临时 PowerShell 5.1 脚本（需管理员权限运行）。

    遍历目标目录中所有以 DesktopAnnotation 开头但不以 Backup 结尾的文件，
    将 "DesktopAnnotation" 前缀替换为 "DesktopAnnotationBackup" 完成批量备份。

    采用 PowerShell 5.1 兼容语法：
      - $ErrorActionPreference = 'Stop' 实现错误即退出
      - Get-ChildItem -File 枚举文件（自动跳过目录）
      - -like 前缀通配 + Substring 实现前缀切片（防止 BackupBackup）
      - try/catch 包裹关键操作以采集异常并写入日志
      - 不包含任何 pause / Read-Host 等调试暂停调用
    """
    entry = _get_entry_command()
    len_prefix = _LEN_DA_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LOCAL_EXE     = '{LOCAL_APPS_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    exit 1
}}

Write-Log "[INSTALL] [START] target=$TARGET_DIR"

# --- 1. 杀掉目标目录下所有 exe 进程 ---
Write-Log "[KILL] [START] enumerate exes"
Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    Write-Log "[KILL] [OK] $($_.Name)"
    try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
}}

# --- 2. 批量重命名 PREFIX* -> BACKUP_PREFIX* ---
#  使用 -like 前缀检测（避免硬编码长度）；NEWNAME 通过 Substring 前缀切片，
#  不会对已有 BACKUP_PREFIX 再套一层（BackupBackup 问题）
Write-Log "[RENAME] [START] enumerate ${{PREFIX}}*"
$renameCount = 0
Get-ChildItem -Path "$TARGET_DIR\\${{PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    $name = $_.Name
    if ($name -like "$BACKUP_PREFIX*") {{
        Write-Log "[RENAME] [SKIP] $name already backed up"
        return
    }}
    $newName = $BACKUP_PREFIX + $name.Substring($LEN_PREFIX)
    $newPath = Join-Path $TARGET_DIR $newName
    if (Test-Path -LiteralPath $newPath) {{
        try {{
            Remove-Item -LiteralPath $newPath -Force
            Write-Log "[RENAME] [INFO] deleted old backup $newName"
        }} catch {{
            Write-Log "[RENAME] [FAILED] del old backup $newName"
            Fail 'FAILED_DEL_OLD_BACKUP'
        }}
    }}
    try {{
        Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
    }} catch {{
        Write-Log "[RENAME] [FAILED] $name -> $newName"
        Fail 'FAILED_RENAME'
    }}
    if (-not (Test-Path -LiteralPath $newPath)) {{
        Write-Log "[RENAME] [VERIFY_FAILED] $newName missing after rename"
        Fail 'FAILED_RENAME_VERIFY'
    }}
    $renameCount++
    Write-Log "[RENAME] [OK] $name -> $newName"
}}
Write-Log "[RENAME] [DONE] count=$renameCount"

# --- 3. 复制替换 exe ---
Write-Log "[COPY] [START] $LOCAL_EXE -> $ORIG_EXE"
try {{
    Copy-Item -LiteralPath $LOCAL_EXE -Destination $ORIG_EXE -Force
}} catch {{
    Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
    Fail 'FAILED_COPY'
}}
if (-not (Test-Path -LiteralPath $ORIG_EXE)) {{
    Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
    Fail 'FAILED_COPY'
}}
Write-Log "[COPY] [OK] $LOCAL_EXE -> $ORIG_EXE"

# --- 4. 写入启动脚本 (.ps1) ---
Write-Log "[WRITE] [START] $LAUNCHER_FILE"
try {{
    Set-Content -LiteralPath $LAUNCHER_FILE -Value @'
{entry}
'@ -Encoding UTF8
}} catch {{
    Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
    Fail 'FAILED_WRITE_LAUNCHER'
}}
if (-not (Test-Path -LiteralPath $LAUNCHER_FILE)) {{
    Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
    Fail 'FAILED_WRITE_LAUNCHER'
}}
Write-Log "[WRITE] [OK] $LAUNCHER_FILE"

Write-Log "[INSTALL] [DONE]"
exit 0
"""


def _build_uninstall_ps1():
    """生成卸载阶段的临时 PowerShell 5.1 脚本（需管理员权限运行）。

    遍历目标目录中所有以 DesktopAnnotationBackup 开头的文件，
    将 "DesktopAnnotationBackup" 前缀还原为 "DesktopAnnotation"。

    采用 PowerShell 5.1 兼容语法 + 内联函数 Strip-BackupPrefixes
    循环剥离重复前缀，最多 10 轮，可修复历史 BackupBackup 嵌套命名。
    """
    len_prefix = _LEN_DA_PREFIX
    len_backup_prefix = _LEN_DA_BACKUP_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}
$LEN_BACKUP_PREFIX = {len_backup_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    exit 1
}}

function Strip-BackupPrefixes([string]$name) {{
    # 循环剥离所有重复的 BACKUP_PREFIX 前缀，再拼接 PREFIX 得到原始文件名
    $n = $name
    while ($n.StartsWith($BACKUP_PREFIX)) {{
        $n = $n.Substring($LEN_BACKUP_PREFIX)
    }}
    return $PREFIX + $n
}}

Write-Log "[UNINSTALL] [START] target=$TARGET_DIR"

# --- 1. 杀掉所有 Backup 相关进程 ---
Write-Log "[KILL] [START] enumerate backup exes"
Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    Write-Log "[KILL] [OK] $($_.Name)"
    try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
}}

# --- 2. 检查是否有备份文件 ---
$hasBackup = $false
if ((Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*" -File -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {{
    $hasBackup = $true
}}
if (-not $hasBackup) {{
    Write-Log "[CHECK] [INFO] no backup files found, nothing to restore"
    Write-Log "[UNINSTALL] [DONE]"
    exit 0
}}
Write-Log "[CHECK] [OK] backup files exist"

# --- 3. 删除我们替换的 exe ---
if (Test-Path -LiteralPath $ORIG_EXE) {{
    Write-Log "[DELETE] [START] $ORIG_EXE"
    try {{
        Remove-Item -LiteralPath $ORIG_EXE -Force
    }} catch {{
        Write-Log "[DELETE] [FAILED] $ORIG_EXE"
        Fail 'FAILED_DEL_ORIG'
    }}
    if (Test-Path -LiteralPath $ORIG_EXE) {{
        Write-Log "[DELETE] [FAILED] $ORIG_EXE"
        Fail 'FAILED_DEL_ORIG'
    }}
    Write-Log "[DELETE] [OK] $ORIG_EXE"
}} else {{
    Write-Log "[DELETE] [SKIP] $ORIG_EXE not found"
}}

# --- 4. 批量还原 BACKUP_PREFIX* -> PREFIX* ---
#  循环扫描最多 10 遍，每一轮对 BACKUP_PREFIX* 文件进行还原；
#  通过 Strip-BackupPrefixes 子例程剥离重复前缀，可修复 BackupBackup
#  / BackupBackupBackup 等多层嵌套命名问题；某一轮没有处理任何文件时退出
Write-Log "[RESTORE] [START] enumerate ${{BACKUP_PREFIX}}*"
$restoreCount = 0
$pass = 0
while ($pass -lt 10) {{
    $pass++
    $passHandled = 0
    Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        $name = $_.Name
        $newName = Strip-BackupPrefixes $name
        $newPath = Join-Path $TARGET_DIR $newName
        Write-Log "[RESTORE] [PASS=$pass] $name -> $newName"
        try {{
            Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
        }} catch {{
            Write-Log "[RESTORE] [FAILED] $name -> $newName"
            Fail 'FAILED_RESTORE'
        }}
        if (-not (Test-Path -LiteralPath $newPath)) {{
            Write-Log "[RESTORE] [VERIFY_FAILED] $newName missing after restore"
            Fail 'FAILED_RESTORE_VERIFY'
        }}
        $restoreCount++
        $passHandled++
        Write-Log "[RESTORE] [OK] $name -> $newName"
    }}
    if ($passHandled -eq 0) {{ break }}
}}
Write-Log "[RESTORE] [DONE] count=$restoreCount passes=$pass"

# --- 5. 清理启动脚本 (.ps1) ---
if (Test-Path -LiteralPath $LAUNCHER_FILE) {{
    Write-Log "[DELETE] [START] $LAUNCHER_FILE"
    try {{
        Remove-Item -LiteralPath $LAUNCHER_FILE -Force
    }} catch {{
        Write-Log "[DELETE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_DEL_LAUNCHER'
    }}
    if (Test-Path -LiteralPath $LAUNCHER_FILE) {{
        Write-Log "[DELETE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_DEL_LAUNCHER'
    }}
    Write-Log "[DELETE] [OK] $LAUNCHER_FILE"
}} else {{
    Write-Log "[DELETE] [SKIP] $LAUNCHER_FILE not found"
}}

Write-Log "[UNINSTALL] [DONE]"
exit 0
"""


def _run_elevated(ps1_content):
    """写入临时 .ps1 并以管理员权限运行（ShellExecuteW runas）。

    通过 powershell.exe -ExecutionPolicy Bypass -NoProfile -File 启动，
    完全移除原 bat 时代的 _decorate_bat pause 调试逻辑。
    调试模式下显示控制台窗口（SW_SHOWNORMAL），正式模式下隐藏（SW_HIDE）。
    """
    is_debug = _is_debug()
    _debug_log(f"_run_elevated called, debug={is_debug}, ps1_len={len(ps1_content)}")
    fd, ps1_path = tempfile.mkstemp(suffix=".ps1", prefix="sar_")
    try:
        # PowerShell 5.1 默认编码为 UTF-8 with BOM 时识别中文注释最佳；写 utf-8-sig
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(ps1_content)
        # 构造 powershell.exe 调用参数：-ExecutionPolicy Bypass 跳过签名限制，
        # -NoProfile 不加载用户配置文件（避免污染），-File 指定脚本路径
        params = f'-ExecutionPolicy Bypass -NoProfile -File "{ps1_path}"'
        show_cmd = 1 if is_debug else 0  # SW_SHOWNORMAL : SW_HIDE
        _debug_log(f"ps1 written to {ps1_path}, show_cmd={show_cmd}, launching...")
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "powershell.exe", params, None, show_cmd
        )
    except Exception as e:
        _critical(f"执行失败：{e}")


def get_install_diagnostics():
    """逐项返回安装状态判定所依赖的检查结果。

    返回值：list of dict，每项含 label / ok / detail。ok=True 表示该项符合预期。
    """
    checks = []

    # 1. 本地安装源（apps\\DesktopAnnotation.exe）
    src_exists = os.path.exists(LOCAL_APPS_EXE)
    src_hash = sha256_file(LOCAL_APPS_EXE) if src_exists else None
    checks.append({
        "label": "安装源完整性",
        "ok": bool(src_exists and src_hash == APPS_EXE_SHA256),
        "detail": (
            f"{LOCAL_APPS_EXE}\n"
            + (f"哈希值：{src_hash}" if src_exists else "文件缺失")
            + (f"\n期望哈希：{APPS_EXE_SHA256}" if src_exists and src_hash != APPS_EXE_SHA256 else "")
        ),
    })

    # 2. 目标 exe 存在性（DesktopAnnotation.exe 是替换入口）
    has_orig = os.path.exists(DESKTOP_ANNOTATION_EXE)
    checks.append({
        "label": "目标程序存在",
        "ok": has_orig,
        "detail": DESKTOP_ANNOTATION_EXE,
    })

    # 3. 目标 exe 哈希（应为"我们的 exe"，若已安装）
    orig_hash = sha256_file(DESKTOP_ANNOTATION_EXE) if has_orig else None
    checks.append({
        "label": "目标程序哈希",
        "ok": bool(has_orig and orig_hash == APPS_EXE_SHA256),
        "detail": (
            f"当前哈希：{orig_hash}" if has_orig and orig_hash
            else ("文件缺失" if not has_orig else "无法读取")
        ),
    })

    # 4. 原始备份文件组（所有 DesktopAnnotationBackup* 文件）
    backup_files = _scan_backup_da_files(DESKTOP_ANNOTATION_DIR)
    backup_exe = _find_primary_exe(backup_files)
    checks.append({
        "label": "原始程序备份",
        "ok": bool(backup_files),
        "detail": (
            f"共 {len(backup_files)} 个文件：\n"
            + "\n".join(f"  {os.path.basename(p)}" for p in backup_files)
            if backup_files else "未发现备份文件"
        ),
    })

    # 5. 原始未备份文件组（信息性展示，不参与健康判定）
    original_files = _scan_original_da_files(DESKTOP_ANNOTATION_DIR)
    checks.append({
        "label": "原始未备份文件",
        "ok": True,
        "detail": (
            f"共 {len(original_files)} 个文件：\n"
            + "\n".join(f"  {os.path.basename(p)}" for p in original_files)
            if original_files else "无（安装后原始文件已被重命名为 DesktopAnnotationBackup*）"
        ),
    })

    # 6. 入口启动脚本 (.ps1)
    has_launcher = os.path.exists(DESKTOP_ANNOTATION_BAT)
    checks.append({
        "label": "启动脚本",
        "ok": has_launcher,
        "detail": DESKTOP_ANNOTATION_BAT,
    })

    # 7. 启动脚本入口路径有效性
    entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT) if has_launcher else []
    all_entry_exist = bool(entry_paths) and all(os.path.exists(p) for p in entry_paths)
    checks.append({
        "label": "启动脚本入口有效",
        "ok": all_entry_exist,
        "detail": (
            "\n".join(f"  {p}" for p in entry_paths) if entry_paths
            else ("启动脚本不存在" if not has_launcher else "无法解析入口命令")
        ),
    })

    return checks


def install():
    """安装：校验 → 杀进程 → 备份 → 替换 → 写启动脚本 (.ps1)。

    返回 (ok, failure_reasons)。ok 为 True 时 failure_reasons 为空列表；
    ok 为 False 时 failure_reasons 是字符串列表（每项描述一项失败检查）。
    """
    _debug_log("install() called")
    _log("INSTALL invoked")
    reasons = []

    if not os.path.exists(LOCAL_APPS_EXE):
        reasons.append(f"未找到安装源：{LOCAL_APPS_EXE}")
        _log(f"INSTALL failed: source not found {LOCAL_APPS_EXE}", "error")
    else:
        actual = sha256_file(LOCAL_APPS_EXE)
        if actual != APPS_EXE_SHA256:
            reasons.append(
                f"安装源哈希不匹配：实际 {actual}，期望 {APPS_EXE_SHA256}"
            )
            _log(f"INSTALL failed: hash mismatch actual={actual} expected={APPS_EXE_SHA256}", "error")

    if reasons:
        _critical(reasons[0])
        return False, reasons

    _log(f"INSTALL validation passed, killing processes for {DESKTOP_ANNOTATION_EXE}")
    kill_process_by_path(DESKTOP_ANNOTATION_EXE)
    kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
    _run_elevated(_build_install_ps1())
    _log("INSTALL ps1 dispatched (elevated)")
    return True, []


def uninstall():
    """卸载：杀进程 → 恢复原文件 → 清理启动脚本 (.ps1)。"""
    _debug_log("uninstall() called")
    _log("UNINSTALL invoked")
    kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
    kill_process_by_path(DESKTOP_ANNOTATION_EXE)
    _run_elevated(_build_uninstall_ps1())
    _log("UNINSTALL ps1 dispatched (elevated)")
    return True


def _decode_png_to_file(png_path, out_path):
    """从 exe2png 编码的 PNG 中还原出原始字节文件。

    兼容三种常见像素格式：
      - L（灰度）/ LA：直接用 arr.reshape(-1)
      - RGB / RGBA：原始 exe2png 编码通常存于第一个通道（R），
        因为灰度图在服务端被自动转成 RGBA 后，R 通道保留原始字节
    """
    if not _HAS_PIL:
        raise RuntimeError("缺少 Pillow / numpy 依赖，无法执行 PNG 解码")
    img = _PILImage.open(png_path)
    data = _numpy.array(img)
    if data.ndim == 2:
        raw = data.reshape(-1).tobytes()
    else:
        raw = data[:, :, 0].reshape(-1).tobytes()
    with open(out_path, "wb") as f:
        f.write(raw.rstrip(b"\x00"))


def _download(url, dest_path):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)


def _download_with_fallback(urls, dest_path):
    """按顺序尝试 urls 中的每个 URL 下载到 dest_path。

    成功即返回 (True, url_used)；全部失败则返回 (False, list_of_errors)。
    """
    if not urls:
        return False, ["下载链接列表为空"]
    errors = []
    for url in urls:
        try:
            _download(url, dest_path)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True, url
            else:
                errors.append(f"下载完成但文件为空：{url}")
        except Exception as e:
            errors.append(f"{url} — {e}")
    return False, errors


def _build_repair_ps1(installer_exe, cleanup_dir):
    """生成修复流程的管理员 PowerShell 5.1 脚本：清理 → 运行原始安装包 → 批量备份 → 替换 → 写启动脚本。

    全程使用 PowerShell 5.1 兼容语法，所有错误退出路径统一 goto :cleanup
    （在 PowerShell 中通过 try/catch + finally 块实现等价语义）。
    """
    entry = _get_entry_command()
    len_prefix = _LEN_DA_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LOCAL_EXE     = '{LOCAL_APPS_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$INSTALLER     = '{installer_exe}'
$CLEANUP_DIR   = '{cleanup_dir}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    Invoke-Cleanup
    exit 1
}}

function Invoke-Cleanup {{
    if ($CLEANUP_DIR -and (Test-Path -LiteralPath $CLEANUP_DIR)) {{
        try {{ Remove-Item -LiteralPath $CLEANUP_DIR -Recurse -Force -ErrorAction SilentlyContinue }} catch {{ }}
        Write-Log "[CLEANUP] [INFO] removed $CLEANUP_DIR"
    }}
}}

Write-Log "[REPAIR] [START] target=$TARGET_DIR installer=$INSTALLER"

try {{
    # --- 1. 杀掉目标目录下所有 exe 进程 ---
    Write-Log "[KILL] [START] enumerate exes"
    Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Log "[KILL] [OK] $($_.Name)"
        try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
    }}

    # --- 2. 清理目标目录 ---
    $uninstaller = Join-Path $TARGET_DIR 'Uninstall.exe'
    if (Test-Path -LiteralPath $uninstaller) {{
        Write-Log "[CLEAN] [START] run Uninstall.exe /S"
        $proc = Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru
        Write-Log "[CLEAN] [OK] Uninstall.exe exit=$($proc.ExitCode)"
    }} else {{
        Write-Log "[CLEAN] [START] rd /s /q $TARGET_DIR"
        try {{ Remove-Item -LiteralPath $TARGET_DIR -Recurse -Force }} catch {{ }}
        Write-Log "[CLEAN] [OK] rd done"
    }}

    # --- 3. 运行全新安装包（静默） ---
    Write-Log "[INSTALLER] [START] $INSTALLER /S"
    $proc = Start-Process -FilePath $INSTALLER -ArgumentList '/S' -Wait -PassThru
    if ($proc.ExitCode -ne 0) {{
        Write-Log "[INSTALLER] [FAILED] exit=$($proc.ExitCode)"
        Fail 'INSTALLER_FAILED'
    }}
    Write-Log "[INSTALLER] [OK] exit=$($proc.ExitCode)"

    if (-not (Test-Path -LiteralPath $TARGET_DIR)) {{
        Write-Log "[CHECK] [FAILED] target dir missing after installer"
        Fail 'TARGET_DIR_MISSING'
    }}
    Write-Log "[CHECK] [OK] target dir exists"

    # --- 4. 执行我们的标准安装（批量备份 + 替换）---
    Write-Log "[KILL] [START] enumerate exes after installer"
    Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Log "[KILL] [OK] $($_.Name)"
        try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
    }}

    # 批量重命名 PREFIX* -> BACKUP_PREFIX*  -like 前缀检测 + Substring 切片
    Write-Log "[RENAME] [START] enumerate ${{PREFIX}}*"
    $renameCount = 0
    Get-ChildItem -Path "$TARGET_DIR\\${{PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        $name = $_.Name
        if ($name -like "$BACKUP_PREFIX*") {{
            Write-Log "[RENAME] [SKIP] $name already backed up"
            return
        }}
        $newName = $BACKUP_PREFIX + $name.Substring($LEN_PREFIX)
        $newPath = Join-Path $TARGET_DIR $newName
        if (Test-Path -LiteralPath $newPath) {{
            try {{
                Remove-Item -LiteralPath $newPath -Force
                Write-Log "[RENAME] [INFO] deleted old backup $newName"
            }} catch {{
                Write-Log "[RENAME] [FAILED] del old backup $newName"
                Fail 'FAILED_DEL_OLD_BACKUP'
            }}
        }}
        try {{
            Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
        }} catch {{
            Write-Log "[RENAME] [FAILED] $name -> $newName"
            Fail 'FAILED_RENAME'
        }}
        if (-not (Test-Path -LiteralPath $newPath)) {{
            Write-Log "[RENAME] [VERIFY_FAILED] $newName missing after rename"
            Fail 'FAILED_RENAME_VERIFY'
        }}
        $renameCount++
        Write-Log "[RENAME] [OK] $name -> $newName"
    }}
    Write-Log "[RENAME] [DONE] count=$renameCount"

    Write-Log "[COPY] [START] $LOCAL_EXE -> $ORIG_EXE"
    try {{
        Copy-Item -LiteralPath $LOCAL_EXE -Destination $ORIG_EXE -Force
    }} catch {{
        Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
        Fail 'FAILED_COPY'
    }}
    if (-not (Test-Path -LiteralPath $ORIG_EXE)) {{
        Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
        Fail 'FAILED_COPY'
    }}
    Write-Log "[COPY] [OK] $LOCAL_EXE -> $ORIG_EXE"

    Write-Log "[WRITE] [START] $LAUNCHER_FILE"
    try {{
        Set-Content -LiteralPath $LAUNCHER_FILE -Value @'
{entry}
'@ -Encoding UTF8
    }} catch {{
        Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_WRITE_LAUNCHER'
    }}
    if (-not (Test-Path -LiteralPath $LAUNCHER_FILE)) {{
        Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_WRITE_LAUNCHER'
    }}
    Write-Log "[WRITE] [OK] $LAUNCHER_FILE"

    Write-Log "[REPAIR] [DONE]"
}} finally {{
    Invoke-Cleanup
}}
exit 0
"""


def repair():
    """修复损坏的安装：读取当前版本 → 匹配下载链接 → 下载原始安装包 → 静默安装 → 标准安装我们的 exe。

    返回 (ok, failure_reasons)。
    """
    _debug_log("repair() called")
    _log("REPAIR invoked")
    reasons = []

    tmpdir = os.path.join(tempfile.gettempdir(), "sar_repair")
    os.makedirs(tmpdir, exist_ok=True)
    png_path = os.path.join(tmpdir, "desktopannotationsetup.png")
    installer_path = os.path.join(tmpdir, "DesktopAnnotationSetup.exe")

    try:
        ver_tuple, ver_source = get_desktop_annotation_version()
        urls = get_repair_urls_for_version(ver_tuple)

        if ver_tuple is None:
            ver_hint = "未知"
        else:
            ver_hint = _version_tuple_to_string(ver_tuple)

        _log(f"REPAIR detected version={ver_hint} source={ver_source or 'N/A'} urls={len(urls)}")

        ok, result = _download_with_fallback(urls, png_path)
        if not ok:
            reasons.append(
                f"下载版本 {ver_hint} 的安装包失败（尝试了 {len(urls)} 个链接）。"
                f"目标来源：{ver_source or '未找到对应 exe'}。"
            )
            for err in result:
                reasons.append(f"  • {err}")
            _log(f"REPAIR download failed: {'; '.join(reasons)}", "error")
            _critical(reasons[0])
            return False, reasons

        _log(f"REPAIR downloaded to {png_path} ({os.path.getsize(png_path)} bytes)")

        if not os.path.exists(png_path) or os.path.getsize(png_path) == 0:
            reasons.append("下载的安装包为空或不存在")
            _log("REPAIR downloaded file empty", "error")
            _critical(reasons[0])
            return False, reasons

        try:
            _decode_png_to_file(png_path, installer_path)
            _log(f"REPAIR decoded PNG to {installer_path} ({os.path.getsize(installer_path)} bytes)")
        except Exception as e:
            reasons.append(f"PNG 解码失败：{e}")
            _log(f"REPAIR PNG decode failed: {e}", "error")
            _critical(reasons[0])
            return False, reasons

        if not os.path.exists(installer_path) or os.path.getsize(installer_path) == 0:
            reasons.append("解码后的安装包为空")
            _log("REPAIR decoded installer empty", "error")
            _critical(reasons[0])
            return False, reasons

        _log("REPAIR dispatching elevated ps1")
        kill_process_by_path(DESKTOP_ANNOTATION_EXE)
        kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
        _run_elevated(_build_repair_ps1(installer_path, tmpdir))
        _log("REPAIR ps1 dispatched (elevated)")
        return True, []

    except Exception as e:
        reasons.append(f"修复异常：{e}")
        _log(f"REPAIR exception: {e}", "error")
        _critical(reasons[0])
        return False, reasons


def get_install_status():
    """返回安装状态：INSTALL_STATUS_INSTALLED / NOT_INSTALLED / CORRUPTED。

    判定规则：
      - NOT_INSTALLED：DESKTOP_ANNOTATION_EXE 存在但 hash 不是我们的，且无备份文件组、无启动脚本
      - INSTALLED：DESKTOP_ANNOTATION_EXE hash 符合 + 存在备份文件组 + 存在有效启动脚本
      - CORRUPTED：其他所有情况
    """
    has_orig = os.path.exists(DESKTOP_ANNOTATION_EXE)
    has_backup = bool(_scan_backup_da_files(DESKTOP_ANNOTATION_DIR))
    has_launcher = os.path.exists(DESKTOP_ANNOTATION_BAT)

    if not has_orig:
        return INSTALL_STATUS_CORRUPTED
    orig_hash = sha256_file(DESKTOP_ANNOTATION_EXE)

    if orig_hash != APPS_EXE_SHA256 and not has_launcher and not has_backup:
        return INSTALL_STATUS_NOT_INSTALLED

    if orig_hash == APPS_EXE_SHA256 and has_backup and has_launcher:
        entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT)
        if entry_paths and all(os.path.exists(p) for p in entry_paths):
            return INSTALL_STATUS_INSTALLED

    return INSTALL_STATUS_CORRUPTED
