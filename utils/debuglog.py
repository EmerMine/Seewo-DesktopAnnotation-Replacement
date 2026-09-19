"""调试模式与日志输出。"""
import sys
import os
import time

from .paths import get_data_dir

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


def _log(msg, level="info"):
    try:
        log_path = os.path.join(get_data_dir(), "sar.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [{level.upper()}] {msg}\n")
    except Exception:
        pass
