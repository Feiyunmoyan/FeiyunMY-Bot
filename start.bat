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

:: 优先使用项目独立虚拟环境，避免依赖系统 / 其他项目的 Python
if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
    echo [OK] 使用项目虚拟环境 .venv
) else (
    set "PY=python"
    echo [!!] 未检测到 .venv，将使用系统 Python
    echo      建议运行 setup_venv.bat 创建独立环境
)
echo.

:: 检查 Python
%PY% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未检测到可用的 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('%PY% --version 2^>^&1') do set pyver=%%i
echo [OK] Python %pyver%

:: 检查并安装依赖
echo [..] 检查依赖...
%PY% -m pip show -q fastapi 2>nul
if %errorlevel% neq 0 (
    echo [..] 首次启动，正在安装依赖...
    %PY% -m pip install -r requirements.txt
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
%PY% -m pip show -q python-multipart 2>nul
if %errorlevel% neq 0 (
    echo [..] 安装 python-multipart（文件上传支持）...
    %PY% -m pip install python-multipart
)

:: 检查密钥配置（密钥已迁移到 .env，config.yaml 中应留空）
if not exist ".env" (
    echo.
    echo [!!] 提示: 未找到 .env 文件
    echo      请复制 .env.example 为 .env 并填入 API Key
    echo.
) else (
    findstr /B /C:"FEIYUN_API_KEY=" .env | findstr /R /C:"FEIYUN_API_KEY=..*" >nul
    if %errorlevel% neq 0 (
        echo.
        echo [!!] 提示: .env 中的 FEIYUN_API_KEY 尚未填写
        echo.
    )
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
echo  局域网 / 移动端访问需要访问令牌
echo  令牌文件:  data\access_token.txt
echo.
echo  按 Ctrl+C 停止服务
echo ============================================
echo.

:: 启动服务
%PY% main.py

:: 服务退出后
echo.
echo [..] 服务已停止
pause
