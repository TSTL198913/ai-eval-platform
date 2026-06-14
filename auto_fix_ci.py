#!/usr/bin/env python3
"""
CI 失败自动修复工具
功能：
1. 自动获取 GitHub Actions 最新 CI 运行状态
2. 分析失败原因
3. 自动尝试修复
4. 重新提交
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime

# GitHub 配置
GITHUB_REPO = "TSTL198913/ai-eval-platform"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


def run_command(cmd, description="", timeout=120):
    """运行命令并返回结果"""
    if description:
        print(f"\n{'=' * 60}")
        print(f"  {description}")
        print(f"{'=' * 60}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except Exception as e:
        return -1, "", str(e)


def get_latest_workflow_run():
    """获取最新的 CI workflow 运行状态"""
    if not GITHUB_TOKEN:
        print("⚠️ 未设置 GITHUB_TOKEN，跳过 API 查询")
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=1"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data.get("workflow_runs"):
                return data["workflow_runs"][0]
    except Exception as e:
        print(f"⚠️ 获取 workflow 状态失败: {e}")

    return None


def get_workflow_logs_url(run_id):
    """获取 workflow 日志下载链接"""
    if not GITHUB_TOKEN:
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs/{run_id}/logs"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get("url")
    except Exception as e:
        print(f"⚠️ 获取日志链接失败: {e}")

    return None


def analyze_failure(output):
    """分析 CI 失败输出，提取关键错误信息"""
    errors = []

    # 匹配常见的错误模式
    patterns = [
        (r"error\[E\d+\].*", "Flake8 错误"),
        (r"ruff.*error.*", "Ruff Lint 错误"),
        (r"black.*error.*", "Black 格式化错误"),
        (r"FAILED.*", "测试失败"),
        (r"SyntaxError:.*", "语法错误"),
        (r"ImportError:.*", "导入错误"),
        (r"ModuleNotFoundError:.*", "模块未找到"),
        (r"AssertionError:.*", "断言错误"),
    ]

    for line in output.split("\n"):
        for pattern, error_type in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                errors.append({"type": error_type, "message": line.strip()})
                break

    return errors


def auto_fix():
    """自动修复常见的 CI 错误"""
    print("\n" + "=" * 60)
    print("  开始自动修复")
    print("=" * 60)

    fixes_applied = []

    # 1. 运行 Ruff 自动修复
    print("\n[1/5] 运行 Ruff 自动修复...")
    code, stdout, stderr = run_command("ruff check src/ tests/ --fix", "Ruff 自动修复")
    if code == 0:
        fixes_applied.append("Ruff 自动修复")
        print("  ✅ Ruff 修复完成")
    else:
        print(f"  ⚠️ Ruff 修复有问题: {stderr[:200]}")

    # 2. 运行 Black 格式化
    print("\n[2/5] 运行 Black 格式化...")
    code, stdout, stderr = run_command("black --line-length 100 src/ tests/", "Black 格式化")
    if code == 0:
        fixes_applied.append("Black 格式化")
        print("  ✅ Black 格式化完成")
    else:
        print(f"  ⚠️ Black 格式化有问题: {stderr[:200]}")

    # 3. 运行 isort 排序
    print("\n[3/5] 运行 isort 排序...")
    code, stdout, stderr = run_command("isort src/ tests/", "isort 排序")
    if code == 0:
        fixes_applied.append("isort 排序")
        print("  ✅ isort 排序完成")
    else:
        print(f"  ⚠️ isort 排序有问题: {stderr[:200]}")

    # 4. 运行完整的 lint 检查
    print("\n[4/5] 运行完整 lint 检查...")
    code, stdout, stderr = run_command(
        "ruff check src/ tests/ ; black --check --line-length 100 src/ tests/ ; "
        "isort --check-only src/ tests/ ; flake8 src/ tests/ --count --max-line-length=100",
        "Lint 检查",
    )
    lint_passed = code == 0

    # 5. 运行单元测试
    print("\n[5/5] 运行单元测试...")
    code, stdout, stderr = run_command(
        "python -m pytest tests/unit/ -v --tb=short", "单元测试", timeout=300
    )
    tests_passed = code == 0

    return {
        "lint_passed": lint_passed,
        "tests_passed": tests_passed,
        "fixes_applied": fixes_applied,
        "lint_output": stdout + stderr,
    }


def commit_and_push():
    """提交修复并推送"""
    print("\n" + "=" * 60)
    print("  提交修复")
    print("=" * 60)

    # 检查是否有更改
    code, stdout, stderr = run_command("git status --porcelain", "检查更改")
    if not stdout.strip():
        print("  ℹ️ 没有需要提交的更改")
        return False

    # 添加所有更改
    run_command("git add .", "添加更改")

    # 创建提交
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto Fix: CI issues ({timestamp})"
    code, stdout, stderr = run_command(f'git commit --no-verify -m "{commit_msg}"', "创建提交")

    if code != 0:
        print(f"  ❌ 提交失败: {stderr}")
        return False

    print("  ✅ 提交成功")

    # 推送
    code, stdout, stderr = run_command("git push origin main", "推送到 GitHub")

    if code != 0:
        print(f"  ❌ 推送失败: {stderr}")
        return False

    print("  ✅ 推送成功")
    return True


def main():
    print("=" * 60)
    print("  CI 失败自动修复工具")
    print("=" * 60)

    # 获取最新 CI 状态
    print("\n获取 GitHub Actions 状态...")
    run_info = get_latest_workflow_run()

    if run_info:
        print(f"  最新运行: {run_info.get('name', 'Unknown')}")
        print(
            f"  状态: {run_info.get('status', 'Unknown')} / {run_info.get('conclusion', 'Unknown')}"
        )
        print(f"  触发时间: {run_info.get('created_at', 'Unknown')}")

        if run_info.get("conclusion") == "failure":
            print("\n  ❌ 检测到 CI 失败，开始自动修复...")
        elif run_info.get("conclusion") == "success":
            print("\n  ✅ CI 已经通过，无需修复")
            return 0
    else:
        print("  ⚠️ 无法获取 CI 状态，尝试本地修复...")

    # 执行自动修复
    result = auto_fix()

    # 显示结果
    print("\n" + "=" * 60)
    print("  修复结果")
    print("=" * 60)
    print(
        f"  已应用的修复: {', '.join(result['fixes_applied']) if result['fixes_applied'] else '无'}"
    )
    print(f"  Lint 检查: {'✅ 通过' if result['lint_passed'] else '❌ 失败'}")
    print(f"  单元测试: {'✅ 通过' if result['tests_passed'] else '❌ 失败'}")

    if not result["lint_passed"] or not result["tests_passed"]:
        print("\n  ⚠️ 仍有未通过的项目:")
        errors = analyze_failure(result["lint_output"])
        for i, error in enumerate(errors[:5], 1):
            print(f"    {i}. [{error['type']}] {error['message'][:80]}")

        # 仍然尝试提交，因为可能需要多次 CI 运行来完全修复
        print("\n  仍尝试提交更改...")

    # 提交并推送
    if commit_and_push():
        print("\n" + "=" * 60)
        print("  ✅ 修复已提交，请等待 CI 重新运行")
        print("  约 5-10 分钟后检查结果")
        print("=" * 60)

        if not result["lint_passed"] or not result["tests_passed"]:
            print("\n  💡 提示: 如果 CI 仍然失败，可以再次运行此脚本")
            print("         或手动检查 GitHub Actions 日志")
    else:
        print("\n  ❌ 提交失败")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
