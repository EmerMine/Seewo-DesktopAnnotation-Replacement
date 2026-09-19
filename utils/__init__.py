"""utils 包：通用工具集合。

原 utils.py 单文件已按职责拆分为以下子模块：
  - paths              路径解析（基础目录 / 数据目录 / 资源文件）
  - config             默认配置加载与全局常量
  - debuglog           调试模式与日志输出
  - settings           用户设置加载 / 保存 / 旧版迁移
  - hashing            文件哈希计算
  - process            进程与外部命令操作
  - qtstyle            Qt 样式 / 主题 / 关键错误弹窗
  - shortcuts          开始菜单 / 桌面快捷方式
  - winversion         Windows 可执行文件版本信息
  - icc                ICC-CE URL 协议检测
  - ifeo               IFEO 劫持检测与清理
  - elevated           管理员权限执行 PowerShell
  - ps_scripts         启动脚本解析与安装/卸载/修复 PS1 生成
  - desktop_annotation 希沃批注安装状态管理
  - repair             修复流程（下载 / PNG 解码 / 静默重装）

本 __init__ 保留原有 ``from utils import X`` 用法的完整兼容门面。
"""
from .paths import (
    _is_win11,
    get_base_dir,
    get_data_dir,
    get_config_path,
    get_icon_path,
    get_shield_icon_path,
)
from .config import (
    _config,
    VERSION,
    DEFAULT_SETTINGS,
    SHORTCUT_NAME,
    ICC_PROTOCOL_KEY,
    ICC_COMMAND_KEY,
    ICC_STATUS_OK,
    ICC_STATUS_NO_PROTOCOL,
    ICC_STATUS_BROKEN,
    ICC_MIN_AUTO_PEN_VERSION,
    DESKTOP_ANNOTATION_DIR,
    DESKTOP_ANNOTATION_EXE,
    DESKTOP_ANNOTATION_BACKUP,
    DESKTOP_ANNOTATION_BAT,
    _DA_LOG_FILE,
    _DA_ORIGINAL_PREFIX,
    _DA_BACKUP_PREFIX,
    _LEN_DA_PREFIX,
    _LEN_DA_BACKUP_PREFIX,
    IFEO_BASE_KEY,
    APPS_EXE_SHA256,
    REPAIR_EXE_PNG_URL,
    REPAIR_URL_MAP,
    INSTALL_STATUS_INSTALLED,
    INSTALL_STATUS_NOT_INSTALLED,
    INSTALL_STATUS_CORRUPTED,
    LOCAL_APPS_EXE,
)
from .debuglog import (
    set_debug_mode,
    _is_debug,
    _debug_log,
    _log,
)
from .settings import (
    _deep_merge,
    load_settings,
    save_settings,
)
from .hashing import sha256_file
from .process import run_protocol, kill_process_by_path
from .qtstyle import apply_style, apply_theme, _critical
from .shortcuts import (
    START_MENU_LNK,
    DESKTOP_LNK,
    shortcut_exists,
    create_shortcut,
    delete_shortcut,
)
from .winversion import get_file_version, _parse_version_tuple
from .icc import (
    check_icc_ce_url_protocol,
    get_icc_ce_exe_path,
    _icc_auto_pen_available,
)
from .ifeo import check_ifeo_hijack, remove_ifeo_hijacks_async
from .elevated import _run_elevated
from .ps_scripts import (
    _get_entry_command,
    _parse_bat_entry,
    _split_command_paths,
    _build_install_ps1,
    _build_uninstall_ps1,
    _build_repair_ps1,
)
from .desktop_annotation import (
    _scan_original_da_files,
    _scan_backup_da_files,
    _find_primary_exe,
    get_desktop_annotation_version,
    get_install_diagnostics,
    install,
    uninstall,
    get_install_status,
)
from .repair import (
    _decode_png_to_file,
    _download,
    _download_with_fallback,
    get_repair_urls_for_version,
    repair,
)
