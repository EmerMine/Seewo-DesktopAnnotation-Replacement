"""IFEO（Image File Execution Options）劫持检测与清理。"""
import winreg

from .config import IFEO_BASE_KEY, _IFEO_TARGET_NAMES
from .elevated import _run_elevated


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
