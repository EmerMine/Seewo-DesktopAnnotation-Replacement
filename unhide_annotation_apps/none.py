import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from utils import (
    load_settings,
    get_icon_path,
)


class DisabledMessageWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("希沃批注替换")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint) # type: ignore
        self.setWindowIcon(QIcon(get_icon_path()))
        label = QLabel("希沃桌面批注已被禁用")
        label.setFont(QFont("微软雅黑", 12))
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


def run():
    settings = load_settings()
    if not settings.get("none_show_disabled_msg", True):
        return 0
    screen = QGuiApplication.primaryScreen()
    geom = screen.availableGeometry()
    win1 = DisabledMessageWindow()
    win2 = DisabledMessageWindow()
    w, h = win1.width(), win1.height()
    x1 = geom.left()
    x2 = geom.left() + geom.width() - w
    y = geom.top() + (geom.height() - h) // 2
    win1.move(x1, y)
    win2.move(x2, y)
    win1.show()
    win2.show()
    dur_ms = max(1, int(settings.get("none_msg_duration", 2))) * 1000
    QTimer.singleShot(dur_ms, lambda: (win1.close(), win2.close(), QApplication.instance().quit())) # type: ignore
    return QApplication.instance().exec() # type: ignore
