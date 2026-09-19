"""进程与外部命令操作。"""
import os
import sys
import subprocess


def run_protocol(uri):
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(
                ["cmd", "/c", "start", "", uri],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
    except Exception:
        pass


def kill_process_by_path(exe_path):
    """强制结束所有命令行与 exe_path 匹配的进程（taskkill /IM 不支持完整路径匹配，
    这里用 wmic 列出命令行后筛选）。忽略找不到进程的情况。"""
    if not os.path.exists(exe_path):
        return
    try:
        result = subprocess.run(
            ["wmic", "process", "where",
             f"name='{os.path.basename(exe_path)}'",
             "get", "processid,commandline", "/format:csv"],
            capture_output=True, text=True, encoding="mbcs", errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return
    exe_lower = exe_path.lower().replace("/", "\\")
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Node") or line.lower().startswith("commandline"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        cmdline = ",".join(parts[1:-1]).lower().replace("/", "\\")
        pid = parts[-1].strip()
        if not pid or not pid.isdigit():
            continue
        if exe_lower in cmdline:
            try:
                subprocess.run(
                    ["taskkill", "/f", "/pid", pid],
                    capture_output=True,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception:
                pass
