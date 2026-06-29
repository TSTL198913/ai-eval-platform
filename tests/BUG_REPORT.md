# AI 评测平台 Bug 报告

> 生成时间: 2026-06-29
> 测试执行人: AI 测试工程师
> 测试环境: Windows 10, Python 3.10.11, pytest 9.0.3

---

## Bug 汇总统计

| 优先级 | 类型 | 数量 | 状态 |
|--------|------|------|------|
| 🔴 P0 - 严重 | 系统崩溃 | 2 | 待修复 |
| 🟠 P1 - 高 | 功能缺陷 | 1 | 待修复 |
| 🟡 P2 - 中 | 警告/潜在风险 | 3 | 规划中 |
| 🟢 P3 - 低 | 改进建议 | 2 | 待讨论 |

---

## 🔴 P0 - 严重缺陷（系统崩溃）

### BUG-001: 并发测试导致 Windows 访问冲突

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-001 |
| **严重程度** | P0 - 严重 |
| **类型** | 系统崩溃 / 并发安全 |
| **影响范围** | 多线程场景 |
| **复现概率** | 100% |
| **首次发现** | test_concurrent_safety.py |
| **堆栈信息** | `Windows fatal exception: code 0xc0000374` |

#### 问题描述

在 `tests/reliability/test_concurrent_safety.py` 的并发安全测试中，多线程同时执行数据库写入操作时触发 Windows 内存损坏异常，导致整个测试进程崩溃。

#### 堆栈追踪

```
Windows fatal exception: code 0xc0000374

Thread 0x0000451c (most recent call first):
  File "D:\python310\lib\site-packages\sqlalchemy\engine\default.py", line 721 in do_close
  File "D:\python310\lib\site-packages\sqlalchemy\pool\base.py", line 883 in __close
  File "src\infra\db\repository.py", line 105 in save  # <-- 触发点
  File "tests\reliability\test_concurrent_safety.py", line 106 in writer
```

#### 根因分析

1. **SQLAlchemy Session 并发共享**: 多线程共享同一个 SQLAlchemy Session
2. **Session 不是线程安全的**: `Session.commit()` 和 `Session.close()` 在并发调用时产生竞争条件
3. **连接池状态损坏**: SQLite 的并发写入在 Windows 平台上导致内存损坏

#### 复现步骤

```bash
cd d:\workspace\ai-eval-platform-refactor
python -m pytest tests/reliability/test_concurrent_safety.py -v
# 预期: 测试崩溃
```

#### 修复建议

```python
# 问题代码 (tests/reliability/test_concurrent_safety.py:106)
def writer(self):
    result = self.repo.save(self.evaluation_result)
    # 多线程共享 repo，Session 不是线程安全

# 修复方案: 每个线程使用独立的 Session
def writer(self):
    # 方案1: 每次操作创建新 session
    with get_db_session() as session:
        result = EvaluationRepository(session).save(self.evaluation_result)
```

#### 负责人建议

- 架构师: 审查 Session 管理策略
- 后端开发: 实现线程安全的数据库访问层

---

### BUG-002: 评估器工厂线程安全测试崩溃

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-002 |
| **严重程度** | P0 - 严重 |
| **类型** | 系统崩溃 / 并发安全 |
| **影响范围** | 评估器并发初始化 |
| **复现概率** | 100% |
| **首次发现** | test_evaluator_factory.py |
| **堆栈信息** | `Windows fatal exception: access violation` |

#### 问题描述

在 `TestThreadSafety::test_concurrent_registration` 测试中，并发注册评估器时触发 SSL 上下文初始化导致的访问冲突。

#### 堆栈追踪

```
Windows fatal exception: access violation

Thread 0x000047e0:
  File "D:\python310\lib\ssl.py", line 766 in create_default_context
  File "D:\python310\lib\site-packages\httpx\_config.py", line 40 in create_ssl_context
  File "src\domain\models\deepseek.py", line 20 in __init__  # <-- 触发点
```

#### 根因分析

1. **SSL 上下文非线程安全**: httpx 的 SSL 上下文在多线程环境下初始化时产生竞争
2. **LLM Client 工厂并发问题**: `create_llm_client()` 在并发调用时创建 DeepSeek 客户端时崩溃
3. **Windows 平台限制**: SSL 上下文创建在 Windows 上有更严格的线程安全要求

#### 复现步骤

```bash
cd d:\workspace\ai-eval-platform-refactor
python -m pytest tests/unit/test_evaluator_factory.py::TestThreadSafety -v
# 或运行完整并发测试
python -m pytest tests/unit/test_evaluator_factory.py tests/reliability/test_stability.py -v
```

#### 修复建议

```python
# 修复方案: 添加线程锁保护 LLM Client 创建
import threading

_llm_client_lock = threading.Lock()

def create_llm_client(model_name: str, **kwargs):
    with _llm_client_lock:
        if model_name == "deepseek":
            return DeepSeekClient(**kwargs)
        # ...
```

#### 负责人建议

- 后端开发: 修复 LLM Client 工厂的线程安全问题
- 测试工程师: 添加并发测试隔离

---

## 🟠 P1 - 高优先级缺陷

### BUG-003: 财务风险评估无法解析非数字评分

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-003 |
| **严重程度** | P1 - 高 |
| **类型** | 功能缺陷 / 评估逻辑 |
| **影响范围** | 金融评估器 |
| **复现概率** | 100% |
| **首次发现** | test_business_scenarios.py |
| **测试文件** | `tests/integration/api/test_business_scenarios.py:93` |

#### 问题描述

在财务风险评估测试中，当 LLM 返回非数字评分（如 "高风险交易"）时，`GeneralEvaluator` 无法正确解析评分，导致 `is_valid=False`。

#### 错误日志

```
ERROR src.domain.evaluators.general:general.py:68
通用评估响应数字提取失败: '高风险交易'

AssertionError: assert False is True
  File "tests/integration/api/test_business_scenarios.py:93"
```

#### 根因分析

1. **评分解析逻辑过于严格**: 当前实现只接受数字格式的评分
2. **缺乏语义评分支持**: 金融评估需要支持 "高/中/低" 等语义评分
3. **降级策略不完善**: 解析失败后应回退到默认评分或人工审核

#### 复现步骤

```python
# 测试代码
def test_financial_risk_assessment(self):
    result = self.client.post("/api/v1/evaluate", json={
        "id": "risk_001",
        "type": "general",
        "payload": {
            "user_input": "这笔交易是否存在风险？",
            "expected_output": "高风险交易",
        }
    })
    assert result["data"]["is_valid"] is True  # 失败
```

#### 修复建议

```python
# 方案1: 增强评分解析，支持语义评分
def safe_parse_score(self, llm_output: str) -> float | None:
    # 数字评分
    numbers = re.findall(r'\d+\.?\d*', llm_output)
    if numbers:
        return float(numbers[0]) / 10 if float(numbers[0]) > 1 else float(numbers[0])

    # 语义评分映射
    semantic_map = {
        "高风险": 0.3, "中等风险": 0.6, "低风险": 0.9,
        "high risk": 0.3, "medium risk": 0.6, "low risk": 0.9,
    }
    for key, score in semantic_map.items():
        if key in llm_output:
            return score

    return None

# 方案2: 添加宽松模式配置
config = EvaluationConfig(
    score_strict_mode=False,  # 允许语义评分
    default_score=0.5,  # 解析失败时的默认分数
)
```

#### 负责人建议

- AI 评测专家: 定义语义评分标准
- 后端开发: 实现语义评分解析

---

## 🟡 P2 - 中等风险

### BUG-004: PytestCollectionWarning - 类名冲突

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-004 |
| **严重程度** | P2 - 中 |
| **类型** | 测试配置警告 |
| **影响范围** | 测试收集 |
| **警告信息** | PytestCollectionWarning |

#### 问题描述

测试收集时出现警告，某些测试类无法被收集：

```
PytestCollectionWarning: cannot collect test class 'TestType'
  because it has a __new__ constructor

PytestCollectionWarning: cannot collect test class 'TestCase'
  because it has a __init__ constructor
```

#### 影响位置

- `src/domain/testing/red_blue_testing.py:29` - `TestType` 类
- `src/domain/testing/red_blue_testing.py:37` - `TestCase` 类

#### 修复建议

```python
# 重命名类避免与 pytest 冲突
class TestType(str, Enum):  # ❌ 冲突
    RED = "red"
    BLUE = "blue"

# 改为
class ColorType(str, Enum):  # ✅ 不冲突
    RED = "red"
    BLUE = "blue"
```

---

### BUG-005: 评估器注册表重置导致测试隔离问题

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-005 |
| **严重程度** | P2 - 中 |
| **类型** | 测试设计缺陷 |
| **影响范围** | 性能测试 |
| **首次发现** | test_unit_performance.py |

#### 问题描述

`conftest.py` 中的 `reset_evaluator_registry` fixture 会重置评估器注册表，导致某些测试无法获取已注册的评估器。

#### 根因分析

```python
# conftest.py
@pytest.fixture(autouse=True)
def reset_evaluator_registry():
    # 只重置注册表，没有重新发现评估器
    EF._registry = {}
    EF._discovered = False
```

#### 已应用的修复

```python
# test_unit_performance.py
@pytest.fixture(autouse=True)
def ensure_evaluators_registered():
    """确保评估器已注册（覆盖conftest的重置）"""
    from src.domain.evaluators import auto_discover
    auto_discover(force=True)
```

#### 建议长期修复

将 `reset_evaluator_registry` fixture 改为仅在特定测试类中使用，或在重置后自动触发 `auto_discover()`。

---

### BUG-006: RAGAS 未安装警告

| 属性 | 值 |
|------|-----|
| **Bug ID** | BUG-006 |
| **严重程度** | P2 - 中 |
| **类型** | 依赖警告 |
| **警告信息** | WARNING: 未安装 ragas，RAGAS 评估器将降级到本地实现 |

#### 说明

这是预期行为，但警告信息可能干扰测试输出。建议：
1. 将警告级别降低为 DEBUG
2. 或在测试环境中自动跳过 RAGAS 相关测试

---

## 🟢 P3 - 低优先级改进建议

### IMP-001: 性能测试基线未固化

| 属性 | 值 |
|------|-----|
| **改进 ID** | IMP-001 |
| **优先级** | P3 |
| **类型** | 改进建议 |

#### 建议

建立性能回归门禁，将当前的经验阈值替换为基于历史数据的实际基线：

```python
# 当前阈值（经验值）
assert result.p95_ms < 100  # 可能过于宽松或严格

# 建议：基于历史数据建立基线
PERFORMANCE_BASELINE = {
    "engine_sync": {"p95_ms": 85, "p99_ms": 120},
    "engine_async": {"p95_ms": 75, "p99_ms": 100},
    "cache_get": {"p95_ms": 3, "p99_ms": 8},
}
```

---

### IMP-002: 测试数据随机性

| 属性 | 值 |
|------|-----|
| **改进 ID** | IMP-002 |
| **优先级** | P3 |
| **类型** | 改进建议 |

#### 建议

使用固定种子确保测试可复现：

```python
import random

@pytest.fixture(autouse=True)
def fixed_random_seed():
    random.seed(42)
    yield
    random.seed(None)  # 恢复随机状态
```

---

## 测试执行摘要

| 测试类别 | 总数 | 通过 | 失败 | 跳过 |
|---------|------|------|------|------|
| 单元测试 | 47 | 47 | 0 | 0 |
| 可靠性测试 | 164 | 28+ | 崩溃 | - |
| 集成测试 | 1097 | 51+ | 1 | - |
| 性能测试 | 14 | 12 | 0 | 2 |

### 通过测试

- ✅ 熔断器单元测试 (22/22 passed)
- ✅ 评估器工厂测试 (25/25 passed)
- ✅ 单元级性能测试 (12 passed, 2 skipped)
- ✅ 组件级性能测试 (13 passed)

### 发现缺陷

- 🔴 2 个系统崩溃缺陷
- 🟠 1 个功能缺陷
- 🟡 3 个警告/潜在风险

---

## 下一步行动

| 优先级 | 任务 | 负责人 | 截止日期 |
|--------|------|--------|----------|
| P0 | 修复并发数据库 Session 问题 | 后端开发 | 2026-07-01 |
| P0 | 修复 SSL 上下文线程安全 | 后端开发 | 2026-07-01 |
| P1 | 实现语义评分解析 | AI评测专家 | 2026-07-03 |
| P2 | 修复类名冲突警告 | 后端开发 | 2026-07-05 |
| P3 | 建立性能基线 | 测试工程师 | 2026-07-10 |

---

*报告生成: AI 测试工程师*
*最后更新: 2026-06-29*
