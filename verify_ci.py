#!/usr/bin/env python3
"""
本地 CI 验证脚本
在提交前运行此脚本，确保所有检查通过后再推送到 GitHub
"""

import os
import subprocess
import sys


def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'=' * 60}")
    print(f"  {description}")
    print(f"{'=' * 60}")
    print(f"运行: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode == 0


def main():
    print("=" * 60)
    print("  AI Evaluation Platform - 本地 CI 验证")
    print("=" * 60)

    # 确保在项目根目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    all_passed = True

    # 1. Ruff Lint 检查
    all_passed &= run_command(["ruff", "check", "src/", "tests/"], "Ruff Lint 检查")

    # 2. Black 格式化检查
    all_passed &= run_command(
        ["black", "--check", "--line-length", "88", "src/", "tests/"], "Black 格式化检查"
    )

    # 3. isort 检查
    all_passed &= run_command(
        ["isort", "--check-only", "--diff", "src/", "tests/"], "isort 导入顺序检查"
    )

    # 4. Flake8 检查
    all_passed &= run_command(
        ["flake8", "src/", "tests/", "--count", "--statistics", "--max-line-length=88"],
        "Flake8 Lint 检查",
    )

    # 5. 运行单元测试
    all_passed &= run_command(
        ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"], "单元测试"
    )

    # 总结
    print("\n" + "=" * 60)
    if all_passed:
        print("  ✅ 所有检查通过！可以安全提交到 GitHub")
        print("=" * 60)
        return 0
    else:
        print("  ❌ 有检查未通过，请修复后再提交")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
