# AI Eval Platform - 部署上线指南

## 一、部署前准备

### 1.1 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Ubuntu 20.04+ / CentOS 7+ |
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| 内存 | 最低4GB，推荐8GB |
| CPU | 最低2核，推荐4核 |
| 存储 | 最低20GB，推荐50GB |
| 网络 | 能访问LLM API（DeepSeek/OpenAI） |

### 1.2 环境变量配置

创建 `.env.prod` 文件：

```bash
# 复制示例文件
cp .env.prod.example .env.prod

# 编辑配置
vim .env.prod
```

**必须配置的环境变量**：

```bash
# LLM API Keys（必须）
DEEPSEEK_API_KEY=sk-your-deepseek-key
OPENAI_API_KEY=sk-your-openai-key  # 可选

# 数据库配置
POSTGRES_USER=eval
POSTGRES_PASSWORD=eval123_secure  # 生产环境请修改
POSTGRES_DB=ai_eval

# Redis配置
REDIS_URL=redis://redis:6379

# RabbitMQ配置
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest_secure  # 生产环境请修改

# 监控配置
PROMETHEUS_ENABLED=true
GRAFANA_ADMIN_PASSWORD=admin_secure  # 生产环境请修改

# 安全配置
ENCRYPTION_KEY=your-32-byte-encryption-key  # 用于敏感信息加密
```

### 1.3 检查清单

- [ ] Docker已安装并运行
- [ ] Docker Compose已安装
- [ ] `.env.prod`已配置
- [ ] LLM API Key已获取
- [ ] 网络端口已开放（8000, 3000, 9090, 5432, 6379, 5672）
- [ ] 服务器防火墙已配置

---

## 二、部署步骤

### 2.1 方式一：一键部署（推荐）

```bash
# 1. 克隆代码
git clone https://github.com/your-org/ai-eval-platform.git
cd ai-eval-platform

# 2. 配置环境变量
cp .env.prod.example .env.prod
vim .env.prod  # 填写API Keys

# 3. 一键启动
chmod +x start-all.sh
./start-all.sh
```

### 2.2 方式二：分步部署

```bash
# 1. 启动基础设施（数据库、缓存、消息队列）
docker-compose up -d postgres redis rabbitmq

# 2. 等待基础设施就绪
sleep 30

# 3. 启动API服务
docker-compose up -d api

# 4. 启动Celery Worker
docker-compose up -d worker

# 5. 启动监控栈（可选）
docker-compose --profile monitoring up -d prometheus grafana pushgateway alertmanager
```

### 2.3 方式三：生产环境部署

```bash
# 使用生产配置
docker-compose -f docker-compose.prod.yml up -d

# 或使用部署脚本
./deploy-prod.sh
```

---

## 三、验证部署

### 3.1 服务健康检查

```bash
# 检查所有容器状态
docker ps

# 检查API健康
curl http://localhost:8000/health

# 检查Prometheus
curl http://localhost:9090/-/healthy

# 检查Grafana
curl http://localhost:3000/api/health
```

### 3.2 功能验证

```bash
# 运行自测脚本
python scripts/self_test.py

# 运行单元测试
pytest tests/unit/ -v

# 测试API接口
curl http://localhost:8000/api/v1/evaluators
```

### 3.3 监控验证

访问以下地址验证监控：

| 服务 | 地址 | 说明 |
|------|------|------|
| API | http://your-ip:8000 | FastAPI服务 |
| Prometheus | http://your-ip:9090 | 指标查询 |
| Grafana | http://your-ip:3000 | 可视化仪表盘 |
| RabbitMQ | http://your-ip:15672 | 消息队列管理 |

---

## 四、监控配置

### 4.1 导入Grafana Dashboard

1. 登录Grafana（http://your-ip:3000，admin/admin）
2. 添加Prometheus数据源：
   - Configuration → Data Sources → Add data source
   - 选择Prometheus
   - URL: http://prometheus:9090
   - Save & Test
3. 导入Dashboard：
   - Dashboards → Import
   - 上传 `grafana/dashboards/ai_eval_platform_ops.json`
   - 上传 `grafana/dashboards/ai_eval_platform_insights.json`

### 4.2 配置告警

告警规则已配置在 `deploy/prometheus/alerts.yml`：

| 告警 | 条件 | 严重度 |
|------|------|--------|
| API可用性低 | <99% | critical |
| API错误率高 | >5% | warning |
| API延迟高 | P99>5s | warning |
| LLM失败率高 | >10% | warning |
| 日成本超预算 | >$50 | warning |
| 队列堆积 | >500 | warning |

---

## 五、回滚方案

### 5.1 快速回滚

```bash
# 停止当前服务
docker-compose down

# 回滚到上一版本
docker-compose -f deploy_backups/docker-compose.backup.TIMESTAMP.yml up -d
```

### 5.2 数据备份

```bash
# 备份PostgreSQL
docker exec ai-eval-postgres pg_dump -U eval ai_eval > backup.sql

# 备份Redis
docker exec ai-eval-redis redis-cli BGSAVE
docker cp ai-eval-redis:/data/dump.rdb ./backup_redis.rdb
```

---

## 六、常见问题

### 6.1 API启动失败

**症状**：API容器无法启动或健康检查失败

**排查步骤**：
```bash
# 查看日志
docker logs ai-eval-api

# 检查依赖服务
docker ps | grep postgres
docker ps | grep redis

# 检查环境变量
docker exec ai-eval-api env | grep API_KEY
```

### 6.2 LLM调用失败

**症状**：评估请求返回LLM错误

**排查步骤**：
```bash
# 检查API Key配置
curl http://localhost:8000/api/v1/config

# 测试LLM连接
curl -X POST http://localhost:8000/api/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{"type":"general","user_input":"test","actual_output":"test"}'
```

### 6.3 监控无数据

**症状**：Grafana面板无数据

**排查步骤**：
```bash
# 检查Prometheus targets
curl http://localhost:9090/api/v1/targets

# 检查指标端点
curl http://localhost:8000/metrics

# 检查Pushgateway
curl http://localhost:9091/metrics
```

### 6.4 队列堆积

**症状**：Celery任务堆积，评估延迟高

**排查步骤**：
```bash
# 检查Worker状态
docker logs ai-eval-worker

# 检查RabbitMQ队列
curl http://localhost:15672/api/queues

# 增加Worker并发
docker-compose up -d --scale worker=3
```

---

## 七、运维命令

### 7.1 常用命令

```bash
# 查看所有服务状态
docker-compose ps

# 查看API日志
docker logs -f ai-eval-api

# 重启API服务
docker restart ai-eval-api

# 查看资源使用
docker stats

# 清理无用容器和镜像
docker system prune -f
```

### 7.2 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose up -d --build

# 或使用部署脚本
./deploy-prod.sh
```

---

## 八、安全建议

### 8.1 生产环境安全

1. **修改默认密码**：
   - PostgreSQL密码
   - RabbitMQ密码
   - Grafana密码

2. **API Key加密存储**：
   ```python
   from src.infra.security import encrypt_api_key, save_key
   
   # 生成加密密钥
   key = generate_key("your-password")
   save_key(key, "data/.key")
   
   # 加密API Key
   encrypted = encrypt_api_key("sk-your-key", key)
   ```

3. **启用HTTPS**：
   - 配置反向代理（Nginx/Traefik）
   - 使用SSL证书

4. **限制网络访问**：
   - 仅开放必要端口
   - 配置防火墙规则

---

## 九、性能优化

### 9.1 建议配置

| 服务 | 配置建议 |
|------|----------|
| API | 2-4实例，负载均衡 |
| Worker | 4-8并发，根据队列调整 |
| PostgreSQL | 连接池50-100 |
| Redis | 内存2GB+ |
| Prometheus | 保留15天数据 |

### 9.2 扩容方案

```bash
# 增加API实例
docker-compose up -d --scale api=3

# 增加Worker实例
docker-compose up -d --scale worker=5
```

---

## 十、联系支持

- **项目地址**：https://github.com/your-org/ai-eval-platform
- **问题反馈**：GitHub Issues
- **文档更新**：docs/目录