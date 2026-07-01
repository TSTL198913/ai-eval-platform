# 技术规范文档 - AI评测系统质量改进 (v2.1.0)

**文档版本**: v2.1.0
**创建日期**: 2026-07-01
**作者**: AI评测系统架构师
**状态**: 正式版

---

## 目录

1. [概述](#1-概述)
2. [评估器状态机](#2-评估器状态机)
3. [置信度系统](#3-置信度系统)
4. [安全评估入口](#4-安全评估入口)
5. [Pydantic模型规范](#5-pydantic模型规范)
6. [日志记录规范](#6-日志记录规范)
7. [配置管理规范](#7-配置管理规范)
8. [架构约束](#8-架构约束)

---

## 1. 概述

本文档描述AI评测系统v2.1.0版本的核心技术改进，旨在解决以下关键问题：

| 问题类别 | 具体问题 | 解决方案 |
|----------|----------|----------|
| 评估结果可信度 | 无法区分"评估失败"与"无法评估" | 引入EvaluatorStatus状态机 |
| 评估结果可靠性 | 无法量化评估结果可信度 | 引入ConfidenceLevel置信度系统 |
| 异常处理 | 异常处理不一致，日志缺失 | 引入safe_evaluate统一入口 |
| 代码规范 | Pydantic模型字段修改不规范 | 强制使用model_validator和model_copy |
| 日志可读性 | 日志记录不完整，置信度读取路径错误 | 结构化日志记录，直接读取response.confidence |

---

## 2. 评估器状态机

### 2.1 状态定义

```python
from enum import Enum

class EvaluatorStatus(Enum):
    SUCCESS = "success"           # 评估正常完成，返回有效分数
    CANNOT_EVALUATE = "cannot_evaluate"  # 无法评估（缺少必要输入）
    PARTIAL = "partial"           # 部分评估（降级评估）
    ERROR = "error"               # 评估失败（业务规则不满足）
```

### 2.2 状态转换规则

```
                    ┌─────────────────┐
                    │   评估开始       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  执行_do_evaluate │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ CANNOT_EVAL │      │   PARTIAL   │      │  SUCCESS    │
│ _UATE       │      │             │      │             │
└──────┬──────┘      └──────┬──────┘      └──────┬──────┘
       │                    │                    │
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│   ERROR     │      │   PASSED    │      │   PASSED    │
│ (系统错误)  │      │ (带降级标记) │      │ (正常通过)  │
└─────────────┘      └─────────────┘      └─────────────┘
```

### 2.3 DomainResponse扩展

```python
class DomainResponse(BaseModel):
    is_valid: bool = True
    text: str | None = None
    score: float | None = None
    evaluation_status: EvaluatorStatus = EvaluatorStatus.SUCCESS
    confidence: float | None = Field(...)
    confidence_level: ConfidenceLevel | None = Field(...)
    error: str | None = None
    metadata: dict | None = None
    data: Any | None = None
```

### 2.4 状态映射（EvaluatorStatus → EvaluationRecordStatus）

| EvaluatorStatus | EvaluationRecordStatus | 说明 |
|-----------------|------------------------|------|
| SUCCESS | PASSED | 正常评估通过 |
| PARTIAL | PASSED | 降级评估，标记置信度 |
| CANNOT_EVALUATE | ERROR | 系统错误，无法评估 |
| ERROR | FAILED/ERROR | 根据error_code判断 |

---

## 3. 置信度系统

### 3.1 置信度等级定义

```python
class ConfidenceLevel(Enum):
    HIGH = "high"         # 完整数据 + LLM评估
    MEDIUM = "medium"     # 部分数据 + LLM评估
    LOW = "low"           # 部分数据 + Embedding
    VERY_LOW = "very_low" # 仅语法检查
```

### 3.2 置信度计算规则

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

### 3.3 置信度与评估方式对应关系

| 置信度范围 | 等级 | 评估方式 | 数据完整性 |
|------------|------|----------|------------|
| ≥0.9 | HIGH | LLM完整评估 | 完整输入+参考答案+测试用例 |
| ≥0.7 | MEDIUM | LLM部分评估 | 部分输入+参考答案 |
| ≥0.5 | LOW | Embedding匹配 | 仅输入文本 |
| <0.5 | VERY_LOW | 语法检查 | 仅代码结构 |

---

## 4. 安全评估入口

### 4.1 同步安全评估

```python
def safe_evaluate(self, request: EvaluationSchema) -> DomainResponse:
    try:
        response = self.evaluate(request)
        if response is None:
            raise ValueError("评估器返回 None")
        self._log_evaluation_result(request, response)
        return response
    except BasePlatformError:
        raise  # 业务异常向上传播
    except Exception as e:
        logger.error(f"安全评估捕获异常: {e}", exc_info=True)
        error_response = self.create_error_response(
            error_message=f"安全评估失败: {str(e)}", 
            error_code="SYSTEM_ERROR"
        )
        self._log_evaluation_result(request, error_response)
        return error_response
```

### 4.2 异步安全评估

```python
async def safe_evaluate_async(self, request: EvaluationSchema) -> DomainResponse:
    try:
        response = await self.evaluate_async(request)
        if response is None:
            raise ValueError("评估器返回 None")
        self._log_evaluation_result(request, response)
        return response
    except BasePlatformError:
        raise
    except Exception as e:
        logger.error(f"安全评估捕获异常: {e}", exc_info=True)
        error_response = self.create_error_response(
            error_message=f"安全评估失败: {str(e)}", 
            error_code="SYSTEM_ERROR"
        )
        self._log_evaluation_result(request, error_response)
        return error_response
```

### 4.3 异常分层处理

```
┌─────────────────────────────────────────────────────────────┐
│                    safe_evaluate入口                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
           ┌────────────────┴────────────────┐
           │                                 │
           ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐
│ BasePlatformError │               │   其他Exception   │
│ (业务异常)       │               │ (系统异常)       │
└────────┬────────┘               └────────┬────────┘
         │                                 │
         ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐
│  向上传播       │               │  创建Error       │
│  由engine处理   │               │  Response       │
└─────────────────┘               └─────────────────┘
```

---

## 5. Pydantic模型规范

### 5.1 禁止直接修改__dict__

**错误做法**:
```python
# ❌ 禁止
response = DomainResponse(...)
response.__dict__["confidence_level"] = ConfidenceLevel.HIGH
```

**正确做法**:
```python
# ✅ 正确 - 使用model_validator
@model_validator(mode="after")
def compute_confidence_level(cls, values):
    if values.confidence is not None:
        values.confidence_level = ConfidenceLevel.HIGH
    return values
```

### 5.2 Frozen模型修改

**错误做法**:
```python
# ❌ 禁止 - EvaluationSchema是frozen=True
request = EvaluationSchema(...)
request.payload["new_field"] = "value"  # 会抛出异常
```

**正确做法**:
```python
# ✅ 正确 - 使用model_copy
new_payload = request.payload.copy()
new_payload["new_field"] = "value"
new_request = request.model_copy(update={"payload": new_payload})
```

---

## 6. 日志记录规范

### 6.1 评估结果日志格式

```python
def _log_evaluation_result(self, request: EvaluationSchema, response: DomainResponse) -> None:
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "evaluator_type": self.__class__.__name__,
        "request_id": request.id,
        "evaluation_type": request.type,
        "score": response.score,
        "evaluation_status": response.evaluation_status.value,
        "confidence": response.confidence,
        "confidence_level": response.confidence_level.value if response.confidence_level else None,
        "is_valid": response.is_valid,
        "error": response.error,
        "metadata": response.metadata,
        "input_sample": str(request.payload)[:500] if request.payload else None,
    }
    logger.info(f"评估结果: {json.dumps(log_entry, ensure_ascii=False)}")
```

### 6.2 置信度读取路径

**错误做法**:
```python
# ❌ 禁止
confidence = response.data.get("confidence")
```

**正确做法**:
```python
# ✅ 正确
confidence = response.confidence
```

---

## 7. 配置管理规范

### 7.1 配置类位置

配置类和配置实例必须放在 `src/config/__init__.py` 中：

```python
# src/config/__init__.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    # ... 配置字段 ...

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

### 7.2 延迟初始化

使用 `@lru_cache` 实现单例模式，避免模块导入时的循环依赖：

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 7.3 兼容性导入层

原 `src/config.py` 作为兼容性导入层：

```python
# src/config.py
from src.config import settings, get_settings, Settings

__all__ = ["settings", "get_settings", "Settings"]
```

---

## 8. 架构约束

### 8.1 评估器实现规范

所有评估器必须实现 `_do_evaluate()`，禁止直接重写 `evaluate()`：

```python
class MyEvaluator(BaseEvaluator):
    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        # ✅ 正确 - 在_do_evaluate中实现评估逻辑
        ...
```

### 8.2 状态枚举判断

使用枚举值判断而非字符串匹配：

```python
# ✅ 正确
if eval_status == EvaluatorStatus.SUCCESS:
    ...

# ❌ 禁止
if eval_status.value == "success":
    ...
```

### 8.3 降级策略状态

降级评估结果必须返回 `PARTIAL` 状态，而非 `SUCCESS`：

```python
# ✅ 正确 - 降级评估返回PARTIAL
return DomainResponse(
    score=0.6,
    evaluation_status=EvaluatorStatus.PARTIAL,
    confidence=0.5,
    metadata={"degraded": True}
)
```

---

## 附录：核心文件清单

| 文件 | 职责 | 关键变更 |
|------|------|----------|
| `src/schemas/evaluation.py` | 评估响应模型 | 添加EvaluatorStatus、ConfidenceLevel、model_validator |
| `src/domain/evaluators/base.py` | 评估器基类 | 添加safe_evaluate、safe_evaluate_async、_log_evaluation_result |
| `src/engine.py` | 评估引擎 | 调用safe_evaluate、修复状态映射逻辑、修复frozen对象修改 |
| `src/config/__init__.py` | 配置管理 | 包含Settings类、get_settings()、settings实例 |
| `.trae/rules/ai_engineer/RULES.md` | 开发规范 | 添加评估器状态机、Pydantic、安全评估等规范 |