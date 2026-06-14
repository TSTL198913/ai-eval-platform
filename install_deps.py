#!/usr/bin/env python3
"""
一键安装脚本 - 使用国内镜像源快速安装依赖

使用方法：
    python install_deps.py

可选参数：
    --mirror    指定镜像源（默认：清华）
    --dev       安装开发依赖
    --upgrade   升级所有依赖
"""

import argparse
import subprocess
import sys

# 国内镜像源列表
MIRRORS = {
    "tsinghua": "https://pypi.tuna.tsinghua.edu.cn/simple",
    "aliyun": "https://mirrors.aliyun.com/pypi/simple",
    "ustc": "https://pypi.mirrors.ustc.edu.cn/simple",
    "hust": "https://pypi.hustunique.com/simple",
    "tencent": "https://mirrors.cloud.tencent.com/pypi/simple",
    "huawei": "https://repo.huaweicloud.com/repository/pypi/simple",
    "default": "https://pypi.org/simple",
}


def install_dependencies(mirror="tsinghua", dev=False, upgrade=False):
    """安装依赖"""
    mirror_url = MIRRORS.get(mirror, MIRRORS["tsinghua"])

    print("=" * 60)
    print("  AI Evaluation Platform - 一键安装依赖")
    print("=" * 60)
    print(f"\n使用镜像源: {mirror_url}")

    # 配置 pip
    print("\n[1/3] 配置 pip 镜像源...")
    subprocess.run(
        ["pip", "config", "set", "global.index-url", mirror_url],
        check=True,
    )

    # 安装核心依赖
    print("\n[2/3] 安装核心依赖...")
    cmd = ["pip", "install", "-r", "requirements.txt"]
    if upgrade:
        cmd.append("--upgrade")
    subprocess.run(cmd, check=True)

    # 安装开发依赖
    if dev:
        print("\n[3/3] 安装开发依赖...")
        dev_packages = [
            "black",
            "flake8",
            "isort",
            "pytest",
            "pytest-cov",
            "pytest-asyncio",
            "pytest-mock",
            "ruff",
            "pre-commit",
        ]
        cmd = ["pip", "install"] + dev_packages
        if upgrade:
            cmd.append("--upgrade")
        subprocess.run(cmd, check=True)
    else:
        print("\n[3/3] 跳过开发依赖安装")

    print("\n" + "=" * 60)
    print("  ✅ 安装完成！")
    print("=" * 60)
    print("\n验证安装:")
    subprocess.run(["pip", "list"], check=False)


def main():
    parser = argparse.ArgumentParser(description="一键安装 Python 依赖")
    parser.add_argument(
        "--mirror",
        choices=list(MIRRORS.keys()),
        default="tsinghua",
        help="选择镜像源",
    )
    parser.add_argument("--dev", action="store_true", help="安装开发依赖")
    parser.add_argument("--upgrade", action="store_true", help="升级所有依赖")

    args = parser.parse_args()

    try:
        install_dependencies(mirror=args.mirror, dev=args.dev, upgrade=args.upgrade)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 安装失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
