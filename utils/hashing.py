"""文件哈希计算。"""
import os
import hashlib


def sha256_file(path):
    """计算文件 SHA-256 哈希（十六进制小写字符串）。文件不存在返回 None。"""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
