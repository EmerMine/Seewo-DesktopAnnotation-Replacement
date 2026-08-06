import sys
import os
import json
import subprocess
import tempfile
import ctypes
import winreg
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox

VERSION = "2.0.1"

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
    "show_loading_window": True,
    "auto_pen": False,
    "thorough_hide": False,
    "loading_duration": 3,
}

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
        if debugger.strip('"') != expected:
            return False
        lnk_path = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\希沃批注替换设置.lnk"
        return os.path.exists(lnk_path)
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

def _critical(text):
    msg = QMessageBox(QMessageBox.Critical, "希沃批注替换", text) # type: ignore
    msg.setWindowIcon(QIcon(get_icon_path()))
    msg.exec()

def create_and_run_bat(is_install):
    target_exe = os.path.join(get_base_dir(), "Annotation.exe")
    if is_install and not os.path.exists(target_exe):
        _critical(f"未找到 {target_exe}")
        return

    lnk_path_str = r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\希沃批注替换设置.lnk"
    reg_key = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"

    if is_install:
        bat_content = f'''@echo off
reg add "{reg_key}" /v Debugger /t REG_SZ /d "\\"{target_exe}\\"" /f
if %errorlevel% neq 0 exit /b 1
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('{lnk_path_str}'); $Shortcut.TargetPath = '{target_exe}'; $Shortcut.Arguments = '-settings'; $Shortcut.Save()"
del "%~f0"
'''
    else:
        bat_content = f'''@echo off
reg delete "{reg_key}" /f
if exist "{lnk_path_str}" del /f /q "{lnk_path_str}"
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
