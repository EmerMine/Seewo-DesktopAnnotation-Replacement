import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import DESKTOP_ANNOTATION_BACKUP


def run():
    """启动备份的原始 DesktopAnnotationBackup.exe 并立即退出。"""
    if not os.path.exists(DESKTOP_ANNOTATION_BACKUP):
        return 0
    try:
        subprocess.Popen(
            [DESKTOP_ANNOTATION_BACKUP],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass
    return 0
