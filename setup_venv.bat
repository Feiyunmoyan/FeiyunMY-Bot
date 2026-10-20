@echo off
chcp 65001 >nul
title FeiyunMY-Bot 环境初始化
color 0B

:: ============================================
:: 创建项目独立虚拟环境并安装依赖
:: 只需运行一次；之后 start.bat 会自动使用 .venv
:: ============================================

cd /d "F:\FeiyunMY-Bot"

echo ============================================
echo  FeiyunMY-Bot 环境初始化
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
    echo [i] 已存在 .venv，将直接复用
) else (
    echo [..] 正在创建虚拟环境 .venv ...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [FAIL] 虚拟环境创建失败，请确认已安装 Python 3.10+
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建
)

echo.
echo [..] 升级 pip ...
.venv\Scripts\python.exe -m pip install --upgrade pip

echo.
echo [..] 安装依赖（首次较慢，含 torch / chromadb，请耐心等待）...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [FAIL] 依赖安装失败，请检查网络后重试
    pause
    exit /b 1
)

echo.
echo [..] 冻结精确版本到 requirements.lock.txt ...
.venv\Scripts\python.exe -m pip freeze > requirements.lock.txt
echo [OK] 已生成 requirements.lock.txt

echo.
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [!!] 已从 .env.example 生成 .env，请编辑填入 API Key
    )
)

echo.
echo ============================================
echo  初始化完成
echo  下一步: 编辑 .env 填入 API Key，然后运行 start.bat
echo ============================================
echo.
pause
