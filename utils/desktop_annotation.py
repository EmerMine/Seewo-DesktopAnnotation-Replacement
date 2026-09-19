"""希沃桌面批注（DesktopAnnotation）安装状态管理：扫描、诊断、安装、卸载与损坏判定。"""
import os

from .config import (
    DESKTOP_ANNOTATION_DIR,
    DESKTOP_ANNOTATION_EXE,
    DESKTOP_ANNOTATION_BACKUP,
    DESKTOP_ANNOTATION_BAT,
    _DA_ORIGINAL_PREFIX,
    _DA_BACKUP_PREFIX,
    LOCAL_APPS_EXE,
    APPS_EXE_SHA256,
    INSTALL_STATUS_INSTALLED,
    INSTALL_STATUS_NOT_INSTALLED,
    INSTALL_STATUS_CORRUPTED,
)
from .hashing import sha256_file
from .process import kill_process_by_path
from .winversion import get_file_version
from .ps_scripts import _parse_bat_entry, _build_install_ps1, _build_uninstall_ps1
from .elevated import _run_elevated
from .debuglog import _debug_log, _log
from .qtstyle import _critical


def _scan_original_da_files(dir_path):
    """返回目录中所有以 DesktopAnnotation 开头但不以 DesktopAnnotationBackup 开头的文件路径。"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    try:
        for name in os.listdir(dir_path):
            if name.startswith(_DA_ORIGINAL_PREFIX) and not name.startswith(_DA_BACKUP_PREFIX):
                result.append(os.path.join(dir_path, name))
    except OSError:
        pass
    return result


def _scan_backup_da_files(dir_path):
    """返回目录中所有以 DesktopAnnotationBackup 开头的文件路径。"""
    if not os.path.isdir(dir_path):
        return []
    result = []
    try:
        for name in os.listdir(dir_path):
            if name.startswith(_DA_BACKUP_PREFIX):
                result.append(os.path.join(dir_path, name))
    except OSError:
        pass
    return result


def _find_primary_exe(paths):
    """从文件路径列表中找到 .exe 文件，找不到返回 None。"""
    for p in paths:
        if p.lower().endswith(".exe"):
            return p
    return None


def get_desktop_annotation_version():
    """读取希沃桌面批注 exe 的版本号。

    优先扫描 DESKTOP_ANNOTATION_DIR 中所有 DesktopAnnotationBackup*.exe；
    若不存在或读取失败，再扫描 DesktopAnnotation*.exe（排除 Backup*）。
    返回 (version_tuple, source_path)；若均读取失败则返回 (None, None)。
    """
    for paths in (_scan_backup_da_files(DESKTOP_ANNOTATION_DIR),
                  _scan_original_da_files(DESKTOP_ANNOTATION_DIR)):
        primary = _find_primary_exe(paths)
        if primary and os.path.exists(primary):
            ver = get_file_version(primary)
            if ver is not None:
                return ver, primary
    return None, None


def get_install_diagnostics():
    """逐项返回安装状态判定所依赖的检查结果。

    返回值：list of dict，每项含 label / ok / detail。ok=True 表示该项符合预期。
    """
    checks = []

    # 1. 本地安装源（apps\\DesktopAnnotation.exe）
    src_exists = os.path.exists(LOCAL_APPS_EXE)
    src_hash = sha256_file(LOCAL_APPS_EXE) if src_exists else None
    checks.append({
        "label": "安装源完整性",
        "ok": bool(src_exists and src_hash == APPS_EXE_SHA256),
        "detail": (
            f"{LOCAL_APPS_EXE}\n"
            + (f"哈希值：{src_hash}" if src_exists else "文件缺失")
            + (f"\n期望哈希：{APPS_EXE_SHA256}" if src_exists and src_hash != APPS_EXE_SHA256 else "")
        ),
    })

    # 2. 目标 exe 存在性（DesktopAnnotation.exe 是替换入口）
    has_orig = os.path.exists(DESKTOP_ANNOTATION_EXE)
    checks.append({
        "label": "目标程序存在",
        "ok": has_orig,
        "detail": DESKTOP_ANNOTATION_EXE,
    })

    # 3. 目标 exe 哈希（应为"我们的 exe"，若已安装）
    orig_hash = sha256_file(DESKTOP_ANNOTATION_EXE) if has_orig else None
    checks.append({
        "label": "目标程序哈希",
        "ok": bool(has_orig and orig_hash == APPS_EXE_SHA256),
        "detail": (
            f"当前哈希：{orig_hash}" if has_orig and orig_hash
            else ("文件缺失" if not has_orig else "无法读取")
        ),
    })

    # 4. 原始备份文件组（所有 DesktopAnnotationBackup* 文件）
    backup_files = _scan_backup_da_files(DESKTOP_ANNOTATION_DIR)
    backup_exe = _find_primary_exe(backup_files)
    # 专项校验：DesktopAnnotationBackup.exe 与替换程序（apps）哈希一致 → 备份损坏
    backup_corrupted = (
        os.path.exists(DESKTOP_ANNOTATION_BACKUP)
        and sha256_file(DESKTOP_ANNOTATION_BACKUP) == APPS_EXE_SHA256
    )
    checks.append({
        "label": "原始程序备份",
        "ok": bool(backup_files) and not backup_corrupted,
        "detail": (
            f"共 {len(backup_files)} 个文件：<br>"
            + "<br>".join(f"  {os.path.basename(p)}" for p in backup_files)
            + ("<br>备份文件与替换程序哈希一致，备份已损坏" if backup_corrupted else "")
            if backup_files else "未发现备份文件"
        ),
    })

    # 5. 原始未备份文件组（信息性展示，不参与健康判定）
    original_files = _scan_original_da_files(DESKTOP_ANNOTATION_DIR)
    checks.append({
        "label": "原始未备份文件",
        "ok": True,
        "detail": (
            f"共 {len(original_files)} 个文件：<br>"
            + "<br>".join(f"  {os.path.basename(p)}" for p in original_files)
            if original_files else "无（安装后原始文件已被重命名为 DesktopAnnotationBackup*）"
        ),
    })

    # 6. 入口启动脚本 (.bat)
    has_launcher = os.path.exists(DESKTOP_ANNOTATION_BAT)
    checks.append({
        "label": "启动脚本",
        "ok": has_launcher,
        "detail": DESKTOP_ANNOTATION_BAT,
    })

    # 7. 启动脚本入口路径有效性
    entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT) if has_launcher else []
    all_entry_exist = bool(entry_paths) and all(os.path.exists(p) for p in entry_paths)
    checks.append({
        "label": "启动脚本入口有效",
        "ok": all_entry_exist,
        "detail": (
            "<br>".join(f"  {p}" for p in entry_paths) if entry_paths
            else ("启动脚本不存在" if not has_launcher else "无法解析入口命令")
        ),
    })

    return checks


def install():
    """安装：校验 → 杀进程 → 备份 → 替换 → 写启动脚本 (.bat)。

    返回 (ok, failure_reasons)。ok 为 True 时 failure_reasons 为空列表；
    ok 为 False 时 failure_reasons 是字符串列表（每项描述一项失败检查）。
    """
    _debug_log("install() called")
    _log("INSTALL invoked")
    reasons = []

    if not os.path.exists(LOCAL_APPS_EXE):
        reasons.append(f"未找到安装源：{LOCAL_APPS_EXE}")
        _log(f"INSTALL failed: source not found {LOCAL_APPS_EXE}", "error")
    else:
        actual = sha256_file(LOCAL_APPS_EXE)
        if actual != APPS_EXE_SHA256:
            reasons.append(
                f"安装源哈希不匹配：实际 {actual}，期望 {APPS_EXE_SHA256}"
            )
            _log(f"INSTALL failed: hash mismatch actual={actual} expected={APPS_EXE_SHA256}", "error")

    if reasons:
        _critical(reasons[0])
        return False, reasons

    _log(f"INSTALL validation passed, killing processes for {DESKTOP_ANNOTATION_EXE}")
    kill_process_by_path(DESKTOP_ANNOTATION_EXE)
    kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
    _run_elevated(_build_install_ps1())
    _log("INSTALL ps1 dispatched (elevated)")
    return True, []


def uninstall():
    """卸载：杀进程 → 恢复原文件 → 清理启动脚本 (.bat)。"""
    _debug_log("uninstall() called")
    _log("UNINSTALL invoked")
    kill_process_by_path(DESKTOP_ANNOTATION_BACKUP)
    kill_process_by_path(DESKTOP_ANNOTATION_EXE)
    _run_elevated(_build_uninstall_ps1())
    _log("UNINSTALL ps1 dispatched (elevated)")
    return True


def get_install_status():
    """返回安装状态：INSTALL_STATUS_INSTALLED / NOT_INSTALLED / CORRUPTED。

    判定规则：
      - NOT_INSTALLED：DESKTOP_ANNOTATION_EXE 存在但 hash 不是我们的，且无备份文件组、无启动脚本
      - INSTALLED：DESKTOP_ANNOTATION_EXE hash 符合 + 存在备份文件组 + 存在有效启动脚本
      - CORRUPTED：其他所有情况（含专项校验：DesktopAnnotationBackup.exe 与替换程序
        exe_sha256 一致时，说明备份已被替换程序覆盖，判定为损坏）
    """
    has_orig = os.path.exists(DESKTOP_ANNOTATION_EXE)
    has_backup = bool(_scan_backup_da_files(DESKTOP_ANNOTATION_DIR))
    has_launcher = os.path.exists(DESKTOP_ANNOTATION_BAT)

    if not has_orig:
        return INSTALL_STATUS_CORRUPTED
    orig_hash = sha256_file(DESKTOP_ANNOTATION_EXE)

    if orig_hash != APPS_EXE_SHA256 and not has_launcher and not has_backup:
        return INSTALL_STATUS_NOT_INSTALLED

    # 专项校验：DesktopAnnotationBackup.exe 的 SHA-256 与预设 exe_sha256 完全一致，
    # 说明备份文件是替换程序的副本而非原始希沃程序，标记为损坏
    if os.path.exists(DESKTOP_ANNOTATION_BACKUP) \
            and sha256_file(DESKTOP_ANNOTATION_BACKUP) == APPS_EXE_SHA256:
        return INSTALL_STATUS_CORRUPTED

    if orig_hash == APPS_EXE_SHA256 and has_backup and has_launcher:
        entry_paths = _parse_bat_entry(DESKTOP_ANNOTATION_BAT)
        if entry_paths and all(os.path.exists(p) for p in entry_paths):
            return INSTALL_STATUS_INSTALLED

    return INSTALL_STATUS_CORRUPTED
