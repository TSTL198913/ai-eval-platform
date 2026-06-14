# =====================================================================
# AI Evaluation Platform - Makefile
# 便捷脚本
# =====================================================================

.PHONY: help build up down restart logs ps test clean dev monitoring git-init git-push lint format install-hooks

# 帮助信息
help:
	@echo "AI Evaluation Platform - 可用命令"
	@echo "================================"
	@echo "make build      - 构建 Docker 镜像"
	@echo "make up         - 启动所有服务"
	@echo "make down       - 停止所有服务"
	@echo "make restart    - 重启所有服务"
	@echo "make logs       - 查看日志 (按 Ctrl+C 退出)"
	@echo "make ps         - 查看服务状态"
	@echo "make test       - 运行单元测试"
	@echo "make dev        - 启动开发模式 (不构建)"
	@echo "make monitoring - 启动监控组件 (Prometheus + Grafana)"
	@echo "make clean      - 清理 Docker 资源"
	@echo ""
	@echo "代码质量命令:"
	@echo "make lint       - 运行代码检查 (flake8)"
	@echo "make format     - 格式化代码 (black + isort)"
	@echo "make install-hooks - 安装 pre-commit 钩子"

# 构建镜像
build:
	docker-compose build

# 启动所有服务
up:
	docker-compose up -d
	@echo ""
	@echo "服务已启动!"
	@echo "============"
	@echo "API Server:   http://localhost:8000"
	@echo "API Docs:     http://localhost:8000/docs"
	@echo "RabbitMQ:     http://localhost:15672 (guest/guest)"
	@echo ""

# 停止所有服务
down:
	docker-compose down

# 重启服务
restart: down up

# 查看日志
logs:
	docker-compose logs -f

# 查看服务状态
ps:
	docker-compose ps

# 运行单元测试
test:
	docker-compose exec api python -m pytest tests/unit/ -v

# 开发模式 (不构建，直接启动已存在的容器)
dev:
	docker-compose up -d redis postgres rabbitmq
	@echo "基础设施已启动，可以使用本地代码运行服务"

# 启动监控组件
monitoring:
	docker-compose --profile monitoring up -d prometheus grafana
	@echo ""
	@echo "监控已启动!"
	@echo "============="
	@echo "Prometheus:   http://localhost:9090"
	@echo "Grafana:      http://localhost:3000 (admin/admin)"

# 清理 Docker 资源
clean:
	docker-compose down -v --remove-orphans
	docker system prune -f
	@echo "清理完成!"

# 完整重建
rebuild: down build up

# 进入 API 容器
shell-api:
	docker-compose exec api /bin/bash

# 进入 Worker 容器
shell-worker:
	docker-compose exec worker /bin/bash

# 查看服务健康状态
health:
	@curl -s http://localhost:8000/health | python -m json.tool || echo "API 未启动"

# Git 部署命令
git-init:
	@if [ ! -d ".git" ]; then \
		git init; \
		git add .; \
		git commit -m "Initial commit: 分布式 AI 评测平台 v1.0"; \
		echo "Git 仓库初始化完成!"; \
	else \
		echo "Git 仓库已初始化"; \
	fi
	@echo ""
	@echo "下一步:"
	@echo "1. 在 GitHub 创建仓库"
	@echo "2. 运行: git remote add origin https://github.com/你的用户名/ai-eval-platform.git"
	@echo "3. 运行: git push -u origin main"

git-push:
	@echo "推送到 GitHub..."
	@git push -u origin main || echo "请先配置远程仓库: git remote add origin <url>"

git-status:
	@git status

git-log:
	@git log --oneline -10

# =====================================================================
# 代码质量命令
# =====================================================================

# 安装代码质量工具
install-lint:
	pip install black flake8 isort pytest-cov pre-commit

# 安装 pre-commit 钩子
install-hooks:
	pre-commit install

# 代码格式检查
lint:
	@echo "运行代码检查..."
	@flake8 src/ tests/ --count --show-source --statistics || true

# 格式化代码
format:
	@echo "格式化代码..."
	@black src/ tests/
	@isort src/ tests/
	@echo "格式化完成!"

# 代码质量检查 (完整)
check: format lint test

# 安装依赖
install:
	pip install -r requirements.txt
