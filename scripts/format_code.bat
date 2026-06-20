@echo off
REM =====================================================================
REM AI Eval Platform - 代码格式化脚本 (Windows)
REM 一键格式化所有代码，确保符合代码规范
REM =====================================================================

echo ========================================
echo AI Eval Platform - 代码格式化 (Windows)
echo ========================================

REM 1. 检查Python版本
echo [1/5] 检查Python版本...
python --version

REM 2. 安装依赖
echo.
echo [2/5] 安装格式化工具...
pip install black ruff isort pre-commit -q
echo ✅ 格式化工具安装完成

REM 3. 格式化代码
echo.
echo [3/5] 运行 Black 格式化...
black src/ tests/ --config pyproject.toml
echo ✅ Black 格式化完成

REM 4. 排序导入
echo.
echo [4/5] 运行 isort 导入排序...
isort src/ tests/ --config pyproject.toml
echo ✅ isort 导入排序完成

REM 5. 检查和修复代码
echo.
echo [5/5] 运行 Ruff 代码检查和修复...
ruff check --fix src/ tests/ --config pyproject.toml
echo ✅ Ruff 检查和修复完成

REM 验证格式化
echo.
echo ========================================
echo 验证格式化结果
echo ========================================

echo 检查 Black 格式...
black --check src/ tests/ --config pyproject.toml
if errorlevel 1 (
    echo ❌ Black 格式检查失败
    exit /b 1
) else (
    echo ✅ Black 格式检查通过
)

echo.
echo 检查 isort 导入排序...
isort --check src/ tests/ --config pyproject.toml
if errorlevel 1 (
    echo ❌ isort 格式检查失败
    exit /b 1
) else (
    echo ✅ isort 格式检查通过
)

echo.
echo 检查 Ruff 代码规范...
ruff check src/ tests/ --config pyproject.toml
if errorlevel 1 (
    echo ❌ Ruff 代码检查失败
    exit /b 1
) else (
    echo ✅ Ruff 代码检查通过
)

echo.
echo ========================================
echo ✅ 代码格式化完成！所有检查通过！
echo ========================================

pause
