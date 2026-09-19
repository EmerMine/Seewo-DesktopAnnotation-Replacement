"""管理员权限执行临时 PowerShell 脚本。"""
import os
import tempfile
import ctypes

from .debuglog import _is_debug, _debug_log
from .qtstyle import _critical


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
