# AI 评测平台增强功能使用指南

> **版本**: 1.0
> **最后更新**: 2026-06-23
> **适用范围**: AI Eval Platform v2.x

本文档介绍平台增强后的四大核心能力：**标准指标库**、**第三方评测框架适配**、**人工标注系统**、**可视化与报告**。

---

## 1. 标准指标评估器（Standard Metrics）

### 1.1 概述

平台已封装业界主流的文本生成评测指标，通过 `EvaluatorFactory` 统一注册，调用方式与内置评估器完全一致。

### 1.2 支持的指标

| 指标名称 | 适用场景 | 输出区间 | 依赖 |
|---|---|---|---|
| `BLEU-4` / `BLEU-2` | 机器翻译质量 | [0, 1] | sacrebleu（本地降级可用） |
| `ROUGE-1` / `ROUGE-2` / `ROUGE-L` | 摘要质量 | [0, 1] | rouge-score（本地降级可用） |
| `METEOR` | 综合翻译质量（考虑同义词） | [0, 1] | nltk + wordnet |
| `Levenshtein` | 短文本精确匹配 | [0, 1] | 纯 Python |
| `CosineSimilarity` | 语义相似度 | [0, 1] | Sentence-BERT |
| `F1-Token` | QA 事实一致性 | [0, 1] | 纯 Python |

### 1.3 API 调用示例

#### 单指标评估

```bash
POST /api/v1/evaluate
{
  "id": "eval-001",
  "type": "standard_metric",
  "payload": {
    "user_input": "法国的首都是哪里？",
    "actual_output": "巴黎是法国的首都。",
    "expected_output": "法国的首都是巴黎。",
    "metric": "BLEU-4"
  }
}
```

**响应**：
```json
{
  "code": 0,
  "data": {
    "status": "success",
    "evaluation_status": "passed",
    "data": {
      "is_valid": true,
      "score": 0.6543,
      "data": {
        "metric": "BLEU-4",
        "description": "基于 4-gram 精度的机器翻译质量评估标准",
        "actual_output": "巴黎是法国的首都。",
        "expected_output": "法国的首都是巴黎。"
      }
    }
  }
}
```

#### 多指标综合评估

```bash
POST /api/v1/evaluate
{
  "id": "eval-002",
  "type": "multi_metric",
  "payload": {
    "user_input": "...",
    "actual_output": "...",
    "expected_output": "...",
    "metrics": ["BLEU-4", "ROUGE-L", "F1-Token", "Levenshtein"]
  }
}
```

**响应**包含每个指标的独立分数与综合分（算术均值）：
```json
{
  "data": {
    "is_valid": true,
    "score": 0.78,
    "data": {
      "metric_count": 4,
      "composite_score": 0.78,
      "metrics": {
        "BLEU-4": {"score": 0.65, "description": "..."},
        "ROUGE-L": {"score": 0.82, "description": "..."},
        ...
      }
    }
  }
}
```

### 1.4 编程调用

```python
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.standard_metric_evaluator import (
    StandardMetricEvaluator, MultiMetricEvaluator
)
from src.schemas.evaluation import EvaluationSchema

# 通过工厂
evaluator = EvaluatorFactory.create("standard_metric", client=None)
result = evaluator.evaluate(EvaluationSchema(
    type="standard_metric",
    payload={
        "user_input": "...",
        "actual_output": "...",
        "expected_output": "...",
        "metric": "ROUGE-L"
    }
))
print(f"Score: {result.score}")
```

---

## 2. 第三方评测框架适配（RAGAS / DeepEval）

### 2.1 设计理念

平台采用**适配器模式**封装 RAGAS 与 DeepEval，自动检测依赖可用性，无缝降级到本地实现，确保生产环境稳定性。

### 2.2 RAGAS 适配器

**支持指标**：
- `faithfulness`：答案对检索上下文的忠实度（无幻觉）
- `answer_relevancy`：答案与问题的相关度
- `context_precision`：检索上下文的精度
- `context_recall`：检索上下文的召回率
- `answer_correctness`：答案正确性
- `answer_similarity`：答案与 ground truth 的语义相似度

**调用示例**：
```bash
POST /api/v1/evaluate
{
  "id": "ragas-001",
  "type": "ragas",
  "payload": {
    "user_input": "什么是 RAG?",
    "answer": "RAG 是检索增强生成",
    "context": "RAG 是 Retrieval-Augmented Generation 的缩写",
    "ground_truth": "RAG 是检索增强生成技术",
    "metrics": ["faithfulness", "answer_relevancy", "context_precision"]
  }
}
```

**降级机制**：未安装 `ragas` 时自动使用本地 Jaccard + Embedding 实现，并在 `data.implementation` 字段标注 `"local"`。

### 2.3 DeepEval 适配器

**支持指标**：
- `hallucination`：幻觉检测（hedging 词识别 + 上下文覆盖度）
- `bias`：偏见检测
- `toxicity`：有害性检测
- `answer_relevancy`：答案相关性

**调用示例**：
```bash
POST /api/v1/evaluate
{
  "id": "deepeval-001",
  "type": "deepeval",
  "payload": {
    "user_input": "Python 是什么？",
    "answer": "Python 是一种编程语言",
    "context": "Python 是一种广泛使用的解释型编程语言",
    "ground_truth": "Python 是一种解释型编程语言"
  }
}
```

### 2.4 安装官方库以启用完整功能

```bash
# 安装 RAGAS（启用 LLM 增强评估）
pip install ragas datasets

# 安装 DeepEval
pip install deepeval
```

**提示**：未安装时不影响基本功能，平台自动使用本地实现。

---

## 3. 人工标注系统

### 3.1 系统架构

```
┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│ 标注任务API │───>│ AnnotationSvc │───>│ SQLite/PG DB │
└─────────────┘    └──────────────┘    └──────────────┘
                           │
                           ├──> Cohen's Kappa 一致性
                           ├──> 黄金样本校准
                           └──> 标注员绩效统计
```

### 3.2 数据模型

| 表名 | 用途 |
|---|---|
| `annotation_tasks` | 标注任务主表 |
| `annotation_results` | 标注结果表（每标注员一条） |
| `annotation_agreements` | 一致性计算结果表 |

### 3.3 完整工作流

#### 步骤 1：创建标注任务

```bash
POST /api/v1/annotations/tasks
{
  "case_id": "case_001",
  "evaluator_type": "ragas",
  "question": "什么是 RAG?",
  "actual_output": "RAG 是检索增强生成",
  "expected_output": "RAG 是检索增强生成技术",
  "context": "RAG 是 Retrieval-Augmented Generation 的缩写",
  "required_annotators": 2,    # 双盲标注
  "priority": 8
}
```

#### 步骤 2：标注员提交标注

```bash
POST /api/v1/annotations/tasks/{task_id}/results
{
  "annotator_id": "ann_001",
  "annotator_name": "张三",
  "score": 0.85,
  "label": "accurate",
  "comment": "回答准确",
  "dimensions": {
    "准确性": 0.9,
    "完整性": 0.8
  },
  "tags": ["good_response"],
  "time_spent_seconds": 120
}
```

> **任务状态自动推进**：`pending` → `in_progress`（首标注后）→ `completed`（达到 `required_annotators` 后）

#### 步骤 3：审核标注

```bash
POST /api/v1/annotations/results/{result_id}/review
{
  "reviewer_id": "rev_001",
  "review_comment": "标注规范",
  "is_valid": true
}
```

#### 步骤 4：黄金样本校准

用于评估标注员质量，偏差 < 0.1 视为通过。

```bash
POST /api/v1/annotations/tasks/{task_id}/golden
{
  "annotator_id": "ann_001",
  "score": 0.9
}
```

**响应**：
```json
{
  "data": {
    "task_id": 1,
    "annotator_id": "ann_001",
    "submitted_score": 0.9,
    "true_score": 0.9,
    "deviation": 0.0,
    "pass": true,
    "needs_retraining": false
  }
}
```

#### 步骤 5：计算一致性（Cohen's Kappa）

```bash
GET /api/v1/annotations/agreement/ragas
```

**响应**：
```json
{
  "data": {
    "evaluator_type": "ragas",
    "sample_size": 50,
    "kappa_score": 0.82,
    "agreement_level": "almost_perfect",
    "annotator_count": 5,
    "metric_payload": {
      "pair_count": 10,
      "kappas": [0.85, 0.79, ...]
    }
  }
}
```

**Kappa 解释**：
| 范围 | 等级 |
|---|---|
| < 0 | worse_than_chance |
| 0 ~ 0.2 | poor |
| 0.21 ~ 0.4 | fair |
| 0.41 ~ 0.6 | moderate |
| 0.61 ~ 0.8 | substantial |
| 0.81 ~ 1.0 | almost_perfect |

#### 步骤 6：标注员绩效统计

```bash
GET /api/v1/annotations/annotators/ann_001/stats
```

**响应**：
```json
{
  "data": {
    "annotator_id": "ann_001",
    "annotator_name": "张三",
    "total_annotations": 100,
    "valid_annotations": 95,
    "avg_score": 0.82,
    "avg_time_seconds": 95.5,
    "golden_count": 10,
    "golden_pass_rate": 0.9
  }
}
```

---

## 4. 可视化与报告

### 4.1 可视化服务

`src/infra/analytics/visualization_service.py` 提供 5 种图表数据生成：

| 图表 | 方法 | 用途 |
|---|---|---|
| 雷达图 | `radar_chart()` | 多模型/多指标对比 |
| 趋势图 | `trend_chart()` | 时间序列评分变化 |
| 分布图 | `distribution_chart()` | 分数分布直方图 |
| 箱线图 | `boxplot_data()` | 异常值检测 |
| 热力图 | `heatmap_data()` | 模型×指标交叉分析 |

**编程调用**：
```python
from src.infra.analytics.visualization_service import VisualizationService

viz = VisualizationService()
data = viz.radar_chart(
    metrics=["accuracy", "completeness", "relevance"],
    series={
        "gpt-4": {"accuracy": 0.92, "completeness": 0.85, "relevance": 0.90},
        "deepseek": {"accuracy": 0.88, "completeness": 0.82, "relevance": 0.87}
    }
)
```

### 4.2 报告生成

`src/infra/analytics/report_generator.py` 支持三种格式：

```bash
GET /api/v1/reports/generate?format=html
GET /api/v1/reports/generate?format=json
GET /api/v1/reports/generate?format=markdown
```

**HTML 报告特性**：
- 嵌入式交互图表（基于 Recharts）
- 模型对比表
- 错误案例高亮
- 标注一致性可视化

---

## 5. 错误码参考

| 错误码 | HTTP | 含义 |
|---|---|---|
| `INVALID_INPUT` | 400 | user_input/text 为空 |
| `INVALID_EXPECTED` | 400 | expected_output 为空 |
| `UNSUPPORTED_METRIC` | 400 | 不支持的标准指标 |
| `METRIC_COMPUTE_ERROR` | 500 | 指标计算异常 |
| `MISSING_QUESTION` | 400 | RAGAS 缺少 question |
| `MISSING_ANSWER` | 400 | RAGAS/DeepEval 缺少 answer |
| `INVALID_SCORE` | 422 | 标注分数不在 [0, 1] 区间 |
| `TASK_NOT_FOUND` | 404 | 标注任务不存在 |
| `DUPLICATE_ANNOTATION` | 409 | 同一标注员重复标注 |

---

## 6. 测试

### 6.1 单元测试

```bash
# 标准指标
pytest tests/unit/test_standard_metrics.py -v
pytest tests/unit/test_standard_metric_evaluator.py -v

# RAGAS / DeepEval
pytest tests/unit/test_ragas_evaluator.py -v
pytest tests/unit/test_deepeval_evaluator.py -v

# 标注服务
pytest tests/unit/test_annotation_service.py -v

# 可视化/报告
pytest tests/unit/test_visualization_service.py -v
pytest tests/unit/test_report_generator.py -v
```

### 6.2 集成测试

```bash
# 标注 API
pytest tests/integration/api/test_annotation_api_integration.py -v

# 新评估器 API
pytest tests/integration/api/test_new_evaluator_api_integration.py -v
```

### 6.3 测试覆盖场景

每个组件均覆盖：
- **正向场景**：合法输入、预期输出
- **负向场景**：非法输入、错误处理
- **边界场景**：空值、极值
- **异常场景**：依赖缺失、超时
- **依赖测试**：外部服务 Mock 验证

---

## 7. 架构合规

所有新组件均遵循项目架构规范：

- ✅ **分层约束**：API → Service → Evaluator → Domain → Infra
- ✅ **工厂注册**：新评估器通过 `@EvaluatorFactory.register()` 注册
- ✅ **错误处理**：所有异常返回 `BasePlatformError` 或业务自定义异常
- ✅ **类型注解**：公共方法 100% 类型覆盖
- ✅ **向后兼容**：未破坏现有 API 协议

---

## 8. 常见问题（FAQ）

**Q1: 未安装 sacrebleu/rouge-score 怎么办？**
A: 平台自动降级到本地实现，精度略低于官方实现但保证功能可用。

**Q2: 如何批量创建标注任务？**
A: 使用 `POST /api/v1/annotations/tasks/bulk` 端点，单次最多 500 个。

**Q3: 标注结果如何修改？**
A: 当前版本不支持修改（保证数据真实性），如需修正请通过审核流程标为 `is_valid=false`。

**Q4: RAGAS 与平台内置 evaluator 冲突吗？**
A: 不冲突。`type` 字段路由到不同评估器，可并存使用。

**Q5: 如何集成自研指标？**
A: 实现 `StandardMetric` 抽象基类，通过 `MetricRegistry.register()` 注册即可。

---

## 9. 更新日志

| 日期 | 版本 | 内容 |
|---|---|---|
| 2026-06-23 | 1.0 | 初始版本：标准指标库、RAGAS/DeepEval 适配、人工标注、可视化报告 |
