import os
import sys
import subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from utils import load_settings, get_icon_path


class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("希沃批注替换")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint) # type: ignore
        self.setWindowIcon(QIcon(get_icon_path()))
        label = QLabel("自定义程序加载中……")
        label.setFont(QFont("微软雅黑", 12))
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


def run():
    settings = load_settings()
    exe_path = settings["custom"].get("exe_path", "")
    if not exe_path or not os.path.exists(exe_path):
        return 0

    try:
        if os.path.splitext(exe_path)[1].lower() in (".bat", ".cmd"):
            proc = subprocess.Popen(
                ["cmd", "/c", exe_path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            proc = subprocess.Popen(
                [exe_path],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except Exception:
        return 0

    if not settings["custom"].get("show_loading_window", True):
        return 0

    screen = QGuiApplication.primaryScreen()
    geom = screen.availableGeometry()
    win1 = LoadingWindow()
    win2 = LoadingWindow()
    w, h = win1.width(), win1.height()
    x1 = geom.left()
    x2 = geom.left() + geom.width() - w
    y = geom.top() + (geom.height() - h) // 2
    win1.move(x1, y)
    win2.move(x2, y)
    win1.show()
    win2.show()

    dur_ms = settings["custom"].get("loading_duration", 3) * 1000
    poll_interval_ms = 200
    min_display_ms = 1500
    state = {"elapsed": 0, "min_passed": False, "proc_ready": False}
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
    return 0
