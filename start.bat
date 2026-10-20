@echo off
chcp 65001 >nul
title FeiyunMY-Bot 启动器
color 0A

:: ============================================
:: FeiyunMY-Bot 一键启动脚本
:: 前台模式 - 自动检查依赖并显示日志
:: ============================================

cd /d "F:\FeiyunMY-Bot"

echo ╔══════════════════════════════════════════╗
echo ║          FeiyunMY-Bot 启动器             ║
echo ║          版本 1.0.0                     ║
echo ╚══════════════════════════════════════════╝
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set pyver=%%i
echo [OK] Python %pyver%

:: 检查并安装依赖
echo [..] 检查依赖...
pip show -q fastapi 2>nul
if %errorlevel% neq 0 (
    echo [..] 首次启动，正在安装依赖...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [FAIL] 依赖安装失败，请检查网络后重试
        pause
        exit /b 1
    )
    echo [OK] 依赖安装完成
) else (
    echo [OK] 依赖已就绪
)

:: 检查 python-multipart（可能不在旧版 requirements 中）
pip show -q python-multipart 2>nul
if %errorlevel% neq 0 (
    echo [..] 安装 python-multipart（文件上传支持）...
    pip install python-multipart
)

:: 检查 API Key
findstr /C:"api_key: ''" config.yaml >nul
if %errorlevel% equ 0 (
    findstr /C:"api_key: \"\"" config.yaml >nul
)
if %errorlevel% equ 0 (
    echo.
    echo [!!] 提示: config.yaml 中的 API Key 尚未配置
    echo      请先编辑 config.yaml 填入你的 API Key
    echo.
)

:: 打印访问地址
echo.
echo ============================================
echo  服务启动后请访问:
echo.
echo  管理面板:  http://localhost:8765/admin  ✨ 全新暗红色主题！
echo  API 文档:  http://localhost:8765/docs
echo  Chat 页面:  http://localhost:8765/admin/#/chat
echo.
echo  按 Ctrl+C 停止服务
echo ============================================
echo.

:: 启动服务
python main.py

:: 服务退出后
echo.
echo [..] 服务已停止
pause
