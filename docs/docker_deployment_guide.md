# AI Eval Platform - Docker部署指南

## 问题诊断与解决

### 问题现象
```
✘ Image ghcr.io/tstl198913/ai-eval-platform:latest-frontend Error error from registry: denied
Error response from daemon: error from registry: denied
```

### 问题原因
前端镜像 `ghcr.io/tstl198913/ai-eval-platform:latest-frontend` 不存在或无法访问(ghcr.io需要GitHub认证)

### 解决方案
修改 `docker-compose.prod.yml`,改为**本地构建**前端镜像,而不是使用预构建镜像。

---

## 快速部署(使用本地构建)

### 前置条件
1. 安装Docker (版本20.10+)
2. 安装Docker Compose (版本2.0+)
3. 确保端口80、443、5432、6379、5672、8000未被占用

### 部署步骤

#### 1. 克隆项目
```bash
git clone https://github.com/tstl198913/ai-eval-platform.git
cd ai-eval-platform
```

#### 2. 配置环境变量
```bash
# 复制生产环境配置模板
cp .env.prod.example .env.prod

# 编辑生产环境配置
nano .env.prod

# 必需配置项:
POSTGRES_USER=eval
POSTGRES_PASSWORD=你的强密码
RABBITMQ_USER=your_rabbitmq_user
RABBITMQ_PASSWORD=你的强密码
DEEPSEEK_API_KEY=你的DeepSeek API密钥
OPENAI_API_KEY=你的OpenAI API密钥
```

#### 3. 构建并启动所有服务
```bash
# 使用生产配置构建并启动
docker-compose -f docker-compose.prod.yml up -d

# 查看服务状态
docker-compose -f docker-compose.prod.yml ps

# 查看日志
docker-compose -f docker-compose.prod.yml logs -f
```

#### 4. 验证服务
```bash
# 等待30秒让服务完全启动

# 检查API服务
curl http://localhost:8000/health

# 检查前端服务
curl http://localhost/health

# 查看所有容器状态
docker ps
```

#### 5. 访问应用
- 前端UI: http://localhost
- API文档: http://localhost:8000/docs
- RabbitMQ管理: http://localhost:15672 (guest/guest)

---

## 部署架构说明

### 服务组件
```
┌─────────────────────────────────────────────────────────┐
│                     Nginx Reverse Proxy                 │
│                      (Frontend Container)                │
└──────────┬──────────────────────────────────────────────┘
           │ /api
           ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Backend                       │
│              (API + Worker Containers)                   │
└──────────┬──────────────────────────────────────────────┘
           │
           ├──────────┬──────────┬──────────┐
           ▼          ▼          ▼          ▼
      PostgreSQL   Redis     RabbitMQ   Prometheus
        DB        Cache    Message Queue  Metrics
```

### 容器说明

| 容器名 | 镜像类型 | 说明 | 端口 |
|--------|---------|------|------|
| ai-eval-postgres | 官方镜像 | PostgreSQL 15 数据库 | 5432 |
| ai-eval-redis | 官方镜像 | Redis 7 缓存服务 | 6379 |
| ai-eval-rabbitmq | 官方镜像 | RabbitMQ 3.13 消息队列 | 5672, 15672 |
| ai-eval-api | 本地构建 | FastAPI 后端服务 | 8000 |
| ai-eval-frontend | 本地构建 | React + Nginx 前端 | 80, 443 |
| ai-eval-worker | 本地构建 | Celery 异步任务处理 | - |

---

## 详细配置说明

### 环境变量配置 (.env.prod)

```bash
# 数据库配置
POSTGRES_USER=eval
POSTGRES_PASSWORD=安全的密码
DATABASE_URL=postgresql://eval:安全的密码@postgres:5432/ai_eval

# Redis配置
REDIS_URL=redis://redis:6379

# RabbitMQ配置
RABBITMQ_USER=your_user
RABBITMQ_PASSWORD=安全的密码
RABBITMQ_URL=amqp://your_user:安全的密码@rabbitmq:5672

# AI模型API密钥(必需)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx

# 其他配置
LOG_LEVEL=INFO
WORKER_CONCURRENCY=4
MAX_WORKERS=8
```

### 数据库初始化
```bash
# 如果需要初始化数据库
docker-compose -f docker-compose.prod.yml exec postgres psql -U eval -d ai_eval -f /docker-entrypoint-initdb.d/init.sql
```

---

## 运维管理

### 常用命令

#### 查看服务状态
```bash
# 查看所有容器状态
docker ps

# 查看实时日志
docker-compose -f docker-compose.prod.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.prod.yml logs -f api
docker-compose -f docker-compose.prod.yml logs -f worker
```

#### 重启服务
```bash
# 重启所有服务
docker-compose -f docker-compose.prod.yml restart

# 重启特定服务
docker-compose -f docker-compose.prod.yml restart api
```

#### 停止服务
```bash
# 停止所有服务(保留数据卷)
docker-compose -f docker-compose.prod.yml down

# 停止所有服务并删除数据卷(慎用!)
docker-compose -f docker-compose.prod.yml down -v
```

#### 重新构建
```bash
# 重新构建所有服务
docker-compose -f docker-compose.prod.yml up -d --build

# 重新构建特定服务
docker-compose -f docker-compose.prod.yml up -d --build frontend
docker-compose -f docker-compose.prod.yml up -d --build api
```

### 性能监控

#### 查看资源使用
```bash
# 查看容器资源使用
docker stats

# 查看特定容器
docker stats ai-eval-api
docker stats ai-eval-worker
```

#### 查看日志
```bash
# 查看API日志(最近100行)
docker-compose -f docker-compose.prod.yml logs --tail=100 api

# 搜索错误日志
docker-compose -f docker-compose.prod.yml logs | grep ERROR

# 导出日志到文件
docker-compose -f docker-compose.prod.yml logs > logs.txt
```

### 数据管理

#### 备份数据库
```bash
# 创建数据库备份
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U eval ai_eval > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker-compose -f docker-compose.prod.yml exec -T postgres psql -U eval -d ai_eval < backup_20240101.sql
```

#### 清理日志
```bash
# 清理Docker日志
truncate -s 0 /var/lib/docker/containers/*/*-json.log

# 清理未使用的Docker资源
docker system prune -a
```

---

## 故障排查

### 常见问题

#### 1. 端口冲突
```bash
# 检查端口占用
netstat -tulpn | grep :80
netstat -tulpn | grep :8000

# 修改docker-compose.prod.yml中的端口映射
```

#### 2. 数据库连接失败
```bash
# 检查数据库是否就绪
docker-compose -f docker-compose.prod.yml logs postgres | grep "database system is ready"

# 检查连接配置
docker-compose -f docker-compose.prod.yml exec api env | grep DATABASE_URL
```

#### 3. Worker无法启动
```bash
# 检查Worker日志
docker-compose -f docker-compose.prod.yml logs worker

# 常见原因:
# - 数据库未就绪
# - Redis连接失败
# - RabbitMQ连接失败
# - 缺少API密钥
```

#### 4. 前端构建失败
```bash
# 检查前端构建日志
docker-compose -f docker-compose.prod.yml logs frontend

# 常见原因:
# - Node版本不兼容
# - npm依赖安装失败
# - 构建超时
```

### 日志诊断
```bash
# 查看所有错误
docker-compose -f docker-compose.prod.yml logs | grep -i error

# 查看最近1小时的日志
docker-compose -f docker-compose.prod.yml logs --since 1h

# 查看特定时间段的日志
docker-compose -f docker-compose.prod.yml logs --since "2024-01-01T00:00:00"
```

### 健康检查
```bash
# 检查所有服务健康状态
for service in postgres redis rabbitmq api frontend worker; do
  echo "Checking $service..."
  docker-compose -f docker-compose.prod.yml exec -T $service sh -c "exit 0" 2>/dev/null && echo "✓ $service OK" || echo "✗ $service FAILED"
done
```

---

## 安全建议

### 必需的安全措施

1. **修改默认密码**
   - PostgreSQL密码
   - RabbitMQ密码
   - API密钥

2. **使用HTTPS**
   - 配置SSL证书
   - 启用HTTPS重定向

3. **网络隔离**
   - 生产环境使用内部网络
   - 不暴露不必要的端口

4. **定期更新**
   - 更新基础镜像
   - 更新依赖包
   - 更新应用程序

### 生产环境建议

1. **使用Docker Swarm或Kubernetes**
   - 容器编排
   - 负载均衡
   - 自动扩缩容

2. **配置监控和告警**
   - Prometheus + Grafana
   - 日志聚合(ELK)
   - 性能告警

3. **定期备份**
   - 数据库每日备份
   - 配置文件备份
   - 验证备份恢复

---

## 扩展阅读

### 相关文档
- [Docker构建问题解决方案](docs/docker_build_solution.md)
- [架构文档](ARCHITECTURE.md)
- [部署指南](docs/deployment_guide.md)
- [API文档](docs/api_reference.md)

### 推荐工具
- Portainer: Docker容器管理界面
- Traefik: 反向代理和负载均衡
- Watchtower: 自动更新容器

---

## 技术支持

遇到问题?
1. 查看日志: `docker-compose logs`
2. 检查配置: `.env.prod`
3. 查看文档: `docs/`
4. 提交Issue: GitHub Issues

---

**文档生成时间**: 2026-06-19
**版本**: 1.0.0
**最后更新**: 2026-06-19
