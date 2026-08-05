@echo off
setlocal

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 请求管理员权限...
    PowerShell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "REG_KEY=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\DesktopAnnotation.exe"
reg query "%REG_KEY%" >nul 2>&1
if %errorlevel% neq 0 (
    echo  "%REG_KEY%" 不存在。
    pause
    exit /b
)

reg delete "%REG_KEY%" /f
if %errorlevel% equ 0 (
    echo 已删除劫持项：
) else (
    echo 删除注册表项失败，请手动删除！(%errorlevel%)
    pause
    exit /b %errorlevel%
)

pause