import sys
import os
import re
import json
import hashlib
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


VERSION = _config.get("version", "3.0.0")

DEFAULT_SETTINGS = _config.get("default_settings", {
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
_DESKTOP_ANNOTATION_BAT_NAME = _da_cfg.get("bat_name", "Seewo-DeskopAnnotation-Replacement.bat")
DESKTOP_ANNOTATION_EXE = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_EXE_NAME)
DESKTOP_ANNOTATION_BACKUP = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_BACKUP_NAME)
DESKTOP_ANNOTATION_BAT = os.path.join(DESKTOP_ANNOTATION_DIR, _DESKTOP_ANNOTATION_BAT_NAME)

_apps_cfg = _config.get("apps", {})
_APPS_EXE_NAME = _apps_cfg.get("exe_name", "DesktopAnnotation.exe")
APPS_EXE_SHA256 = _apps_cfg.get("exe_sha256", "")

_repair_cfg = _config.get("repair", {})
REPAIR_EXE_PNG_URL = _repair_cfg.get("exe_png_url", "")

_install_cfg = _config.get("install_status", {})
INSTALL_STATUS_INSTALLED = _install_cfg.get("installed", "installed")
INSTALL_STATUS_NOT_INSTALLED = _install_cfg.get("not_installed", "not_installed")
INSTALL_STATUS_CORRUPTED = _install_cfg.get("corrupted", "corrupted")


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
    """返回写进 bat 文件的命令字符串。

    源码模式 (sys.frozen 为 False)：用 python.exe 启动 main.py
    打包模式：直接启动 Annotation.exe
    """
    base = get_base_dir()
    if getattr(sys, "frozen", False):
        exe = os.path.join(base, "Annotation.exe")
        return f'"{exe}"'
    python = sys.executable
    main_py = os.path.join(base, "main.py")
    return f'"{python}" "{main_py}"'


def _parse_bat_entry(bat_path):
    """从 bat 文件中提取入口命令的所有路径段。找不到返回空列表。

    典型输出：
      打包模式：["C:\\...\\Annotation.exe"]
      源码模式：["C:\\...\\python.exe", "D:\\...\\main.py"]
    """
    if not os.path.exists(bat_path):
        return []
    try:
        with open(bat_path, "r", encoding="mbcs", errors="ignore") as f:
            content = f.read()
    except Exception:
        return []
    first_line = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("@") or line.startswith("rem"):
            continue
        first_line = line
        break
    if not first_line:
        return []
    return _split_command_paths(first_line)


def _split_command_paths(cmd):
    """从命令字符串中提取所有被引号包围或空格分隔的路径参数。"""
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
            paths.append(cmd[i:j])
            i = j
    return paths


def _build_install_bat():
    """生成安装阶段的临时 bat（需管理员权限运行）。"""
    entry = _get_entry_command()
    return f'''@echo off
setlocal
set "TARGET_DIR={DESKTOP_ANNOTATION_DIR}"
set "ORIG_EXE={DESKTOP_ANNOTATION_EXE}"
set "BACKUP_EXE={DESKTOP_ANNOTATION_BACKUP}"
set "LOCAL_EXE={LOCAL_APPS_EXE}"
set "BAT_FILE={DESKTOP_ANNOTATION_BAT}"

taskkill /f /im DesktopAnnotation.exe /t >nul 2>&1
if exist "%BACKUP_EXE%" (
    echo already backed up
) else (
    ren "%ORIG_EXE%" "DesktopAnnotationBackup.exe"
    if errorlevel 1 (
        echo FAILED_RENAME
        exit /b 1
    )
)
copy /y "%LOCAL_EXE%" "%ORIG_EXE%"
if errorlevel 1 (
    echo FAILED_COPY
    exit /b 1
)
> "%BAT_FILE%" echo @echo off
>> "%BAT_FILE%" echo {entry}
endlocal
'''


def _build_uninstall_bat():
    """生成卸载阶段的临时 bat（需管理员权限运行）。"""
    return f'''@echo off
setlocal
set "ORIG_EXE={DESKTOP_ANNOTATION_EXE}"
set "BACKUP_EXE={DESKTOP_ANNOTATION_BACKUP}"
set "BAT_FILE={DESKTOP_ANNOTATION_BAT}"

taskkill /f /im DesktopAnnotationBackup.exe /t >nul 2>&1
if not exist "%BACKUP_EXE%" (
    echo NO_BACKUP
    exit /b 0
)
if exist "%ORIG_EXE%" del /f /q "%ORIG_EXE%"
ren "%BACKUP_EXE%" "DesktopAnnotation.exe"
if exist "%BAT_FILE%" del /f /q "%BAT_FILE%"
endlocal
'''


def _run_elevated(bat_content):
    """写入临时 bat 并以管理员权限运行（ShellExecuteW runas）。"""
    fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="sar_")
    try:
        with os.fdopen(fd, "w", encoding="mbcs") as f:
            f.write(bat_content)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", bat_path, "", None, 0
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

    # 2. 目标 exe 存在性
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

    # 4. 备份文件
    has_backup = os.path.exists(DESKTOP_ANNOTATION_BACKUP)
    checks.append({
        "label": "原始程序备份",
        "ok": has_backup,
        "detail": DESKTOP_ANNOTATION_BACKUP,
    })

    # 5. 入口 bat 文件
    has_bat = os.path.exists(DESKTOP_ANNOTATION_BAT)
    checks.append({
        "label": "启动脚本",
        "ok": has_bat,
        "detail": DESKTOP_ANNOTATION_BAT,
    })

    # 6. bat 入口路径有效性
    entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT) if has_bat else []
    all_entry_exist = bool(entry_paths) and all(os.path.exists(p) for p in entry_paths)
    checks.append({
        "label": "启动脚本入口有效",
        "ok": all_entry_exist,
        "detail": (
            "\n".join(f"  {p}" for p in entry_paths) if entry_paths
            else ("启动脚本不存在" if not has_bat else "无法解析入口命令")
        ),
    })

    return checks


def install():
    """安装：校验 → 杀进程 → 备份 → 替换 → 写 bat。

    返回 (ok, failure_reasons)。ok 为 True 时 failure_reasons 为空列表；
    ok 为 False 时 failure_reasons 是字符串列表（每项描述一项失败检查）。
    """
    reasons = []

    if not os.path.exists(LOCAL_APPS_EXE):
        reasons.append(f"未找到安装源：{LOCAL_APPS_EXE}")
    else:
        actual = sha256_file(LOCAL_APPS_EXE)
        if actual != APPS_EXE_SHA256:
            reasons.append(
                f"安装源哈希不匹配：实际 {actual}，期望 {APPS_EXE_SHA256}"
            )

    if reasons:
        _critical(reasons[0])
        return False, reasons

    kill_process_by_path(DESKTOP_ANNOTATION_EXE)
    _run_elevated(_build_install_bat())
    return True, []


def uninstall():
    """卸载：杀进程 → 恢复原文件 → 清理 bat。"""
    kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
    _run_elevated(_build_uninstall_bat())
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


def _build_repair_bat(installer_exe, cleanup_dir):
    """生成修复流程的管理员 bat：清理 → 运行原始安装包 → 标准安装我们的 exe。"""
    entry = _get_entry_command()
    return f'''@echo off
setlocal
set "TARGET_DIR={DESKTOP_ANNOTATION_DIR}"
set "ORIG_EXE={DESKTOP_ANNOTATION_EXE}"
set "BACKUP_EXE={DESKTOP_ANNOTATION_BACKUP}"
set "LOCAL_EXE={LOCAL_APPS_EXE}"
set "BAT_FILE={DESKTOP_ANNOTATION_BAT}"
set "INSTALLER={installer_exe}"
set "CLEANUP_DIR={cleanup_dir}"

rem --- 1. 杀掉所有相关进程 ---
taskkill /f /im DesktopAnnotation.exe /t >nul 2>&1
taskkill /f /im DesktopAnnotationBackup.exe /t >nul 2>&1

rem --- 2. 清理目标目录 ---
if exist "%TARGET_DIR%\\Uninstall.exe" (
    cd /d "%TARGET_DIR%"
    call Uninstall.exe /S
) else (
    rd /s /q "%TARGET_DIR%"
)

rem --- 3. 运行全新安装包（静默） ---
start /wait "" "%INSTALLER%" /S
if errorlevel 1 (
    echo INSTALLER_FAILED
    goto :cleanup
)

rem --- 4. 执行我们的标准安装 ---
taskkill /f /im DesktopAnnotation.exe /t >nul 2>&1
if not exist "%BACKUP_EXE%" (
    ren "%ORIG_EXE%" "DesktopAnnotationBackup.exe"
    if errorlevel 1 (
        echo FAILED_RENAME
        goto :cleanup
    )
)
copy /y "%LOCAL_EXE%" "%ORIG_EXE%"
if errorlevel 1 (
    echo FAILED_COPY
    goto :cleanup
)
> "%BAT_FILE%" echo @echo off
>> "%BAT_FILE%" echo {entry}

:cleanup
rem --- 5. 清理临时目录 ---
if defined CLEANUP_DIR (
    rd /s /q "%CLEANUP_DIR%" >nul 2>&1
)
endlocal
'''


def repair():
    """修复损坏的安装：下载原始安装包 → 静默安装 → 标准安装我们的 exe。

    返回 (ok, failure_reasons)。
    """
    reasons = []

    tmpdir = os.path.join(tempfile.gettempdir(), "sar_repair")
    os.makedirs(tmpdir, exist_ok=True)
    png_path = os.path.join(tmpdir, "desktopannotationsetup.png")
    installer_path = os.path.join(tmpdir, "DesktopAnnotationSetup.exe")

    try:
        try:
            _download(REPAIR_EXE_PNG_URL, png_path)
        except Exception as e:
            reasons.append(f"下载安装包失败：{e}")
            return False, reasons

        if not os.path.exists(png_path) or os.path.getsize(png_path) == 0:
            reasons.append("下载的安装包为空或不存在")
            return False, reasons

        try:
            _decode_png_to_file(png_path, installer_path)
        except Exception as e:
            reasons.append(f"PNG 解码失败：{e}")
            return False, reasons

        if not os.path.exists(installer_path) or os.path.getsize(installer_path) == 0:
            reasons.append("解码后的安装包为空")
            return False, reasons

        kill_process_by_path(DESKTOP_ANNOTATION_EXE)
        kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
        _run_elevated(_build_repair_bat(installer_path, tmpdir))
        return True, []

    except Exception as e:
        reasons.append(f"修复异常：{e}")
        return False, reasons


def get_install_status():
    """返回安装状态：INSTALL_STATUS_INSTALLED / NOT_INSTALLED / CORRUPTED。

    判定规则：
      - NOT_INSTALLED：仅存在 DesktopAnnotation.exe 且 hash 不是我们的，且不存在 bat
      - INSTALLED：三个文件都存在 + DesktopAnnotation.exe hash 符合 + bat 入口存在
      - CORRUPTED：其他所有情况
    """
    has_orig = os.path.exists(DESKTOP_ANNOTATION_EXE)
    has_backup = os.path.exists(DESKTOP_ANNOTATION_BACKUP)
    has_bat = os.path.exists(DESKTOP_ANNOTATION_BAT)

    if not has_orig:
        return INSTALL_STATUS_CORRUPTED
    orig_hash = sha256_file(DESKTOP_ANNOTATION_EXE)

    if orig_hash != APPS_EXE_SHA256 and not has_bat and not has_backup:
        return INSTALL_STATUS_NOT_INSTALLED

    if orig_hash == APPS_EXE_SHA256 and has_backup and has_bat:
        entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT)
        if entry_paths and all(os.path.exists(p) for p in entry_paths):
            return INSTALL_STATUS_INSTALLED

    return INSTALL_STATUS_CORRUPTED
