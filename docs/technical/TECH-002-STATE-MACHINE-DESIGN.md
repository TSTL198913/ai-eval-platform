# 技术规范文档 - 评估器状态机设计 (v2.1.0)

**文档版本**: v2.1.0
**创建日期**: 2026-07-01
**作者**: AI评测系统架构师
**状态**: 正式版

---

## 目录

1. [概述](#1-概述)
2. [状态机设计](#2-状态机设计)
3. [字段规范](#3-字段规范)
4. [方法职责](#4-方法职责)
5. [状态转换规则](#5-状态转换规则)
6. [向后兼容策略](#6-向后兼容策略)
7. [代码检查清单](#7-代码检查清单)

---

## 1. 概述

本文档定义AI评测系统v2.1.0版本的状态机设计规范，旨在消除语义重复、统一状态管理、确保评估结果的可信度和可追溯性。

### 设计目标

| 目标 | 说明 |
|------|------|
| 消除语义重复 | `is_valid` 和 `evaluation_status` 语义重叠，统一为 `evaluation_status` |
| 状态明确 | 四态枚举清晰区分"评估成功"、"部分评估"、"无法评估"、"评估失败" |
| 置信度量化 | 通过置信度和置信度等级量化评估结果可靠性 |
| 向后兼容 | `is_valid` 作为计算属性保留，确保旧代码不破坏 |

---

## 2. 状态机设计

### 2.1 EvaluatorStatus 枚举

```python
class EvaluatorStatus(str, Enum):
    SUCCESS = "success"           # 评估正常完成，返回有效分数
    CANNOT_EVALUATE = "cannot_evaluate"  # 无法评估（缺少必要输入）
    PARTIAL = "partial"           # 部分评估（降级评估）
    ERROR = "error"               # 评估失败（业务规则不满足）
```

### 2.2 状态含义详解

| 状态 | 含义 | 是否有分数 | 是否有置信度 | 典型场景 |
|------|------|------------|--------------|----------|
| SUCCESS | 评估正常完成 | 有 | 有（通常≥0.7） | LLM完整评估通过 |
| PARTIAL | 部分评估 | 有 | 有（通常0.3-0.7） | LLM超时后Embedding降级 |
| CANNOT_EVALUATE | 无法评估 | 无 | 无 | 缺少必要输入字段 |
| ERROR | 评估失败 | 无 | 无（0.0） | 业务规则不满足、系统异常 |

### 2.3 状态转换流程图

```
评估请求进入
     │
     ▼
┌───────────────┐
│  输入验证     │
└──────┬────────┘
       │
       ├─ 验证失败 ──► CANNOT_EVALUATE
       │
       ▼
┌───────────────┐
│  执行评估     │
└──────┬────────┘
       │
       ├─ 成功 ──► SUCCESS
       │
       ├─ 降级 ──► PARTIAL
       │
       └─ 失败 ──► ERROR
```

---

## 3. 字段规范

### 3.1 DomainResponse 字段定义

```python
class DomainResponse(BaseModel):
    text: str | None = None                      # 评估文本描述
    score: float | None = None                   # 评估分数 (0.0-1.0)
    evaluation_status: EvaluatorStatus = EvaluatorStatus.SUCCESS  # 评估状态
    confidence: float | None = Field(            # 评估置信度 (0.0-1.0)
        default=None, ge=0.0, le=1.0
    )
    confidence_level: ConfidenceLevel | None = None  # 置信度等级（自动计算）
    error: str | None = None                     # 错误信息
    metadata: dict | None = None                 # 元数据
    data: Any | None = None                      # 扩展数据

    @property
    def is_valid(self) -> bool:
        """向后兼容属性，基于 evaluation_status 推导"""
        return self.evaluation_status != EvaluatorStatus.ERROR
```

### 3.2 字段约束规则

| 字段 | 约束 | 说明 |
|------|------|------|
| `score` | 仅在 SUCCESS/PARTIAL 状态有值 | ERROR/CANNOT_EVALUATE 状态时为 None |
| `confidence` | 仅在 SUCCESS/PARTIAL 状态有值 | CANNOT_EVALUATE 状态时为 None |
| `confidence_level` | 由 confidence 自动计算 | 可手动覆盖（特殊场景） |
| `error` | 仅在 ERROR 状态有值 | 其他状态时为 None |
| `evaluation_status` | 必填，默认 SUCCESS | 所有响应必须设置 |

### 3.3 置信度等级计算规则

```python
@model_validator(mode="after")
def compute_confidence_level(cls, values: "DomainResponse") -> "DomainResponse":
    if values.confidence is not None and values.confidence_level is None:
        if values.confidence >= 0.9:
            values.confidence_level = ConfidenceLevel.HIGH
        elif values.confidence >= 0.7:
            values.confidence_level = ConfidenceLevel.MEDIUM
        elif values.confidence >= 0.5:
            values.confidence_level = ConfidenceLevel.LOW
        else:
            values.confidence_level = ConfidenceLevel.VERY_LOW
    return values
```

| 置信度范围 | 等级 | 评估方式 | 数据完整性 |
|------------|------|----------|------------|
| ≥0.9 | HIGH | LLM完整评估 | 完整输入+参考答案+测试用例 |
| ≥0.7 | MEDIUM | LLM部分评估 | 部分输入+参考答案 |
| ≥0.5 | LOW | Embedding匹配 | 仅输入文本 |
| <0.5 | VERY_LOW | 语法检查 | 仅代码结构 |

---

## 4. 方法职责

### 4.1 响应工厂方法

| 方法 | 职责 | 返回状态 | 置信度默认值 |
|------|------|----------|--------------|
| `create_success_response()` | 创建成功响应 | SUCCESS | 0.95（完整）/ 0.85（非完整） |
| `create_error_response()` | 创建错误响应 | ERROR | 0.0 |
| `create_cannot_evaluate_response()` | 创建无法评估响应 | CANNOT_EVALUATE | None |
| `create_partial_response()` | 创建部分评估响应 | PARTIAL | 根据覆盖率计算 |

### 4.2 部分评估置信度计算

```python
# 根据评估方法和维度覆盖率计算默认置信度
if evaluation_method == "llm":
    confidence = 0.7 * coverage_ratio + 0.25  # 0.25-0.95
elif evaluation_method == "embedding":
    confidence = 0.5 * coverage_ratio + 0.3  # 0.3-0.80
else:  # heuristic
    confidence = 0.3 * coverage_ratio + 0.2  # 0.2-0.50
```

### 4.3 评估入口方法

| 方法 | 职责 | 异常处理 |
|------|------|----------|
| `evaluate()` | 同步评估入口 | 熔断、降级、异常捕获 |
| `evaluate_async()` | 异步评估入口 | 熔断、降级、异常捕获 |
| `safe_evaluate()` | 安全评估入口 | 业务异常传播，非业务异常转换 |
| `safe_evaluate_async()` | 安全异步评估入口 | 业务异常传播，非业务异常转换 |

---

## 5. 状态转换规则

### 5.1 EvaluatorStatus → EvaluationRecordStatus 映射

| EvaluatorStatus | EvaluationRecordStatus | 说明 |
|-----------------|------------------------|------|
| SUCCESS | PASSED | 正常评估通过 |
| PARTIAL | PASSED | 降级评估，标记为部分评估 |
| CANNOT_EVALUATE | ERROR | 系统错误，无法评估 |
| ERROR | FAILED/ERROR | 根据 error_code 判断 |

### 5.2 is_valid 推导规则

| evaluation_status | is_valid | 说明 |
|-------------------|----------|------|
| SUCCESS | True | 评估成功，有有效分数 |
| PARTIAL | True | 部分评估，结果有效 |
| CANNOT_EVALUATE | False | 无法评估，无有效结果 |
| ERROR | False | 评估失败，结果无效 |

---

## 6. 向后兼容策略

### 6.1 is_valid 计算属性

`is_valid` 从字段改为计算属性，确保旧代码无需修改：

```python
@property
def is_valid(self) -> bool:
    return self.evaluation_status != EvaluatorStatus.ERROR
```

### 6.2 序列化兼容性

计算属性会被包含在 `model_dump()` 输出中，确保 API 响应格式不变。

### 6.3 创建响应时的兼容性

移除 `is_valid` 参数后，旧代码可能仍然传入该参数，但 Pydantic 的 `model_config = {"extra": "allow"}` 会忽略未知参数。

---

## 7. 代码检查清单

### 7.1 新评估器开发检查清单

- [ ] 继承 `BaseEvaluator`
- [ ] 实现 `_do_evaluate()` 方法
- [ ] 使用响应工厂方法创建响应
- [ ] 设置正确的 `evaluation_status`
- [ ] 设置合理的 `confidence` 值
- [ ] 不要直接设置 `is_valid`

### 7.2 代码审查检查清单

- [ ] 所有 `DomainResponse` 创建使用工厂方法
- [ ] 不直接修改 `__dict__`
- [ ] 使用 `evaluation_status` 枚举判断而非字符串
- [ ] 降级评估返回 `PARTIAL` 状态
- [ ] 日志记录包含 `evaluation_status` 和 `confidence`

### 7.3 测试覆盖检查清单

- [ ] SUCCESS 状态测试
- [ ] PARTIAL 状态测试
- [ ] CANNOT_EVALUATE 状态测试
- [ ] ERROR 状态测试
- [ ] 置信度自动计算测试
- [ ] 状态转换规则测试
- [ ] 向后兼容性测试（is_valid 属性）

---

## 附录：核心文件位置

| 文件 | 职责 |
|------|------|
| `src/schemas/evaluation.py` | DomainResponse、EvaluatorStatus、ConfidenceLevel 定义 |
| `src/domain/evaluators/base.py` | BaseEvaluator、响应工厂方法 |
| `src/engine.py` | 状态转换逻辑 |
| `tests/unit/test_evaluation_status_machine.py` | 状态机测试用例 |