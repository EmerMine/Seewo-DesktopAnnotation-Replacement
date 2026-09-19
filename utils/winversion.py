"""Windows 可执行文件版本信息读取（Win32 API，无需 pywin32）。"""
import re
import ctypes
import struct


def get_file_version(path):
    """读取 Windows 可执行文件的 FILEVERSION，返回 (major, minor, patch, build) 元组。

    使用 ctypes 调用 GetFileVersionInfo 系列 Win32 API，无需 pywin32 依赖。
    读取失败时返回 None。
    """
    try:
        size = ctypes.windll.version.GetFileVersionInfoSizeW(path, None)
        if not size:
            return None
        buf = ctypes.create_string_buffer(size)
        if not ctypes.windll.version.GetFileVersionInfoW(path, None, size, buf):
            return None

        # 读取 Translation 块（LANGID + CODEPAGE 对）
        res_ptr = ctypes.c_void_p()
        res_len = ctypes.c_uint()
        if not ctypes.windll.version.VerQueryValueW(
            buf, r"\VarFileInfo\Translation", ctypes.byref(res_ptr), ctypes.byref(res_len)
        ):
            return None
        # 取第一对 (LANGID, CODEPAGE)，各占 2 字节，共 4 字节
        data = ctypes.string_at(res_ptr, res_len.value)
        lang_id, codepage = struct.unpack_from("<HH", data, 0)

        query = f"\\StringFileInfo\\{lang_id:04x}{codepage:04x}\\FileVersion"
        if not ctypes.windll.version.VerQueryValueW(
            buf, query, ctypes.byref(res_ptr), ctypes.byref(res_len)
        ):
            return None
        # 注意：res_len 是字符数，含末尾 null
        version_str = ctypes.wstring_at(res_ptr, res_len.value - 1)
        return _parse_version_tuple(version_str)
    except Exception:
        return None


def _parse_version_tuple(s):
    """将 "1.7.18.7" 或 "1, 7, 18, 7" 等格式解析为 (1, 7, 18, 7)。"""
    if not s:
        return None
    parts = re.split(r"[.,\s]+", s.strip())
    result = []
    for p in parts:
        m = re.match(r"(\d+)", p)
        if m:
            result.append(int(m.group(1)))
    if not result:
        return None
    while len(result) < 4:
        result.append(0)
    return tuple(result[:4])
