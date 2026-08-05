@echo off
setlocal enabledelayedexpansion

:: 检查管理员权限
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 请求管理员权限...
    PowerShell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "TARGET_EXE=%SCRIPT_DIR%\Annotation.exe"

if not exist "%TARGET_EXE%" (
    echo 未找到 "%TARGET_EXE%"！
    echo 请确保 Annotation.exe 与本脚本位于同一目录。
    pause
    exit /b 1
)

:: 设置映像劫持注册表项
set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
reg add "%REG_KEY%" /v Debugger /t REG_SZ /d "\"%TARGET_EXE%\"" /f
if %errorlevel% equ 0 (
    echo 已设置劫持项。
) else (
    echo 设置劫持项失败！(%errorlevel%)
    pause
    exit /b %errorlevel%
)

pause