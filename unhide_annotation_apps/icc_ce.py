import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from utils import (
    load_settings,
    save_settings,
    run_protocol,
    get_icon_path,
    check_icc_ce_url_protocol,
    ICC_STATUS_OK,
    ICC_STATUS_NO_PROTOCOL,
    ICC_STATUS_BROKEN,
)


def _show_toast(text_fields):
    try:
        from windows_toasts import Toast, WindowsToaster
        toast = Toast(text_fields=text_fields)
        toaster = WindowsToaster("希沃批注替换")
        toaster.show_toast(toast)
    except Exception:
        pass


class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("希沃批注替换")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint) # type: ignore
        self.setWindowIcon(QIcon(get_icon_path()))
        label = QLabel("ICC-CE 批注加载中……")
        label.setFont(QFont("微软雅黑", 12))
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())


def _fallback_to_none(protocol_status):
    if protocol_status == ICC_STATUS_NO_PROTOCOL:
        reason = "未检测到ICC-CE的URL协议（icc://）注册"
    elif protocol_status == ICC_STATUS_BROKEN:
        reason = "ICC-CE的URL协议已损坏"
    else:
        reason = "ICC-CE的URL协议不可用"

    settings = load_settings()
    settings["general"]["ink_product"] = "none"
    save_settings(settings)

    _show_toast(["ICC-CE 不可用", f"{reason}，已自动切换为禁用希沃桌面批注模式。"])


def run():
    protocol_status = check_icc_ce_url_protocol()
    if protocol_status != ICC_STATUS_OK:
        _fallback_to_none(protocol_status)
        from unhide_annotation_apps import none
        return none.run()

    settings = load_settings()
    run_protocol("icc://unfold")
    if settings["iccce"].get("auto_pen", False):
        run_protocol("icc://tool/pen")
    if settings["iccce"].get("show_loading_window", True):
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
        dur_ms = settings["iccce"].get("loading_duration", 3) * 1000
        QTimer.singleShot(dur_ms, lambda: (win1.close(), win2.close(), QApplication.instance().quit())) # type: ignore
        return QApplication.instance().exec() # type: ignore
