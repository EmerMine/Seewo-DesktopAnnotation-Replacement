"""ICA 系列批注软件的取消收纳（unhide）逻辑。

运行流程：
  1. 读取配置文件中的 ``ica_active_profile_id``，确定当前激活的方案
  2. 从激活方案中读取 ``window_title``，枚举系统窗口并聚焦匹配窗口
     - 未找到时通过系统 Toast 通知提示用户
  3. 从激活方案中读取 ``unhide_scheme``，模拟键盘快捷键取消收纳：
     - scheme1: Alt+D，若 auto_pen 为 False 则 0.1s 后 Alt+Q
     - scheme2: Alt+B → 0.1s → Alt+B，若 auto_pen 为 True 则 0.1s 后 Alt+D
"""
import os
import sys
import time
import ctypes

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import load_settings, _log

# Win32 API 句柄（仅 Windows 平台可用）
_user32 = ctypes.windll.user32
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


# ------------------------------------------------------------------ #
#  键盘模拟
# ------------------------------------------------------------------ #

def _send_alt_key(vk_key):
    """模拟 Alt+<key> 组合键的完整按下与释放序列。

    顺序：Alt 按下 → 目标键按下 → 目标键释放 → Alt 释放。
    使用 keybd_event（系统级输入模拟 API），确保按键事件能被
    当前前台窗口正确接收。
    """
    try:
        _user32.keybd_event(_VK_MENU, 0, 0, 0)                    # Alt 按下
        _user32.keybd_event(vk_key, 0, 0, 0)                      # 目标键按下
        _user32.keybd_event(vk_key, 0, _KEYEVENTF_KEYUP, 0)       # 目标键释放
        _user32.keybd_event(_VK_MENU, 0, _KEYEVENTF_KEYUP, 0)     # Alt 释放
    except Exception as e:
        _log(f"_send_alt_key(0x{vk_key:02X}): {e}", level="error")


def _precise_sleep(seconds):
    """使用高精度定时器休眠指定秒数。

    Windows 默认定时器分辨率约 15.6ms，调用 ``timeBeginPeriod(1)``
    可将分辨率提升至 1ms，确保 0.1s 延迟的准确性。
    """
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
#  窗口操作
# ------------------------------------------------------------------ #

def _find_window_by_title(target_title):
    """枚举所有可见顶层窗口，返回标题完全匹配的窗口句柄（HWND）。

    使用 Win32 ``EnumWindows`` + ``GetWindowTextW`` 遍历所有顶级窗口，
    与 ``settings/ica_series.py`` 的窗口检测逻辑保持一致的技术路线，
    但此处为精确字符串匹配（非正则）。

    返回 None 表示未找到匹配窗口。
    """
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
            return False  # 找到匹配，停止枚举
        return True

    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    _user32.EnumWindows(CMPFUNC(_enum_cb), 0)
    return found[0]


def _bring_window_to_foreground(hwnd):
    """将指定窗口置于前台并获取焦点。

    Windows 的 ``SetForegroundWindow`` 存在前台锁定限制：仅当调用
    进程已在前台时才允许切换。通过先模拟一次 Alt 按键释放来满足
    该限制（业界通用的 workaround）。
    """
    try:
        # 如果窗口最小化，先恢复
        if _user32.IsIconic(hwnd):
            _user32.ShowWindow(hwnd, _SW_RESTORE)
        # 模拟 Alt 按下+释放，绕过前台锁定
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
    """ICA 系列批注软件的取消收纳入口。

    返回 0 表示成功，1 表示失败。
    """
    # ---------- 1. 配置读取与方案定位 ----------
    try:
        settings = load_settings()
    except Exception as e:
        _log(f"ica_series.run: load_settings failed: {e}", level="error")
        return 1

    ica = settings.get("ica_series", {})
    profiles = ica.get("ica_profiles", [])
    active_id = ica.get("ica_active_profile_id", "")

    # 查找当前激活的配置方案
    profile = None
    for p in profiles:
        if p.get("id") == active_id:
            profile = p
            break
    if profile is None and profiles:
        # 激活 ID 无效时回退到第一个方案
        profile = profiles[0]
        _log(f"ica_series.run: active_id '{active_id}' not found, "
             f"falling back to '{profile.get('id', '')}'", level="warning")

    if profile is None:
        _log("ica_series.run: no profile available", level="error")
        return 1

    window_title = profile.get("window_title", "")
    unhide_scheme = profile.get("unhide_scheme", "scheme1")
    auto_pen = profile.get("auto_pen", False)

    # ---------- 2. 窗口焦点控制 ----------
    if window_title:
        hwnd = _find_window_by_title(window_title)
        if hwnd:
            _bring_window_to_foreground(hwnd)
            # 等待窗口响应前台切换后再发送快捷键
            _precise_sleep(0.1)
        else:
            _show_toast(["未找到指定窗口", window_title])
            _log(f"ica_series.run: window not found: '{window_title}'",
                 level="warning")

    # ---------- 3. 取消收纳方案 ----------
    try:
        if unhide_scheme == "scheme1":
            # 方案 1：Alt+D 取消收纳
            _send_alt_key(_VK_D)
            if not auto_pen:
                _precise_sleep(0.1)
                _send_alt_key(_VK_Q)
        elif unhide_scheme == "scheme2":
            # 方案 2：Alt+B → 0.1s → Alt+B，auto_pen 为 True 时追加 Alt+D
            _send_alt_key(_VK_B)
            _precise_sleep(0.1)
            _send_alt_key(_VK_B)
            if auto_pen:
                _precise_sleep(0.1)
                _send_alt_key(_VK_D)
        else:
            _log(f"ica_series.run: unknown unhide_scheme: '{unhide_scheme}'",
                 level="warning")
    except Exception as e:
        _log(f"ica_series.run: keyboard simulation failed: {e}",
             level="error")
        return 1

    return 0
