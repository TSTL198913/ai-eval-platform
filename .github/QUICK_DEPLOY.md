# AI 评测平台 - 快速部署指南

## 一键部署到 Ubuntu 服务器

### 前置要求

**服务器环境：**
- Ubuntu 20.04 LTS 或更高版本
- 最低配置：2 CPU + 4GB RAM
- 推荐配置：4 CPU + 8GB RAM
- 磁盘空间：至少 20GB 可用空间

**必需软件：**
- Docker 20.10+
- Docker Compose 2.0+
- Git（用于拉取代码）

### 快速部署步骤

#### 步骤 1: 服务器环境准备

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要工具
sudo apt install -y curl wget git

# 安装 Docker（如果尚未安装）
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 验证安装
docker --version
docker-compose --version
```

#### 步骤 2: 获取部署文件

```bash
# 创建部署目录
mkdir -p ~/ai-eval-platform && cd ~/ai-eval-platform

# 方式 A: 从 GitHub 拉取（推荐）
git clone https://github.com/tstl198913/ai-eval-platform-refactor.git .

# 方式 B: 手动上传文件
# 将以下文件上传到服务器：
# - .env.prod
# - docker-compose.prod.yml
# - deploy-prod.sh
```

#### 步骤 3: 配置环境变量

```bash
# 编辑生产环境配置
nano .env.prod

# 修改以下必需配置项：
# - POSTGRES_PASSWORD=your_secure_password  （数据库密码）
# - RABBITMQ_PASSWORD=your_secure_password    （消息队列密码）
# - DEEPSEEK_API_KEY=your_api_key            （DeepSeek API Key）
# - OPENAI_API_KEY=your_api_key             （OpenAI API Key，可选）
```

**`.env.prod` 必需配置项：**

```bash
# ==================== 必需配置 ====================

# 数据库密码（必须修改）
POSTGRES_PASSWORD=your_secure_db_password_here

# RabbitMQ 密码（必须修改）
RABBITMQ_PASSWORD=your_secure_rabbitmq_password_here

# DeepSeek API Key（必需）
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# ==================== 可选配置 ====================

# OpenAI API Key（如使用）
OPENAI_API_KEY=your_openai_api_key_here

# 其他配置可使用默认值
```

#### 步骤 4: 执行一键部署

```bash
# 赋予执行权限
chmod +x deploy-prod.sh

# 执行部署（需要 5-10 分钟）
./deploy-prod.sh
```

部署脚本会自动完成：
1. 拉取最新 Docker 镜像
2. 备份当前配置
3. 启动所有服务
4. 验证服务健康状态

### 验证部署

#### 检查服务状态

```bash
# 查看容器状态
docker compose -f docker-compose.prod.yml ps

# 查看日志
docker compose -f docker-compose.prod.yml logs -f
```

#### 测试 API 接口

```bash
# 健康检查
curl http://localhost:8000/health

# 预期响应：
# {"status":"healthy","service":"ai-eval-platform"}

# Prometheus 指标（可选）
curl http://localhost:8000/metrics
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| API | http://your-server-ip:8000 | 主 API 服务 |
| 健康检查 | http://your-server-ip:8000/health | 健康状态 |
| 指标端点 | http://your-server-ip:8000/metrics | Prometheus 监控 |
| RabbitMQ | http://your-server-ip:15672 | 消息队列管理界面 |
| PostgreSQL | localhost:5432 | 数据库（仅内网访问）|
| Redis | localhost:6379 | 缓存（仅内网访问）|

### 常见问题

#### Q1: 部署脚本执行失败？

```bash
# 检查 Docker 服务状态
sudo systemctl status docker

# 手动启动服务
docker compose -f docker-compose.prod.yml up -d

# 查看详细日志
docker compose -f docker-compose.prod.yml logs
```

#### Q2: 数据库连接失败？

```bash
# 等待数据库完全启动（约 30 秒）
sleep 30

# 检查数据库日志
docker compose -f docker-compose.prod.yml logs postgres
```

#### Q3: API 健康检查失败？

```bash
# 检查 API 日志
docker compose -f docker-compose.prod.yml logs api

# 确认所有依赖服务健康
docker compose -f docker-compose.prod.yml ps
```

### 日常运维

#### 更新部署

```bash
# 拉取最新代码
git pull origin main

# 重新部署
./deploy-prod.sh
```

#### 备份数据

```bash
# 备份数据库
docker exec ai-eval-postgres pg_dump -U eval ai_eval > backup_$(date +%Y%m%d).sql

# 备份配置文件
tar -czf configs_backup_$(date +%Y%m%d).tar.gz .env.prod docker-compose.prod.yml
```

#### 回滚操作

```bash
# 查看备份列表
ls -la deploy_backups/

# 使用备份恢复
docker compose -f docker-compose.prod.yml down
docker compose -f deploy_backups/docker-compose.backup.20250615_120000.yml up -d
```

### 卸载服务

```bash
# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 删除数据卷（谨慎操作，会删除所有数据）
docker volume rm ai-eval-platform_postgres_data
docker volume rm ai-eval-platform_redis_data
docker volume rm ai-eval-platform_rabbitmq_data

# 删除部署目录
cd ~ && rm -rf ai-eval-platform
```

### 安全建议

1. **修改默认密码**：生产环境必须修改 `.env.prod` 中的所有默认密码
2. **配置防火墙**：仅开放必要端口（8000、15672）
3. **启用 HTTPS**：生产环境建议配置 Nginx 反向代理和 SSL 证书
4. **定期备份**：建立自动化备份机制
5. **监控告警**：配置 Prometheus + Grafana 监控告警

### 技术支持

如遇问题，请检查：
1. Docker 日志：`docker compose logs`
2. 服务状态：`docker compose ps`
3. 资源使用：`docker stats`

---

**部署愉快！** 如有问题请提交 Issue。
