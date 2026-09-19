import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config import APPS_EXE_SHA256, DESKTOP_ANNOTATION_BACKUP
from utils.hashing import sha256_file


def _show_toast(text_fields):
    """通过系统 Toast 通知弹出提示（与 icc_ce.py / ica_series.py 保持一致）。"""
    try:
        from windows_toasts import Toast, WindowsToaster
        toast = Toast(text_fields=text_fields)
        toaster = WindowsToaster("希沃批注替换")
        toaster.show_toast(toast)
    except Exception:
        pass


def _backup_corrupted():
    """专项校验 DesktopAnnotationBackup.exe 是否损坏。

    其 SHA-256 与预设 exe_sha256（替换程序哈希）完全一致时，说明备份文件
    是替换程序的副本而非原始希沃程序，视为损坏。
    """
    if not os.path.exists(DESKTOP_ANNOTATION_BACKUP):
        return False
    return sha256_file(DESKTOP_ANNOTATION_BACKUP) == APPS_EXE_SHA256


def run():
    """启动备份的原始 DesktopAnnotationBackup.exe 并立即退出。"""
    if not os.path.exists(DESKTOP_ANNOTATION_BACKUP):
        return 0
    # 运行前强制哈希校验：备份与替换程序同哈希即为损坏，禁止运行
    if _backup_corrupted():
        _show_toast(["Seewo-DesktopAnnotation-Replacement", "希沃桌面批注已损坏，请前往软件内修复"])
        return 1
    try:
        subprocess.Popen(
            [DESKTOP_ANNOTATION_BACKUP],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
    return 0
