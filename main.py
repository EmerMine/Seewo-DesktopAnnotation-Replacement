import sys
import os
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from settings import SettingsWindow
from unhide_annotation_apps import icc_ce
from utils import (
    load_settings,
    is_installed,
    get_icon_path,
    apply_style,
    apply_theme,
)

def main():
    args = sys.argv[1:]
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = QApplication(sys.argv)
    settings = load_settings()
    apply_style(settings.get("style", "windowsvista"))
    apply_theme(settings.get("theme", "system"))

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

    sys.exit(icc_ce.run())

if __name__ == "__main__":
    main()
