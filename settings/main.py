import os
import sys
import webbrowser
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import winreg
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QPushButton, QCheckBox, QMessageBox, QComboBox, QRadioButton,
    QGroupBox, QFrame, QStyle,
)
from utils import (
    VERSION,
    DEFAULT_SETTINGS,
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
    _is_win11,
)
from .icc_ce import ICCCESettingsWindow
from .none import NoneSettingsWindow
from .update import check_for_update


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

        is_win11 = _is_win11()
        self._info_border_radius = "6px" if is_win11 else "0px"
        self.info_frame = QFrame()
        self.info_text = QLabel(
            "可通过「.\\Annotation.exe -settings」命令打开本设置窗口。"
        )
        self.info_text.setWordWrap(True)
        self.info_icon = QLabel()
        info_layout = QHBoxLayout(self.info_frame)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.addWidget(self.info_icon, 0, Qt.AlignTop) # type: ignore
        info_layout.addSpacing(4)
        info_layout.addWidget(self.info_text, 1)
        self._apply_info_banner_style()
        QApplication.styleHints().colorSchemeChanged.connect(self._apply_info_banner_style) # type: ignore

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

        self.chk_auto_update = QCheckBox("自动检查更新")
        self.chk_auto_update.setChecked(self.settings.get("auto_check_update", True))
        self.chk_auto_update.toggled.connect(self.on_auto_update_toggled)

        grp_common = QGroupBox("通用")
        common_layout = QVBoxLayout()
        common_layout.addLayout(style_row)
        common_layout.addLayout(theme_row)
        common_layout.addWidget(self.chk_auto_update)
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

        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        reset_color = "#ff6b6b" if is_dark else "#cc0000"
        bottom_layout = QHBoxLayout()
        self.btn_reset = QPushButton("重置设置")
        reset_palette = self.btn_reset.palette()
        reset_palette.setColor(QPalette.ButtonText, reset_color) # type: ignore
        self.btn_reset.setPalette(reset_palette)
        self.btn_reset.clicked.connect(self.on_reset_clicked)
        bottom_layout.addWidget(self.btn_reset)
        bottom_layout.addStretch()
        self.btn_about = QPushButton("关于")
        self.btn_about.setFixedWidth(80)
        self.btn_about.clicked.connect(self._show_about)
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_about)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.info_frame)
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
        self.btn_action.setEnabled(True)
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
        is_installing = self._install_status != "installed"
        self.btn_action.setEnabled(False)
        self.btn_action.setText("劫持中，请稍后……" if is_installing else "取消劫持中，请稍后……")
        try:
            create_and_run_bat(is_install=is_installing)
        except Exception:
            self.btn_action.setEnabled(True)
            self.update_install_buttons()
            return
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

    def on_reset_clicked(self):
        msg_box = QMessageBox(QMessageBox.Warning, "希沃批注替换", "", parent=self) # type: ignore
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            "<h3>确定要重置设置吗？</h3>"
            "<p>重置设置将恢复所有配置至默认值，此操作不可撤销。</p>"
        )
        btn_confirm = msg_box.addButton("确认", QMessageBox.DestructiveRole) # type: ignore
        btn_cancel = msg_box.addButton("取消", QMessageBox.RejectRole) # type: ignore
        msg_box.setDefaultButton(btn_cancel)
        msg_box.exec()
        if msg_box.clickedButton() != btn_confirm:
            return
        save_settings(DEFAULT_SETTINGS.copy())
        self.settings = load_settings()
        self._refresh_ui_from_settings()
        QMessageBox.information(self, "希沃批注替换", "设置已重置为默认值。")

    def _refresh_ui_from_settings(self):
        style = self.settings.get("style", "windowsvista")
        idx = self.cmb_style.findData(style)
        self.cmb_style.setCurrentIndex(idx if idx >= 0 else 0)

        theme = self.settings.get("theme", "system")
        idx = self.cmb_theme.findData(theme)
        self.cmb_theme.setCurrentIndex(idx if idx >= 0 else 0)

        product = self.settings.get("ink_product", "none")
        product_map = {"none": self.radio_none, "ica": self.radio_ia, "icc": self.radio_icc, "icc_ce": self.radio_icc_ce}
        target = product_map.get(product, self.radio_none)
        self.radio_group.setExclusive(False)
        for rb in (self.radio_none, self.radio_ia, self.radio_icc, self.radio_icc_ce):
            rb.setChecked(rb is target)
        self.radio_group.setExclusive(True)

        self.chk_start_menu.blockSignals(True)
        self.chk_start_menu.setChecked(shortcut_exists("start_menu"))
        self.chk_start_menu.blockSignals(False)
        self.chk_desktop.blockSignals(True)
        self.chk_desktop.setChecked(shortcut_exists("desktop"))
        self.chk_desktop.blockSignals(False)

        self.chk_auto_update.blockSignals(True)
        self.chk_auto_update.setChecked(self.settings.get("auto_check_update", True))
        self.chk_auto_update.blockSignals(False)

        self._sync_theme_enabled()
        apply_style(style)
        apply_theme(theme)
        self.update_install_buttons()

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

    def _show_about(self):
        msg_box = QMessageBox(QMessageBox.Information, "关于希沃批注替换", "", parent=self) # type: ignore
        icon = QIcon(get_icon_path())
        msg_box.setIconPixmap(icon.pixmap(QSize(48, 48)))
        msg_box.setWindowIcon(icon)
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(
            f"<h3>希沃批注替换 v{VERSION}</h3>"
            "<p>替换「希沃桌面2.0+ 桌面批注」为第三方批注。</p>"
        )
        btn_check_update = msg_box.addButton("检查更新", QMessageBox.ResetRole) # type: ignore
        btn_github = msg_box.addButton("GitHub", QMessageBox.ActionRole) # type: ignore
        btn_close = msg_box.addButton("关闭", QMessageBox.RejectRole) # type: ignore
        msg_box.setDefaultButton(btn_close)
        msg_box.setEscapeButton(btn_close)

        # Disconnect QMessageBox's default click handler so the dialog
        # stays open when user clicks "检查更新" or "GitHub".
        try:
            btn_check_update.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            btn_github.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        btn_check_update.clicked.connect(self._on_about_check_update)
        btn_github.clicked.connect(self._on_about_github)

        msg_box.exec()

    def _on_about_check_update(self):
        release = check_for_update(present=False)
        if release is None:
            QMessageBox.information(self, "希沃批注替换", "当前已是最新版本。")
        else:
            from .update import UpdateDialog
            UpdateDialog(release, parent=None).exec()

    def _on_about_github(self):
        webbrowser.open("https://github.com/EmerMine/Seewo-DesktopAnnotation-Replacement")

    def _apply_info_banner_style(self):
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        if is_dark:
            bg_color = "#1e3a5f"
            text_color = "#a8d4f0"
        else:
            bg_color = "#d1ecf1"
            text_color = "#0c5460"
        self.info_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border-radius: {self._info_border_radius}; }}"
        )
        self.info_text.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
        self.info_icon.setPixmap(self.style().standardIcon( # type: ignore
            QStyle.StandardPixmap.SP_MessageBoxInformation # type: ignore
        ).pixmap(14, 14))

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

    def on_auto_update_toggled(self, checked):
        self.settings["auto_check_update"] = checked
        save_settings(self.settings)

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
