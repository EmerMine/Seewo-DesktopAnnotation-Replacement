"""修复流程：版本检测 → 下载安装包（PNG 载体）→ 解码 → 静默重装。"""
import os
import urllib.request
import tempfile

try:
    from PIL import Image as _PILImage
    import numpy as _numpy
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

from .config import REPAIR_EXE_PNG_URL, REPAIR_URL_MAP, DESKTOP_ANNOTATION_EXE, DESKTOP_ANNOTATION_BACKUP
from .debuglog import _debug_log, _log
from .process import kill_process_by_path
from .qtstyle import _critical
from .elevated import _run_elevated
from .ps_scripts import _build_repair_ps1
from .desktop_annotation import get_desktop_annotation_version


def _version_tuple_to_string(ver):
    """将 (1, 0, 0, 133) 转为 "1.0.0.133"。"""
    if ver is None:
        return None
    return ".".join(str(p) for p in ver)


def _version_string_to_tuple(s):
    """将 JSON 键 "1.0.0.133" 转为版本元组。"""
    parts = s.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _get_latest_version_key(url_map):
    """从版本→URL列表的映射中，按语义版本号比较选取最大的版本键。"""
    if not url_map:
        return None
    best_key = None
    best_tuple = None
    for key in url_map:
        t = _version_string_to_tuple(key)
        if t is None:
            continue
        if best_tuple is None or t > best_tuple:
            best_tuple = t
            best_key = key
    return best_key


def get_repair_urls_for_version(ver_tuple):
    """根据版本元组查找修复安装包的下载链接列表。

    优先匹配完全对应的版本；若找不到则回退到最新版本；
    若映射表本身为空则回退到默认 REPAIR_EXE_PNG_URL。
    返回 list[str]（可能为空列表）。
    """
    url_map = REPAIR_URL_MAP
    if not url_map:
        return [REPAIR_EXE_PNG_URL] if REPAIR_EXE_PNG_URL else []

    if ver_tuple is not None:
        key = _version_tuple_to_string(ver_tuple)
        matched = url_map.get(key)
        if matched:
            return list(matched)

    latest_key = _get_latest_version_key(url_map)
    if latest_key:
        return list(url_map[latest_key])

    return [REPAIR_EXE_PNG_URL] if REPAIR_EXE_PNG_URL else []


def _decode_png_to_file(png_path, out_path):
    """从 exe2png 编码的 PNG 中还原出原始字节文件。

    兼容三种常见像素格式：
      - L（灰度）/ LA：直接用 arr.reshape(-1)
      - RGB / RGBA：原始 exe2png 编码通常存于第一个通道（R），
        因为灰度图在服务端被自动转成 RGBA 后，R 通道保留原始字节
    """
    if not _HAS_PIL:
        raise RuntimeError("缺少 Pillow / numpy 依赖，无法执行 PNG 解码")
    img = _PILImage.open(png_path)
    data = _numpy.array(img)
    if data.ndim == 2:
        raw = data.reshape(-1).tobytes()
    else:
        raw = data[:, :, 0].reshape(-1).tobytes()
    with open(out_path, "wb") as f:
        f.write(raw.rstrip(b"\x00"))


def _download(url, dest_path):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                f.write(chunk)


def _download_with_fallback(urls, dest_path):
    """按顺序尝试 urls 中的每个 URL 下载到 dest_path。

    成功即返回 (True, url_used)；全部失败则返回 (False, list_of_errors)。
    """
    if not urls:
        return False, ["下载链接列表为空"]
    errors = []
    for url in urls:
        try:
            _download(url, dest_path)
            if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                return True, url
            else:
                errors.append(f"下载完成但文件为空：{url}")
        except Exception as e:
            errors.append(f"{url} — {e}")
    return False, errors


def repair():
    """修复损坏的安装：读取当前版本 → 匹配下载链接 → 下载原始安装包 → 静默安装 → 标准安装我们的 exe。

    返回 (ok, failure_reasons)。
    """
    _debug_log("repair() called")
    _log("REPAIR invoked")
    reasons = []

    tmpdir = os.path.join(tempfile.gettempdir(), "sar_repair")
    os.makedirs(tmpdir, exist_ok=True)
    png_path = os.path.join(tmpdir, "desktopannotationsetup.png")
    installer_path = os.path.join(tmpdir, "DesktopAnnotationSetup.exe")

    try:
        ver_tuple, ver_source = get_desktop_annotation_version()
        urls = get_repair_urls_for_version(ver_tuple)

        if ver_tuple is None:
            ver_hint = "未知"
        else:
            ver_hint = _version_tuple_to_string(ver_tuple)

        _log(f"REPAIR detected version={ver_hint} source={ver_source or 'N/A'} urls={len(urls)}")

        ok, result = _download_with_fallback(urls, png_path)
        if not ok:
            reasons.append(
                f"下载版本 {ver_hint} 的安装包失败（尝试了 {len(urls)} 个链接）。"
                f"目标来源：{ver_source or '未找到对应 exe'}。"
            )
            for err in result:
                reasons.append(f"  • {err}")
            _log(f"REPAIR download failed: {'; '.join(reasons)}", "error")
            _critical(reasons[0])
            return False, reasons

        _log(f"REPAIR downloaded to {png_path} ({os.path.getsize(png_path)} bytes)")

        if not os.path.exists(png_path) or os.path.getsize(png_path) == 0:
            reasons.append("下载的安装包为空或不存在")
            _log("REPAIR downloaded file empty", "error")
            _critical(reasons[0])
            return False, reasons

        try:
            _decode_png_to_file(png_path, installer_path)
            _log(f"REPAIR decoded PNG to {installer_path} ({os.path.getsize(installer_path)} bytes)")
        except Exception as e:
            reasons.append(f"PNG 解码失败：{e}")
            _log(f"REPAIR PNG decode failed: {e}", "error")
            _critical(reasons[0])
            return False, reasons

        if not os.path.exists(installer_path) or os.path.getsize(installer_path) == 0:
            reasons.append("解码后的安装包为空")
            _log("REPAIR decoded installer empty", "error")
            _critical(reasons[0])
            return False, reasons

        _log("REPAIR dispatching elevated ps1")
        kill_process_by_path(DESKTOP_ANNOTATION_EXE)
        kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
        _run_elevated(_build_repair_ps1(installer_path, tmpdir))
        _log("REPAIR ps1 dispatched (elevated)")
        return True, []

    except Exception as e:
        reasons.append(f"修复异常：{e}")
        _log(f"REPAIR exception: {e}", "error")
        _critical(reasons[0])
        return False, reasons
