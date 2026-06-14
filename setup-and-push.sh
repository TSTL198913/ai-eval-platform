#!/bin/bash
# =====================================================================
# 分布式 AI 评测平台 - 完整部署脚本
# 使用方法: bash setup-and-push.sh <github-username> <repo-name>
# 示例: bash setup-and-push.sh john ai-eval-platform
# =====================================================================

set -e

GITHUB_USERNAME="${1:-}"
REPO_NAME="${2:-}"

echo ""
echo "============================================"
echo "  分布式 AI 评测平台 - 一键部署"
echo "============================================"
echo ""

# 检查参数
if [ -z "$GITHUB_USERNAME" ] || [ -z "$REPO_NAME" ]; then
    echo "[错误] 缺少参数"
    echo ""
    echo "使用方法: bash setup-and-push.sh <github-username> <repo-name>"
    echo "示例: bash setup-and-push.sh john ai-eval-platform"
    echo ""
    exit 1
fi

REPO_URL="https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"

echo "[步骤 1] 初始化 Git 仓库..."
if [ ! -d ".git" ]; then
    git init
    git add .
    git commit -m "Initial commit: 分布式 AI 评测平台 v1.0"
    echo "[完成]"
else
    echo "[跳过] 已初始化"
fi

echo ""
echo "[步骤 2] 配置远程仓库..."
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git branch -M main
echo "[完成] 远程地址: $REPO_URL"

echo ""
echo "[步骤 3] 推送到 GitHub..."
echo "[提示] 可能需要输入 GitHub 用户名和 Personal Access Token"
echo ""

git push -u origin main

echo ""
echo "============================================"
echo "  部署完成！"
echo "============================================"
echo ""
echo "仓库地址: https://github.com/${GITHUB_USERNAME}/${REPO_NAME}"
echo ""
echo "虚拟机部署命令:"
echo "  git clone $REPO_URL"
echo "  cd $REPO_NAME"
echo "  cp .env.example .env"
echo "  docker compose up -d --build"
echo ""
