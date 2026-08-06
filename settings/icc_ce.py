import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QSpinBox, QGroupBox,
    QSpacerItem, QSizePolicy, QStyle, QFrame,
)
from utils import (
    get_icon_path,
    load_settings,
    save_settings,
    run_protocol,
    _is_win11,
)


class ICCCESettingsWindow(QWidget):
    """ICC-CE 专用设置窗口"""
    def __init__(self):
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
        lbl_hint.setStyleSheet("color: gray; font-size: 9pt;")
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

        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        is_win11 = _is_win11()
        border_radius = "6px" if is_win11 else "0px"
        if is_dark:
            bg_color = "#4a3f1f"
            text_color = "#f7d87a"
        else:
            bg_color = "#fff3cd"
            text_color = "#856404"

        warning_frame = QFrame()
        warning_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border-radius: {border_radius}; }}"
        )
        warning_layout = QHBoxLayout(warning_frame)
        warning_layout.setContentsMargins(10, 8, 10, 8)
        icon_label = QLabel()
        icon_label.setPixmap(self.style().standardIcon( # type: ignore
            QStyle.StandardPixmap.SP_MessageBoxWarning # type: ignore
        ).pixmap(16, 16))
        warning_text = QLabel(
            "<b>请确保 ICC-CE 已开启「启用外部协议 (icc://)」设置项。</b><br>"
            "路径：ICC-CE 设置 > 通用 > 基本 > 开启「启用外部协议 (icc://)」。"
        )
        warning_text.setStyleSheet(f"color: {text_color}; font-size: 9pt;")
        warning_text.setTextFormat(Qt.RichText) # type: ignore
        warning_text.setWordWrap(True)
        warning_layout.addWidget(icon_label, 0, Qt.AlignTop) # type: ignore
        warning_layout.addSpacing(6)
        warning_layout.addWidget(warning_text, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(warning_frame)
        main_layout.addWidget(grp_replace)
        main_layout.addWidget(grp_icc)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self._init_ui = False
        self.resize(360, 400)

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
