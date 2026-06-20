# AI Evaluation Platform SDK

一行代码完成 AI 模型评测。

## 安装

```bash
pip install ai-eval-sdk
```

## 快速开始

### 1. 基础评测

```python
from ai_eval_sdk import evaluate

# 一行代码评测模型
result = evaluate("gpt-4", "mmlu", api_key="your-api-key")
print(result)
# Output: EvaluationResult(model=gpt-4, metrics=accuracy=0.92, latency=245.3ms)
```

### 2. 模型对比

```python
from ai_eval_sdk import compare

# 对比多个模型
report = compare([
    {"model": "gpt-4", "dataset": "mmlu"},
    {"model": "claude-3", "dataset": "mmlu"}
], api_key="your-api-key")

report.print_summary()
```

输出：
```
============================================================
Model Comparison Report - mmlu
============================================================
#1 gpt-4                | accuracy=0.92 | 245.3ms
#2 claude-3             | accuracy=0.89 | 198.7ms
============================================================
```

### 3. 异步评测

```python
from ai_eval_sdk import Client
import asyncio

async def main():
    client = Client(api_key="your-api-key")

    # 提交异步任务
    task_id = await client.evaluate_async(model="gpt-4", dataset="mmlu")

    # 获取结果
    result = await client.get_result(task_id)
    print(result)

    await client.close()

asyncio.run(main())
```

## 主要功能

### 评测指标

| 指标 | 说明 | 适用场景 |
|------|------|----------|
| `accuracy` | 准确率 | 问答、选择题 |
| `latency` | 响应延迟 | 性能评测 |
| `cost` | 成本 | 经济性评测 |
| `pass_rate` | 通过率 | 代码评测 |
| `relevance` | 相关性 | 生成质量 |

### 数据集

| 数据集 | 说明 | 模型类型 |
|--------|------|----------|
| `mmlu` | 多任务语言理解 | 通用 LLM |
| `humaneval` | 代码生成 | 代码模型 |
| `gsm8k` | 数学推理 | 数学模型 |
| `truthfulqa` | 真实性 | 对话模型 |

### 自定义评测

```python
from ai_eval_sdk import Client

async with Client(api_key="your-api-key") as client:
    # 自定义提示词
    custom_prompts = [
        "What is the capital of France?",
        "Explain quantum computing.",
    ]

    result = await client.evaluate(
        model="gpt-4",
        custom_prompts=custom_prompts,
        metrics=["accuracy", "relevance"]
    )
```

## API 参考

### Client

```python
Client(
    api_key: str,           # API 密钥
    base_url: str,          # API 地址（默认 https://api.ai-eval.com）
    timeout: float = 30.0,  # 超时时间
    max_retries: int = 3    # 最大重试次数
)
```

### evaluate()

```python
await client.evaluate(
    model: str,                     # 模型名称
    dataset: str | None = None,     # 数据集名称
    metrics: list[str] = ["accuracy"],  # 评测指标
    custom_prompts: list[str] | None = None  # 自定义提示词
) -> EvaluationResult
```

### compare()

```python
await client.compare(
    models: list[dict],     # 模型列表
    dataset: str | None,    # 数据集名称
    metrics: list[str]      # 评测指标
) -> ComparisonReport
```

## 使用场景

### 1. 模型选型

```python
# 对比候选模型，选择最佳方案
report = compare([
    {"model": "gpt-4", "dataset": "mmlu"},
    {"model": "gpt-3.5-turbo", "dataset": "mmlu"},
    {"model": "claude-3", "dataset": "mmlu"}
])

# 根据准确率和成本决策
best_model = min(report.results, key=lambda r: r.metrics["cost"] / r.metrics["accuracy"])
print(f"推荐模型: {best_model.model}")
```

### 2. 性能监控

```python
# 定期评测模型性能
import schedule

def monitor_model():
    result = evaluate("gpt-4", "mmlu")
    if result.metrics["accuracy"] < 0.90:
        alert("模型性能下降")

schedule.every().day.at("09:00").do(monitor_model)
```

### 3. A/B 测试

```python
# A/B 测试两个模型版本
async def ab_test():
    client = Client(api_key="your-api-key")

    result_a = await client.evaluate(model="gpt-4-v1", dataset="custom")
    result_b = await client.evaluate(model="gpt-4-v2", dataset="custom")

    if result_b.metrics["accuracy"] > result_a.metrics["accuracy"]:
        print("新版本表现更好，建议升级")

    await client.close()
```

## 最佳实践

### 1. 使用异步客户端

```python
# 推荐：异步并发评测
async with Client(api_key="your-api-key") as client:
    tasks = [
        client.evaluate(model=m, dataset="mmlu")
        for m in ["gpt-4", "claude-3", "gemini"]
    ]
    results = await asyncio.gather(*tasks)
```

### 2. 缓存结果

```python
# 缓存评测结果，避免重复调用
import functools

@functools.lru_cache(maxsize=100)
def cached_evaluate(model, dataset):
    return evaluate(model, dataset)
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
        if e.response.status_code == 401:
            print("API 密钥无效")
        elif e.response.status_code == 429:
            print("请求频率超限，请稍后重试")
        return None
    finally:
        await client.close()
```

## 定价

| 计划 | 价格 | 包含 |
|------|------|------|
| 免费版 | ¥0 | 100 次评测/月 |
| 专业版 | ¥999/月 | 10000 次评测/月 |
| 企业版 | ¥9999/月 | 无限评测 + SLA |

## 支持

- 文档：https://docs.ai-eval.com
- API 参考：https://api.ai-eval.com/docs
- GitHub：https://github.com/ai-eval/sdk
- 问题反馈：support@ai-eval.com

## 许可证

MIT License
