@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
title FeiyunMY-Bot 一体启动器
color 0B

rem ============================================================
rem  FeiyunMY-Bot 一体化启动脚本（替代 setup_venv / start / start_bg / stop / lint）
rem
rem  [1/5] 环境自检   虚拟环境 / 依赖 / 配置 / 密钥
rem  [2/5] 代码完整性 关键文件 / 语法编译 / ruff 静态检查
rem  [3/5] 端口与残留 清理本项目残留进程，检查 8765 占用
rem  [4/5] 前台启动   日志直接显示在本窗口
rem  [5/5] 收尾清理   退出后自动结束残留进程
rem
rem  用法: 双击运行
rem        FeiyunMY-Bot.bat --fast   跳过代码完整性检查，快速启动
rem ============================================================

cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "PY=%ROOT%\.venv\Scripts\python.exe"
set "PORT=8765"
set "FAST=0"
if /i "%~1"=="--fast" set "FAST=1"




echo ============================================================
echo                 FeiyunMY-Bot 一体启动器
echo ============================================================
echo   项目目录: %ROOT%
echo   服务端口: %PORT%
echo ============================================================
echo.

rem ---------- [1/5] 环境自检 ----------
echo [1/5] 环境自检
echo ------------------------------------------------------------

if not exist "%PY%" (
    echo [..] 未发现 .venv，开始创建虚拟环境...
    set "BASEPY="
    for /f "delims=" %%p in ('where python 2^>nul') do if not defined BASEPY set "BASEPY=%%p"
    if not defined BASEPY (
        echo [FAIL] 系统中找不到 python，请先安装 Python 3.10+ 并加入 PATH
        goto :abort
    )
    call :check_pyver "!BASEPY!" || goto :abort
    "!BASEPY!" -m venv "%ROOT%\.venv"
    if not exist "%PY%" (
        echo [FAIL] 虚拟环境创建失败
        goto :abort
    )
    echo [OK] 虚拟环境已创建
    echo [..] 安装依赖（首次较慢，含 torch / chromadb，请耐心等待）...
    "%PY%" -m pip install --upgrade pip --quiet
    "%PY%" -m pip install -r "%ROOT%\requirements.txt"
    if errorlevel 1 (
        echo [FAIL] 依赖安装失败，请检查网络后重试
        goto :abort
    )
    "%PY%" -m pip freeze > "%ROOT%\requirements.lock.txt"
    echo [OK] 依赖已安装
) else (
    echo [OK] 虚拟环境: %PY%
    call :check_pyver "%PY%" || goto :abort
    "%PY%" -m pip show -q fastapi >nul 2>&1
    if errorlevel 1 (
        echo [..] 检测到 fastapi 缺失，正在补装依赖...
        "%PY%" -m pip install -r "%ROOT%\requirements.txt"
        if errorlevel 1 (
            echo [FAIL] 依赖安装失败，请检查网络后重试
            goto :abort
        )
        echo [OK] 依赖已安装
    )
)

"%PY%" -m pip show -q python-multipart >nul 2>&1
if errorlevel 1 (
    echo [..] 补装 python-multipart（文件上传支持）...
    "%PY%" -m pip install python-multipart >nul 2>&1
)
echo [OK] 依赖检查完成

if not exist "%ROOT%\config.yaml" (
    if exist "%ROOT%\config.example.yaml" (
        copy /y "%ROOT%\config.example.yaml" "%ROOT%\config.yaml" >nul
        echo [WARN] 已从模板生成 config.yaml，请按需修改
    ) else (
        echo [FAIL] 缺少 config.yaml 且找不到模板 config.example.yaml
        goto :abort
    )
)
echo [OK] 配置文件 config.yaml

if not exist "%ROOT%\.env" (
    if exist "%ROOT%\.env.example" (
        copy /y "%ROOT%\.env.example" "%ROOT%\.env" >nul
        echo [WARN] 已从模板生成 .env
    )
)

set "NOKEY=1"
if exist "%ROOT%\.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%ROOT%\.env") do (
        if /i "%%a"=="FEIYUN_API_KEY" if not "%%b"=="" set "NOKEY=0"
    )
)
if "!NOKEY!"=="1" (
    echo [WARN] 警告: .env 中 FEIYUN_API_KEY 为空，模型调用会失败
    echo      文件: %ROOT%\.env
) else (
    echo [OK] API 密钥已配置
)

rem ---------- [2/5] 代码完整性 ----------
echo.
if "%FAST%"=="1" (
    echo [2/5] 代码完整性 —— 已通过 --fast 跳过
    goto :port_check
)
echo [2/5] 代码完整性检查
echo ------------------------------------------------------------

set "MISSING="
for %%f in (main.py api agent active_engine memory provider tools utils db persona workspace knowledge skills webui\dist\index.html) do (
    if not exist "%ROOT%\%%f" set "MISSING=!MISSING! %%f"
)
if not "!MISSING!"=="" (
    echo [FAIL] 缺少关键文件或目录:!MISSING!
    echo        项目可能不完整，请检查后重试
    goto :abort
)
echo [OK] 关键文件与目录齐全

set "PYTARGETS=main.py"
for %%d in (api agent active_engine memory provider tools utils db persona workspace knowledge skills) do (
    if exist "%ROOT%\%%d" set "PYTARGETS=!PYTARGETS! %%d"
)
pushd "%ROOT%"
"%PY%" -m compileall -q !PYTARGETS! >nul 2>&1
if errorlevel 1 (
    echo [FAIL] 语法编译未通过，错误详情:
    "%PY%" -m compileall -q !PYTARGETS!
    popd
    goto :abort
)
echo [OK] 语法编译通过

"%PY%" -m ruff --version >nul 2>&1
if errorlevel 1 (
    echo [i] 未安装 ruff，跳过静态检查
) else (
    "%PY%" -m ruff check . > "%TEMP%\feiyun_lint.txt" 2>&1
    set "LINTRC=!errorlevel!"
    if "!LINTRC!"=="0" (
        echo [OK] ruff 静态检查通过
    ) else (
        set "LINTMSG=详见报告文件"
        for /f "tokens=*" %%l in ('findstr /r /c:"[0-9] error" "%TEMP%\feiyun_lint.txt"') do set "LINTMSG=%%l"
        echo [WARN] ruff 发现问题（不阻断启动）: !LINTMSG!
        echo      报告: %TEMP%\feiyun_lint.txt
    )
)
popd

rem ---------- [3/5] 端口与残留进程 ----------
:port_check
echo.
echo [3/5] 端口 %PORT% 与残留进程
echo ------------------------------------------------------------

set "PIDFILE=%TEMP%\feiyun_pids.txt"
set "NETFILE=%TEMP%\feiyun_netstat.txt"
call :list_own_pids
set "STALE=0"
for /f %%p in ('type "%PIDFILE%" 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
    if not errorlevel 1 set /a STALE+=1
)
if !STALE! GTR 0 (
    echo [OK] 已清理上次残留进程 !STALE! 个
) else (
    echo [OK] 无本项目残留进程
)

set "HOLDER="
netstat -ano > "%NETFILE%" 2>nul
for /f "tokens=4,5" %%a in ('findstr /c:":%PORT% " "%NETFILE%"') do (
    if /i "%%a"=="LISTENING" if not "%%b"=="0" set "HOLDER=%%b"
)
if not "!HOLDER!"=="" (
    echo [WARN] 端口 %PORT% 已被占用，占用进程 PID !HOLDER!
    powershell -NoProfile -Command "Get-Process -Id !HOLDER! -ErrorAction SilentlyContinue | ForEach-Object { '     占用者: ' + $_.ProcessName + ' (PID ' + $_.Id + ')' }" 2>nul
    set "ANS="
    set /p "ANS=     结束该进程并继续启动? [Y=结束 / N=退出] "
    if /i not "!ANS!"=="y" (
        echo [i] 已取消启动
        goto :abort
    )
    taskkill /f /pid !HOLDER! >nul 2>&1
    ping -n 2 127.0.0.1 >nul
    echo [OK] 占用已释放
) else (
    echo [OK] 端口 %PORT% 可用
)

rem ---------- [4/5] 前台启动 ----------
echo.
echo [4/5] 启动服务
echo ------------------------------------------------------------
echo   管理面板: http://localhost:%PORT%/admin
echo   API 文档: http://localhost:%PORT%/docs
echo   Chat 页面: http://localhost:%PORT%/admin/#/chat

echo   停止服务: 本窗口按 Ctrl+C
echo             若出现「终止批处理操作吗(Y/N)?」提示，请选 N，
echo             脚本会继续执行收尾清理
echo ------------------------------------------------------------
echo.

pushd "%ROOT%"
"%PY%" main.py
set "EXITCODE=!errorlevel!"
popd

echo.
echo [i] 服务已退出，返回码 !EXITCODE!

rem ---------- [5/5] 收尾清理 ----------
echo.
echo [5/5] 收尾清理
echo ------------------------------------------------------------
set "KILLED=0"
call :list_own_pids
for /f %%p in ('type "%PIDFILE%" 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
    if not errorlevel 1 (
        echo [OK] 已结束残留进程 PID %%p
        set /a KILLED+=1
    )
)
if !KILLED! EQU 0 echo [OK] 无需清理
for /f "tokens=4,5" %%a in ('findstr /c:":%PORT% " "%NETFILE%"') do (
    if /i "%%a"=="LISTENING" if not "%%b"=="0" taskkill /f /pid %%b >nul 2>&1
)

echo.
echo ============================================================
echo   已完成。按任意键关闭窗口
echo ============================================================
pause >nul
exit /b 0

rem ---- 子过程：校验 Python 版本 >= 3.10 ----
rem   参数: %~1 = 解释器完整路径
:check_pyver
set "CHKP=%~1"
if not exist "!CHKP!" (
    echo [FAIL] Python 解释器不存在: !CHKP!
    exit /b 1
)
set "VFILE=%TEMP%\feiyun_pyver.txt"
"!CHKP!" -c "import sys;print('%%d.%%d.%%d'%%sys.version_info[:3])" > "!VFILE!" 2>nul
if errorlevel 1 (
    echo [FAIL] 无法获取 Python 版本: !CHKP!
    exit /b 1
)
set "PYVER="
set /p PYVER=<"!VFILE!"
set "PYMAJ="
set "PYMIN="
for /f "tokens=1,2 delims=." %%a in ("!PYVER!") do (
    set "PYMAJ=%%a"
    set "PYMIN=%%b"
)
if not defined PYMAJ (
    echo [FAIL] 无法解析 Python 版本: !PYVER!
    exit /b 1
)
if !PYMAJ! LSS 3 (
    echo [FAIL] 需要 Python 3.10 或更高，当前 !PYVER!
    exit /b 1
)
if !PYMAJ! EQU 3 if !PYMIN! LSS 10 (
    echo [FAIL] 需要 Python 3.10 或更高，当前 !PYVER!
    exit /b 1
)
echo [OK] Python !PYVER!（要求 3.10 及以上）
exit /b 0

rem ---- 子过程：把"属于本项目虚拟环境"的 python 进程号写入 %PIDFILE% ----
rem   venv 里的 python.exe 是重定向器，杀掉外层壳时其内层解释器与子进程会随 Job 一并结束。
rem   这里只用单引号，避免 bat 内嵌套双引号导致的解析问题。
:list_own_pids
powershell -NoProfile -Command "Get-Process -Name python,pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '%ROOT%\.venv\*' } | ForEach-Object { $_.Id }" > "%PIDFILE%" 2>nul
exit /b 0

:abort
echo.
echo ============================================================
echo   启动中止，请按上面提示处理后重试
echo ============================================================
pause >nul
exit /b 1
