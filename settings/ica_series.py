import ctypes
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QPushButton, QCheckBox, QLineEdit, QComboBox, QTabWidget,
    QFileDialog, QMessageBox, QInputDialog, QFrame, QStyle,
    QDialog, QListWidget, QListWidgetItem,
)
from utils import (
    get_icon_path,
    load_settings,
    save_settings,
    _is_win11,
    _log,
)

# 允许用户选择的可执行程序扩展名（与 settings/custom.py 保持一致）
_EXEC_EXTENSIONS = (".exe", ".pif", ".com", ".bat", ".cmd")
# 文件对话框过滤器：程序文件 + 所有文件
_EXEC_FILE_FILTER = "程序文件 (*.exe *.pif *.com *.bat *.cmd);;所有文件 (*.*)"

_WINDOW_TITLE_RE = re.compile(r'^Ink Canvas .+ 画板$')
_WINDOW_TITLE_EXCLUDE = "Ink Canvas Plus 画板"
# 窗口标题精确匹配项（严格等于）
_WINDOW_TITLE_STRICT = "InkCanvasforClass"

_SCHEME_DESCRIPTIONS = {
    "scheme1": (
        '<b>推荐模式说明：</b>自动按下 <code>Alt + D</code> 显示浮动栏并进入批注模式，<br>'
        '再按下 <code>Alt + Q</code> 退出批注模式（若未勾选「自动切换到笔」选项）<br>'
        '几乎无感，建议使用此方案，若批注软件出现 Bug，请改用「兼容模式」'
    ),
    "scheme2": (
        "<b>兼容模式说明：</b>自动按下两次 <code>Alt + B</code> 进入并退出画板，<br>"
        '再按下 <code>Alt + D</code> 进入批注模式（若已勾选「自动切换到笔」选项）<br>'
        '会闪过 0.3s 画板界面，请优先使用「推荐模式」'
    ),
}

def _make_banner(parent, margin_top=8):
    frame = QFrame(parent)
    text = QLabel(frame)
    text.setTextFormat(Qt.RichText) # type: ignore
    text.setWordWrap(True)
    icon = QLabel(frame)
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(10, margin_top, 10, 8)
    layout.addWidget(icon, 0, Qt.AlignTop) # type: ignore
    layout.addSpacing(6)
    layout.addWidget(text, 1)
    return frame, text, icon


def detect_ica_window_titles():
    """枚举当前所有可见顶层窗口，返回符合 ICA 标题格式的列表。

    匹配规则：
      1. 标题严格等于 ``InkCanvasforClass``（精确匹配）
      2. 以「Ink Canvas 」开头（含空格），以「 画板」结尾（含空格），
         且中间至少 1 个字符；排除完全等于「Ink Canvas Plus 画板」的标题。
    """
    if not sys.platform.startswith("win"):
        return []

    user32 = ctypes.windll.user32
    results = []

    def _enum_cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        matched = (
            title == _WINDOW_TITLE_STRICT
            or (title != _WINDOW_TITLE_EXCLUDE and _WINDOW_TITLE_RE.match(title))
        )
        if matched and title not in results:
            results.append(title)
        return True

    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(CMPFUNC(_enum_cb), 0)
    return results


class SelectWindowTitleDialog(QDialog):
    """多窗口标题候选时的选择对话框"""
    def __init__(self, titles, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择批注软件窗口标题")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(self.windowFlags() | Qt.Window) # type: ignore
        self._selected = None

        hint = QLabel("检测到多个符合条件的批注软件窗口，请选择对应的窗口标题：")
        hint.setWordWrap(True)

        self.list_widget = QListWidget()
        for t in titles:
            item = QListWidgetItem(t)
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._on_double_clicked)

        btn_ok = QPushButton("确定")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)

        layout = QVBoxLayout()
        layout.addWidget(hint)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(btn_row)
        self.setLayout(layout)
        self.resize(360, 380)

    def _on_double_clicked(self, _item):
        self._accept()

    def _accept(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self._selected = item.text()
        self.accept()

    def selected_title(self):
        return self._selected


class ICASettingsWindow(QWidget):
    """Ink Canvas Artistry 系列专用设置窗口"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ink Canvas Artistry 系列设置 - 希沃批注替换")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setWindowFlags(Qt.Window) # type: ignore
        self.settings = load_settings()
        self._init_ui = True

        # 记录本会话内"新建且从未修改过"的方案 id：删除时直接跳过确认
        self._new_unmodified_ids = set()

        self._ensure_profiles()

        is_win11 = _is_win11()
        self._banner_border_radius = "6px" if is_win11 else "0px"

        self.info_frame, self.info_text, self.info_icon = _make_banner(self)
        self._apply_info_banner_style()

        self.warning_frame, self.warning_text, self.warning_icon = _make_banner(self)
        self.warning_text.setText("<b>警告占位符</b><br>[此处填写警告内容]")
        self._apply_warning_banner_style()

        btn_new = QPushButton("新建")
        btn_rename = QPushButton("重命名")
        btn_delete = QPushButton("删除")
        btn_new.clicked.connect(self._add_profile)
        btn_rename.clicked.connect(self._rename_profile)
        btn_delete.clicked.connect(self._delete_profile)

        btn_row = QHBoxLayout()
        btn_row.addWidget(QLabel("方案管理："))
        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_rename)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()

        self.tabs = QTabWidget()
        self.tabs.setMovable(False)
        self.tabs.setTabsClosable(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._build_tabs()

        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.close)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.addWidget(self.info_frame)
        main_layout.addWidget(self.warning_frame)
        main_layout.addLayout(btn_row)
        main_layout.addWidget(self.tabs, 1)
        main_layout.addLayout(bottom_layout)
        self.setLayout(main_layout)

        QApplication.styleHints().colorSchemeChanged.connect(self._on_color_scheme_changed) # type: ignore

        self._init_ui = False
        self.resize(520, 480)

    def _ensure_profiles(self):
        """确保 ica_series 分类下有合法的 ica_profiles 列表与 active_profile_id。

        负责：
          1. 检测嵌套结构中是否已有 ica_profiles
          2. 若有：补全缺失的 window_title / shortcut_scope 字段、修正无效的 active_profile_id
          3. 若无：创建默认方案
        """
        ica_series = self.settings.setdefault("ica_series", {})
        if "ica_profiles" in ica_series:
            fixed = False
            for p in ica_series["ica_profiles"]:
                if "window_title" not in p:
                    p["window_title"] = ""
                    fixed = True
                if "shortcut_scope" not in p:
                    p["shortcut_scope"] = "local"
                    fixed = True
            if not ica_series["ica_profiles"]:
                ica_series["ica_profiles"] = [
                    {"id": "p1", "name": "方案 1", "exe_path": "",
                     "window_title": "", "auto_pen": False,
                     "unhide_scheme": "scheme1", "shortcut_scope": "local"},
                ]
                ica_series["ica_active_profile_id"] = "p1"
                try:
                    save_settings(self.settings)
                except Exception as e:
                    _log(f"_ensure_profiles: save failed (empty profiles): {e}", level="error")
            elif ica_series.get("ica_active_profile_id") not in [
                p["id"] for p in ica_series["ica_profiles"]
            ]:
                ica_series["ica_active_profile_id"] = ica_series["ica_profiles"][0]["id"]
                try:
                    save_settings(self.settings)
                except Exception as e:
                    _log(f"_ensure_profiles: save failed (bad active id): {e}", level="error")
            elif fixed:
                try:
                    save_settings(self.settings)
                except Exception as e:
                    _log(f"_ensure_profiles: save failed (field fix): {e}", level="error")
            return

        # 无 ica_profiles：创建默认方案
        ica_series["ica_profiles"] = [
            {"id": "p1", "name": "方案 1", "exe_path": "",
             "window_title": "", "auto_pen": False,
             "unhide_scheme": "scheme1", "shortcut_scope": "local"},
        ]
        ica_series["ica_active_profile_id"] = "p1"
        try:
            save_settings(self.settings)
        except Exception as e:
            _log(f"_ensure_profiles: save failed (default profile): {e}", level="error")

    def _next_profile_id(self):
        max_n = 0
        for p in self.settings["ica_series"]["ica_profiles"]:
            try:
                n = int(p["id"].lstrip("p"))
                max_n = max(max_n, n)
            except (ValueError, AttributeError):
                continue
        return f"p{max_n + 1}"

    # ---------- banner styles ----------

    def _on_color_scheme_changed(self, _scheme):
        self._apply_info_banner_style()
        self._apply_warning_banner_style()
        self._update_scheme_desc_style()

    def _apply_info_banner_style(self):
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation) # type: ignore
        if is_dark:
            bg, fg = "#1e3a5f", "#a8d4f0"
        else:
            bg, fg = "#d1ecf1", "#0c5460"
        self.info_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: {self._banner_border_radius}; }}"
        )
        self.info_text.setStyleSheet(f"color: {fg}; font-size: 9pt;")
        self.info_icon.setPixmap(icon.pixmap(16, 16))
        self.info_text.setText(
            "<b>提示</b><br>"
            '本设置支持同时兼容 <b>"Dongsf119/Ink-Canvas-Artistry"</b> 与 '
            '<b>"InkCanvas/Ink-Canvas-Artistry"</b> 两个版本。'
        )

    def _apply_warning_banner_style(self):
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning) # type: ignore
        if is_dark:
            bg, fg = "#4a3f1f", "#f7d87a"
        else:
            bg, fg = "#fff3cd", "#856404"
        self.warning_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: {self._banner_border_radius}; }}"
        )
        self.warning_text.setStyleSheet(f"color: {fg}; font-size: 9pt;")
        self.warning_icon.setPixmap(icon.pixmap(16, 16))

    # ---------- tab management ----------

    def _build_tabs(self):
        active_id = self.settings["ica_series"].get("ica_active_profile_id")
        active_idx = 0
        for i, profile in enumerate(self.settings["ica_series"]["ica_profiles"]):
            widget = self._create_tab_page(profile)
            self.tabs.addTab(widget, profile.get("name", f"方案 {i+1}"))
            if profile["id"] == active_id:
                active_idx = i
        self.tabs.setCurrentIndex(active_idx)

    def _create_tab_page(self, profile):
        page = QWidget(self.tabs)

        # ---- 软件路径 ----
        txt_path = QLineEdit(page)
        txt_path.setPlaceholderText(f"请选择批注软件的可执行程序路径")
        txt_path.setText(profile.get("exe_path", ""))
        txt_path.editingFinished.connect(lambda: self._on_path_edited())

        btn_browse = QPushButton("浏览…", page)
        btn_browse.clicked.connect(lambda: self._on_browse_clicked())

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("软件路径："))
        path_row.addWidget(txt_path, 1)
        path_row.addWidget(btn_browse)

        # ---- 软件快捷键作用范围 ----
        cmb_scope = QComboBox(page)
        cmb_scope.addItem("局部", "local")
        cmb_scope.addItem("全局", "global")
        current_scope = profile.get("shortcut_scope", "local")
        idx = cmb_scope.findData(current_scope)
        cmb_scope.setCurrentIndex(idx if idx >= 0 else 0)
        cmb_scope.currentIndexChanged.connect(lambda _i: self._on_scope_changed())

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("软件快捷键作用范围："))
        scope_row.addWidget(cmb_scope)
        scope_row.addStretch()

        # ---- 窗口标题（包装在容器中以支持缩进 + 整体隐藏） ----
        txt_title = QLineEdit(page)
        txt_title.setPlaceholderText("可在任务视图中查看")
        txt_title.setText(profile.get("window_title", ""))
        txt_title.editingFinished.connect(lambda: self._on_title_edited())

        btn_detect = QPushButton("检测", page)
        btn_detect.clicked.connect(lambda: self._on_detect_clicked())

        title_row_inner = QHBoxLayout()
        title_row_inner.addWidget(QLabel("窗口标题："))
        title_row_inner.addWidget(txt_title, 1)
        title_row_inner.addWidget(btn_detect)

        title_container = QWidget(page)
        title_ly = QHBoxLayout(title_container)
        # 默认局部模式：缩进 20px 以突出从属关系
        title_ly.setContentsMargins(20, 0, 0, 0)
        title_ly.addLayout(title_row_inner)

        # ---- 取消收纳方案 ----
        cmb_scheme = QComboBox(page)
        cmb_scheme.addItem("推荐模式", "scheme1")
        cmb_scheme.addItem("兼容模式", "scheme2")
        current_scheme = profile.get("unhide_scheme", "scheme1")
        idx = cmb_scheme.findData(current_scheme)
        cmb_scheme.setCurrentIndex(idx if idx >= 0 else 0)
        cmb_scheme.currentIndexChanged.connect(lambda _i: self._on_scheme_changed())

        scheme_row = QHBoxLayout()
        scheme_row.addWidget(QLabel("取消收纳方案："))
        scheme_row.addWidget(cmb_scheme)
        scheme_row.addStretch()

        lbl_scheme_desc = QLabel(page)
        lbl_scheme_desc.setWordWrap(True)

        chk_auto_pen = QCheckBox("自动切换为笔", page)
        chk_auto_pen.setChecked(profile.get("auto_pen", False))
        chk_auto_pen.toggled.connect(lambda _v: self._on_auto_pen_toggled())

        layout = QVBoxLayout(page)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(8)
        layout.addLayout(path_row)
        layout.addLayout(scope_row)
        layout.addWidget(title_container)
        layout.addLayout(scheme_row)
        layout.addWidget(lbl_scheme_desc)
        layout.addWidget(chk_auto_pen)
        layout.addStretch()

        page._txt_path = txt_path
        page._title_container = title_container
        page._txt_title = txt_title
        page._cmb_scope = cmb_scope
        page._cmb_scheme = cmb_scheme
        page._lbl_scheme_desc = lbl_scheme_desc
        page._chk_auto_pen = chk_auto_pen
        self._apply_scope_visibility(page)
        self._update_scheme_desc_for(page)
        return page

    def _apply_scope_visibility(self, page):
        """根据当前 shortcut_scope 设置窗口标题容器的可见性与缩进。"""
        scope = page._cmb_scope.currentData()
        if scope == "global":
            page._title_container.hide()
        else:
            # 局部模式：向内缩进 20px 以体现与「软件快捷键作用范围」的从属关系
            page._title_container.layout().setContentsMargins(20, 0, 0, 0)
            page._title_container.show()

    # ---------- helpers ----------

    def _current_profile_index(self):
        return self.tabs.currentIndex()

    def _current_profile(self):
        idx = self._current_profile_index()
        if 0 <= idx < len(self.settings["ica_series"]["ica_profiles"]):
            return self.settings["ica_series"]["ica_profiles"][idx]
        return None

    def _current_page(self):
        return self.tabs.currentWidget()

    def _mark_current_dirty(self):
        profile = self._current_profile()
        if profile is not None:
            self._new_unmodified_ids.discard(profile.get("id"))

    def _save_current_profile(self):
        page = self._current_page()
        profile = self._current_profile()
        if page is None or profile is None:
            return
        profile["exe_path"] = page._txt_path.text().strip()
        profile["window_title"] = page._txt_title.text().strip()
        profile["shortcut_scope"] = page._cmb_scope.currentData()
        profile["unhide_scheme"] = page._cmb_scheme.currentData()
        profile["auto_pen"] = page._chk_auto_pen.isChecked()
        try:
            save_settings(self.settings)
        except Exception as e:
            _log(f"_save_current_profile: save failed: {e}", level="error")
            QMessageBox.warning(
                self, "希沃批注替换",
                f"设置保存失败：\n{e}\n\n请检查配置文件是否被占用或权限不足。"
            )

    def _update_scheme_desc_for(self, page):
        scheme = page._cmb_scheme.currentData()
        desc = _SCHEME_DESCRIPTIONS.get(scheme, "")
        is_dark = QApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark # type: ignore
        hint_color = "#b0b0b0" if is_dark else "gray"
        page._lbl_scheme_desc.setStyleSheet(f"color: {hint_color}; font-size: 9pt;")
        page._lbl_scheme_desc.setText(desc)

    def _update_scheme_desc_style(self):
        for i in range(self.tabs.count()):
            self._update_scheme_desc_for(self.tabs.widget(i))

    # ---------- slots ----------

    def _on_tab_changed(self, _idx):
        if self._init_ui:
            return
        profile = self._current_profile()
        if profile is not None:
            self.settings["ica_series"]["ica_active_profile_id"] = profile["id"]
        save_settings(self.settings)

    def _on_scope_changed(self):
        if self._init_ui:
            return
        page = self._current_page()
        if page is not None:
            self._apply_scope_visibility(page)
        self._mark_current_dirty()
        self._save_current_profile()

    def _on_path_edited(self):
        if self._init_ui:
            return
        page = self._current_page()
        if page is not None:
            path = page._txt_path.text().strip()
            if path and not self._validate_exe_path(path, show_warning=True):
                return
        self._mark_current_dirty()
        self._save_current_profile()

    def _on_title_edited(self):
        if self._init_ui:
            return
        self._mark_current_dirty()
        self._save_current_profile()

    def _validate_exe_path(self, path, show_warning=False):
        """校验路径是否指向有效的可执行程序。

        校验规则：
          - 路径非空
          - 文件存在且为文件（非目录）
          - 扩展名属于 _EXEC_EXTENSIONS (.exe/.pif/.com/.bat/.cmd)

        show_warning=True 时，校验失败会弹出 QMessageBox.warning 提示用户。
        返回 True 表示通过，False 表示不通过。
        """
        if not path:
            if show_warning:
                QMessageBox.warning(
                    self, "希沃批注替换",
                    "软件路径不能为空。"
                )
            return False
        if not os.path.exists(path):
            if show_warning:
                QMessageBox.warning(
                    self, "希沃批注替换",
                    f"文件不存在：\n{path}\n请检查路径是否正确。"
                )
            return False
        if not os.path.isfile(path):
            if show_warning:
                QMessageBox.warning(
                    self, "希沃批注替换",
                    f"路径不是文件：\n{path}"
                )
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext not in _EXEC_EXTENSIONS:
            if show_warning:
                QMessageBox.warning(
                    self, "希沃批注替换",
                    f"不支持的文件类型：{ext or '（无扩展名）'}\n"
                    f"请选择以下类型的可执行程序：{', '.join(_EXEC_EXTENSIONS)}"
                )
            return False
        return True

    def _on_browse_clicked(self):
        page = self._current_page()
        if page is None:
            return
        start_dir = os.path.dirname(page._txt_path.text()) if page._txt_path.text() else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择批注软件可执行程序",
            start_dir,
            _EXEC_FILE_FILTER,
        )
        if not file_path:
            return
        if not self._validate_exe_path(file_path, show_warning=True):
            return
        page._txt_path.setText(file_path)
        self._mark_current_dirty()
        self._save_current_profile()

    def _on_detect_clicked(self):
        if not sys.platform.startswith("win"):
            QMessageBox.information(
                self, "希沃批注替换",
                "窗口标题检测功能仅在 Windows 系统下可用。"
            )
            return
        try:
            titles = detect_ica_window_titles()
        except Exception as e:
            QMessageBox.critical(
                self, "希沃批注替换",
                f"检测窗口标题时出错：{e}"
            )
            return

        page = self._current_page()
        if page is None:
            return

        if not titles:
            QMessageBox.information(
                self, "希沃批注替换",
                "未检测到符合条件的批注软件窗口。\n"
                "请先启动 Ink Canvas Artistry 再重试。"
            )
            return
        if len(titles) == 1:
            page._txt_title.setText(titles[0])
            self._mark_current_dirty()
            self._save_current_profile()
            return

        dialog = SelectWindowTitleDialog(titles, self)
        if dialog.exec() == QDialog.Accepted:
            selected = dialog.selected_title()
            if selected:
                page._txt_title.setText(selected)
                self._mark_current_dirty()
                self._save_current_profile()

    def _on_scheme_changed(self):
        if self._init_ui:
            return
        page = self._current_page()
        if page is not None:
            self._update_scheme_desc_for(page)
        self._mark_current_dirty()
        self._save_current_profile()

    def _on_auto_pen_toggled(self):
        if self._init_ui:
            return
        self._mark_current_dirty()
        self._save_current_profile()

    # ---------- profile management buttons ----------

    def _add_profile(self):
        self._save_current_profile()
        new_id = self._next_profile_id()
        new_profile = {
            "id": new_id,
            "name": f"方案 {len(self.settings['ica_series']['ica_profiles']) + 1}",
            "exe_path": "",
            "window_title": "",
            "auto_pen": False,
            "unhide_scheme": "scheme1",
            "shortcut_scope": "local",
        }
        self.settings["ica_series"]["ica_profiles"].append(new_profile)
        self._new_unmodified_ids.add(new_id)
        page = self._create_tab_page(new_profile)
        self.tabs.addTab(page, new_profile["name"])
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        save_settings(self.settings)

    def _rename_profile(self):
        idx = self._current_profile_index()
        profile = self._current_profile()
        if profile is None:
            return
        name, ok = QInputDialog.getText(
            self, "重命名方案", "请输入新名称：", text=profile.get("name", "")
        )
        if not ok or not name.strip():
            return
        name = name.strip()
        self._init_ui = True
        self.tabs.setTabText(idx, name)
        self._init_ui = False
        profile["name"] = name
        self._new_unmodified_ids.discard(profile.get("id"))
        save_settings(self.settings)

    def _delete_profile(self):
        if self.tabs.count() <= 1:
            QMessageBox.information(
                self, "希沃批注替换",
                "至少需要保留一个方案。"
            )
            return
        profile = self._current_profile()
        if profile is None:
            return
        profile_id = profile.get("id")
        # 本会话新建且从未修改：直接删除，不弹出确认框
        if profile_id not in self._new_unmodified_ids:
            reply = QMessageBox.question(
                self, "希沃批注替换",
                f"确定要删除方案「{profile.get('name', '')}」吗？此操作不可撤销。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No # type: ignore
            )
            if reply != QMessageBox.Yes: # type: ignore
                return
        idx = self._current_profile_index()
        self.settings["ica_series"]["ica_profiles"].pop(idx)
        self._new_unmodified_ids.discard(profile_id)
        self._init_ui = True
        self.tabs.removeTab(idx)
        self._init_ui = False
        new_idx = min(idx, self.tabs.count() - 1)
        self.settings["ica_series"]["ica_active_profile_id"] = self.settings["ica_series"]["ica_profiles"][new_idx]["id"]
        save_settings(self.settings)
