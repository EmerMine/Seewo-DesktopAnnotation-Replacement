import sys
import os
import json
import subprocess
import tempfile
import ctypes
import webbrowser
import winreg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QSpinBox, QMessageBox,
    QSpacerItem, QSizePolicy, QGroupBox, QStyle,
)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_base_dir(), "config.json")

def get_icon_path():
    return os.path.join(get_base_dir(), "icon.ico")

def get_shield_icon_path():
    return os.path.join(get_base_dir(), "admin.ico")

DEFAULT_SETTINGS = {
    "show_loading_window": True,
    "auto_pen": False,
    "thorough_hide": False,
    "loading_duration": 3,
}

def load_settings():
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    settings = DEFAULT_SETTINGS.copy()
    settings.update(data)
    return settings

def save_settings(settings):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

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

def is_installed():
    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        debugger, _ = winreg.QueryValueEx(key, "Debugger")
        winreg.CloseKey(key)
        expected = os.path.join(get_base_dir(), "Annotation.exe")
        if debugger.strip('"') != expected:
            return False
        lnk_path = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
        return os.path.exists(lnk_path)
    except Exception:
        return False

def check_security_software_running():
    """返回正在运行的安全软件名称，若未找到则返回 None"""
    known_software = {
        "hipstray.exe": "火绒安全软件",
        "360tray.exe": "360安全卫士",
        "qqpctray.exe": "腾讯电脑管家",
        "pyas.exe": "PYAS Security Antivirus",
        # 常用的就这些吧，懒得补了
    }
    try:
        output = subprocess.check_output(
            "tasklist /fo csv /nh", shell=True, encoding="mbcs", errors="ignore"
        )
        output_lower = output.lower()
        for proc, name in known_software.items():
            if proc in output_lower:
                return name
    except Exception:
        pass
    return None

def create_and_run_bat(is_install):
    target_exe = os.path.join(get_base_dir(), "Annotation.exe")
    if is_install and not os.path.exists(target_exe):
        QMessageBox.critical(None, "错误", f"未找到 {target_exe}")
        return

    lnk_path_str = r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
    reg_key = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"

    if is_install:
        bat_content = f'''@echo off
reg add "{reg_key}" /v Debugger /t REG_SZ /d "\\"{target_exe}\\"" /f
if %errorlevel% neq 0 exit /b 1
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('{lnk_path_str}'); $Shortcut.TargetPath = '{target_exe}'; $Shortcut.Arguments = '-settings'; $Shortcut.Save()"
del "%~f0"
'''
    else:
        bat_content = f'''@echo off
reg delete "{reg_key}" /f
if exist "{lnk_path_str}" del /f /q "{lnk_path_str}"
del "%~f0"
'''

    fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='icc_ce_')
    try:
        with os.fdopen(fd, 'w', encoding='mbcs') as f:
            f.write(bat_content)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", bat_path, "", None, 0
        )
    except Exception as e:
        QMessageBox.critical(None, "错误", f"执行失败：{e}")

class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICC-CE 批注替换")
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

class FAQWindow(QWidget):
    """常见问题独立窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("常见问题")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 问题 1
        lbl_q1 = QLabel("<b>Q: 弹出「需要使用新应用以打开此 icc 链接」窗口</b>")
        lbl_a1 = QLabel("A: 请开启 ICC-CE「启用外部协议 (icc://)」设置项。\n"
                        "路径：ICC-CE 工具栏 > 工具 > 设置 > 新设置窗口 > 打开新设置窗口 > "
                        "高级选项 > 外部协议调用 > 开启「启用外部协议 (icc://)」设置项。")
        lbl_a1.setWordWrap(True)

        # 问题 2
        lbl_q2 = QLabel("<b>Q: 切换到批注模式时，无法自动切换到笔</b>")
        lbl_a2 = QLabel("A: 将 ICC-CE 升级到 1.7.18.7 及以上。")
        lbl_a2.setWordWrap(True)

        # OK 按钮（右下角，默认按钮）
        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(80)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.close)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_ok)

        layout.addWidget(lbl_q1)
        layout.addWidget(lbl_a1)
        layout.addSpacing(10)
        layout.addWidget(lbl_q2)
        layout.addWidget(lbl_a2)
        layout.addStretch()
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.resize(420, 280)

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICC-CE 批注替换 - 设置")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.settings = load_settings()
        self._init_ui = True

        # 安装状态行：状态标签在左，刷新和安装/卸载按钮在右
        self.lbl_install_status = QLabel()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        self.btn_action = QPushButton()
        self.btn_action.setFixedWidth(80)
        # 添加 admin.ico 图标
        shield_path = get_shield_icon_path()
        if os.path.exists(shield_path):
            self.btn_action.setIcon(QIcon(shield_path))
        self.btn_action.clicked.connect(self.on_action_clicked)

        install_row = QHBoxLayout()
        install_row.addWidget(self.lbl_install_status)
        install_row.addStretch()
        install_row.addWidget(self.btn_refresh)
        install_row.addWidget(self.btn_action)
        grp_install = QGroupBox("安装状态")
        grp_install.setLayout(install_row)

        # ---- 其余 UI 不变 ----
        # 显示加载窗口
        self.chk_show = QCheckBox("显示加载窗口")
        self.chk_show.setChecked(self.settings["show_loading_window"])
        self.chk_show.toggled.connect(self.on_show_toggled)

        indent = (self.style().pixelMetric(QStyle.PM_IndicatorWidth) + # type: ignore
                  self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing)) # type: ignore
        dur_layout = QHBoxLayout()
        dur_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        dur_layout.addWidget(QLabel("加载窗口显示时长（秒）："))
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(1, 10)
        self.spin_dur.setValue(self.settings["loading_duration"])
        self.spin_dur.valueChanged.connect(self.on_dur_changed)
        dur_layout.addWidget(self.spin_dur)
        dur_layout.addStretch()
        self.spin_dur.setEnabled(self.settings["show_loading_window"])

        lbl_hint = QLabel("请按计算机运行 icc:// 协议的时长酌情调整")
        lbl_hint.setStyleSheet("color: gray; font-size: 9pt;")
        hint_layout = QHBoxLayout()
        hint_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        hint_layout.addWidget(lbl_hint)
        hint_layout.addStretch()

        self.chk_pen = QCheckBox("自动切换为笔")
        self.chk_pen.setChecked(self.settings["auto_pen"])
        self.chk_pen.toggled.connect(self.on_pen_toggled)

        grp_replace = QGroupBox("批注替换")
        replace_layout = QVBoxLayout()
        replace_layout.addWidget(self.chk_show)
        replace_layout.addLayout(dur_layout)
        replace_layout.addLayout(hint_layout)
        replace_layout.addWidget(self.chk_pen)
        grp_replace.setLayout(replace_layout)

        # 收纳时彻底隐藏 + 显示工具栏按钮
        self.chk_hide = QCheckBox("收纳时彻底隐藏")
        self.chk_hide.setChecked(self.settings["thorough_hide"])
        self.chk_hide.toggled.connect(self.on_hide_toggled)

        self.btn_show_toolbar = QPushButton("显示 ICC-CE 工具栏")
        self.btn_show_toolbar.clicked.connect(lambda: run_protocol("icc://unfold"))

        icc_layout = QVBoxLayout()
        icc_layout.addWidget(self.chk_hide)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_show_toolbar)
        btn_row.addStretch()
        icc_layout.addLayout(btn_row)
        grp_icc = QGroupBox("ICC-CE 隐藏设置")
        grp_icc.setLayout(icc_layout)

        self.thorough_timer = QTimer(self)
        self.thorough_timer.setSingleShot(True)
        self.thorough_timer.timeout.connect(self.restore_hide_cb)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.btn_faq = QPushButton("常见问题")
        self.btn_faq.clicked.connect(self.show_faq)
        bottom_layout.addWidget(self.btn_faq)
        bottom_layout.addStretch()
        self.btn_about = QPushButton("关于")
        self.btn_about.setFixedWidth(80)
        self.btn_about.clicked.connect(lambda: QMessageBox.about(self, "关于 ICC-CE 批注替换", "ICC-CE 批注替换 v2.0\n本程序可替换「希沃桌面2.0 桌面批注」为 ICC-CE 批注。"))
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_about)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp_install)
        main_layout.addWidget(grp_replace)
        main_layout.addWidget(grp_icc)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        # 状态刷新定时器
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)
        self.refresh_timer.timeout.connect(self.check_install_status)
        # 延迟安装检查定时器（单次）
        self._delay_install_check_timer = QTimer(self)
        self._delay_install_check_timer.setSingleShot(True)
        self._delay_install_check_timer.timeout.connect(self._start_install_check)

        self._last_installed_state = None
        self._refresh_attempts = 0
        self._install_completed_message_shown = False
        self._install_status = None   # 当前安装状态字符串

        self._init_ui = False
        self.update_install_buttons()
        self.resize(320, 430)

    def _get_install_status(self):
        """检查注册表和快捷方式，返回 'installed', 'broken' 或 'not_installed'"""
        reg_ok = False
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            debugger, _ = winreg.QueryValueEx(key, "Debugger")
            winreg.CloseKey(key)
            expected = os.path.join(get_base_dir(), "Annotation.exe")
            if debugger.strip('"') == expected:
                reg_ok = True
        except Exception:
            pass

        lnk_path = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
        lnk_ok = os.path.exists(lnk_path)

        if reg_ok and lnk_ok:
            return "installed"
        elif not reg_ok and not lnk_ok:
            return "not_installed"
        else:
            return "broken"

    def update_install_buttons(self):
        status = self._get_install_status()
        self._install_status = status
        if status == "installed":
            self.btn_action.setText("卸载")
            self.lbl_install_status.setText("√ 已安装")
            self.lbl_install_status.setStyleSheet("color: green")
        elif status == "broken":
            self.btn_action.setText("修复")
            self.lbl_install_status.setText("[!] 安装损坏")
            self.lbl_install_status.setStyleSheet("color: #FFA500")
        else:
            self.btn_action.setText("安装")
            self.lbl_install_status.setText("× 未安装")
            self.lbl_install_status.setStyleSheet("color: red")

    def restore_hide_cb(self):
        self.chk_hide.setText("收纳时彻底隐藏")
        self.chk_hide.setEnabled(True)

    def _warn_security_software(self):
        sw_name = check_security_software_running()
        if not sw_name:
            return True

        msg_box = QMessageBox(QMessageBox.Warning, "警告", "", parent=self) # type: ignore
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            f"<h3>请关闭「{sw_name}」</h3>"
            "<p>该程序通过映像劫持替换「希沃桌面2.0 桌面批注」，这是系统敏感操作，"
            "可能会被安全软件拦截导致安装失败。请退出安全软件后单击「继续」。</p>"
        )
        btn_continue = msg_box.addButton("继续", QMessageBox.AcceptRole) # type: ignore
        btn_cancel = msg_box.addButton("取消", QMessageBox.RejectRole) # type: ignore
        msg_box.setDefaultButton(btn_cancel)
        msg_box.exec()
        return msg_box.clickedButton() == btn_continue

    def _start_install_check(self):
        self.refresh_timer.start()

    def on_refresh_clicked(self):
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self.update_install_buttons()

    def on_action_clicked(self):
        if not self._warn_security_software():
            return
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self._last_installed_state = self._install_status
        self._refresh_attempts = 0
        if self._install_status == "installed":
            create_and_run_bat(is_install=False)
        else:
            create_and_run_bat(is_install=True)
        self._delay_install_check_timer.start(3000)

    def check_install_status(self):
        current = self._get_install_status()
        self._refresh_attempts += 1
        if current != self._last_installed_state:
            if current == "installed" and not self._install_completed_message_shown:
                self._install_completed_message_shown = True
                QMessageBox.information(
                    self, "提示",
                    "<h3>请开启「外部协议调用」</h3>"
                    "<p>本程序需要 ICC-CE 开启该功能后才可正常使用，路径：ICC-CE 工具栏 > 工具 > 设置 > "
                    "新设置窗口 > 打开新设置窗口 > 高级选项 > 外部协议调用 > 开启「启用外部协议 (icc://)」设置项。</p>"
                )
            self._last_installed_state = current
            self.refresh_timer.stop()
            self.update_install_buttons()
        elif self._refresh_attempts >= 10:
            self.refresh_timer.stop()
            self.update_install_buttons()

    def show_faq(self):
        self.faq_window = FAQWindow()
        self.faq_window.show()

    def on_show_toggled(self, checked):
        self.settings["show_loading_window"] = checked
        self.spin_dur.setEnabled(checked)
        save_settings(self.settings)

    def on_pen_toggled(self, checked):
        self.settings["auto_pen"] = checked
        save_settings(self.settings)

    def on_hide_toggled(self, checked):
        if self._init_ui:
            return
        if checked:
            run_protocol("icc://thoroughhideon")
        else:
            run_protocol("icc://thoroughhideoff")
        self.settings["thorough_hide"] = checked
        save_settings(self.settings)
        self.chk_hide.setEnabled(False)
        self.chk_hide.setText("设置中，请稍后...")
        self.thorough_timer.start(3000)

    def on_dur_changed(self, val):
        self.settings["loading_duration"] = val
        save_settings(self.settings)

def main():
    args = sys.argv[1:]
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) # type: ignore
    app = QApplication(sys.argv)

    if not is_installed() and not args:
        msg_box = QMessageBox(QMessageBox.Information, "提示", "") # type: ignore
        msg_box.setWindowIcon(QIcon(get_icon_path()))
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>欢迎</h3>"
            "<p>欢迎使用「ICC-CE 批注替换」！</p>"
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
import sys
import os
import json
import subprocess
import tempfile
import ctypes
import webbrowser
import winreg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QSpinBox, QMessageBox,
    QSpacerItem, QSizePolicy, QGroupBox, QStyle,
)

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

def get_config_path():
    return os.path.join(get_base_dir(), "config.json")

def get_icon_path():
    return os.path.join(get_base_dir(), "icon.ico")

def get_shield_icon_path():
    return os.path.join(get_base_dir(), "admin.ico")

DEFAULT_SETTINGS = {
    "show_loading_window": True,
    "auto_pen": False,
    "thorough_hide": False,
    "loading_duration": 3,
}

def load_settings():
    config_path = get_config_path()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    settings = DEFAULT_SETTINGS.copy()
    settings.update(data)
    return settings

def save_settings(settings):
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

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

def is_installed():
    try:
        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        debugger, _ = winreg.QueryValueEx(key, "Debugger")
        winreg.CloseKey(key)
        expected = os.path.join(get_base_dir(), "Annotation.exe")
        if debugger.strip('"') != expected:
            return False
        lnk_path = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
        return os.path.exists(lnk_path)
    except Exception:
        return False

def check_security_software_running():
    """返回正在运行的安全软件名称，若未找到则返回 None"""
    known_software = {
        "hipstray.exe": "火绒安全软件",
        "360tray.exe": "360安全卫士",
        "qqpctray.exe": "腾讯电脑管家",
        "pyas.exe": "PYAS Security Antivirus",
        # 常用的就这些吧，懒得补了
    }
    try:
        output = subprocess.check_output(
            "tasklist /fo csv /nh", shell=True, encoding="mbcs", errors="ignore"
        )
        output_lower = output.lower()
        for proc, name in known_software.items():
            if proc in output_lower:
                return name
    except Exception:
        pass
    return None

def create_and_run_bat(is_install):
    target_exe = os.path.join(get_base_dir(), "Annotation.exe")
    if is_install and not os.path.exists(target_exe):
        QMessageBox.critical(None, "错误", f"未找到 {target_exe}")
        return

    lnk_path_str = r"%ProgramData%\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
    reg_key = r"HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"

    if is_install:
        bat_content = f'''@echo off
reg add "{reg_key}" /v Debugger /t REG_SZ /d "\\"{target_exe}\\"" /f
if %errorlevel% neq 0 exit /b 1
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('{lnk_path_str}'); $Shortcut.TargetPath = '{target_exe}'; $Shortcut.Arguments = '-settings'; $Shortcut.Save()"
del "%~f0"
'''
    else:
        bat_content = f'''@echo off
reg delete "{reg_key}" /f
if exist "{lnk_path_str}" del /f /q "{lnk_path_str}"
del "%~f0"
'''

    fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='icc_ce_')
    try:
        with os.fdopen(fd, 'w', encoding='mbcs') as f:
            f.write(bat_content)
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", bat_path, "", None, 0
        )
    except Exception as e:
        QMessageBox.critical(None, "错误", f"执行失败：{e}")

class LoadingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICC-CE 批注替换")
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

class FAQWindow(QWidget):
    """常见问题独立窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("常见问题")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore

        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 问题 1
        lbl_q1 = QLabel("<b>Q: 弹出「需要使用新应用以打开此 icc 链接」窗口</b>")
        lbl_a1 = QLabel("A: 请开启 ICC-CE「启用外部协议 (icc://)」设置项。\n"
                        "路径：ICC-CE 工具栏 > 工具 > 设置 > 新设置窗口 > 打开新设置窗口 > "
                        "高级选项 > 外部协议调用 > 开启「启用外部协议 (icc://)」设置项。")
        lbl_a1.setWordWrap(True)

        # 问题 2
        lbl_q2 = QLabel("<b>Q: 切换到批注模式时，无法自动切换到笔</b>")
        lbl_a2 = QLabel("A: 将 ICC-CE 升级到 1.7.18.7 及以上。")
        lbl_a2.setWordWrap(True)

        # OK 按钮（右下角，默认按钮）
        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(80)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.close)
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_ok)

        layout.addWidget(lbl_q1)
        layout.addWidget(lbl_a1)
        layout.addSpacing(10)
        layout.addWidget(lbl_q2)
        layout.addWidget(lbl_a2)
        layout.addStretch()
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.resize(420, 280)

class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ICC-CE 批注替换 - 设置")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.settings = load_settings()
        self._init_ui = True

        # 安装状态行：状态标签在左，刷新和安装/卸载按钮在右
        self.lbl_install_status = QLabel()
        self.btn_refresh = QPushButton("刷新")
        self.btn_refresh.setFixedWidth(80)
        self.btn_refresh.clicked.connect(self.on_refresh_clicked)
        self.btn_action = QPushButton()
        self.btn_action.setFixedWidth(80)
        # 添加 admin.ico 图标
        shield_path = get_shield_icon_path()
        if os.path.exists(shield_path):
            self.btn_action.setIcon(QIcon(shield_path))
        self.btn_action.clicked.connect(self.on_action_clicked)

        install_row = QHBoxLayout()
        install_row.addWidget(self.lbl_install_status)
        install_row.addStretch()
        install_row.addWidget(self.btn_refresh)
        install_row.addWidget(self.btn_action)
        grp_install = QGroupBox("安装状态")
        grp_install.setLayout(install_row)

        # ---- 其余 UI 不变 ----
        # 显示加载窗口
        self.chk_show = QCheckBox("显示加载窗口")
        self.chk_show.setChecked(self.settings["show_loading_window"])
        self.chk_show.toggled.connect(self.on_show_toggled)

        indent = (self.style().pixelMetric(QStyle.PM_IndicatorWidth) + # type: ignore
                  self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing)) # type: ignore
        dur_layout = QHBoxLayout()
        dur_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        dur_layout.addWidget(QLabel("加载窗口显示时长（秒）："))
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(1, 10)
        self.spin_dur.setValue(self.settings["loading_duration"])
        self.spin_dur.valueChanged.connect(self.on_dur_changed)
        dur_layout.addWidget(self.spin_dur)
        dur_layout.addStretch()
        self.spin_dur.setEnabled(self.settings["show_loading_window"])

        lbl_hint = QLabel("请按计算机运行 icc:// 协议的时长酌情调整")
        lbl_hint.setStyleSheet("color: gray; font-size: 9pt;")
        hint_layout = QHBoxLayout()
        hint_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        hint_layout.addWidget(lbl_hint)
        hint_layout.addStretch()

        self.chk_pen = QCheckBox("自动切换为笔")
        self.chk_pen.setChecked(self.settings["auto_pen"])
        self.chk_pen.toggled.connect(self.on_pen_toggled)

        grp_replace = QGroupBox("批注替换")
        replace_layout = QVBoxLayout()
        replace_layout.addWidget(self.chk_show)
        replace_layout.addLayout(dur_layout)
        replace_layout.addLayout(hint_layout)
        replace_layout.addWidget(self.chk_pen)
        grp_replace.setLayout(replace_layout)

        # 收纳时彻底隐藏 + 显示工具栏按钮
        self.chk_hide = QCheckBox("收纳时彻底隐藏")
        self.chk_hide.setChecked(self.settings["thorough_hide"])
        self.chk_hide.toggled.connect(self.on_hide_toggled)

        self.btn_show_toolbar = QPushButton("显示 ICC-CE 工具栏")
        self.btn_show_toolbar.clicked.connect(lambda: run_protocol("icc://unfold"))

        icc_layout = QVBoxLayout()
        icc_layout.addWidget(self.chk_hide)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_show_toolbar)
        btn_row.addStretch()
        icc_layout.addLayout(btn_row)
        grp_icc = QGroupBox("ICC-CE 隐藏设置")
        grp_icc.setLayout(icc_layout)

        self.thorough_timer = QTimer(self)
        self.thorough_timer.setSingleShot(True)
        self.thorough_timer.timeout.connect(self.restore_hide_cb)

        # 底部按钮
        bottom_layout = QHBoxLayout()
        self.btn_faq = QPushButton("常见问题")
        self.btn_faq.clicked.connect(self.show_faq)
        bottom_layout.addWidget(self.btn_faq)
        bottom_layout.addStretch()
        self.btn_about = QPushButton("关于")
        self.btn_about.setFixedWidth(80)
        self.btn_about.clicked.connect(lambda: QMessageBox.about(self, "关于 ICC-CE 批注替换", "ICC-CE 批注替换 v2.0\n本程序可替换「希沃桌面2.0 桌面批注」为 ICC-CE 批注。"))
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_about)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp_install)
        main_layout.addWidget(grp_replace)
        main_layout.addWidget(grp_icc)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        # 状态刷新定时器
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)
        self.refresh_timer.timeout.connect(self.check_install_status)
        # 延迟安装检查定时器（单次）
        self._delay_install_check_timer = QTimer(self)
        self._delay_install_check_timer.setSingleShot(True)
        self._delay_install_check_timer.timeout.connect(self._start_install_check)

        self._last_installed_state = None
        self._refresh_attempts = 0
        self._install_completed_message_shown = False
        self._install_status = None   # 当前安装状态字符串

        self._init_ui = False
        self.update_install_buttons()
        self.resize(320, 430)

    def _get_install_status(self):
        """检查注册表和快捷方式，返回 'installed', 'broken' 或 'not_installed'"""
        reg_ok = False
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            debugger, _ = winreg.QueryValueEx(key, "Debugger")
            winreg.CloseKey(key)
            expected = os.path.join(get_base_dir(), "Annotation.exe")
            if debugger.strip('"') == expected:
                reg_ok = True
        except Exception:
            pass

        lnk_path = r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\ICC-CE 批注替换设置.lnk"
        lnk_ok = os.path.exists(lnk_path)

        if reg_ok and lnk_ok:
            return "installed"
        elif not reg_ok and not lnk_ok:
            return "not_installed"
        else:
            return "broken"

    def update_install_buttons(self):
        status = self._get_install_status()
        self._install_status = status
        if status == "installed":
            self.btn_action.setText("卸载")
            self.lbl_install_status.setText("√ 已安装")
            self.lbl_install_status.setStyleSheet("color: green")
        elif status == "broken":
            self.btn_action.setText("修复")
            self.lbl_install_status.setText("[!] 安装损坏")
            self.lbl_install_status.setStyleSheet("color: #FFA500")
        else:
            self.btn_action.setText("安装")
            self.lbl_install_status.setText("× 未安装")
            self.lbl_install_status.setStyleSheet("color: red")

    def restore_hide_cb(self):
        self.chk_hide.setText("收纳时彻底隐藏")
        self.chk_hide.setEnabled(True)

    def _warn_security_software(self):
        sw_name = check_security_software_running()
        if not sw_name:
            return True

        msg_box = QMessageBox(QMessageBox.Warning, "警告", "", parent=self) # type: ignore
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            f"<h3>请关闭「{sw_name}」</h3>"
            "<p>该程序通过映像劫持替换「希沃桌面2.0 桌面批注」，这是系统敏感操作，"
            "可能会被安全软件拦截导致安装失败。请退出安全软件后单击「继续」。</p>"
        )
        btn_continue = msg_box.addButton("继续", QMessageBox.AcceptRole) # type: ignore
        btn_cancel = msg_box.addButton("取消", QMessageBox.RejectRole) # type: ignore
        msg_box.setDefaultButton(btn_cancel)
        msg_box.exec()
        return msg_box.clickedButton() == btn_continue

    def _start_install_check(self):
        self.refresh_timer.start()

    def on_refresh_clicked(self):
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self.update_install_buttons()

    def on_action_clicked(self):
        if not self._warn_security_software():
            return
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self._last_installed_state = self._install_status
        self._refresh_attempts = 0
        if self._install_status == "installed":
            create_and_run_bat(is_install=False)
        else:
            create_and_run_bat(is_install=True)
        self._delay_install_check_timer.start(3000)

    def check_install_status(self):
        current = self._get_install_status()
        self._refresh_attempts += 1
        if current != self._last_installed_state:
            if current == "installed" and not self._install_completed_message_shown:
                self._install_completed_message_shown = True
                QMessageBox.information(
                    self, "提示",
                    "<h3>请开启「外部协议调用」</h3>"
                    "<p>本程序需要 ICC-CE 开启该功能后才可正常使用，路径：ICC-CE 工具栏 > 工具 > 设置 > "
                    "新设置窗口 > 打开新设置窗口 > 高级选项 > 外部协议调用 > 开启「启用外部协议 (icc://)」设置项。</p>"
                )
            self._last_installed_state = current
            self.refresh_timer.stop()
            self.update_install_buttons()
        elif self._refresh_attempts >= 10:
            self.refresh_timer.stop()
            self.update_install_buttons()

    def show_faq(self):
        self.faq_window = FAQWindow()
        self.faq_window.show()

    def on_show_toggled(self, checked):
        self.settings["show_loading_window"] = checked
        self.spin_dur.setEnabled(checked)
        save_settings(self.settings)

    def on_pen_toggled(self, checked):
        self.settings["auto_pen"] = checked
        save_settings(self.settings)

    def on_hide_toggled(self, checked):
        if self._init_ui:
            return
        if checked:
            run_protocol("icc://thoroughhideon")
        else:
            run_protocol("icc://thoroughhideoff")
        self.settings["thorough_hide"] = checked
        save_settings(self.settings)
        self.chk_hide.setEnabled(False)
        self.chk_hide.setText("设置中，请稍后...")
        self.thorough_timer.start(3000)

    def on_dur_changed(self, val):
        self.settings["loading_duration"] = val
        save_settings(self.settings)

def main():
    args = sys.argv[1:]
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True) # type: ignore
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True) # type: ignore
    app = QApplication(sys.argv)

    if not is_installed() and not args:
        msg_box = QMessageBox(QMessageBox.Information, "提示", "") # type: ignore
        msg_box.setWindowIcon(QIcon(get_icon_path()))
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>欢迎</h3>"
            "<p>欢迎使用「ICC-CE 批注替换」！</p>"
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