import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QSpinBox, QGroupBox,
    QSpacerItem, QSizePolicy, QStyle, QFrame, QTextBrowser,
)
from utils import (
    get_icon_path,
    get_data_dir,
    load_settings,
    save_settings,
    run_protocol,
    _is_win11,
    ICC_STATUS_OK,
    ICC_STATUS_NO_PROTOCOL,
    ICC_STATUS_BROKEN,
    check_icc_ce_url_protocol,
)


_HELP_DIR = os.path.join(
    get_data_dir(), "resources", "help", "turn_on_icc_ce_url"
)

_HELP_DOC = """## 启用 ICC-CE URL 协议

1. 通过 ICC-CE 工具栏，转到 ICC-CE 设置。

![]({0}/1.png)

2. 转到"通用 > 基本"，切换右侧开关以启用"外部协议调用(icc://)" 设置项。

![]({0}/2.png)

3. 单击本窗口"重新检测"按钮刷新状态，若一切无误，您可在"批注替换"分组框中选择"ICC-CE"选项。
"""

def _help_doc(is_dark):
    return _HELP_DOC.format("dark" if is_dark else "light")


_MD_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def _rewrite_md_images(content, base_dir):
    """将 markdown 图片语法改写为 <img> HTML，便于 QTextBrowser.setMarkdown 正确渲染。

    QTextBrowser.setMarkdown 会丢弃原生 markdown 图片语法 `![](path)`，
    但保留嵌入的 HTML <img> 标签。此函数在渲染前将图片转换为带绝对 file:// URL
    的 <img> 标签，确保 Qt 能找到并显示图片。
    """
    def _replace(match):
        alt, src = match.group(1), match.group(2)
        if src.startswith(("http://", "https://", "file://", "data:")):
            abs_url = src
        else:
            abs_path = os.path.normpath(os.path.join(base_dir, src))
            abs_url = QUrl.fromLocalFile(abs_path).toString()
        return f'<img src="{abs_url}" alt="{alt}" />'
    return _MD_IMAGE_RE.sub(_replace, content)


class ICCURLTroubleshootWindow(QWidget):
    """ICC-CE URL 注册问题疑难解答窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ICC-CE URL 注册问题疑难解答 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore

        is_win11 = _is_win11()
        self._warning_border_radius = "6px" if is_win11 else "0px"

        self.warning_frame = QFrame()
        self.warning_text = QLabel()
        self.warning_text.setTextFormat(Qt.RichText) # type: ignore
        self.warning_text.setWordWrap(True)
        self.icon_label = QLabel()
        warning_layout = QHBoxLayout(self.warning_frame)
        warning_layout.setContentsMargins(10, 8, 10, 8)
        warning_layout.addWidget(self.icon_label, 0, Qt.AlignTop) # type: ignore
        warning_layout.addSpacing(6)
        warning_layout.addWidget(self.warning_text, 1)

        self.doc_browser = QTextBrowser()
        self.doc_browser.setOpenExternalLinks(True)
        self.doc_browser.setMinimumHeight(200)

        QApplication.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed) # type: ignore

        btn_retest = QPushButton("重新检测")
        btn_retest.clicked.connect(self._retest)

        btn_ok = QPushButton("OK")
        btn_ok.setFixedWidth(80)
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.close)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(btn_retest)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_ok)

        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.addWidget(self.warning_frame)
        layout.addWidget(self.doc_browser, 1)
        layout.addLayout(bottom_layout)
        self.setLayout(layout)
        self.resize(850, 700)

        self._retest()
        self._load_help_doc()

    def _retest(self):
        status = check_icc_ce_url_protocol()
        self._apply_warning_style(status)

    def _on_color_scheme_changed(self, _scheme):
        self._apply_warning_style()
        self._load_help_doc()

    def _load_help_doc(self):
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        content = _rewrite_md_images(_help_doc(is_dark), _HELP_DIR)
        self.doc_browser.setMarkdown(content)

    def _apply_warning_style(self, status=None):
        if status is None:
            status = check_icc_ce_url_protocol()
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        if status == ICC_STATUS_OK:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation) # type: ignore
            if is_dark:
                bg_color = "#1e3a5f"
                text_color = "#a8d4f0"
            else:
                bg_color = "#d1ecf1"
                text_color = "#0c5460"
            self.warning_text.setText(
                "<b>ICC-CE URL 协议检测通过</b><br>"
                "icc:// 协议已正确注册，可正常使用 ICC-CE 批注功能。"
            )
        else:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning) # type: ignore
            if is_dark:
                bg_color = "#4a3f1f"
                text_color = "#f7d87a"
            else:
                bg_color = "#fff3cd"
                text_color = "#856404"
            if status == ICC_STATUS_NO_PROTOCOL:
                detail = "未检测到 icc:// 协议注册。请开启 ICC-CE 的 URL 协议功能。"
            elif status == ICC_STATUS_BROKEN:
                detail = "icc:// 协议已注册但可执行文件路径无效，需在 ICC-CE 内重新启用。"
            else:
                detail = "icc:// 协议不可用。"
            self.warning_text.setText(
                "<b>ICC-CE URL 协议检测未通过</b><br>" + detail
            )

        self.warning_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border-radius: {self._warning_border_radius}; }}"
        )
        self.warning_text.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
        self.icon_label.setPixmap(icon.pixmap(16, 16))


class ICCCESettingsWindow(QWidget):
    """ICC-CE 专用设置窗口"""
    def __init__(self, icc_protocol_status=None):
        super().__init__()
        self.setWindowTitle("ICC-CE 设置 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore
        self.settings = load_settings()
        self._init_ui = True

        indent = (self.style().pixelMetric(QStyle.PM_IndicatorWidth) + # type: ignore
                  self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing)) # type: ignore

        self.chk_show = QCheckBox("显示加载窗口")
        self.chk_show.setChecked(self.settings["show_loading_window"])
        self.chk_show.toggled.connect(self.on_show_toggled)

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
        hint_color = "#b0b0b0" if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "gray" # type: ignore
        lbl_hint.setStyleSheet(f"color: {hint_color}; font-size: 9pt;")
        hint_layout = QHBoxLayout()
        hint_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        hint_layout.addWidget(lbl_hint)
        hint_layout.addStretch()

        self.chk_pen = QCheckBox("自动切换为笔")
        self.chk_pen.setChecked(self.settings["auto_pen"])
        self.chk_pen.toggled.connect(self.on_pen_toggled)

        grp_replace = QGroupBox("ICC-CE 替换设置")
        replace_layout = QVBoxLayout()
        replace_layout.addWidget(self.chk_show)
        replace_layout.addLayout(dur_layout)
        replace_layout.addLayout(hint_layout)
        replace_layout.addWidget(self.chk_pen)
        grp_replace.setLayout(replace_layout)

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

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp_replace)
        main_layout.addWidget(grp_icc)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self._init_ui = False
        self.resize(380, 360)

    def restore_hide_cb(self):
        self.chk_hide.setText("收纳时彻底隐藏")
        self.chk_hide.setEnabled(True)

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
        self.chk_hide.setText("设置中，请稍后……")
        self.thorough_timer.start(3000)

    def on_dur_changed(self, val):
        self.settings["loading_duration"] = val
        save_settings(self.settings)
