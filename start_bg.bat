@echo off
chcp 65001 >nul
title FeiyunMY-Bot 后台服务
color 0A

:: ============================================
:: FeiyunMY-Bot 后台静默启动
:: 自动检查依赖，不显示日志窗口
:: ============================================

cd /d "F:\FeiyunMY-Bot"

:: 检查是否已在运行
tasklist /fi "ImageName eq python.exe" /v 2>nul | findstr "main.py" >nul
if %errorlevel% equ 0 (
    echo [!!] FeiyunMY-Bot 似乎已在运行
    echo      请先运行 stop.bat 停止后再启动
    pause
    exit /b 1
)

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未检测到 Python
    pause
    exit /b 1
)

:: 检查并安装依赖
pip show -q fastapi 2>nul
if %errorlevel% neq 0 (
    echo [..] 正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [FAIL] 依赖安装失败
        pause
        exit /b 1
    )
    echo [OK] 依赖安装完成
)

:: 检查 python-multipart
pip show -q python-multipart 2>nul
if %errorlevel% neq 0 (
    pip install python-multipart >nul 2>&1
)

echo [..] 正在后台启动 FeiyunMY-Bot...

:: 后台启动服务
start /min /b "" python main.py > data\logs\server.log 2>&1

:: 等待几秒检查是否启动成功
timeout /t 3 /nobreak >nul

tasklist /fi "ImageName eq python.exe" /v 2>nul | findstr "main.py" >nul
if %errorlevel% equ 0 (
    echo.
    echo [OK] 服务已后台启动!
    echo.
    echo ============================================
    echo  管理面板:  http://localhost:8765/admin  ✨ 全新暗红色主题！
    echo  API 文档:  http://localhost:8765/docs
    echo  Chat 页面:  http://localhost:8765/admin/#/chat
    echo.
    echo  日志文件:  data\logs\server.log
    echo  停止服务:  双击 stop.bat
    echo ============================================
    echo.
    start http://localhost:8765/admin
) else (
    echo [FAIL] 服务启动失败，请检查日志
)

echo 按任意键关闭本窗口（服务仍在后台运行）
pause >nul
