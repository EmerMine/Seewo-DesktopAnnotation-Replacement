import os
import sys
import copy
import webbrowser
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QButtonGroup,
    QPushButton, QCheckBox, QMessageBox, QComboBox, QRadioButton,
    QGroupBox, QFrame, QStyle, QDialog,
)
from utils import (
    VERSION,
    DEFAULT_SETTINGS,
    get_icon_path,
    get_shield_icon_path,
    load_settings,
    save_settings,
    apply_style,
    apply_theme,
    install,
    uninstall,
    repair,
    get_install_status,
    get_install_diagnostics,
    INSTALL_STATUS_INSTALLED,
    INSTALL_STATUS_CORRUPTED,
    shortcut_exists,
    create_shortcut,
    delete_shortcut,
    # _is_win11,
    check_icc_ce_url_protocol,
    _is_debug,
    ICC_STATUS_OK,
    ICC_STATUS_NO_PROTOCOL,
    ICC_STATUS_BROKEN,
    check_ifeo_hijack,
    remove_ifeo_hijacks_async,
)
from .icc_ce import ICCCESettingsWindow, ICCURLTroubleshootWindow
from .ica_series import ICASettingsWindow
from .none import NoneSettingsWindow
from .custom import CustomSettingsWindow
from .update import check_for_update


class SettingsWindow(QWidget):
    # 会话级"不再提示"标记：用户勾选后，本次运行期间关闭主窗口不再弹出确认框
    _suppress_close_confirm = False

    def __init__(self):
        super().__init__()
        self.setWindowTitle("希沃批注替换" + ("（调试模式）" if _is_debug() else ""))
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

        self.lbl_view_reasons = QLabel(
            '<a href="#diagnostics" style="color: #0078d4; text-decoration: none;">查看原因</a>'
        )
        self.lbl_view_reasons.setTextFormat(Qt.RichText) # type: ignore
        self.lbl_view_reasons.setOpenExternalLinks(False)
        self.lbl_view_reasons.linkActivated.connect(self._show_install_diagnostics)
        self.lbl_view_reasons.hide()

        self._last_failure_reasons = []

        self.chk_start_menu = QCheckBox("开始菜单快捷方式")
        self.chk_start_menu._original_text = "开始菜单快捷方式" # type: ignore
        self.chk_start_menu.setChecked(shortcut_exists("start_menu"))
        self.chk_start_menu.toggled.connect(self.on_start_menu_toggled)
        self.chk_desktop = QCheckBox("桌面快捷方式")
        self.chk_desktop._original_text = "桌面快捷方式" # type: ignore
        self.chk_desktop.setChecked(shortcut_exists("desktop"))
        self.chk_desktop.toggled.connect(self.on_desktop_toggled)

        # is_win11 = _is_win11()
        # self._info_border_radius = "6px" if is_win11 else "0px"
        # self.info_frame = QFrame()
        # self.info_text = QLabel(
        #     "可通过「.\\Annotation.exe -settings」命令打开本设置窗口。"
        # )
        # self.info_text.setWordWrap(True)
        # self.info_icon = QLabel()
        # info_layout = QHBoxLayout(self.info_frame)
        # info_layout.setContentsMargins(8, 6, 8, 6)
        # info_layout.addWidget(self.info_icon, 0, Qt.AlignTop) # type: ignore
        # info_layout.addSpacing(4)
        # info_layout.addWidget(self.info_text, 1)
        # self._apply_info_banner_style()
        # QApplication.styleHints().colorSchemeChanged.connect(self._apply_info_banner_style) # type: ignore

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
        current_style = self.settings["general"].get("style", "windowsvista")
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
        current_theme = self.settings["general"].get("theme", "system")
        idx = self.cmb_theme.findData(current_theme)
        self.cmb_theme.setCurrentIndex(idx if idx >= 0 else 0)
        self.cmb_theme.currentIndexChanged.connect(self.on_theme_changed)
        theme_row.addWidget(self.cmb_theme)
        theme_row.addStretch()

        self.chk_auto_update = QCheckBox("自动检查更新")
        self.chk_auto_update.setChecked(self.settings["general"].get("auto_check_update", True))
        self.chk_auto_update.toggled.connect(self.on_auto_update_toggled)

        self.chk_close_warn = QCheckBox("关闭多个窗口前发出警告")
        self.chk_close_warn.setChecked(not self.settings["general"].get("suppress_close_confirm", False))
        self.chk_close_warn.toggled.connect(self.on_close_warn_toggled)

        grp_common = QGroupBox("通用")
        common_layout = QVBoxLayout()
        common_layout.addLayout(style_row)
        common_layout.addLayout(theme_row)
        common_layout.addWidget(self.chk_auto_update)
        common_layout.addWidget(self.chk_close_warn)
        grp_common.setLayout(common_layout)

        self.radio_group = QButtonGroup(self)
        self.radio_keep = QRadioButton("不替换（保持希沃原批注）")
        self.radio_none = QRadioButton("空程序（禁用希沃桌面批注）")
        self.radio_ica = QRadioButton("Ink Canvas Artistry 系列")
        self.radio_icc_ce = QRadioButton("ICC-CE")
        self.radio_custom = QRadioButton("自定义程序")
        self.radio_group.addButton(self.radio_keep, 0)
        self.radio_group.addButton(self.radio_none, 1)
        self.radio_group.addButton(self.radio_ica, 2)
        self.radio_group.addButton(self.radio_icc_ce, 3)
        self.radio_group.addButton(self.radio_custom, 4)
        product = self.settings["general"].get("ink_product", "none")
        product_map = {"keep": self.radio_keep, "none": self.radio_none, "ica": self.radio_ica, "icc_ce": self.radio_icc_ce, "custom": self.radio_custom}
        product_map.get(product, self.radio_none).setChecked(True)
        self.radio_group.idClicked.connect(self.on_product_changed)

        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        link_color = "#7ab8ff" if is_dark else "#0066cc"
        link_style = f"<a href='#' style='color: {link_color}; text-decoration: none;'>设置</a>"
        self.lbl_set_none = QLabel(link_style)
        self.lbl_set_ica = QLabel(link_style)
        self.lbl_set_icc_ce = QLabel(link_style)
        self.lbl_set_custom = QLabel(link_style)
        for lbl in (self.lbl_set_none, self.lbl_set_ica, self.lbl_set_icc_ce, self.lbl_set_custom):
            lbl.setOpenExternalLinks(False)
            lbl.setCursor(Qt.PointingHandCursor) # type: ignore

        self.lbl_set_none.linkActivated.connect(lambda: self._open_product_settings("none"))
        self.lbl_set_ica.linkActivated.connect(lambda: self._open_product_settings("ica"))
        self.lbl_set_icc_ce.linkActivated.connect(lambda: self._open_product_settings("icc_ce"))
        self.lbl_set_custom.linkActivated.connect(lambda: self._open_product_settings("custom"))

        self.lbl_icc_ce_issue = QLabel(link_style.replace("设置", "解决问题"))
        self.lbl_icc_ce_issue.setOpenExternalLinks(False)
        self.lbl_icc_ce_issue.setCursor(Qt.PointingHandCursor) # type: ignore
        self.lbl_icc_ce_issue.linkActivated.connect(self._open_icc_troubleshoot)

        row_keep = QHBoxLayout()
        row_keep.addWidget(self.radio_keep)
        row_keep.addStretch()
        row_none = QHBoxLayout()
        row_none.addWidget(self.radio_none)
        row_none.addStretch()
        row_none.addWidget(self.lbl_set_none)
        row_ica = QHBoxLayout()
        row_ica.addWidget(self.radio_ica)
        row_ica.addStretch()
        row_ica.addWidget(self.lbl_set_ica)
        row_icc_ce = QHBoxLayout()
        row_icc_ce.addWidget(self.radio_icc_ce)
        row_icc_ce.addStretch()
        row_icc_ce.addWidget(self.lbl_icc_ce_issue)
        row_icc_ce.addSpacing(8)
        row_icc_ce.addWidget(self.lbl_set_icc_ce)
        row_custom = QHBoxLayout()
        row_custom.addWidget(self.radio_custom)
        row_custom.addStretch()
        row_custom.addWidget(self.lbl_set_custom)

        self.lbl_icc_ce_hint = QLabel()
        self.lbl_icc_ce_hint.setWordWrap(True)

        self.lbl_replace_hint = QLabel("您需要先单击上方「替换」按钮，才能将希沃桌面批注替换为下方任意选项。")
        self.lbl_replace_hint.setWordWrap(True)
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        hint_color = "#b0b0b0" if is_dark else "gray"
        self.lbl_replace_hint.setStyleSheet(f"color: {hint_color}; font-size: 9pt;")

        grp_replace = QGroupBox("批注替换")
        replace_layout = QVBoxLayout()
        hijack_row = QHBoxLayout()
        hijack_row.addWidget(self.btn_action)
        hijack_row.addWidget(self.lbl_view_reasons)
        hijack_row.addStretch()
        replace_layout.addLayout(hijack_row)
        replace_layout.addWidget(self.lbl_replace_hint)
        replace_layout.addLayout(row_keep)
        replace_layout.addLayout(row_none)
        replace_layout.addLayout(row_ica)
        replace_layout.addLayout(row_icc_ce)
        replace_layout.addWidget(self.lbl_icc_ce_hint)
        replace_layout.addLayout(row_custom)
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
        # main_layout.addWidget(self.info_frame)
        main_layout.addWidget(grp_shortcuts)
        main_layout.addWidget(grp_common)
        main_layout.addWidget(grp_replace)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
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

        QTimer.singleShot(0, self._check_ifeo_hijack)

    def _check_ifeo_hijack(self):
        """启动后异步检查 IFEO 劫持并弹出警告对话框。"""
        if self.settings["general"].get("suppress_ifeo_warning", False):
            return
        hijacks = check_ifeo_hijack()
        if not hijacks:
            return

        hijack_details = []
        for h in hijacks:
            detail = f"{h['hive']}\\...\\{h['name']}"
            if h.get("has_debugger") and h.get("debugger"):
                detail += f"<br>Debugger: <code>{h['debugger']}</code>"
            hijack_details.append(detail)

        dialog = QDialog(self)
        dialog.setWindowTitle("希沃批注替换")
        dialog.setWindowIcon(QIcon(get_icon_path()))
        dialog.setModal(True)

        icon = QLabel()
        icon_pixmap = self.style().standardIcon( # type: ignore
            QStyle.StandardPixmap.SP_MessageBoxWarning # type: ignore
        ).pixmap(QSize(48, 48))
        icon.setPixmap(icon_pixmap)
        icon.setAlignment(Qt.AlignTop | Qt.AlignHCenter) # type: ignore
        icon.setFixedWidth(icon_pixmap.width() + 16)

        text_label = QLabel()
        text_label.setTextFormat(Qt.RichText) # type: ignore
        text_label.setWordWrap(True)
        text_label.setText(
            "<h3>映像劫持替换方法已不再受支持</h3>"
            "<p>检测到希沃桌面批注的映像劫持，这可能是旧版本希沃批注替换生成的。</p>"
            "<p>新版本已更换替换方法，保留映像劫持项可能引发问题。</p>"
            "<p>若该劫持项不是您手动创建的，请手动关闭安全软件后，单击「是」删除映像劫持项。</p>"
            + "<ul style='margin: 0; padding-left: 18px;'>"
            + "".join(f"<li>{d}</li>" for d in hijack_details)
            + "</ul>"
        )

        top_row = QHBoxLayout()
        top_row.addWidget(icon)
        top_row.addWidget(text_label, 1)
        top_row.setContentsMargins(16, 16, 16, 16)

        content_frame = QFrame()
        content_frame.setLayout(top_row)
        if self.settings["general"].get("style") == "windowsvista":
            content_frame.setStyleSheet(
                "QFrame { background-color: #ffffff; }"
            )

        btn_never = QPushButton("不再提示")
        btn_no = QPushButton("否")
        btn_yes = QPushButton("是")
        btn_yes.setDefault(True)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(btn_never)
        bottom_row.addStretch(1)
        bottom_row.addWidget(btn_no)
        bottom_row.addSpacing(6)
        bottom_row.addWidget(btn_yes)
        bottom_row.setContentsMargins(12, 8, 12, 12)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("QFrame { background-color: #dfdfdf; }")

        root = QVBoxLayout(dialog)
        root.addWidget(content_frame, 1)
        root.addWidget(separator)
        root.addLayout(bottom_row)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        result = {"action": "cancel"}

        btn_never.clicked.connect(lambda: result.__setitem__("action", "never_remind"))
        btn_never.clicked.connect(dialog.reject)
        btn_no.clicked.connect(lambda: result.__setitem__("action", "no"))
        btn_no.clicked.connect(dialog.reject)
        btn_yes.clicked.connect(lambda: result.__setitem__("action", "yes"))
        btn_yes.clicked.connect(dialog.accept)

        QApplication.beep()
        dialog.exec()

        if result["action"] == "never_remind":
            self.settings["general"]["suppress_ifeo_warning"] = True
            save_settings(self.settings)
            return

        if result["action"] == "yes":
            remove_ifeo_hijacks_async()

    def _get_install_status(self):
        return get_install_status()

    def update_install_buttons(self):
        status = self._get_install_status()
        self._install_status = status
        self.btn_action.setEnabled(True)
        if status == INSTALL_STATUS_INSTALLED:
            self.btn_action.setText("还原")
        elif status == INSTALL_STATUS_CORRUPTED:
            self.btn_action.setText("修复")
        else:
            self.btn_action.setText("替换")

        show_link = (
            status == INSTALL_STATUS_CORRUPTED
            or bool(self._last_failure_reasons)
        )
        if show_link:
            self.lbl_view_reasons.show()
        else:
            self.lbl_view_reasons.hide()
        # 替换提示仅在"替换"状态下显示（"修复"/"还原"状态下隐藏）
        show_hint = status not in (INSTALL_STATUS_INSTALLED, INSTALL_STATUS_CORRUPTED)
        self.lbl_replace_hint.setVisible(show_hint)
        self._sync_radio_enabled()

    def _sync_radio_enabled(self):
        is_installed = self._install_status == INSTALL_STATUS_INSTALLED
        self.radio_keep.setEnabled(is_installed)
        self.radio_none.setEnabled(is_installed)
        self.radio_ica.setEnabled(is_installed)
        self.radio_icc_ce.setEnabled(is_installed)
        self.radio_custom.setEnabled(is_installed)
        if not is_installed:
            self.radio_group.setExclusive(False)
            self.radio_keep.setChecked(False)
            self.radio_none.setChecked(False)
            self.radio_ica.setChecked(False)
            self.radio_icc_ce.setChecked(False)
            self.radio_custom.setChecked(False)
            self.radio_group.setExclusive(True)

        self._icc_status = check_icc_ce_url_protocol()
        hint_style = "color: #cc8800; font-size: 8pt; margin-left: 18px;"
        if self._icc_status == ICC_STATUS_OK:
            self.lbl_icc_ce_hint.setText("")
            self.lbl_icc_ce_issue.hide()
        elif self._icc_status == ICC_STATUS_NO_PROTOCOL:
            self.radio_icc_ce.setEnabled(False)
            self.lbl_icc_ce_hint.setText(
                "未开启 ICC-CE「外部协议调用 (icc://)」功能，单击「解决问题」查看启用方法"
            )
            self.lbl_icc_ce_hint.setStyleSheet(hint_style)
            self.lbl_icc_ce_issue.show()
            if self.radio_icc_ce.isChecked():
                self.radio_none.setChecked(True)
        elif self._icc_status == ICC_STATUS_BROKEN:
            self.lbl_icc_ce_hint.setText(
                "ICC-CE URL 协议已损坏，单击「解决问题」查看启用方法"
            )
            self.lbl_icc_ce_hint.setStyleSheet(hint_style)
            self.lbl_icc_ce_issue.show()

    def _sync_hint_label_style(self):
        if not self.lbl_icc_ce_hint.text():
            return
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        hint_color = "#f0b429" if is_dark else "#cc8800"
        self.lbl_icc_ce_hint.setStyleSheet(f"color: {hint_color}; font-size: 8pt; margin-left: 18px;")

    def _start_install_check(self):
        self.refresh_timer.start()

    def on_refresh_clicked(self):
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self.update_install_buttons()

    def on_action_clicked(self):
        self.refresh_timer.stop()
        self._delay_install_check_timer.stop()
        self._last_installed_state = self._install_status
        self._refresh_attempts = 0
        is_uninstalling = self._install_status == INSTALL_STATUS_INSTALLED
        is_repair = self._install_status == INSTALL_STATUS_CORRUPTED
        self.btn_action.setEnabled(False)
        if is_uninstalling:
            self.btn_action.setText("还原中……")
        else:
            self.btn_action.setText(
                "修复中……"
                if is_repair
                else "替换中……"
            )
        self.btn_action.repaint()
        QApplication.processEvents()
        try:
            if is_uninstalling:
                uninstall()
                self._last_failure_reasons = []
            elif is_repair:
                ok, reasons = repair()
                if not ok:
                    self._last_failure_reasons = reasons
                    self.btn_action.setEnabled(True)
                    self.update_install_buttons()
                    return
                self._last_failure_reasons = []
            else:
                ok, reasons = install()
                if not ok:
                    self._last_failure_reasons = reasons
                    self.btn_action.setEnabled(True)
                    self.update_install_buttons()
                    return
                self._last_failure_reasons = []
        except Exception as e:
            self._last_failure_reasons = [f"执行异常：{e}"]
            self.btn_action.setEnabled(True)
            self.update_install_buttons()
            return
        delay_ms = 8000 if is_repair else 3000
        self._delay_install_check_timer.start(delay_ms)

    def check_install_status(self):
        current = self._get_install_status()
        self._refresh_attempts += 1
        if current != self._last_installed_state:
            was_not_installed = self._last_installed_state != INSTALL_STATUS_INSTALLED
            was_installed = not was_not_installed
            self._last_installed_state = current
            self.refresh_timer.stop()
            self.settings["general"]["ink_product"] = "keep"
            save_settings(self.settings)
            self.radio_keep.setChecked(True)
            self.update_install_buttons()
        elif self._refresh_attempts >= 40:
            self.refresh_timer.stop()
            self.update_install_buttons()

    def _show_install_diagnostics(self):
        """弹出模态提示框，展示安装状态的逐项诊断结果。"""
        if self._last_failure_reasons:
            items = [
                ('<span style="color: #d13438;">✗</span> ' + r)
                for r in self._last_failure_reasons
            ]
        else:
            items = []
            for c in get_install_diagnostics():
                icon = (
                    '<span style="color: #107c10;">✓</span>' if c["ok"]
                    else '<span style="color: #d13438;">✗</span>'
                )
                items.append(
                    f"{icon} <b>{c['label']}</b>：{'通过' if c['ok'] else '未通过'}<br>"
                    f'<span style="color: #666; font-size: 8pt;">{c["detail"]}</span>'
                )

        text = (
            "<h3>替换失败原因</h3>"
            "<p>以下是导致替换异常的条件判断结果：</p>"
            + "<ul style='margin: 0; padding-left: 18px;'>"
            + "".join(f"<li>{it}</li>" for it in items)
            + "</ul>"
        )

        msg_box = QMessageBox(QMessageBox.Information, "希沃批注替换", "", parent=self) # type: ignore
        msg_box.setTextFormat(Qt.RichText) # type: ignore
        msg_box.setText(text)
        msg_box.setDetailedText(
            "\n\n".join(
                f"[{c['label']}] {'PASS' if c['ok'] else 'FAIL'}\n{c['detail']}"
                for c in get_install_diagnostics()
            )
        )
        msg_box.exec()

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
        save_settings(copy.deepcopy(DEFAULT_SETTINGS))
        self.settings = load_settings()
        self._refresh_ui_from_settings()
        QMessageBox.information(self, "希沃批注替换", "设置已重置为默认值。")

    def _refresh_ui_from_settings(self):
        style = self.settings["general"].get("style", "windowsvista")
        idx = self.cmb_style.findData(style)
        self.cmb_style.setCurrentIndex(idx if idx >= 0 else 0)

        theme = self.settings["general"].get("theme", "system")
        idx = self.cmb_theme.findData(theme)
        self.cmb_theme.setCurrentIndex(idx if idx >= 0 else 0)

        product = self.settings["general"].get("ink_product", "none")
        product_map = {"keep": self.radio_keep, "none": self.radio_none, "ica": self.radio_ica, "icc_ce": self.radio_icc_ce, "custom": self.radio_custom}
        target = product_map.get(product, self.radio_none)
        self.radio_group.setExclusive(False)
        for rb in (self.radio_keep, self.radio_none, self.radio_ica, self.radio_icc_ce, self.radio_custom):
            rb.setChecked(rb is target)
        self.radio_group.setExclusive(True)

        self.chk_start_menu.blockSignals(True)
        self.chk_start_menu.setChecked(shortcut_exists("start_menu"))
        self.chk_start_menu.blockSignals(False)
        self.chk_desktop.blockSignals(True)
        self.chk_desktop.setChecked(shortcut_exists("desktop"))
        self.chk_desktop.blockSignals(False)

        self.chk_auto_update.blockSignals(True)
        self.chk_auto_update.setChecked(self.settings["general"].get("auto_check_update", True))
        self.chk_auto_update.blockSignals(False)

        self.chk_close_warn.blockSignals(True)
        self.chk_close_warn.setChecked(not self.settings["general"].get("suppress_close_confirm", False))
        self.chk_close_warn.blockSignals(False)

        self._sync_theme_enabled()
        apply_style(style)
        apply_theme(theme)
        self.update_install_buttons()

    def on_product_changed(self, btn_id):
        product_map = {0: "keep", 1: "none", 2: "ica", 3: "icc_ce", 4: "custom"}
        self.settings["general"]["ink_product"] = product_map.get(btn_id, "none")
        save_settings(self.settings)

    def _open_product_settings(self, product):
        if product == "icc_ce":
            self.icc_ce_window = ICCCESettingsWindow()
            self.icc_ce_window.show()
        elif product == "ica":
            self.ica_window = ICASettingsWindow()
            self.ica_window.show()
        elif product == "none":
            self.none_window = NoneSettingsWindow()
            self.none_window.show()
        elif product == "custom":
            self.custom_window = CustomSettingsWindow()
            self.custom_window.show()
        else:
            QMessageBox.error( # type: ignore
                self, "希沃批注替换",
                f"{product} 设置页面不存在，请向开发者反馈。"
            )

    def _open_icc_troubleshoot(self):
        self.icc_troubleshoot_window = ICCURLTroubleshootWindow()
        self.icc_troubleshoot_window.show()

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

    # def _apply_info_banner_style(self):
    #     is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
    #     if is_dark:
    #         bg_color = "#1e3a5f"
    #         text_color = "#a8d4f0"
    #     else:
    #         bg_color = "#d1ecf1"
    #         text_color = "#0c5460"
    #     self.info_frame.setStyleSheet(
    #         f"QFrame {{ background-color: {bg_color}; border-radius: {self._info_border_radius}; }}"
    #     )
    #     self.info_text.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
    #     self.info_icon.setPixmap(self.style().standardIcon( # type: ignore
    #         QStyle.StandardPixmap.SP_MessageBoxInformation # type: ignore
    #     ).pixmap(14, 14))

    def _sync_theme_enabled(self):
        is_fusion = self.cmb_style.currentData() == "Fusion"
        self.cmb_theme.setEnabled(is_fusion)
        if not is_fusion:
            idx = self.cmb_theme.findData("light")
            if idx >= 0:
                self.cmb_theme.setCurrentIndex(idx)

    def on_style_changed(self, _index):
        style = self.cmb_style.currentData()
        self.settings["general"]["style"] = style
        if style != "Fusion":
            self.settings["general"]["theme"] = "light"
        save_settings(self.settings)
        apply_style(style)
        apply_theme(self.settings["general"]["theme"])
        self._sync_theme_enabled()

    def on_theme_changed(self, _index):
        theme = self.cmb_theme.currentData()
        self.settings["general"]["theme"] = theme
        save_settings(self.settings)
        apply_theme(theme)

    def on_auto_update_toggled(self, checked):
        self.settings["general"]["auto_check_update"] = checked
        save_settings(self.settings)

    def on_close_warn_toggled(self, checked):
        self.settings["general"]["suppress_close_confirm"] = not checked
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

    # ------------------------------------------------------------------ #
    #  窗口关闭管理
    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        """拦截主窗口关闭事件：多窗口时弹出确认对话框。

        - 配置中已选"不再提示"：直接关闭所有窗口
        - 仅主窗口（无子窗口）：直接关闭
        - 多窗口：弹出确认对话框，用户选"是"则关闭全部，选"否"则取消
        """
        # 读取持久化配置，已勾选"不再提示"则跳过对话框
        if self.settings["general"].get("suppress_close_confirm", False):
            self._close_all_other_windows()
            event.accept()
            return

        # 统计除主窗口外的可见顶层窗口
        visible_others = [
            w for w in QApplication.topLevelWidgets()
            if w.isVisible() and w is not self
        ]

        if not visible_others:
            # 无子窗口，直接关闭
            event.accept()
            return

        # 多窗口状态，弹出确认对话框
        should_close, dont_remind = self._show_close_confirmation()
        if should_close:
            if dont_remind:
                self.settings["general"]["suppress_close_confirm"] = True
                save_settings(self.settings)
            self._close_all_other_windows()
            event.accept()
        else:
            event.ignore()

    def _close_all_other_windows(self):
        """关闭除主窗口外的所有可见顶层窗口。"""
        for w in QApplication.topLevelWidgets():
            if w is not self and w.isVisible():
                w.close()

    def _show_close_confirmation(self):
        """弹出"将关闭所有窗口"确认对话框。

        Returns
        -------
        tuple[bool, bool]
            ``(should_close, dont_remind)``：是否确认关闭 / 是否勾选"不再提示"
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("希沃批注替换")
        dialog.setWindowIcon(QIcon(get_icon_path()))
        dialog.setModal(True)

        # 问号图标
        icon_label = QLabel()
        icon_pixmap = self.style().standardIcon( # type: ignore
            QStyle.StandardPixmap.SP_MessageBoxQuestion # type: ignore
        ).pixmap(QSize(40, 40))
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter) # type: ignore
        icon_label.setFixedWidth(icon_pixmap.width() + 16)

        # 提示文本（含 h3 标题）
        text_label = QLabel("<h3>关闭所有窗口？</h3><p>您已打开了多个窗口。")
        text_label.setTextFormat(Qt.RichText) # type: ignore
        text_label.setWordWrap(True)

        top_row = QHBoxLayout()
        top_row.addWidget(icon_label)
        top_row.addWidget(text_label, 1)
        top_row.setContentsMargins(16, 16, 16, 16)

        content_frame = QFrame()
        content_frame.setLayout(top_row)
        if self.settings["general"].get("style") == "windowsvista":
            content_frame.setStyleSheet(
                "QFrame { background-color: #ffffff; }"
            )

        # "不再提示"勾选框（左下角）
        chk_dont_remind = QCheckBox("不再提示")

        # 按钮："取消"在左，"全部关闭"在右
        btn_no = QPushButton("取消")
        btn_yes = QPushButton("全部关闭")
        btn_yes.setDefault(True)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(chk_dont_remind)
        bottom_row.addStretch(1)
        bottom_row.addWidget(btn_yes)
        bottom_row.addSpacing(6)
        bottom_row.addWidget(btn_no)
        bottom_row.setContentsMargins(12, 8, 12, 12)

        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("QFrame { background-color: #dfdfdf; }")

        root = QVBoxLayout(dialog)
        root.addWidget(content_frame, 1)
        root.addWidget(separator)
        root.addLayout(bottom_row)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        result = {"should_close": False}

        btn_yes.clicked.connect(lambda: result.__setitem__("should_close", True))
        btn_yes.clicked.connect(dialog.accept)
        btn_no.clicked.connect(dialog.reject)

        QApplication.beep()
        dialog.exec()

        return result["should_close"], chk_dont_remind.isChecked()
