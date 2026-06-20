# AI Evaluation Platform API 文档

## 概述

AI 评测平台提供 RESTful API，支持 AI 模型的自动化评测、对比和分析。

### 基本信息

- **Base URL**: `https://api.ai-eval.com`
- **版本**: v1
- **认证**: API Key（Bearer Token）
- **格式**: JSON

### 认证

所有请求需要在 Header 中携带 API Key：

```http
Authorization: Bearer your-api-key
```

### 请求限制

| 计划 | 每分钟限制 | 每日限制 |
|------|-----------|----------|
| 免费版 | 10 | 100 |
| 专业版 | 100 | 10000 |
| 企业版 | 1000 | 无限 |

---

## API 架构

### 路由模块结构（v2.0）

API端点按业务领域拆分为独立路由模块：

| 路由模块 | 端点前缀 | 功能描述 |
|---------|---------|---------|
| `auth_routes.py` | `/api/v1/auth` | 用户认证（登录、刷新令牌） |
| `health_routes.py` | `/` | 健康检查与监控指标 |
| `evaluation_routes.py` | `/api/v1/evaluate` | 模型评测执行 |
| `records_routes.py` | `/api/v1/records` | 评测记录CRUD管理 |
| `evaluator_routes.py` | `/api/v1/evaluators` | 评估器配置与版本管理 |
| `model_routes.py` | `/api/v1/models` | 模型列表与对比分析 |
| `report_routes.py` | `/api/v1/reports` | 评测报告生成与导出 |
| `dataset_routes.py` | `/api/v1/datasets` | 数据集管理 |
| `calibration_routes.py` | `/api/v1/calibration` | 黄金数据集与校准 |
| `finetune_routes.py` | `/api/v1/finetune` | 模型微调训练管理 |
| `statistics_routes.py` | `/api/v1/statistics` | 统计分析与A/B测试 |
| `dashboard_routes.py` | `/api/v1/dashboard` | 仪表盘数据聚合 |

**路由聚合器**: `src/api/server.py` 负责注册所有路由模块，保持中间件和异常处理全局统一。

**公共模块**: `src/api/common.py` 提供共享函数（响应格式、输入验证、资源获取），避免循环依赖。

---

## API 端点

### 1. 评测 API

#### 单模型评测

**POST** `/v1/evaluate`

评测单个模型在指定数据集上的表现。

**请求参数**：

```json
{
  "model": "gpt-4",
  "dataset": "mmlu",
  "metrics": ["accuracy", "latency", "cost"],
  "custom_prompts": null,
  "parameters": {
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称 |
| dataset | string | 否 | 数据集名称 |
| metrics | array | 否 | 评测指标 |
| custom_prompts | array | 否 | 自定义提示词 |
| parameters | object | 否 | 模型参数 |

**响应示例**：

```json
{
  "request_id": "eval-abc123",
  "model": "gpt-4",
  "dataset": "mmlu",
  "metrics": {
    "accuracy": 0.92,
    "latency": 245.3,
    "cost": 0.05
  },
  "latency_ms": 245.3,
  "timestamp": 1705312800,
  "status": "completed",
  "details": {
    "questions_evaluated": 1000,
    "correct_answers": 920
  }
}
```

#### 异步评测

**POST** `/v1/evaluate/async`

提交异步评测任务。

**响应示例**：

```json
{
  "task_id": "task-xyz789",
  "status": "pending",
  "estimated_duration": 120
}
```

#### 获取评测结果

**GET** `/v1/evaluate/result/{task_id}`

获取异步评测结果。

**响应示例**：

```json
{
  "task_id": "task-xyz789",
  "status": "completed",
  "result": {
    "model": "gpt-4",
    "metrics": {
      "accuracy": 0.92
    }
  }
}
```

---

### 2. 对比 API

#### 模型对比

**POST** `/v1/compare`

对比多个模型的表现。

**请求参数**：

```json
{
  "models": [
    {"model": "gpt-4", "dataset": "mmlu"},
    {"model": "claude-3", "dataset": "mmlu"}
  ],
  "metrics": ["accuracy", "latency", "cost"]
}
```

**响应示例**：

```json
{
  "report_id": "compare-abc123",
  "models": ["gpt-4", "claude-3"],
  "dataset": "mmlu",
  "results": [
    {
      "model": "gpt-4",
      "metrics": {
        "accuracy": 0.92,
        "latency": 245.3
      }
    },
    {
      "model": "claude-3",
      "metrics": {
        "accuracy": 0.89,
        "latency": 198.7
      }
    }
  ],
  "rankings": {
    "gpt-4": 1,
    "claude-3": 2
  },
  "summary": {
    "best_accuracy": "gpt-4",
    "best_latency": "claude-3"
  }
}
```

---

### 3. 数据集 API

#### 获取数据集列表

**GET** `/v1/datasets`

**响应示例**：

```json
{
  "datasets": [
    {
      "id": "mmlu",
      "name": "MMLU",
      "category": "通用",
      "questions": 14000,
      "description": "多任务语言理解评测"
    },
    {
      "id": "humaneval",
      "name": "HumanEval",
      "category": "代码",
      "questions": 164,
      "description": "代码生成评测"
    }
  ]
}
```

#### 获取数据集详情

**GET** `/v1/datasets/{dataset_id}`

---

### 4. 模型 API

#### 获取模型列表

**GET** `/v1/models`

**响应示例**：

```json
{
  "models": [
    {
      "id": "gpt-4",
      "name": "GPT-4",
      "provider": "OpenAI",
      "capabilities": ["text", "code", "image"],
      "pricing": {
        "input": 0.03,
        "output": 0.06
      }
    }
  ]
}
```

---

### 5. 报告 API

#### 生成评测报告

**POST** `/v1/reports/generate`

**请求参数**：

```json
{
  "evaluation_ids": ["eval-abc123", "eval-def456"],
  "format": "pdf",
  "include_details": true
}
```

**响应示例**：

```json
{
  "report_id": "report-xyz789",
  "download_url": "https://api.ai-eval.com/reports/report-xyz789.pdf",
  "expires_at": 1705316400
}
```

---

### 6. 用户 API

#### 获取使用统计

**GET** `/v1/usage`

**响应示例**：

```json
{
  "total_calls": 12543,
  "remaining_quota": 87457,
  "monthly_cost": 8560.00,
  "daily_stats": [
    {
      "date": "2024-01-15",
      "calls": 523,
      "cost": 125.60
    }
  ]
}
```

#### 获取 API 密钥列表

**GET** `/v1/api-keys`

---

## 错误处理

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_API_KEY",
    "message": "API key is invalid or expired",
    "details": {
      "key_id": "abc123"
    }
  }
}
```

### 错误代码

| 代码 | HTTP 状态 | 说明 |
|------|-----------|------|
| INVALID_API_KEY | 401 | API 密钥无效 |
| PERMISSION_DENIED | 403 | 权限不足 |
| RATE_LIMIT_EXCEEDED | 429 | 请求频率超限 |
| MODEL_NOT_FOUND | 404 | 模型不存在 |
| DATASET_NOT_FOUND | 404 | 数据集不存在 |
| INTERNAL_ERROR | 500 | 内部错误 |

---

## SDK 使用

### Python SDK

```python
from ai_eval_sdk import Client

client = Client(api_key="your-api-key")

# 评测模型
result = await client.evaluate(
    model="gpt-4",
    dataset="mmlu",
    metrics=["accuracy", "latency"]
)

# 对比模型
report = await client.compare([
    {"model": "gpt-4", "dataset": "mmlu"},
    {"model": "claude-3", "dataset": "mmlu"}
])
```

### JavaScript SDK

```javascript
import { Client } from 'ai-eval-sdk';

const client = new Client({ apiKey: 'your-api-key' });

// 评测模型
const result = await client.evaluate({
  model: 'gpt-4',
  dataset: 'mmlu'
});

// 对比模型
const report = await client.compare([
  { model: 'gpt-4', dataset: 'mmlu' },
  { model: 'claude-3', dataset: 'mmlu' }
]);
```

---

## 最佳实践

### 1. 使用异步评测

对于大规模评测，推荐使用异步 API：

```python
# 提交多个异步任务
task_ids = []
for model in models:
    task_id = await client.evaluate_async(model=model, dataset="mmlu")
    task_ids.append(task_id)

# 等待结果
results = []
for task_id in task_ids:
    result = await client.get_result(task_id)
    results.append(result)
```

### 2. 缓存评测结果

避免重复评测同一模型：

```python
import hashlib

def get_cache_key(model, dataset):
    return hashlib.md5(f"{model}:{dataset}".encode()).hexdigest()

# 检查缓存
cache_key = get_cache_key("gpt-4", "mmlu")
cached_result = cache.get(cache_key)

if cached_result:
    return cached_result

# 执行评测
result = await client.evaluate(model="gpt-4", dataset="mmlu")
cache.set(cache_key, result, ttl=3600)
```

### 3. 错误处理

```python
from ai_eval_sdk import Client
import httpx

async def safe_evaluate():
    try:
        client = Client(api_key="your-api-key")
        result = await client.evaluate(model="gpt-4", dataset="mmlu")
        return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # 等待后重试
            await asyncio.sleep(60)
            return await safe_evaluate()
        raise
```

---

## 定价

### 按调用计费

| 操作 | 价格 |
|------|------|
| 单模型评测 | ¥0.10/次 |
| 模型对比（2个） | ¥0.20/次 |
| 报告生成 | ¥1.00/次 |

### 订阅计划

| 计划 | 月费 | 包含调用 | 超额价格 |
|------|------|----------|----------|
| 免费版 | ¥0 | 100 | ¥0.15/次 |
| 专业版 | ¥999 | 10000 | ¥0.08/次 |
| 企业版 | ¥9999 | 无限 | - |

---

## 支持

- **文档**: https://docs.ai-eval.com
- **API 状态**: https://status.ai-eval.com
- **问题反馈**: support@ai-eval.com
- **GitHub**: https://github.com/ai-eval
