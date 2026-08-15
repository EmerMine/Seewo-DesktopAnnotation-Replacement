import sys
import os
import argparse
import webbrowser
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from settings import SettingsWindow
from settings.update import check_for_update, check_for_update_async # type: ignore
from unhide_annotation_apps import icc_ce, none, original
from utils import (
    load_settings,
    get_install_status,
    INSTALL_STATUS_INSTALLED,
    INSTALL_STATUS_NOT_INSTALLED,
    get_icon_path,
    apply_style,
    apply_theme,
    _is_debug,
    _debug_log,
    set_debug_mode,
)


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="Seewo-DesktopAnnotation-Replacement",
        description="希沃批注替换工具",
        add_help=False,
    )
    parser.add_argument("-debug", "--debug", action="store_true", dest="debug",
                        help="强制启用调试模式")
    parser.add_argument("-settings", "--settings", action="store_true", dest="settings",
                        help="直接打开设置窗口")
    parser.add_argument("-h", "--help", action="store_true", dest="help",
                        help="显示帮助信息")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        _debug_log(f"未识别的命令行参数已忽略: {unknown}")
    if args.help:
        parser.print_help()
        sys.exit(0)
    return args


def main():
    args = _parse_args(sys.argv[1:])

    if args.debug:
        set_debug_mode(True)
        _debug_log("命令行参数 -debug 已激活，强制启用调试模式")
    _debug_log(f"main() 启动, sys.argv={sys.argv[1:]}, _is_debug()={_is_debug()}")

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = QApplication(sys.argv)
    settings = load_settings()
    apply_style(settings.get("style", "windowsvista"))
    apply_theme(settings.get("theme", "system"))

    if get_install_status() == INSTALL_STATUS_NOT_INSTALLED and not args.settings:
        msg_box = QMessageBox(QMessageBox.Information, "希沃批注替换" + ("（调试模式）" if _is_debug() else ""), "") # type: ignore
        msg_box.setWindowIcon(QIcon(get_icon_path()))
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>欢迎</h3>"
            "<p>欢迎使用「希沃批注替换」！</p>"
            "<p>使用本程序前，建议在您的计算机上安装以下软件，以替换希沃桌面批注：</p>"
            "<ul>"
            "<li><a href='https://github.com/InkCanvasForClass/community'>InkCanvasForClass Community Edition</a> 1.7.18.7+</li>"
            "<li><a href='https://github.com/Dongsf119/Ink-Canvas-Artistry'>Dongsf119/Ink-Canvas-Artistry</a> 任意版本</li>"
            "</ul>"
            "<p>您也可以安装以下任意软件，但体验欠佳，并且有已知的 bug：</p>"
            "<ul>"
            "<li><a href='https://github.com/InkCanvas/Ink-Canvas-Artistry'>InkCanvas/Ink-Canvas-Artistry</a> 任意版本</li>"
            "<li><a href='https://github.com/BaiYang2238/Ink-Canvas-Better'>Ink Canvas Better</a> 任意版本</li>"
            "<li><a href='https://github.com/InkCanvas/InkCanvasForClass'>InkCanvasForClass</a> 任意版本</li>"
            "</ul>"
            "<p>不安装以上任意一款软件，您仍然可以使用本程序的「禁用希沃桌面批注」功能。</p>"
            "<p>您可以单击上方链接前往 Github 下载。</p>"
        )
        msg_box.exec()

        w = SettingsWindow()
        w.show()
        if settings.get("auto_check_update", True):
            check_for_update_async(parent=w, show_dialog=True) # type: ignore
        sys.exit(app.exec())

    if args.settings:
        w = SettingsWindow()
        w.show()
        if settings.get("auto_check_update", True):
            check_for_update_async(parent=w, show_dialog=True)
        sys.exit(app.exec())

    if settings.get("ink_product") == "none":
        exit_code = none.run()

    elif settings.get("ink_product") == "icc_ce":
        exit_code = icc_ce.run()

    elif settings.get("ink_product") == "keep":
        exit_code = original.run()

    else:
        exit_code = 1

    if settings.get("auto_check_update", True):
        check_for_update()

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
