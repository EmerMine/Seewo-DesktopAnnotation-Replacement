"""路径解析：基础目录、数据目录与资源文件路径。"""
import os
import sys


def _is_win11():
    ver = sys.getwindowsversion()
    return ver.build >= 22000


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        # 本文件位于 <项目根>/utils/ 下，需向上一级才是项目根
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_data_dir():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        internal = os.path.join(base, "_internal")
        return internal if os.path.isdir(internal) else base
    else:
        cwd = os.getcwd()
        internal = os.path.join(cwd, "_internal")
        return internal if os.path.isdir(internal) else cwd


def get_config_path():
    return os.path.join(get_data_dir(), "config.json")


def get_icon_path():
    return os.path.join(get_data_dir(), "resources", "icon.ico")


def get_shield_icon_path():
    filename = "win11.ico" if _is_win11() else "win10.ico"
    return os.path.join(get_data_dir(), "resources", "admin", filename)
