import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import winreg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QPushButton, QCheckBox, QMessageBox, QComboBox, QRadioButton,
    QGroupBox,
)
from utils import (
    VERSION,
    get_base_dir,
    get_icon_path,
    get_shield_icon_path,
    load_settings,
    save_settings,
    apply_style,
    apply_theme,
    check_security_software_running,
    create_and_run_bat,
    shortcut_exists,
    create_shortcut,
    delete_shortcut,
)
from .icc_ce import ICCCESettingsWindow
from .none import NoneSettingsWindow


class FAQWindow(QWidget):
    """常见问题独立窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("常见问题 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore

        layout = QVBoxLayout()
        layout.setSpacing(10)

        lbl_q1 = QLabel("<b>Q: 弹出「需要使用新应用以打开此 icc 链接」窗口</b>")
        lbl_a1 = QLabel("A: 请开启 ICC-CE「启用外部协议 (icc://)」设置项。\n"
                        "路径：ICC-CE 设置 > 通用 > 基本 > 开启「启用外部协议 (icc://)」设置项。")
        lbl_a1.setWordWrap(True)

        lbl_q2 = QLabel("<b>Q: 切换到批注模式时，无法自动切换到笔</b>")
        lbl_a2 = QLabel("A: 将 ICC-CE 升级到 1.7.18.7 及以上。")
        lbl_a2.setWordWrap(True)

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
        self.setWindowTitle("希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.settings = load_settings()
        self._init_ui = True

        self.lbl_install_status = None
        self.btn_refresh = None
        self.btn_action = QPushButton()
        shield_path = get_shield_icon_path()
        if os.path.exists(shield_path):
            self.btn_action.setIcon(QIcon(shield_path))
        self.btn_action.clicked.connect(self.on_action_clicked)

        self.chk_start_menu = QCheckBox("开始菜单快捷方式")
        self.chk_start_menu._original_text = "开始菜单快捷方式" # type: ignore
        self.chk_start_menu.setChecked(shortcut_exists("start_menu"))
        self.chk_start_menu.toggled.connect(self.on_start_menu_toggled)
        self.chk_desktop = QCheckBox("桌面快捷方式")
        self.chk_desktop._original_text = "桌面快捷方式" # type: ignore
        self.chk_desktop.setChecked(shortcut_exists("desktop"))
        self.chk_desktop.toggled.connect(self.on_desktop_toggled)
        grp_shortcuts = QGroupBox("快捷方式")
        shortcuts_layout = QVBoxLayout()
        shortcuts_layout.addWidget(self.chk_start_menu)
        shortcuts_layout.addWidget(self.chk_desktop)
        grp_shortcuts.setLayout(shortcuts_layout)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel("风格："))
        self.cmb_style = QComboBox()
        self.cmb_style.addItem("系统默认", "windowsvista")
        self.cmb_style.addItem("Fusion", "Fusion")
        current_style = self.settings.get("style", "windowsvista")
        idx = self.cmb_style.findData(current_style)
        self.cmb_style.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_style.currentIndexChanged.connect(self.on_style_changed)
        style_row.addWidget(self.cmb_style)
        style_row.addStretch()

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("主题："))
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem("跟随系统", "system")
        self.cmb_theme.addItem("浅色", "light")
        self.cmb_theme.addItem("深色", "dark")
        current_theme = self.settings.get("theme", "system")
        idx = self.cmb_theme.findData(current_theme)
        self.cmb_theme.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_theme.currentIndexChanged.connect(self.on_theme_changed)
        theme_row.addWidget(self.cmb_theme)
        theme_row.addStretch()

        grp_common = QGroupBox("通用")
        common_layout = QVBoxLayout()
        common_layout.addLayout(style_row)
        common_layout.addLayout(theme_row)
        grp_common.setLayout(common_layout)

        self.radio_group = QButtonGroup(self)
        self.radio_none = QRadioButton("空程序（禁用希沃桌面批注）")
        self.radio_ia = QRadioButton("Ink Canvas Artistry (WIP)")
        self.radio_ia.setEnabled(False)
        self.radio_icc = QRadioButton("InkCanvasForClass (WIP)")
        self.radio_icc.setEnabled(False)
        self.radio_icc_ce = QRadioButton("ICC-CE")
        self.radio_group.addButton(self.radio_none, 0)
        self.radio_group.addButton(self.radio_ia, 1)
        self.radio_group.addButton(self.radio_icc, 2)
        self.radio_group.addButton(self.radio_icc_ce, 3)
        product = self.settings.get("ink_product", "none")
        product_map = {"none": self.radio_none, "ica": self.radio_ia, "icc": self.radio_icc, "icc_ce": self.radio_icc_ce}
        product_map.get(product, self.radio_none).setChecked(True)
        self.radio_group.idClicked.connect(self.on_product_changed)

        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        link_color = "#7ab8ff" if is_dark else "#0066cc"
        link_style = f"<a href='#' style='color: {link_color}; text-decoration: none;'>设置</a>"
        self.lbl_set_none = QLabel(link_style)
        self.lbl_set_ia = QLabel(link_style)
        self.lbl_set_icc = QLabel(link_style)
        self.lbl_set_icc_ce = QLabel(link_style)
        for lbl in (self.lbl_set_none, self.lbl_set_ia, self.lbl_set_icc, self.lbl_set_icc_ce):
            lbl.setOpenExternalLinks(False)
            lbl.setCursor(Qt.PointingHandCursor) # type: ignore

        self.lbl_set_none.linkActivated.connect(lambda: self._open_product_settings("none"))
        self.lbl_set_ia.linkActivated.connect(lambda: self._open_product_settings("ica"))
        self.lbl_set_icc.linkActivated.connect(lambda: self._open_product_settings("icc"))
        self.lbl_set_icc_ce.linkActivated.connect(lambda: self._open_product_settings("icc_ce"))

        row_none = QHBoxLayout()
        row_none.addWidget(self.radio_none)
        row_none.addStretch()
        row_none.addWidget(self.lbl_set_none)
        row_ia = QHBoxLayout()
        row_ia.addWidget(self.radio_ia)
        row_ia.addStretch()
        row_ia.addWidget(self.lbl_set_ia)
        row_icc = QHBoxLayout()
        row_icc.addWidget(self.radio_icc)
        row_icc.addStretch()
        row_icc.addWidget(self.lbl_set_icc)
        row_icc_ce = QHBoxLayout()
        row_icc_ce.addWidget(self.radio_icc_ce)
        row_icc_ce.addStretch()
        row_icc_ce.addWidget(self.lbl_set_icc_ce)

        grp_replace = QGroupBox("批注替换")
        replace_layout = QVBoxLayout()
        hijack_row = QHBoxLayout()
        hijack_row.addWidget(self.btn_action)
        hijack_row.addStretch()
        replace_layout.addLayout(hijack_row)
        replace_layout.addLayout(row_none)
        replace_layout.addLayout(row_ia)
        replace_layout.addLayout(row_icc)
        replace_layout.addLayout(row_icc_ce)
        grp_replace.setLayout(replace_layout)

        bottom_layout = QHBoxLayout()
        self.btn_faq = QPushButton("常见问题")
        self.btn_faq.clicked.connect(self.show_faq)
        bottom_layout.addWidget(self.btn_faq)
        bottom_layout.addStretch()
        self.btn_about = QPushButton("关于")
        self.btn_about.setFixedWidth(80)
        self.btn_about.clicked.connect(
            lambda: QMessageBox.about(
                self, "关于希沃批注替换",
                f"希沃批注替换 v{VERSION}\n替换「希沃桌面2.0+ 桌面批注」为 ICC-CE 批注。"
                )
                )
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_about)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp_shortcuts)
        main_layout.addWidget(grp_common)
        main_layout.addWidget(grp_replace)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(500)
        self.refresh_timer.timeout.connect(self.check_install_status)
        self._delay_install_check_timer = QTimer(self)
        self._delay_install_check_timer.setSingleShot(True)
        self._delay_install_check_timer.timeout.connect(self._start_install_check)

        self._last_installed_state = None
        self._refresh_attempts = 0
        self._install_status = None

        self._sync_theme_enabled()
        self._init_ui = False
        self.update_install_buttons()
        self.resize(300, 380)

    def _get_install_status(self):
        """检查注册表，返回 'installed' 或 'not_installed'"""
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
            debugger, _ = winreg.QueryValueEx(key, "Debugger")
            winreg.CloseKey(key)
            expected = os.path.join(get_base_dir(), "Annotation.exe")
            if debugger.strip('"') == expected:
                return "installed"
        except Exception:
            pass
        return "not_installed"

    def update_install_buttons(self):
        status = self._get_install_status()
        self._install_status = status
        if status == "installed":
            self.btn_action.setText("取消劫持希沃桌面批注")
        else:
            self.btn_action.setText("劫持希沃桌面批注")
        self._sync_radio_enabled()

    def _sync_radio_enabled(self):
        is_hijacked = self._install_status == "installed"
        self.radio_none.setEnabled(is_hijacked)
        self.radio_icc_ce.setEnabled(is_hijacked)
        if not is_hijacked:
            self.radio_group.setExclusive(False)
            self.radio_none.setChecked(False)
            self.radio_ia.setChecked(False)
            self.radio_icc.setChecked(False)
            self.radio_icc_ce.setChecked(False)
            self.radio_group.setExclusive(True)

    def _warn_security_software(self):
        sw_name = check_security_software_running()
        if not sw_name:
            return True

        msg_box = QMessageBox(QMessageBox.Warning, "希沃批注替换", "", parent=self) # type: ignore
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            f"<h3>请关闭「{sw_name}」</h3>"
            "<p>该程序通过映像劫持替换「希沃桌面2.0+ 桌面批注」，这是系统敏感操作，"
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
            self._last_installed_state = current
            self.refresh_timer.stop()
            self.update_install_buttons()
        elif self._refresh_attempts >= 10:
            self.refresh_timer.stop()
            self.update_install_buttons()

    def show_faq(self):
        self.faq_window = FAQWindow()
        self.faq_window.show()

    def on_product_changed(self, btn_id):
        product_map = {0: "none", 1: "ica", 2: "icc", 3: "icc_ce"}
        self.settings["ink_product"] = product_map.get(btn_id, "none")
        save_settings(self.settings)

    def _open_product_settings(self, product):
        if product == "icc_ce":
            self.icc_ce_window = ICCCESettingsWindow()
            self.icc_ce_window.show()
        elif product == "none":
            self.none_window = NoneSettingsWindow()
            self.none_window.show()
        else:
            QMessageBox.information(
                self, "希沃批注替换",
                f"{product} 设置暂未开放。"
            )

    def _sync_theme_enabled(self):
        is_fusion = self.cmb_style.currentData() == "Fusion"
        self.cmb_theme.setEnabled(is_fusion)
        if not is_fusion:
            idx = self.cmb_theme.findData("light")
            if idx >= 0:
                self.cmb_theme.setCurrentIndex(idx)

    def on_style_changed(self, _index):
        style = self.cmb_style.currentData()
        self.settings["style"] = style
        if style != "Fusion":
            self.settings["theme"] = "light"
        save_settings(self.settings)
        apply_style(style)
        apply_theme(self.settings["theme"])
        self._sync_theme_enabled()

    def on_theme_changed(self, _index):
        theme = self.cmb_theme.currentData()
        self.settings["theme"] = theme
        save_settings(self.settings)
        apply_theme(theme)

    def _do_shortcut(self, kind, checked, checkbox):
        checkbox.setText("创建中，请稍后……")
        checkbox.setEnabled(False)
        QTimer.singleShot(0, lambda: self._run_shortcut_work(kind, checked, checkbox))

    def _run_shortcut_work(self, kind, checked, checkbox):
        try:
            if checked:
                create_shortcut(kind)
            else:
                delete_shortcut(kind)
        except Exception as e:
            QMessageBox.warning(
                self, "希沃批注替换",
                f"快捷方式操作失败：{e}"
            )
        checkbox.blockSignals(True)
        checkbox.setChecked(shortcut_exists(kind))
        checkbox.blockSignals(False)
        checkbox.setText(checkbox._original_text)
        checkbox.setEnabled(True)

    def on_start_menu_toggled(self, checked):
        self._do_shortcut("start_menu", checked, self.chk_start_menu)

    def on_desktop_toggled(self, checked):
        self._do_shortcut("desktop", checked, self.chk_desktop)
