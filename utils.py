import sys
import os
import re
import json
import subprocess
import tempfile
import ctypes
import struct
import winreg
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

VERSION = "3.0.0"

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

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

DEFAULT_SETTINGS = {
    "ink_product": "none",
    "show_loading_window": True,
    "auto_pen": False,
    "thorough_hide": False,
    "loading_duration": 3,
    "theme": "system",
    "style": "windowsvista",
    "none_show_disabled_msg": True,
    "none_msg_duration": 2,
    "auto_check_update": True,
    "update_never_remind": False,
    "update_skipped_version": None,
}

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

def load_settings():
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    settings = DEFAULT_SETTINGS.copy()
    settings.update(data)
    return settings

def save_settings(settings):
    config_path = get_config_path()
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

def is_installed():
    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        debugger, _ = winreg.QueryValueEx(key, "Debugger")
        winreg.CloseKey(key)
        expected = os.path.join(get_base_dir(), "Annotation.exe")
        return debugger.strip('"') == expected
    except Exception:
        return False

def check_security_software_running():
    """返回正在运行的安全软件名称，若未找到则返回 None"""
    known_software = {
        "hipstray.exe": "火绒安全软件",
        "360tray.exe": "360安全卫士",
        "qqpctray.exe": "腾讯电脑管家",
        "pyas.exe": "PYAS Security Antivirus",
    }
    try:
        output = subprocess.check_output(
            "tasklist /fo csv /nh", shell=True, encoding="mbcs", errors="ignore"
        )
        output_lower = output.lower()
        for proc, name in known_software.items():
            if proc in output_lower:
                return name
    except Exception:
        pass
    return None

SHORTCUT_NAME = "希沃批注替换设置.lnk"
START_MENU_LNK = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                              r"Microsoft\Windows\Start Menu\Programs", SHORTCUT_NAME)
DESKTOP_LNK = os.path.join(os.path.expanduser("~"), "Desktop", SHORTCUT_NAME)

def shortcut_exists(kind):
    if kind == "start_menu":
        return os.path.exists(START_MENU_LNK)
    if kind == "desktop":
        return os.path.exists(DESKTOP_LNK)
    return False

def create_shortcut(kind):
    target = os.path.join(get_base_dir(), "Annotation.exe")
    if kind == "start_menu":
        lnk = START_MENU_LNK
    elif kind == "desktop":
        lnk = DESKTOP_LNK
    else:
        return False
    try:
        subprocess.run(
            ["powershell", "-Command",
             "$wsh = New-Object -ComObject WScript.Shell;"
             f"$s = $wsh.CreateShortcut('{lnk}');"
             f"$s.TargetPath = '{target}';"
             "$s.Arguments = '-settings';"
             "$s.Save()"],
            check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
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

ICC_PROTOCOL_KEY = r"icc"
ICC_COMMAND_KEY = r"icc\shell\open\command"

ICC_STATUS_OK = "ok"
ICC_STATUS_NO_PROTOCOL = "no_protocol"
ICC_STATUS_BROKEN = "broken"


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


ICC_MIN_AUTO_PEN_VERSION = (1, 7, 18, 7)


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


def create_and_run_bat(is_install):
    target_exe = os.path.join(get_base_dir(), "Annotation.exe")
    if is_install and not os.path.exists(target_exe):
        _critical(f"未找到 {target_exe}")
        return

    reg_key = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"

    if is_install:
        bat_content = f'''@echo off
reg add "{reg_key}" /v Debugger /t REG_SZ /d "\\"{target_exe}\\"" /f
if %errorlevel% neq 0 exit /b 1
del "%~f0"
'''
    else:
        bat_content = f'''@echo off
reg delete "{reg_key}" /f
del "%~f0"
'''

    fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='icc_ce_')
    try:
        with os.fdopen(fd, 'w', encoding='mbcs') as f:
            f.write(bat_content)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", bat_path, "", None, 0
        )
    except Exception as e:
        _critical(f"执行失败：{e}")
