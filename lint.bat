@echo off
chcp 65001 >nul
title FeiyunMY-Bot 代码检查
color 0E

:: ============================================
:: ruff 静态检查
::   直接双击：检查全部规则，列出问题
::   带参数：  lint.bat --fix        自动修复可修项
::             lint.bat --statistics 只看统计
:: ============================================

cd /d "%~dp0"

if exist ".venv\Scripts\ruff.exe" (
    set "RUFF=.venv\Scripts\ruff.exe"
) else (
    set "RUFF=ruff"
)

if not exist ".venv\Scripts\ruff.exe" (
    if not exist "%RUFF%" (
        echo [FAIL] 未找到 ruff，请先运行 setup_venv.bat 或 pip install ruff
        pause
        exit /b 1
    )
)

echo [..] 检查中...
echo.
%RUFF% check . %*
set "RC=%errorlevel%"
echo.
if "%RC%"=="0" (
    echo [OK] 未发现问题
) else (
    echo [!!] 发现问题，退出码 %RC%
)
echo.
pause >nul
