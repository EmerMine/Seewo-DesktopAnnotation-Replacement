import sys
import os
import argparse
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QPushButton, QMessageBox
from settings import SettingsWindow
from settings.update import check_for_update, check_for_update_async # type: ignore
from unhide_annotation_apps import icc_ce, none, original, custom, ica_series
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
                        help="打开设置窗口")
    parser.add_argument("-run_annotation_app", "--run_annotation_app", action="store_true",
                        dest="run_annotation_app",
                        help="直接启动批注软件（供 bat 入口调用）")
    parser.add_argument("-h", "--help", action="store_true", dest="help",
                        help="显示帮助信息")
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        _debug_log(f"未识别的命令行参数已忽略: {unknown}")
    if args.help:
        parser.print_help()
        sys.exit(0)
    return args


def _run_annotation_app():
    settings = load_settings()
    if settings["general"].get("ink_product") == "none":
        exit_code = none.run()
    elif settings["general"].get("ink_product") == "icc_ce":
        exit_code = icc_ce.run()
    elif settings["general"].get("ink_product") == "keep":
        exit_code = original.run()
    elif settings["general"].get("ink_product") == "custom":
        exit_code = custom.run()
    elif settings["general"].get("ink_product") == "ica":
        exit_code = ica_series.run()
    else:
        exit_code = 1
    if settings["general"].get("auto_check_update", True):
        check_for_update()
    return exit_code


def main():
    args = _parse_args(sys.argv[1:])

    if args.debug:
        set_debug_mode(True)
        _debug_log("命令行参数 -debug 已激活，强制启用调试模式")
    _debug_log(f"main() 启动, sys.argv={sys.argv[1:]}, _is_debug()={_is_debug()}")

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = QApplication(sys.argv)
    settings = load_settings()
    apply_style(settings["general"].get("style", "windowsvista"))
    apply_theme(settings["general"].get("theme", "system"))

    if args.run_annotation_app:
        sys.exit(_run_annotation_app())

    if get_install_status() == INSTALL_STATUS_NOT_INSTALLED:
        msg_box = QMessageBox(QMessageBox.Information, "希沃批注替换" + ("（调试模式）" if _is_debug() else ""), "") # type: ignore
        msg_box.setWindowIcon(QIcon(get_icon_path()))
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>欢迎</h3>"
            "<p>欢迎使用「希沃批注替换」！</p>"
            '下列软件与本程序搭配使用最为完美：'
            '<ul>'
            '<li><a href="https://github.com/Dongsf119/Ink-Canvas-Artistry">Dongsf119/Ink-Canvas-Artistry</a></li>'
            '<li><a href="https://github.com/Huchangzhi/Ink-Canvas-Artistry-hcz">Huchangzhi/Ink-Canvas-Artistry-hcz</a></li>'
            '<li><a href="https://github.com/MiraEvo/Ink-Canvas-Artistry">MiraEvo/Ink-Canvas-Artistry</a></li>'
            '<li><a href="https://github.com/DaleGreen123/Ink-Canvas-DeepRethink">DaleGreen123/Ink-Canvas-DeepRethink</a></li>'
            '<li><a href="https://github.com/MKStoler1024/InkCanvasforDrawing">MKStoler1024/InkCanvasforDrawing</a></li>'
            '<li><a href="https://github.com/Tayasui-rainnya/Ink-Canvas-Artistry"> Tayasui-rainnya/Ink-Canvas-Artistry</a></li>'
            '<li><a href="https://github.com/TomKe123/Ink-Canvas-Artistry">TomKe123/Ink-Canvas-Artistry</a></li>'
            '<li><a href="https://github.com/awesome-iwb/icc-20240610-stable">awesome-iwb/icc-20240610-stable</a> 请注意您可能无法访问该链接</li>'
            '<li><a href="https://github.com/InkCanvasForClass/community">InkCanvasForClass/community</a></li>'
            '</ul>'
            '下列软件与本程序搭配使用时，存在一些已知问题：'
            '<ul>'
            '<li><a href="https://github.com/InkCanvas/Ink-Canvas-Artistry">InkCanvas/Ink-Canvas-Artistry</a></li>'
            '<li><a href="https://github.com/BaiYang2238/Ink-Canvas-Better">BaiYang2238/Ink-Canvas-Better</a></li>'
            '<li><a href="https://github.com/jizilin6732/Ink-Canvas-Attention">jizilin6732/Ink-Canvas-Attention</a></li>'
            '<li><a href="https://github.com/pigeons2023/Ink-Canvas-Basic">pigeons2023/Ink-Canvas-Basic</a></li>'
            '</ul>'
            '本程序不对下列软件提供支持：'
            '<ul>'
            '<li><a href="https://github.com/WXRIW/Ink-Canvas">WXRIW/Ink-Canvas</a></li>'
            '<li><a href="https://github.com/clover-yan/Ink-Canvas-Plus">clover-yan/Ink-Canvas-Plus</a></li>'
            '<li><a href="https://github.com/LiuYan-xwx/InkCanvasForClass-Remastered">LiuYan-xwx/InkCanvasForClass-Remastered</a></li>'
            '</ul>'
            "<p>不安装以上任意一款软件，您仍然可以使用本程序的「禁用希沃桌面批注」功能，或是使用自定义程序。</p>"
            "<p>您可以单击上方链接前往 Github 下载。</p>"
        )
        msg_box.exec()

    w = SettingsWindow()
    w.show()
    if settings["general"].get("auto_check_update", True):
        check_for_update_async(parent=w, show_dialog=True) # type: ignore
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
