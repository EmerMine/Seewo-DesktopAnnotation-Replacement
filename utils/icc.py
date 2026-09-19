"""ICC-CE URL 协议（icc://）检测与可执行文件路径解析。"""
import os
import winreg

from .config import (
    ICC_PROTOCOL_KEY,
    ICC_COMMAND_KEY,
    ICC_STATUS_OK,
    ICC_STATUS_NO_PROTOCOL,
    ICC_STATUS_BROKEN,
    ICC_MIN_AUTO_PEN_VERSION,
)
from .winversion import get_file_version


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
