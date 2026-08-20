import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QGroupBox, QFileDialog,
    QCheckBox, QSpinBox, QSizePolicy, QSpacerItem, QStyle, QApplication,
)
from utils import (
    get_icon_path,
    load_settings,
    save_settings,
)


class CustomSettingsWindow(QWidget):
    """自定义程序设置窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("自定义程序设置 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore
        self.settings = load_settings()
        self._init_ui = True

        txt_path = QLineEdit()
        txt_path.setPlaceholderText("请输入可执行程序路径")
        txt_path.setText(self.settings["custom"].get("exe_path", ""))
        txt_path.editingFinished.connect(self._on_path_edited)

        btn_browse = QPushButton("浏览…")
        btn_browse.clicked.connect(self._on_browse_clicked)

        row = QHBoxLayout()
        row.addWidget(txt_path, 1)
        row.addWidget(btn_browse)

        indent = (self.style().pixelMetric(QStyle.PM_IndicatorWidth) + # type: ignore
                  self.style().pixelMetric(QStyle.PM_CheckBoxLabelSpacing)) # type: ignore

        chk_show = QCheckBox("显示加载窗口")
        chk_show.setChecked(self.settings["custom"].get("show_loading_window", True))
        chk_show.toggled.connect(self.on_show_toggled)

        dur_layout = QHBoxLayout()
        dur_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        dur_layout.addWidget(QLabel("加载窗口显示时长（秒）："))
        spin_dur = QSpinBox()
        spin_dur.setRange(1, 10)
        spin_dur.setValue(self.settings["custom"].get("loading_duration", 3))
        spin_dur.valueChanged.connect(self.on_dur_changed)
        dur_layout.addWidget(spin_dur)
        dur_layout.addStretch()
        spin_dur.setEnabled(self.settings["custom"].get("show_loading_window", True))

        lbl_hint = QLabel("加载中窗口最短显示 1.5 秒，确保不会因程序启动过快而闪烁")
        hint_color = "#b0b0b0" if QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark else "gray" # type: ignore
        lbl_hint.setStyleSheet(f"color: {hint_color}; font-size: 9pt;")
        hint_layout = QHBoxLayout()
        hint_layout.addSpacerItem(QSpacerItem(indent, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)) # type: ignore
        hint_layout.addWidget(lbl_hint)
        hint_layout.addStretch()

        grp = QGroupBox("自定义程序替换设置")
        grp_layout = QVBoxLayout()
        grp_layout.addLayout(row)
        grp_layout.addSpacing(8)
        grp_layout.addWidget(chk_show)
        grp_layout.addLayout(dur_layout)
        grp_layout.addLayout(hint_layout)
        grp.setLayout(grp_layout)

        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.close)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)

        main_layout = QVBoxLayout()
        main_layout.addWidget(grp)
        main_layout.addStretch()
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        self._txt_path = txt_path
        self._spin_dur = spin_dur
        self._init_ui = False
        self.resize(460, 200)

    def _save(self):
        self.settings["custom"]["exe_path"] = self._txt_path.text().strip()
        save_settings(self.settings)

    def _on_path_edited(self):
        if self._init_ui:
            return
        self._save()

    def _on_browse_clicked(self):
        start_dir = os.path.dirname(self._txt_path.text()) if self._txt_path.text() else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择可执行程序",
            start_dir,
            "程序文件 (*.exe *.pif *.com *.bat *.cmd);;所有文件 (*.*)",
        )
        if not file_path:
            return
        self._txt_path.setText(file_path)
        self._save()

    def on_show_toggled(self, checked):
        self.settings["custom"]["show_loading_window"] = checked
        self._spin_dur.setEnabled(checked)
        save_settings(self.settings)

    def on_dur_changed(self, val):
        self.settings["custom"]["loading_duration"] = val
        save_settings(self.settings)
