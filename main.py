import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QMessageBox, QVBoxLayout,
)
import webbrowser
from settings import SettingsWindow
from utils import (
    load_settings,
    run_protocol,
    is_installed,
    get_icon_path,
)

class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("希沃批注替换")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint) # type: ignore
        self.setWindowIcon(QIcon(get_icon_path()))
        label = QLabel("ICC-CE 批注加载中...")
        label.setFont(QFont("微软雅黑", 12))
        layout = QVBoxLayout()
        layout.addWidget(label)
        layout.setContentsMargins(20, 15, 20, 15)
        self.setLayout(layout)
        self.adjustSize()
        self.setFixedSize(self.size())

def main():
    args = sys.argv[1:]
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) # type: ignore
    app = QApplication(sys.argv)

    if not is_installed() and not args:
        msg_box = QMessageBox(QMessageBox.Information, "希沃批注替换", "") # type: ignore
        msg_box.setWindowIcon(QIcon(get_icon_path()))
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>欢迎</h3>"
            "<p>欢迎使用「希沃批注替换」！</p>"
            "<p>使用本程序前，请先确保您的计算机上安装了「InkCanvasForClass Community Edition」，且版本大于 1.7.18.7。"
            "您可以单击下方按钮前往官网或 Github 上下载。</p>"
        )
        btn_website = QPushButton("前往官网")
        btn_github = QPushButton("前往 Github")
        msg_box.addButton(btn_website, QMessageBox.AcceptRole) # type: ignore
        msg_box.addButton(btn_github, QMessageBox.AcceptRole) # type: ignore
        msg_box.addButton("OK", QMessageBox.AcceptRole) # type: ignore
        btn_website.clicked.connect(
            lambda: webbrowser.open("https://inkcanvasforclass.github.io/website/download")
        )
        btn_github.clicked.connect(
            lambda: webbrowser.open("https://github.com/InkCanvasForClass/community/releases")
        )
        msg_box.exec()

        w = SettingsWindow()
        w.show()
        sys.exit(app.exec())

    if "-settings" in args:
        w = SettingsWindow()
        w.show()
        sys.exit(app.exec())

    settings = load_settings()
    run_protocol("icc://unfold")
    if settings.get("auto_pen", False):
        run_protocol("icc://tool/pen")
    if settings.get("show_loading_window", True):
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
        dur_ms = settings.get("loading_duration", 3) * 1000
        QTimer.singleShot(dur_ms, lambda: (win1.close(), win2.close(), app.quit()))
        sys.exit(app.exec())
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
