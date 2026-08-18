import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QSpinBox, QGroupBox,
    QSpacerItem, QSizePolicy, QStyle,
)
from utils import (
    get_icon_path,
    load_settings,
    save_settings,
)


class NoneSettingsWindow(QWidget):
    """空程序（禁用批注）设置窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("空程序设置 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore
        self.settings = load_settings()
        self._init_ui = True

        indent = (self.style().pixelMetric(QStyle.PM_IndicatorWidth) + # type: ignore
                  self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing)) # type: ignore

        self.chk_show_msg = QCheckBox("显示「希沃桌面批注已被禁用」提示")
        self.chk_show_msg.setChecked(self.settings["none"].get("none_show_disabled_msg", True))
        self.chk_show_msg.toggled.connect(self.on_show_msg_toggled)

        dur_layout = QHBoxLayout()
        dur_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        dur_layout.addWidget(QLabel("提示显示时长（秒）："))
        self.spin_dur = QSpinBox()
        self.spin_dur.setRange(1, 10)
        self.spin_dur.setValue(self.settings["none"].get("none_msg_duration", 2))
        self.spin_dur.valueChanged.connect(self.on_dur_changed)
        dur_layout.addWidget(self.spin_dur)
        dur_layout.addStretch()
        self.spin_dur.setEnabled(self.settings["none"].get("none_show_disabled_msg", True))

        grp = QGroupBox("禁用提示")
        grp_layout = QVBoxLayout()
        grp_layout.addWidget(self.chk_show_msg)
        grp_layout.addLayout(dur_layout)
        grp.setLayout(grp_layout)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.setFixedWidth(80)
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self._init_ui = False
        self.resize(300, 160)

    def on_show_msg_toggled(self, checked):
        self.settings["none"]["none_show_disabled_msg"] = checked
        self.spin_dur.setEnabled(checked)
        save_settings(self.settings)

    def on_dur_changed(self, val):
        self.settings["none"]["none_msg_duration"] = val
        save_settings(self.settings)
