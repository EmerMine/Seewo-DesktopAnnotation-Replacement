"""ICA 系列批注软件的取消收纳（unhide）逻辑。

运行流程：
  1. 读取 ``ica_active_profile_id`` 确定当前激活的方案
  2. 进程状态检测：
     - 未运行：启动进程，随后立即读取 exe 同级目录 ``Settings.json`` 中
       ``startup.isFoldAtStartup``：
       - ``false``：等待进程就绪后立即退出（程序启动时自动展开，无需取消收纳）
       - ``true`` ：显示加载窗口 → 1 秒后关闭并确认 → 等待 5 秒就绪后继续
     - 已运行：直接进入后续步骤
  3. ``shortcut_scope == "local"``：读取 ``window_title``，枚举系统窗口并聚焦匹配窗口
     - 未找到时通过系统 Toast 通知并退出（避免快捷键发往错误窗口）
     ``shortcut_scope == "global"``：跳过窗口遍历与聚焦
  4. 读取 ``unhide_scheme``，模拟键盘快捷键取消收纳
"""
import os
import sys
import json
import time
import ctypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from utils import load_settings, _log
from unhide_annotation_apps.custom import (
    launch_executable,
    app_name_from_path,
    LoadingWindow,
)

# Win32 API 句柄（仅 Windows 平台可用）
_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_winmm = ctypes.windll.winmm

# 虚拟键码（Virtual-Key Codes）
_VK_MENU = 0x12   # Alt
_VK_D = 0x44      # D
_VK_Q = 0x51      # Q
_VK_B = 0x42      # B

# keybd_event 标志位
_KEYEVENTF_KEYUP = 0x0002

# ShowWindow 命令
_SW_RESTORE = 9

# CreateToolhelp32Snapshot 标志
_TH32CS_SNAPPROCESS = 0x00000002
_MAX_PATH = 260


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_ulong),
        ("cntUsage", ctypes.c_ulong),
        ("th32ProcessID", ctypes.c_ulong),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", ctypes.c_ulong),
        ("cntThreads", ctypes.c_ulong),
        ("th32ParentProcessID", ctypes.c_ulong),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", ctypes.c_ulong),
        ("szExeFile", ctypes.c_char * _MAX_PATH),
    ]


# ------------------------------------------------------------------ #
#  键盘模拟
# ------------------------------------------------------------------ #

def _send_alt_key(vk_key):
    """模拟 Alt+<key> 组合键的完整按下与释放序列。"""
    try:
        _user32.keybd_event(_VK_MENU, 0, 0, 0)                    # Alt 按下
        _user32.keybd_event(vk_key, 0, 0, 0)                      # 目标键按下
        _user32.keybd_event(vk_key, 0, _KEYEVENTF_KEYUP, 0)       # 目标键释放
        _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)     # Alt 释放
    except Exception as e:
        _log(f"_send_alt_key(0x{vk_key:02X}): {e}", level="error")


def _precise_sleep(seconds):
    """使用高精度定时器休眠指定秒数（timeBeginPeriod 提升至 1ms）。"""
    try:
        _winmm.timeBeginPeriod(1)
    except Exception:
        pass
    try:
        time.sleep(seconds)
    finally:
        try:
            _winmm.timeEndPeriod(1)
        except Exception:
            pass


# ------------------------------------------------------------------ #
#  进程检测
# ------------------------------------------------------------------ #

def _process_base_name(exe_path):
    """从软件路径中提取进程可执行文件名称（不含目录与扩展名），失败返回 ``""``。"""
    try:
        if exe_path:
            base = os.path.basename(exe_path)
            name, _ext = os.path.splitext(base)
            if name:
                return name
    except Exception:
        pass
    return ""


def _is_process_running(base_name_no_ext):
    """通过 CreateToolhelp32Snapshot 检查 ``<base_name_no_ext>.exe`` 是否在运行。"""
    if not base_name_no_ext or not sys.platform.startswith("win"):
        return False
    try:
        target = (base_name_no_ext + ".exe").lower()
    except Exception:
        return False

    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if snapshot in (0, -1):
        return False
    try:
        pe = _PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(_PROCESSENTRY32)
        if not _kernel32.Process32First(snapshot, ctypes.byref(pe)):
            return False
        while True:
            try:
                exe_file = pe.szExeFile.decode("mbcs", errors="ignore")
            except Exception:
                exe_file = ""
            if exe_file.lower() == target:
                return True
            if not _kernel32.Process32Next(snapshot, ctypes.byref(pe)):
                break
        return False
    finally:
        try:
            _kernel32.CloseHandle(snapshot)
        except Exception:
            pass


def _wait_process_ready(base_name_no_ext, timeout_s=5.0, poll_interval_s=0.1):
    """轮询等待 ``<base_name_no_ext>.exe`` 进程出现在系统快照中，返回是否检测到。"""
    if not base_name_no_ext:
        return False
    deadline = time.monotonic() + timeout_s
    while True:
        if _is_process_running(base_name_no_ext):
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        _precise_sleep(min(poll_interval_s, remaining))


# ------------------------------------------------------------------ #
#  Settings.json 读取
# ------------------------------------------------------------------ #

def _read_is_fold_at_startup(exe_path):
    """读取可执行程序同级目录 ``Settings.json`` 中 ``startup.isFoldAtStartup`` 的布尔值。

    Returns
    -------
    tuple[bool | None, str]
        ``(value, status)``：
        - value 为 True/False 表示成功解析；``None`` 表示配置文件不存在 / 字段缺失 / 解析失败
        - status 是简短状态描述（"ok"、"file_missing"、"json_error"、"key_missing"、"path_error"），用于日志
    """
    try:
        if not exe_path:
            return None, "path_error"
        exe_dir = os.path.dirname(os.path.abspath(exe_path))
    except Exception as e:
        _log(f"_read_is_fold_at_startup: resolve exe_dir failed: {e}", level="warning")
        return None, "path_error"

    settings_path = os.path.join(exe_dir, "Settings.json")
    if not os.path.isfile(settings_path):
        _log(f"_read_is_fold_at_startup: Settings.json not found at '{settings_path}'",
             level="warning")
        return None, "file_missing"

    try:
        with open(settings_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as e:
        _log(f"_read_is_fold_at_startup: JSON parse error in '{settings_path}': {e}",
             level="warning")
        return None, "json_error"
    except OSError as e:
        _log(f"_read_is_fold_at_startup: cannot read '{settings_path}': {e}",
             level="warning")
        return None, "io_error"
    except Exception as e:
        _log(f"_read_is_fold_at_startup: unexpected error reading '{settings_path}': {e}",
             level="warning")
        return None, "unexpected"

    startup = cfg.get("startup")
    if startup is None or not isinstance(startup, dict):
        _log(f"_read_is_fold_at_startup: 'startup' section missing/not-object in '{settings_path}'",
             level="warning")
        return None, "key_missing"

    if "isFoldAtStartup" not in startup:
        _log(f"_read_is_fold_at_startup: 'startup.isFoldAtStartup' missing in '{settings_path}'",
             level="warning")
        return None, "key_missing"

    val = startup["isFoldAtStartup"]
    if not isinstance(val, bool):
        # 容忍：Python 语义布尔化，但记录警告
        _log(f"_read_is_fold_at_startup: 'isFoldAtStartup' is not bool ({type(val).__name__}), coercing",
             level="warning")
    val_bool = bool(val)
    _log(f"_read_is_fold_at_startup: startup.isFoldAtStartup={val_bool}")
    return val_bool, "ok"


# ------------------------------------------------------------------ #
#  手动加载窗口控制（显式 显示 → 延时 → 关闭 → 确认）
# ------------------------------------------------------------------ #

def _show_and_close_loading_windows(app_label, display_s=1.0):
    """创建并显示双屏加载窗口，``display_s`` 秒后关闭，并确认窗口已不可见。

    与 ``custom.show_loading_window`` 的自动轮询状态机不同，此函数
    严格按「显示 → 固定延时 → 关闭 → 状态确认」的顺序执行，用于
    ``isFoldAtStartup == True`` 分支的确定性过渡展示。
    """
    app = QApplication.instance()
    try:
        screen = QGuiApplication.primaryScreen()
        geom = screen.availableGeometry()
    except Exception as e:
        _log(f"_show_and_close_loading_windows: cannot get screen geometry: {e}",
             level="warning")
        return

    win1 = LoadingWindow(app_label)
    win2 = LoadingWindow(app_label)
    w, h = win1.width(), win1.height()
    x1 = geom.left()
    x2 = geom.left() + geom.width() - w
    y = geom.top() + (geom.height() - h) // 2
    win1.move(x1, y)
    win2.move(x2, y)

    # ---- 显示阶段 ----
    win1.show()
    win2.show()
    if app is not None:
        app.processEvents()
    _log(f"_show_and_close_loading_windows: displayed, will hold for {display_s:.1f}s")

    # ---- a. 延时 display_s 秒 ----
    _precise_sleep(display_s)

    # ---- b. 关闭加载窗口 ----
    win1.close()
    win2.close()
    _log("_show_and_close_loading_windows: close() called on both windows")

    # ---- c. 确认加载窗口完全关闭 ----
    if app is not None:
        # 多次 drain 事件循环，以确保 pending 的 Close/Expose 事件全部处理完
        for _ in range(3):
            app.processEvents()
            _precise_sleep(0.02)
    closed = (not win1.isVisible()) and (not win2.isVisible())
    if closed:
        _log("_show_and_close_loading_windows: both windows confirmed closed")
    else:
        _log(f"_show_and_close_loading_windows: still visible after close "
             f"(win1={win1.isVisible()}, win2={win2.isVisible()})",
             level="warning")


# ------------------------------------------------------------------ #
#  窗口操作
# ------------------------------------------------------------------ #

def _find_window_by_title(target_title):
    """枚举所有可见顶层窗口，返回标题完全匹配的窗口句柄（HWND），未找到返回 None。"""
    if not sys.platform.startswith("win"):
        return None

    found = [None]

    def _enum_cb(hwnd, _lparam):
        if not _user32.IsWindowVisible(hwnd):
            return True
        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value == target_title:
            found[0] = hwnd
            return False
        return True

    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    _user32.EnumWindows(CMPFUNC(_enum_cb), 0)
    return found[0]


def _bring_window_to_foreground(hwnd):
    """将指定窗口置于前台并获取焦点（Alt workaround 绕过前台锁定）。"""
    try:
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, _SW_RESTORE)
        _user32.keybd_event(_VK_MENU, 0, 0, 0)
        _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)
        _user32.SetForegroundWindow(hwnd)
    except Exception as e:
        _log(f"_bring_window_to_foreground: {e}", level="error")


# ------------------------------------------------------------------ #
#  Toast 通知
# ------------------------------------------------------------------ #

def _show_toast(text_fields):
    """通过系统 Toast 通知机制弹出提示（与 icc_ce.py 保持一致）。"""
    try:
        from windows_toasts import Toast, WindowsToaster
        toast = Toast(text_fields=text_fields)
        toaster = WindowsToaster("希沃批注替换")
        toaster.show_toast(toast)
    except Exception as e:
        _log(f"_show_toast: {e}", level="error")


# ------------------------------------------------------------------ #
#  主入口
# ------------------------------------------------------------------ #

def run():
    """ICA 系列批注软件的取消收纳入口。返回 0 表示成功，1 表示致命错误。"""
    # ================= 1. 配置读取与方案定位 =================
    try:
        settings = load_settings()
    except Exception as e:
        _log(f"ica_series.run: load_settings failed: {e}", level="error")
        return 1

    ica = settings.get("ica_series", {})
    profiles = ica.get("ica_profiles", [])
    active_id = ica.get("ica_active_profile_id", "")

    profile = None
    for p in profiles:
        if p.get("id") == active_id:
            profile = p
            break
    if profile is None and profiles:
        profile = profiles[0]
        _log(f"ica_series.run: active_id '{active_id}' not found, "
             f"falling back to '{profile.get('id', '')}'", level="warning")

    if profile is None:
        _log("ica_series.run: no profile available", level="error")
        return 1

    exe_path = profile.get("exe_path", "")
    window_title = profile.get("window_title", "")
    unhide_scheme = profile.get("unhide_scheme", "scheme1")
    auto_pen = profile.get("auto_pen", False)
    shortcut_scope = profile.get("shortcut_scope", "local")
    proc_name = _process_base_name(exe_path)
    app_label = app_name_from_path(exe_path) if exe_path else "Ink Canvas Artistry"

    _log(f"ica_series.run: profile id={profile.get('id')}, "
         f"exe='{exe_path}', proc_name='{proc_name}', "
         f"scope={shortcut_scope}, scheme={unhide_scheme}, auto_pen={auto_pen}")

    # ================= 2. 进程状态检测 / 启动 / Settings.json 分支 =================
    started_proc = None

    if exe_path and proc_name:
        running_before = _is_process_running(proc_name)
        if not running_before:
            # --- 2.1 启动进程 ---
            _log(f"ica_series.run: process '{proc_name}' not running, launching '{exe_path}'")
            started_proc = launch_executable(exe_path)
            if started_proc is None:
                _show_toast(["ICA 启动失败", f"无法启动程序：{app_label}"])
                _log(f"ica_series.run: launch_executable failed for '{exe_path}'",
                     level="error")
                return 0  # 启动失败：用户侧已 Toast，优雅退出

            # 启动命令状态确认：Popen.poll() 返回 None 表示子进程已创建并运行中
            launch_confirmed = False
            try:
                launch_confirmed = started_proc.poll() is None
            except Exception as e:
                _log(f"ica_series.run: started_proc.poll() error: {e}", level="warning")
            _log(f"ica_series.run: launch confirmed={launch_confirmed} "
                 f"(pid={getattr(started_proc, 'pid', '?')})")

            # --- 2.2 读取进程同级目录 Settings.json（立即） ---
            is_fold, _cfg_status = _read_is_fold_at_startup(exe_path)

            if is_fold is False:
                # isFoldAtStartup = false → 等进程就绪，如果不用切换到笔，那么不再执行取消收纳
                _log("ica_series.run: isFoldAtStartup=false; waiting process ready then exiting")
                ok = _wait_process_ready(proc_name, timeout_s=5.0)
                _log(f"ica_series.run: process ready after launch={ok} (isFoldAtStartup=false)")
                if not auto_pen:
                    _log("ica_series.run: auto_pen=false; skipping unhide step and exiting")
                    return 0  # 不切换到笔 → 直接退出

            # isFoldAtStartup = true 或 配置缺失/异常 → 按收纳流程走：展示加载窗口
            # --- 2.3.a/b/c 加载窗口：显示 1 秒 → 关闭 → 确认关闭 ---
            _log("ica_series.run: isFoldAtStartup=true (or unknown); show loading windows")
            _show_and_close_loading_windows(app_label, display_s=1.0)

            # --- 启动就绪状态确认（最长 5 秒） ---
            ok = _wait_process_ready(proc_name, timeout_s=5.0)
            _log(f"ica_series.run: process ready after loading windows={ok}")
            if ok:
                # 进程就绪后再给主线程一个 200ms 喘息时间：创建窗口 / 注册快捷键 / 初始化输入钩子
                _precise_sleep(1)
            else:
                _log("ica_series.run: process not confirmed within 5s; proceeding anyway",
                     level="warning")
        else:
            _log(f"ica_series.run: process '{proc_name}' already running; skipping launch step")
    else:
        _log("ica_series.run: exe_path or proc_name empty; skipping launch step",
             level="warning")

    # ================= 3. 窗口焦点控制（仅局部快捷键需要） =================
    if shortcut_scope == "local" and window_title:
        hwnd = _find_window_by_title(window_title)
        if hwnd:
            _bring_window_to_foreground(hwnd)
            _precise_sleep(0.1)
            _log(f"ica_series.run: brought to foreground: '{window_title}'")
        else:
            _show_toast([f"未找到{window_title}窗口"])
            _log(f"ica_series.run: window not found: '{window_title}', aborting",
                 level="warning")
            return 0
    elif shortcut_scope == "global":
        _log("ica_series.run: shortcut_scope=global, skipping window focus")
    else:
        _log("ica_series.run: shortcut_scope=local but window_title empty; skipping focus")

    # ================= 4. 取消收纳方案 =================
    _log(f"ica_series.run: executing unhide scheme '{unhide_scheme}' (auto_pen={auto_pen})")
    try:
        if unhide_scheme == "scheme1":
            _send_alt_key(_VK_D)
            if not auto_pen:
                _precise_sleep(0.1)
                _send_alt_key(_VK_Q)
        elif unhide_scheme == "scheme2":
            if running_before:
                _send_alt_key(_VK_B)
                _precise_sleep(0.3)
                _send_alt_key(_VK_B)
            if auto_pen:
                _precise_sleep(0.1)
                _send_alt_key(_VK_D)
        else:
            _log(f"ica_series.run: unknown unhide_scheme: '{unhide_scheme}'",
                 level="warning")
    except Exception as e:
        _log(f"ica_series.run: keyboard simulation failed: {e}", level="error")
        return 1

    _log("ica_series.run: finished successfully")
    return 0
