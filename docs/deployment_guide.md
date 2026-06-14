# AI 评测平台部署指南

## 概述

本文档提供 AI 评测平台的完整部署指南，涵盖开发环境、生产环境、Kubernetes 部署等多种场景。

## 环境要求

### 硬件要求

| 环境 | CPU | 内存 | 磁盘 | 说明 |
|------|-----|------|------|------|
| 开发 | 2 核 | 4 GB | 20 GB | 单机部署 |
| 测试 | 4 核 | 8 GB | 50 GB | 含 Redis/DB |
| 生产 | 8+ 核 | 16+ GB | 100+ GB | 多节点部署 |

### 软件要求

- Python 3.10+
- Redis 6.0+
- PostgreSQL 14+ (可选)
- RabbitMQ 3.9+ (可选)
- Kubernetes 1.24+ (生产环境)

## 开发环境部署

### 1. 克隆代码

```bash
git clone https://github.com/ai-eval/platform.git
cd platform
```

### 2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
pip install -e .
```

### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# AI Eval 配置
AI_EVAL_API_KEY=your-api-key
AI_EVAL_SECRET_KEY=your-secret-key

# Redis 配置
REDIS_URL=redis://localhost:6379/0

# 数据库配置
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_eval

# 日志配置
LOG_LEVEL=INFO
```

### 5. 启动服务

```bash
# 启动 API 服务
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload

# 或启动分布式服务
uvicorn src.api.distributed_server:app --host 0.0.0.0 --port 8001 --workers 4
```

### 6. 验证部署

```bash
curl http://localhost:8000/health
```

## Docker 部署

### 1. 构建镜像

```bash
docker build -t ai-eval-platform:latest .
```

### 2. 运行容器

```bash
# 单机部署
docker run -d \
  --name ai-eval \
  -p 8000:8000 \
  -e REDIS_URL=redis://host.docker.internal:6379/0 \
  ai-eval-platform:latest

# 带数据库部署
docker-compose up -f docker-compose.yml -d
```

### 3. Docker Compose 配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/ai_eval
    depends_on:
      - redis
      - db

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  db:
    image: postgres:14-alpine
    environment:
      - POSTGRES_DB=ai_eval
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    volumes:
      - pgdata:/var/lib/postgresql/data

  worker:
    build: .
    command: celery -A src.workers.celery_app worker --loglevel=info
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
      - db

volumes:
  pgdata:
```

## Kubernetes 部署

### 1. 前置要求

- Kubernetes 1.24+
- Helm 3.8+
- kubectl 配置完成

### 2. 创建 Namespace

```bash
kubectl create namespace ai-eval
```

### 3. 部署配置

```bash
# 应用配置
kubectl apply -f docker/k8s/configmap.yaml -n ai-eval
kubectl apply -f docker/k8s/deployment.yaml -n ai-eval
kubectl apply -f docker/k8s/service.yaml -n ai-eval
kubectl apply -f docker/k8s/hpa.yaml -n ai-eval

# 检查部署状态
kubectl get pods -n ai-eval
kubectl get services -n ai-eval
```

### 4. Ingress 配置

```yaml
# docker/k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ai-eval-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  rules:
    - host: api.ai-eval.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ai-eval-api
                port:
                  number: 8000
```

### 5. 水平自动扩缩容

```yaml
# HPA 配置
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ai-eval-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ai-eval-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
```

## 生产环境配置

### 1. Nginx 反向代理

```nginx
# /etc/nginx/conf.d/ai-eval.conf
upstream ai_eval_backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name api.ai-eval.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.ai-eval.com;

    ssl_certificate /etc/ssl/certs/ai-eval.crt;
    ssl_certificate_key /etc/ssl/private/ai-eval.key;

    location / {
        proxy_pass http://ai_eval_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://ai_eval_backend/health;
        proxy_http_version 1.1;
    }
}
```

### 2. SSL 证书配置

```bash
# 使用 Let's Encrypt
certbot --nginx -d api.ai-eval.com

# 或手动配置
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/ai-eval.key \
  -out /etc/ssl/certs/ai-eval.crt
```

### 3. 系统服务配置

```ini
# /etc/systemd/system/ai-eval.service
[Unit]
Description=AI Evaluation Platform
After=network.target redis.service

[Service]
Type=simple
User=ai_eval
Group=ai_eval
WorkingDirectory=/opt/ai-eval
Environment="PATH=/opt/ai-eval/venv/bin"
Environment="REDIS_URL=redis://localhost:6379/0"
ExecStart=/opt/ai-eval/venv/bin/uvicorn src.api.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl enable ai-eval
sudo systemctl start ai-eval
sudo systemctl status ai-eval
```

## 监控配置

### 1. Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ai-eval'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

### 2. Grafana 仪表盘

```bash
# 导入仪表盘
curl -X POST http://localhost:3000/api/dashboards/import \
  -H "Content-Type: application/json" \
  -d @docker/grafana/dashboards/ai-eval.json
```

## 备份配置

### 1. Redis 备份

```bash
# crontab 备份
0 2 * * * redis-cli BGSAVE && cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

### 2. 数据库备份

```bash
# 每日备份脚本
#!/bin/bash
DATE=$(date +%Y%m%d)
pg_dump -U postgres ai_eval > /backup/db-$DATE.sql
```

## 部署检查清单

- [ ] 环境变量配置完成
- [ ] 依赖服务（Redis/DB）可用
- [ ] SSL 证书配置
- [ ] 监控告警配置
- [ ] 日志收集配置
- [ ] 备份策略配置
- [ ] 健康检查通过
- [ ] 性能基线验证

## 常见问题

### 1. 服务启动失败

```bash
# 检查日志
journalctl -u ai-eval -n 100

# 检查端口占用
netstat -tlnp | grep 8000
```

### 2. Redis 连接失败

```bash
# 检查 Redis 状态
redis-cli ping
redis-cli info clients
```

### 3. 性能问题

```bash
# 检查资源使用
top -u ai_eval
free -h
df -h
```
