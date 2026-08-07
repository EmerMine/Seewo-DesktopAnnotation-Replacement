import json
import re
import threading
import urllib.request
import webbrowser
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QCheckBox, QTextBrowser, QDialog,
)
from utils import VERSION, get_icon_path, load_settings, save_settings


REPO_API = "https://api.github.com/repos/EmerMine/Seewo-DesktopAnnotation-Replacement/releases/latest"
RELEASES_URL = "https://github.com/EmerMine/Seewo-DesktopAnnotation-Replacement/releases"
REQUEST_TIMEOUT = 10
APP_USER_MODEL_ID = "Seewo.DesktopAnnotation.Replacement"


def _set_app_user_model_id():
    """Set the Windows AppUserModelID so toast notifications appear under our app name."""
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:
        pass


_set_app_user_model_id()


def _version_tuple(v):
    s = v.lstrip("vV").strip()
    parts = re.split(r"[.\-+]", s)
    result = []
    for p in parts:
        m = re.match(r"(\d+)", p)
        if m:
            result.append(int(m.group(1)))
    while len(result) < 3:
        result.append(0)
    return tuple(result[:3])


def version_greater(latest, current=VERSION):
    try:
        return _version_tuple(latest) > _version_tuple(current)
    except Exception:
        return False


def fetch_latest_release():
    req = urllib.request.Request(
        REPO_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Seewo-DesktopAnnotation-Replacement"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    return {
        "tag_name": data.get("tag_name", ""),
        "body": data.get("body", ""),
        "html_url": data.get("html_url", RELEASES_URL),
    }


def _persist_skip_version(version):
    s = load_settings()
    s["update_skipped_version"] = version
    save_settings(s)


def _persist_never_remind():
    s = load_settings()
    s["update_never_remind"] = True
    save_settings(s)


def _is_never_remind():
    return load_settings().get("update_never_remind", False)


def _skipped_matches(version):
    return load_settings().get("update_skipped_version") == version


class UpdateDialog(QDialog):
    def __init__(self, release, parent=None):
        super().__init__(parent)
        tag = release["tag_name"]
        body = release.get("body", "").strip()
        self.setWindowTitle(f"发现新版本 v{tag} - 希沃批注替换")
        icon_path = get_icon_path()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        self.setMinimumWidth(480)
        self.setMinimumHeight(360)
        self._release = release
        self._skip_this = False
        text_browser = QTextBrowser()
        text_browser.setOpenExternalLinks(True)
        if body:
            markdown = body
        else:
            markdown = "（暂无更新说明）"
        text_browser.setMarkdown(markdown)

        self.btn_never = QPushButton("不再提示更新")
        self.btn_never.clicked.connect(self._on_never_remind)
        btn_skip = QPushButton("跳过此更新")
        btn_skip.clicked.connect(self._on_skip_this)
        self.btn_now = QPushButton("立即更新")
        self.btn_now.setDefault(True)
        self.btn_now.clicked.connect(self._on_update_now)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_never)
        btn_row.addWidget(btn_skip)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_now)
        btn_row.addWidget(btn_close)

        layout = QVBoxLayout(self)
        layout.addWidget(text_browser, 1)
        layout.addLayout(btn_row)

    def _on_never_remind(self):
        _persist_never_remind()
        self.reject()

    def _on_update_now(self):
        webbrowser.open(self._release["html_url"])
        self.accept()

    def _on_skip_this(self):
        _persist_skip_version(self._release["tag_name"])
        self._skip_this = True
        self.reject()

    @property
    def skip_this(self):
        return self._skip_this


def _show_toast(release):
    """Show a Windows-native toast notification via windows-toasts."""
    try:
        from windows_toasts import Toast, WindowsToaster
        toast = Toast(
            text_fields=["发现新版本", f"希沃批注替换 v{release['tag_name']} 已发布，单击跳转至 Github Releases 页面。"],
            launch_action=release["html_url"],
        )
        toaster = WindowsToaster("希沃批注替换")
        toaster.show_toast(toast)
    except Exception:
        pass


def check_for_update(parent=None, show_dialog=False, present=True):
    """同步检查更新。若 present=False 仅返回结果，不弹出任何 UI。"""
    release = _check_logic()
    if release is None:
        return None
    if not present:
        return release
    if show_dialog:
        UpdateDialog(release, parent=parent).exec()
    else:
        _show_toast(release)
    return release


def _check_logic():
    if _is_never_remind():
        return None
    release = fetch_latest_release()
    if release is None:
        return None
    tag = release["tag_name"]
    if not version_greater(tag):
        return None
    if _skipped_matches(tag):
        return None
    return release


class _AsyncHelper(QObject):
    done = Signal(object)

    def __init__(self, parent=None, show_dialog=False):
        super().__init__(parent)
        self._show_dialog = show_dialog
        self._parent = parent
        self.done.connect(self._on_result)

    def _fetch(self):
        release = _check_logic()
        self.done.emit(release)

    def _on_result(self, release):
        if release is None:
            return
        if self._show_dialog:
            UpdateDialog(release, parent=self._parent).exec()
        else:
            _show_toast(release)


def check_for_update_async(parent=None, show_dialog=False):
    """异步检查更新，不阻塞 UI 线程。网络请求在后台线程，UI 在主线程。"""
    helper = _AsyncHelper(parent=parent, show_dialog=show_dialog)
    t = threading.Thread(target=helper._fetch, daemon=True)
    t.start()
    return helper
