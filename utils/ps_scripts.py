"""启动脚本（.bat）解析与安装/卸载/修复用管理员 PowerShell 脚本生成。"""
import os
import sys

from .config import (
    DESKTOP_ANNOTATION_DIR,
    DESKTOP_ANNOTATION_EXE,
    DESKTOP_ANNOTATION_BAT,
    _DA_LOG_FILE,
    _DA_ORIGINAL_PREFIX,
    _DA_BACKUP_PREFIX,
    _LEN_DA_PREFIX,
    _LEN_DA_BACKUP_PREFIX,
    LOCAL_APPS_EXE,
)
from .paths import get_base_dir


def _get_entry_command():
    """返回写进启动脚本（.bat）的命令字符串（供希沃调用，应直接启动批注软件）。

    返回值是 cmd.exe 可直接执行的命令行：
    - 打包模式：``"C:\\...\\Annotation.exe" -run_annotation_app``
    - 源码模式：``"C:\\...\\pythonw.exe" "D:\\...\\main.py" -run_annotation_app``
    """
    base = get_base_dir()
    if getattr(sys, "frozen", False):
        exe = os.path.join(base, "Annotation.exe")
        return f'"{exe}" -run_annotation_app'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    main_py = os.path.join(base, "main.py")
    return f'@echo off \n"{pythonw}" "{main_py}" -run_annotation_app\nexit /b'


def _parse_bat_entry(bat_path):
    """从启动脚本（.bat）中提取入口命令的所有路径段。找不到返回空列表。

    首行形如 ``"C:\\...\\Annotation.exe" -run_annotation_app``（被 ``@echo off`` / ``rem`` 头跳过后）。

    典型输出：
      打包模式：["C:\\...\\Annotation.exe"]
      源码模式：["C:\\...\\pythonw.exe", "D:\\...\\main.py"]
    """
    if not os.path.exists(bat_path):
        return []
    # 以 UTF-8 解码；失败则回退到 mbcs（Windows ANSI）
    content = None
    for encoding in ("utf-8", "mbcs"):
        try:
            with open(bat_path, "r", encoding=encoding, errors="ignore") as f:
                content = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if content is None:
        return []
    first_line = None
    for line in content.splitlines():
        line = line.strip()
        # 跳过空行、bat 头、rem 注释
        if not line or line.startswith("@") or line.startswith("rem"):
            continue
        first_line = line
        break
    if not first_line:
        return []
    return _split_command_paths(first_line)


def _split_command_paths(cmd):
    """从命令字符串中提取所有被引号包围或空格分隔的路径参数（过滤 -flag 形式的非路径 token）。
    """
    paths = []
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if c in (' ', '\t'):
            i += 1
            continue
        if c == '"':
            end = cmd.find('"', i + 1)
            if end == -1:
                break
            paths.append(cmd[i + 1:end])
            i = end + 1
        else:
            j = i
            while j < n and cmd[j] not in (' ', '\t'):
                j += 1
            token = cmd[i:j]
            # 跳过 -flag 形式的参数
            if not token.startswith('-'):
                paths.append(token)
            i = j
    return paths


def _build_install_ps1():
    """生成安装阶段的临时 PowerShell 5.1 脚本（需管理员权限运行）。

    遍历目标目录中所有以 DesktopAnnotation 开头但不以 Backup 结尾的文件，
    将 "DesktopAnnotation" 前缀替换为 "DesktopAnnotationBackup" 完成批量备份。

    采用 PowerShell 5.1 兼容语法：
      - $ErrorActionPreference = 'Stop' 实现错误即退出
      - Get-ChildItem -File 枚举文件（自动跳过目录）
      - -like 前缀通配 + Substring 实现前缀切片（防止 BackupBackup）
      - try/catch 包裹关键操作以采集异常并写入日志
      - 不包含任何 pause / Read-Host 等调试暂停调用
    """
    entry = _get_entry_command()
    len_prefix = _LEN_DA_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LOCAL_EXE     = '{LOCAL_APPS_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    exit 1
}}

Write-Log "[INSTALL] [START] target=$TARGET_DIR"

# --- 1. 杀掉目标目录下所有 exe 进程 ---
Write-Log "[KILL] [START] enumerate exes"
Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    Write-Log "[KILL] [OK] $($_.Name)"
    try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
}}

# --- 2. 批量重命名 PREFIX* -> BACKUP_PREFIX* ---
#  使用 -like 前缀检测（避免硬编码长度）；NEWNAME 通过 Substring 前缀切片，
#  不会对已有 BACKUP_PREFIX 再套一层（BackupBackup 问题）
Write-Log "[RENAME] [START] enumerate ${{PREFIX}}*"
$renameCount = 0
Get-ChildItem -Path "$TARGET_DIR\\${{PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    $name = $_.Name
    if ($name -like "$BACKUP_PREFIX*") {{
        Write-Log "[RENAME] [SKIP] $name already backed up"
        return
    }}
    $newName = $BACKUP_PREFIX + $name.Substring($LEN_PREFIX)
    $newPath = Join-Path $TARGET_DIR $newName
    if (Test-Path -LiteralPath $newPath) {{
        try {{
            Remove-Item -LiteralPath $newPath -Force
            Write-Log "[RENAME] [INFO] deleted old backup $newName"
        }} catch {{
            Write-Log "[RENAME] [FAILED] del old backup $newName"
            Fail 'FAILED_DEL_OLD_BACKUP'
        }}
    }}
    try {{
        Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
    }} catch {{
        Write-Log "[RENAME] [FAILED] $name -> $newName"
        Fail 'FAILED_RENAME'
    }}
    if (-not (Test-Path -LiteralPath $newPath)) {{
        Write-Log "[RENAME] [VERIFY_FAILED] $newName missing after rename"
        Fail 'FAILED_RENAME_VERIFY'
    }}
    $renameCount++
    Write-Log "[RENAME] [OK] $name -> $newName"
}}
Write-Log "[RENAME] [DONE] count=$renameCount"

# --- 3. 复制替换 exe ---
Write-Log "[COPY] [START] $LOCAL_EXE -> $ORIG_EXE"
try {{
    Copy-Item -LiteralPath $LOCAL_EXE -Destination $ORIG_EXE -Force
}} catch {{
    Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
    Fail 'FAILED_COPY'
}}
if (-not (Test-Path -LiteralPath $ORIG_EXE)) {{
    Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
    Fail 'FAILED_COPY'
}}
Write-Log "[COPY] [OK] $LOCAL_EXE -> $ORIG_EXE"

# --- 4. 写入启动脚本 (.bat) ---
Write-Log "[WRITE] [START] $LAUNCHER_FILE"
try {{
    Set-Content -LiteralPath $LAUNCHER_FILE -Value @'
{entry}
'@ -Encoding ASCII
}} catch {{
    Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
    Fail 'FAILED_WRITE_LAUNCHER'
}}
if (-not (Test-Path -LiteralPath $LAUNCHER_FILE)) {{
    Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
    Fail 'FAILED_WRITE_LAUNCHER'
}}
Write-Log "[WRITE] [OK] $LAUNCHER_FILE"

Write-Log "[INSTALL] [DONE]"
exit 0
"""


def _build_uninstall_ps1():
    """生成卸载阶段的临时 PowerShell 5.1 脚本（需管理员权限运行）。

    遍历目标目录中所有以 DesktopAnnotationBackup 开头的文件，
    将 "DesktopAnnotationBackup" 前缀还原为 "DesktopAnnotation"。

    采用 PowerShell 5.1 兼容语法 + 内联函数 Strip-BackupPrefixes
    循环剥离重复前缀，最多 10 轮，可修复历史 BackupBackup 嵌套命名。
    """
    len_prefix = _LEN_DA_PREFIX
    len_backup_prefix = _LEN_DA_BACKUP_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}
$LEN_BACKUP_PREFIX = {len_backup_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    exit 1
}}

function Strip-BackupPrefixes([string]$name) {{
    # 循环剥离所有重复的 BACKUP_PREFIX 前缀，再拼接 PREFIX 得到原始文件名
    $n = $name
    while ($n.StartsWith($BACKUP_PREFIX)) {{
        $n = $n.Substring($LEN_BACKUP_PREFIX)
    }}
    return $PREFIX + $n
}}

Write-Log "[UNINSTALL] [START] target=$TARGET_DIR"

# --- 1. 杀掉所有 Backup 相关进程 ---
Write-Log "[KILL] [START] enumerate backup exes"
Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
    Write-Log "[KILL] [OK] $($_.Name)"
    try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
}}

# --- 2. 检查是否有备份文件 ---
$hasBackup = $false
if ((Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*" -File -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {{
    $hasBackup = $true
}}
if (-not $hasBackup) {{
    Write-Log "[CHECK] [INFO] no backup files found, nothing to restore"
    Write-Log "[UNINSTALL] [DONE]"
    exit 0
}}
Write-Log "[CHECK] [OK] backup files exist"

# --- 3. 删除我们替换的 exe ---
if (Test-Path -LiteralPath $ORIG_EXE) {{
    Write-Log "[DELETE] [START] $ORIG_EXE"
    try {{
        Remove-Item -LiteralPath $ORIG_EXE -Force
    }} catch {{
        Write-Log "[DELETE] [FAILED] $ORIG_EXE"
        Fail 'FAILED_DEL_ORIG'
    }}
    if (Test-Path -LiteralPath $ORIG_EXE) {{
        Write-Log "[DELETE] [FAILED] $ORIG_EXE"
        Fail 'FAILED_DEL_ORIG'
    }}
    Write-Log "[DELETE] [OK] $ORIG_EXE"
}} else {{
    Write-Log "[DELETE] [SKIP] $ORIG_EXE not found"
}}

# --- 4. 批量还原 BACKUP_PREFIX* -> PREFIX* ---
#  循环扫描最多 10 遍，每一轮对 BACKUP_PREFIX* 文件进行还原；
#  通过 Strip-BackupPrefixes 子例程剥离重复前缀，可修复 BackupBackup
#  / BackupBackupBackup 等多层嵌套命名问题；某一轮没有处理任何文件时退出
Write-Log "[RESTORE] [START] enumerate ${{BACKUP_PREFIX}}*"
$restoreCount = 0
$pass = 0
while ($pass -lt 10) {{
    $pass++
    $passHandled = 0
    Get-ChildItem -Path "$TARGET_DIR\\${{BACKUP_PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        $name = $_.Name
        $newName = Strip-BackupPrefixes $name
        $newPath = Join-Path $TARGET_DIR $newName
        Write-Log "[RESTORE] [PASS=$pass] $name -> $newName"
        try {{
            Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
        }} catch {{
            Write-Log "[RESTORE] [FAILED] $name -> $newName"
            Fail 'FAILED_RESTORE'
        }}
        if (-not (Test-Path -LiteralPath $newPath)) {{
            Write-Log "[RESTORE] [VERIFY_FAILED] $newName missing after restore"
            Fail 'FAILED_RESTORE_VERIFY'
        }}
        $restoreCount++
        $passHandled++
        Write-Log "[RESTORE] [OK] $name -> $newName"
    }}
    if ($passHandled -eq 0) {{ break }}
}}
Write-Log "[RESTORE] [DONE] count=$restoreCount passes=$pass"

# --- 5. 清理启动脚本 (.bat) ---
if (Test-Path -LiteralPath $LAUNCHER_FILE) {{
    Write-Log "[DELETE] [START] $LAUNCHER_FILE"
    try {{
        Remove-Item -LiteralPath $LAUNCHER_FILE -Force
    }} catch {{
        Write-Log "[DELETE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_DEL_LAUNCHER'
    }}
    if (Test-Path -LiteralPath $LAUNCHER_FILE) {{
        Write-Log "[DELETE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_DEL_LAUNCHER'
    }}
    Write-Log "[DELETE] [OK] $LAUNCHER_FILE"
}} else {{
    Write-Log "[DELETE] [SKIP] $LAUNCHER_FILE not found"
}}

Write-Log "[UNINSTALL] [DONE]"
exit 0
"""


def _build_repair_ps1(installer_exe, cleanup_dir):
    """生成修复流程的管理员 PowerShell 5.1 脚本：清理 → 运行原始安装包 → 批量备份 → 替换 → 写启动脚本。

    全程使用 PowerShell 5.1 兼容语法，所有错误退出路径统一 goto :cleanup
    （在 PowerShell 中通过 try/catch + finally 块实现等价语义）。
    """
    entry = _get_entry_command()
    len_prefix = _LEN_DA_PREFIX
    return f"""#Requires -version 5.1
$ErrorActionPreference = 'Stop'

$TARGET_DIR    = '{DESKTOP_ANNOTATION_DIR}'
$ORIG_EXE      = '{DESKTOP_ANNOTATION_EXE}'
$LOCAL_EXE     = '{LOCAL_APPS_EXE}'
$LAUNCHER_FILE = '{DESKTOP_ANNOTATION_BAT}'
$INSTALLER     = '{installer_exe}'
$CLEANUP_DIR   = '{cleanup_dir}'
$LOG_FILE      = '{_DA_LOG_FILE}'
$PREFIX        = '{_DA_ORIGINAL_PREFIX}'
$BACKUP_PREFIX = '{_DA_BACKUP_PREFIX}'
$LEN_PREFIX    = {len_prefix}

function Write-Log([string]$msg) {{
    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path $LOG_FILE -Value "[$ts] $msg"
}}

function Fail([string]$code) {{
    Write-Output $code
    Invoke-Cleanup
    exit 1
}}

function Invoke-Cleanup {{
    if ($CLEANUP_DIR -and (Test-Path -LiteralPath $CLEANUP_DIR)) {{
        try {{ Remove-Item -LiteralPath $CLEANUP_DIR -Recurse -Force -ErrorAction SilentlyContinue }} catch {{ }}
        Write-Log "[CLEANUP] [INFO] removed $CLEANUP_DIR"
    }}
}}

Write-Log "[REPAIR] [START] target=$TARGET_DIR installer=$INSTALLER"

try {{
    # --- 1. 杀掉目标目录下所有 exe 进程 ---
    Write-Log "[KILL] [START] enumerate exes"
    Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Log "[KILL] [OK] $($_.Name)"
        try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
    }}

    # --- 2. 清理目标目录 ---
    $uninstaller = Join-Path $TARGET_DIR 'Uninstall.exe'
    if (Test-Path -LiteralPath $uninstaller) {{
        Write-Log "[CLEAN] [START] run Uninstall.exe /S"
        $proc = Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru
        Write-Log "[CLEAN] [OK] Uninstall.exe exit=$($proc.ExitCode)"
    }} else {{
        Write-Log "[CLEAN] [START] rd /s /q $TARGET_DIR"
        try {{ Remove-Item -LiteralPath $TARGET_DIR -Recurse -Force }} catch {{ }}
        Write-Log "[CLEAN] [OK] rd done"
    }}

    # --- 3. 运行全新安装包（静默） ---
    Write-Log "[INSTALLER] [START] $INSTALLER /S"
    $proc = Start-Process -FilePath $INSTALLER -ArgumentList '/S' -Wait -PassThru
    if ($proc.ExitCode -ne 0) {{
        Write-Log "[INSTALLER] [FAILED] exit=$($proc.ExitCode)"
        Fail 'INSTALLER_FAILED'
    }}
    Write-Log "[INSTALLER] [OK] exit=$($proc.ExitCode)"

    if (-not (Test-Path -LiteralPath $TARGET_DIR)) {{
        Write-Log "[CHECK] [FAILED] target dir missing after installer"
        Fail 'TARGET_DIR_MISSING'
    }}
    Write-Log "[CHECK] [OK] target dir exists"

    # --- 4. 执行我们的标准安装（批量备份 + 替换）---
    Write-Log "[KILL] [START] enumerate exes after installer"
    Get-ChildItem -Path "$TARGET_DIR\\*.exe" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        Write-Log "[KILL] [OK] $($_.Name)"
        try {{ & taskkill /f /im $($_.Name) /t 2>&1 | Out-Null }} catch {{ }}
    }}

    # 批量重命名 PREFIX* -> BACKUP_PREFIX*  -like 前缀检测 + Substring 切片
    Write-Log "[RENAME] [START] enumerate ${{PREFIX}}*"
    $renameCount = 0
    Get-ChildItem -Path "$TARGET_DIR\\${{PREFIX}}*" -File -ErrorAction SilentlyContinue | ForEach-Object {{
        $name = $_.Name
        if ($name -like "$BACKUP_PREFIX*") {{
            Write-Log "[RENAME] [SKIP] $name already backed up"
            return
        }}
        $newName = $BACKUP_PREFIX + $name.Substring($LEN_PREFIX)
        $newPath = Join-Path $TARGET_DIR $newName
        if (Test-Path -LiteralPath $newPath) {{
            try {{
                Remove-Item -LiteralPath $newPath -Force
                Write-Log "[RENAME] [INFO] deleted old backup $newName"
            }} catch {{
                Write-Log "[RENAME] [FAILED] del old backup $newName"
                Fail 'FAILED_DEL_OLD_BACKUP'
            }}
        }}
        try {{
            Rename-Item -LiteralPath $_.FullName -NewName $newName -Force
        }} catch {{
            Write-Log "[RENAME] [FAILED] $name -> $newName"
            Fail 'FAILED_RENAME'
        }}
        if (-not (Test-Path -LiteralPath $newPath)) {{
            Write-Log "[RENAME] [VERIFY_FAILED] $newName missing after rename"
            Fail 'FAILED_RENAME_VERIFY'
        }}
        $renameCount++
        Write-Log "[RENAME] [OK] $name -> $newName"
    }}
    Write-Log "[RENAME] [DONE] count=$renameCount"

    Write-Log "[COPY] [START] $LOCAL_EXE -> $ORIG_EXE"
    try {{
        Copy-Item -LiteralPath $LOCAL_EXE -Destination $ORIG_EXE -Force
    }} catch {{
        Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
        Fail 'FAILED_COPY'
    }}
    if (-not (Test-Path -LiteralPath $ORIG_EXE)) {{
        Write-Log "[COPY] [FAILED] $LOCAL_EXE -> $ORIG_EXE"
        Fail 'FAILED_COPY'
    }}
    Write-Log "[COPY] [OK] $LOCAL_EXE -> $ORIG_EXE"

    Write-Log "[WRITE] [START] $LAUNCHER_FILE"
    try {{
        Set-Content -LiteralPath $LAUNCHER_FILE -Value @'
{entry}
'@ -Encoding ASCII
    }} catch {{
        Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_WRITE_LAUNCHER'
    }}
    if (-not (Test-Path -LiteralPath $LAUNCHER_FILE)) {{
        Write-Log "[WRITE] [FAILED] $LAUNCHER_FILE"
        Fail 'FAILED_WRITE_LAUNCHER'
    }}
    Write-Log "[WRITE] [OK] $LAUNCHER_FILE"

    Write-Log "[REPAIR] [DONE]"
}} finally {{
    Invoke-Cleanup
}}
exit 0
"""
