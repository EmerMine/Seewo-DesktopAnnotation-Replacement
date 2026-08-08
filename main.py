import sys
import os
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from settings import SettingsWindow
from settings.update import check_for_update, check_for_update_async # type: ignore
from unhide_annotation_apps import icc_ce, none
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
            "<p>使用本程序前，建议在您的计算机上安装以下任意软件：</p>"
            "<ul>"
            # "<li>「Ink Canvas Artistry (ICA)」任意版本</li>"
            # "<li>「InkCanvasForClass (ICC)」任意版本</li>"
            "<li>「InkCanvasForClass Community Edition (ICC-CE)」1.7.18.7+</li>"
            "</ul>"
            "您可以单击下方按钮前往 Github 下载。</p>"
        )
        # btn_ica_website = QPushButton("ICA Github")
        # btn_icc_website = QPushButton("ICC Github")
        btn_icc_ce_website = QPushButton("ICC-CE Github")
        # msg_box.addButton(btn_ica_website, QMessageBox.AcceptRole) # type: ignore
        # msg_box.addButton(btn_icc_website, QMessageBox.AcceptRole) # type: ignore
        msg_box.addButton(btn_icc_ce_website, QMessageBox.AcceptRole) # type: ignore
        ok_btn = msg_box.addButton("OK", QMessageBox.AcceptRole) # type: ignore
        msg_box.setDefaultButton(ok_btn)
        
        # btn_ica_website.clicked.connect(
        #     lambda: webbrowser.open("https://github.com/InkCanvas/Ink-Canvas-Artistry")
        # )
        # btn_icc_website.clicked.connect(
        #     lambda: webbrowser.open("https://github.com/InkCanvas/InkCanvasForClass")
        # )
        btn_icc_ce_website.clicked.connect(
            lambda: webbrowser.open("https://github.com/InkCanvasForClass/community")
        )
        msg_box.exec()

        w = SettingsWindow()
        w.show()
        if settings.get("auto_check_update", True):
            check_for_update_async(parent=w, show_dialog=True) # type: ignore
        sys.exit(app.exec())

    if "-settings" in args:
        w = SettingsWindow()
        w.show()
        if settings.get("auto_check_update", True):
            check_for_update_async(parent=w, show_dialog=True)
        sys.exit(app.exec())

    if settings.get("ink_product") == "none":
        exit_code = none.run()

    elif settings.get("ink_product") == "icc_ce":
        exit_code = icc_ce.run()

    else:
        exit_code = 1

    if settings.get("auto_check_update", True):
        check_for_update()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
