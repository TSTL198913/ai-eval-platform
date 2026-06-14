# =====================================================================
# 部署验证命令速查
# =====================================================================

## 方式一：使用验证脚本（推荐�?
### Linux/Mac
```bash
# 赋予执行权限
chmod +x verify_deploy.sh

# 查看帮助
./verify_deploy.sh help

# 完整功能测试
./verify_deploy.sh test

# 只测�?API
./verify_deploy.sh api

# 查看日志
./verify_deploy.sh logs

# 健康检�?./verify_deploy.sh health
```

### Windows PowerShell
```powershell
# 查看帮助
.\verify_deploy.ps1 help

# 完整功能测试
.\verify_deploy.ps1 test

# 只测�?API
.\verify_deploy.ps1 api

# 查看日志
.\verify_deploy.ps1 logs
```

---

## 方式二：手动命令验证

### 1. 检查服务状�?
```bash
# Docker 容器状�?docker compose ps

# 或单独查�?docker ps | grep ai-eval
```

### 2. 健康检�?
```bash
# API 健康检�?curl http://localhost:8000/health

# Redis 健康检�?redis-cli ping
# �?docker compose exec redis redis-cli ping
```

### 3. API 功能测试

```bash
# 测试 1: 契约拦截（发送无效数据）
curl -X POST http://localhost:8000/api/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{"wrong": "data"}'

# 预期: 返回 CONTRACT_ERROR

# 测试 2: 正常评估请求
curl -X POST http://localhost:8000/api/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "id": "TEST_001",
    "type": "finance",
    "payload": {
      "case_id": "c1",
      "user_input": "10000元存一年定期，利率3%，利息多少？",
      "expected_output": "300�?
    }
  }'

# 测试 3: 异步任务提交
curl -X POST http://localhost:8000/api/v1/evaluate/async \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ASYNC_001",
    "type": "general",
    "payload": {
      "case_id": "c2",
      "user_input": "你好"
    }
  }'

# 查看异步任务结果（用返回�?task_id�?curl http://localhost:8000/api/v1/task/{task_id}/status
```

### 4. 查看日志

```bash
# 查看所有容器日志（实时�?docker compose logs -f

# 查看特定服务日志
docker compose logs -f api
docker compose logs -f worker

# 最�?100 �?docker compose logs --tail=100

# 保存日志到文�?docker compose logs > app.log
```

### 5. Celery Worker 测试

```bash
# 进入 worker 容器
docker compose exec worker bash

# 查看 worker 状�?celery -A src.workers.celery_app inspect stats

# 查看活跃任务
celery -A src.workers.celery_app inspect active

# 查看已注册任�?celery -A src.workers.celery_app inspect registered

# 手动触发任务（测试用�?celery -A src.workers.celery_app call src.worker.tasks.eval_case_task \
  --args '["TEST", {"case_id": "c1"}]'
```

### 6. Redis 检�?
```bash
# 进入 Redis 容器
docker compose exec redis bash

# 查看键数�?redis-cli dbsize

# 查看所有键
redis-cli keys "*"

# 查看任务队列长度
redis-cli llen celery

# 查看结果队列
redis-cli llen celery@1

# 监控 Redis 操作（实时）
redis-cli monitor
```

### 7. 数据库检查（如使�?PostgreSQL�?
```bash
# 进入数据库容�?docker compose exec postgres psql -U postgres

# 连接到数据库
\c ai_eval_db

# 查看�?\dt

# 查看评估记录
SELECT * FROM evaluations LIMIT 10;
```

---

## 快速诊�?
```bash
# 1. 确认所有服务运行中
docker compose ps

# 2. 查看资源使用
docker stats

# 3. 检查网络连�?docker compose exec api ping redis

# 4. 重启服务
docker compose restart

# 5. 完全重建（清除缓存）
docker compose down -v
docker compose build --no-cache
docker compose up -d

# 6. 查看完整错误日志
docker compose logs --tail=500 | grep -i error
```

---

## 常用端口

| 服务 | 端口 | 说明 |
|------|------|------|
| API | 8000 | FastAPI 服务 |
| Redis | 6379 | 缓存/消息队列 |
| PostgreSQL | 5432 | 数据库（可选） |
| Flower | 5555 | Celery 监控（如果启用）|
| Streamlit | 8501 | 前端界面（如果启用）|

---

## 常见问题排查

### API 返回 500 错误
```bash
# 查看 API 日志
docker compose logs api --tail=100

# 检查环境变�?docker compose exec api env | grep -i openai
```

### Worker 不处理任�?```bash
# 检�?worker 是否运行
docker compose ps worker

# 查看 worker 日志
docker compose logs worker --tail=100

# 检�?Redis 连接
docker compose exec worker ping redis
```

### 任务卡住不执�?```bash
# 查看任务队列
redis-cli llen celery

# 查看 worker 状�?docker compose exec worker celery -A src.workers.celery_app inspect stats

# 查看是否有死�?docker compose exec worker celery -A src.workers.celery_app inspect active
```
