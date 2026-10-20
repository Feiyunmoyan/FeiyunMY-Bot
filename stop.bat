@echo off
chcp 65001 >nul
title FeiyunMY-Bot 停止脚本
color 0C

:: ============================================
:: FeiyunMY-Bot 停止服务
:: ============================================

cd /d "F:\FeiyunMY-Bot"

echo [*] 正在查找 FeiyunMY-Bot 进程...

:: 查找所有运行 main.py 的 python 进程
tasklist /fi "ImageName eq python.exe" /v 2>nul | findstr "main.py" >nul
if %errorlevel% equ 0 (
    echo [*] 找到运行中的服务，正在停止...
    
    :: 用 taskkill 终止，/f 强制，/t 终止子进程
    for /f "tokens=2 delims= " %%a in ('tasklist /fi "ImageName eq python.exe" /v ^| findstr "main.py"') do (
        taskkill /f /pid %%a >nul 2>&1
    )
    
    echo [✓] 服务已停止
) else (
    echo [i] 未检测到运行中的 FeiyunMY-Bot 服务
)

echo.
echo 按任意键关闭
pause >nul
