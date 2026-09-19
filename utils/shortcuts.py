"""开始菜单 / 桌面快捷方式的创建、检测与删除。"""
import os
import sys
import base64
import subprocess

from .config import SHORTCUT_NAME
from .paths import get_base_dir, get_icon_path

START_MENU_LNK = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                              r"Microsoft\Windows\Start Menu\Programs", SHORTCUT_NAME)
DESKTOP_LNK = os.path.join(os.path.expanduser("~"), "Desktop", SHORTCUT_NAME)


def shortcut_exists(kind):
    if kind == "start_menu":
        return os.path.exists(START_MENU_LNK)
    if kind == "desktop":
        return os.path.exists(DESKTOP_LNK)
    return False


def _ps_quote(s):
    """将任意字符串安全嵌入 PowerShell 单引号字符串（把 ' 替换成 ''）。"""
    return s.replace("'", "''")


def create_shortcut(kind):
    """在开始菜单或桌面创建快捷方式。

    根据运行模式自动选择目标：
      - 源码模式 (sys.frozen=False): TargetPath=pythonw.exe, Arguments='"main.py" -settings'
      - 打包模式 (sys.frozen=True):  TargetPath=Annotation.exe, Arguments='-settings'
    """
    if kind == "start_menu":
        lnk = START_MENU_LNK
    elif kind == "desktop":
        lnk = DESKTOP_LNK
    else:
        return False

    base = get_base_dir()

    if getattr(sys, 'frozen', False):
        target = os.path.join(base, "Annotation.exe")
        arguments = "-settings"
        icon = target
    else:
        target = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        main_py = os.path.join(base, "main.py")
        arguments = f'"{main_py}" -settings'
        icon_path = get_icon_path()
        icon = icon_path if os.path.exists(icon_path) else sys.executable

    workdir = base

    ps_script = (
        "$wsh = New-Object -ComObject WScript.Shell;"
        f"$s = $wsh.CreateShortcut('{_ps_quote(lnk)}');"
        f"$s.TargetPath = '{_ps_quote(target)}';"
        f"$s.Arguments = '{_ps_quote(arguments)}';"
        f"$s.WorkingDirectory = '{_ps_quote(workdir)}';"
        f"$s.IconLocation = '{_ps_quote(icon)},0';"
        "$s.Save()"
    )

    try:
        encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')
        subprocess.run(
            ["powershell", "-NoProfile", "-EncodedCommand", encoded],
            check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"快捷方式创建失败 (exit={e.returncode}): "
            f"{e.stderr.decode('mbcs', errors='ignore').strip() or e.stdout.decode('mbcs', errors='ignore').strip()}"
        ) from e
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
