@echo off
REM =====================================================================
REM 分布式 AI 评测平台 - GitHub 部署脚本
REM 使用方法: 双击运行此脚本，或在终端执行
REM =====================================================================

echo.
echo ============================================
echo   分布式 AI 评测平台 - GitHub 部署工具
echo ============================================
echo.

REM 检查 Git 是否安装
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Git 未安装，请先安装 Git
    echo 下载地址: https://git-scm.com/download/win
    pause
    exit /b 1
)

REM 检查是否为 Git 仓库
if not exist ".git" (
    echo [步骤 1] 初始化 Git 仓库...
    git init
    git add .
    git commit -m "Initial commit: 分布式 AI 评测平台 v1.0"
    echo [完成] Git 仓库初始化完成
) else (
    echo [跳过] Git 仓库已初始化
)

echo.
echo ============================================
echo   下一步操作说明
echo ============================================
echo.
echo 1. 在 GitHub 上创建新仓库:
echo    访问: https://github.com/new
echo    - Repository name: ai-eval-platform
echo    - Description: 分布式 AI 评测平台
echo    - 选择 Private 或 Public
echo    - 不要勾选 Add a README
echo.
echo 2. 复制仓库 URL，然后运行:
echo.
echo    git remote add origin https://github.com/你的用户名/ai-eval-platform.git
echo    git branch -M main
echo    git push -u origin main
echo.
echo ============================================
echo.
echo 如果需要一键推送，请提供你的 GitHub 用户名和仓库名
echo 我将自动完成远程仓库配置和推送
echo.

pause
