import os
import sys
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from utils import load_settings, get_icon_path


class LoadingWindow(QWidget):
    def __init__(self, app_label="自定义程序"):
        super().__init__()
        self.setWindowTitle("希沃批注替换")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint) # type: ignore
        self.setWindowIcon(QIcon(get_icon_path()))
        label = QLabel(f"{app_label} 加载中……")
        label.setFont(QFont("微软雅黑", 12))
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


def app_name_from_path(exe_path):
    """从可执行程序路径中提取显示名称（不含目录与扩展名）。

    路径为空或异常时返回 ``"自定义程序"``。
    """
    try:
        if exe_path:
            base = os.path.basename(exe_path)
            name, _ext = os.path.splitext(base)
            if name:
                return name
    except Exception:
        pass
    return "自定义程序"


def launch_executable(exe_path):
    """按扩展名启动指定可执行程序，返回 :class:`subprocess.Popen` 对象，失败返回 ``None``。

    - ``.bat`` / ``.cmd`` 以 ``cmd /c`` 方式启动
    - 其它类型（``.exe`` / ``.pif`` / ``.com``）直接启动
    所有子进程都传入 ``CREATE_NO_WINDOW`` 标志（Windows）。
    """
    if not exe_path or not os.path.exists(exe_path):
        return None
    try:
        ext = os.path.splitext(exe_path)[1].lower()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if ext in (".bat", ".cmd"):
            return subprocess.Popen(["cmd", "/c", exe_path], creationflags=flags)
        return subprocess.Popen([exe_path], creationflags=flags)
    except Exception:
        return None


def show_loading_window(proc, app_label="自定义程序", duration_s=3,
                        min_display_ms=1500):
    """显示双屏加载窗口（与 ``custom.run`` 相同的状态机），窗口关闭后返回。

    Parameters
    ----------
    proc: subprocess.Popen | None
        已启动的子进程；为 ``None`` 时跳过进程就绪轮询，只按时间关闭。
    app_label: str
        显示在加载提示中的应用名称。
    duration_s: int
        最长展示时长（秒），超时后强制关闭。
    min_display_ms: int
        最小展示时长（毫秒），防止界面闪烁。
    """
    screen = QGuiApplication.primaryScreen()
    geom = screen.availableGeometry()
    win1 = LoadingWindow(app_label)
    win2 = LoadingWindow(app_label)
    w, h = win1.width(), win1.height()
    x1 = geom.left()
    x2 = geom.left() + geom.width() - w
    y = geom.top() + (geom.height() - h) // 2
    win1.move(x1, y)
    win2.move(x2, y)
    win1.show()
    win2.show()

    dur_ms = max(1, int(duration_s)) * 1000
    poll_interval_ms = 200
    state = {"elapsed": 0, "min_passed": False, "proc_ready": proc is None}
    app = QApplication.instance()

    def _close():
        win1.close()
        win2.close()
        if app is not None:
            app.quit()

    def _maybe_close():
        if state["min_passed"] and state["proc_ready"]:
            _close()

    def _on_min_passed():
        state["min_passed"] = True
        _maybe_close()

    def _poll():
        state["elapsed"] += poll_interval_ms
        if proc is not None:
            try:
                if proc.poll() is None:
                    state["proc_ready"] = True
                    _maybe_close()
                    return
            except Exception:
                pass
        if state["elapsed"] >= dur_ms:
            _close()
            return
        QTimer.singleShot(poll_interval_ms, _poll)

    QTimer.singleShot(min_display_ms, _on_min_passed)
    QTimer.singleShot(poll_interval_ms, _poll)
    QTimer.singleShot(dur_ms + 500, _close)

    if app is not None:
        app.exec()


def run():
    settings = load_settings()
    exe_path = settings["custom"].get("exe_path", "")
    if not exe_path or not os.path.exists(exe_path):
        return 0

    proc = launch_executable(exe_path)
    if proc is None:
        return 0

    if not settings["custom"].get("show_loading_window", True):
        return 0

    dur_s = settings["custom"].get("loading_duration", 3)
    app_label = app_name_from_path(exe_path)
    show_loading_window(proc, app_label=app_label, duration_s=dur_s)
    return 0
