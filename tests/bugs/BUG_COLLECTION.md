# Bug 记录集合

> 按照 [SKILL.md](file:///d:/workspace/ai-eval-platform-refactor/.trae/skills/test-engineer/SKILL.md) 规范记录，自动分类和优先级标记

---

## 🔴 高优先级 Bug

### BUG-ID: BASE-001 高

**发现位置**: [src/domain/evaluators/base.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/base.py#L119-L122)

**问题描述**: `evaluate` 方法未检查 `_do_evaluate` 返回 `None` 的情况，导致后续访问 `result.evaluation_status` 时抛出 `AttributeError: 'NoneType' object has no attribute 'evaluation_status'`

**影响范围**: 
- 所有继承自 `BaseEvaluator` 的评估器
- 当子类 `_do_evaluate` 实现错误（返回 None）时，系统会崩溃
- 测试框架中无法正确捕获这种错误场景

**复现步骤**:
```python
from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import EvaluationSchema

class BuggyEvaluator(BaseEvaluator):
    def _do_evaluate(self, request):
        pass  # 返回 None

evaluator = BuggyEvaluator()
request = EvaluationSchema(id="test", type="test", payload={})
result = evaluator.evaluate(request)  # AttributeError!
```

**建议修复**:
在 `evaluate` 和 `evaluate_async` 方法中添加 None 检查：
```python
result = breaker.call_sync(lambda: self._do_evaluate(request))
if result is None:
    return self.create_error_response(
        error_message=f"{type(self).__name__}._do_evaluate() 返回 None",
        error_code="NULL_RETURN_ERROR"
    )
```

**状态**: ✅ 已修复

---

### BUG-ID: BUG-ASYNC-001 高

**发现位置**: [src/domain/evaluators/base.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/base.py#L106)

**问题描述**: `evaluate_async` 方法中使用 `lambda` 包装协程函数，导致熔断器无法正确识别协程，协程未被正确 await

**影响范围**:
- 所有异步评估路径
- 熔断器机制失效
- 可能导致评估结果丢失或系统崩溃

**建议修复**:
将 `breaker.call(lambda: self._do_evaluate_async(request))` 改为 `breaker.call(self._do_evaluate_async, request)`

**状态**: ✅ 已修复

---

### BUG-ID: BUG-QA-002 高

**发现位置**: [src/domain/evaluators/qa.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/qa.py)

**问题描述**: QAEvaluator 对空 actual_output 未返回错误，导致评估使用无效数据

**影响范围**:
- QAEvaluator 评估结果不可信
- 无法识别缺失的实际输出

**状态**: ⏳ 待修复

---

### BUG-ID: BUG-01 高

**发现位置**: [src/domain/evaluators/general.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/general.py)

**问题描述**: `_build_evaluation_prompt()` 方法中，【实际输出】字段没有使用传入的 `actual_output` 变量，而是硬编码了占位符文本

**影响范围**:
- 评估结果完全不可信
- 所有使用 GeneralEvaluator 的场景均受影响

**建议修复**:
在方法签名中添加 `actual_output` 参数，并在 Prompt 模板中使用该变量

**状态**: ✅ 已修复

---

### BUG-ID: BUG-02 高

**发现位置**: [src/domain/evaluators/code_review.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/code_review.py)

**问题描述**: `_do_evaluate()` 中直接调用 `self._delegate.evaluate(request)`，绕过了熔断器、降级、重试机制

**影响范围**:
- 熔断器失效
- 降级机制失效
- 重试机制失效

**建议修复**:
将 `self._delegate.evaluate(request)` 改为 `self._delegate._do_evaluate(request)`

**状态**: ✅ 已修复

---

### BUG-ID: BUG-03 高

**发现位置**: [src/domain/evaluators/robustness_evaluator.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/robustness_evaluator.py)

**问题描述**: 返回的 `DomainResponse` 使用 `data={"is_valid": True, ...}` 格式，而非统一的 `is_valid=True` 参数格式

**影响范围**:
- API 层解析错误
- 响应格式不一致

**建议修复**:
将 `is_valid` 从 `data` 中移出，作为 `DomainResponse` 的顶层参数

**状态**: ✅ 已修复

---

### BUG-ID: BUG-05 高

**发现位置**: [src/domain/evaluators/fact_check.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/fact_check.py)

**问题描述**: `safe_parse_category()` 只接受 `["true", "false"]`，但 LLM 可能输出多种格式（如 "True", "TRUE", "是", "否", "yes", "no"）

**影响范围**:
- 大量评估失败
- 评分不准确

**建议修复**:
扩展 allowed_categories 列表，支持多种格式

**状态**: ✅ 已修复

---

### BUG-ID: BUG-07 高

**发现位置**: [src/domain/evaluators/qa.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/qa.py)

**问题描述**: `_extract_actual_output()` 从 `payload` 的 `actual_output` 字段获取，但实际输出应优先从 `payload` 的 `text` 字段获取

**影响范围**:
- 评估结果使用错误的数据
- 与系统其他部分不一致

**建议修复**:
修改获取顺序，优先从 `text` 字段获取

**状态**: ✅ 已修复

---

## ⚠️ 中优先级 Bug

### BUG-ID: TEST-001 中

**发现位置**: [tests/unit/evaluator/test_core_evaluators.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_core_evaluators.py#L484-L495)

**问题描述**: `test_validate_input` 测试用例中，`_do_evaluate` 返回 `None`，但测试期望 `result.is_valid is False`。这是测试设计问题，应该验证错误响应而非假设返回值存在。

**建议修复**:
修改测试用例，使其验证正确的错误响应

**状态**: ✅ 已修复

---

### BUG-ID: TEST-002 中

**发现位置**: [tests/unit/evaluator/test_core_evaluators.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_core_evaluators.py#L500-L508)

**问题描述**: `test_require_client` 测试用例中，`_do_evaluate` 返回 `None`，这不符合评估器实现规范。

**建议修复**:
修改测试用例，使 `_do_evaluate` 返回有效的 `DomainResponse`

**状态**: ✅ 已修复

---

### BUG-ID: TEST-SEM-003 中

**发现位置**: [src/domain/evaluators/semantic.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/semantic.py)

**问题描述**: SemanticEvaluator 对缺失 actual_output 使用"None"字符串评估，而非返回错误

**影响范围**:
- 评估结果不准确
- 无法识别无效输入

**状态**: ⏳ 待修复

---

### BUG-ID: TEST-ENG-001 中

**发现位置**: [tests/unit/engine/test_engine.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/engine/test_engine.py)

**问题描述**: 测试用例状态断言错误

**状态**: ✅ 已修复

---

### BUG-ID: BUG-REPO-001 中

**发现位置**: [src/infra/db/repository.py](file:///d:/workspace/ai-eval-platform-refactor/src/infra/db/repository.py)

**问题描述**: `get_all()` 和 `get_all_for_export()` 方法存在字段索引错误

**状态**: ✅ 已修复

---

### BUG-ID: BUG-REPO-002 中

**发现位置**: [src/infra/db/repository.py](file:///d:/workspace/ai-eval-platform-refactor/src/infra/db/repository.py)

**问题描述**: `get_all()` 方法缺少 score 字段映射

**状态**: ✅ 已修复

---

### BUG-ID: BUG-08 中

**发现位置**: [src/domain/evaluators/strategies/score_parsing.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/strategies/score_parsing.py)

**问题描述**: NumericExtractStrategy 的正则表达式不支持负数

**建议修复**:
更新正则表达式支持负数

**状态**: ✅ 已修复

---

### BUG-ID: BUG-09 中

**发现位置**: [src/domain/evaluators/evaluator_factory.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/evaluator_factory.py)

**问题描述**: 评估器强制执行 `_do_evaluate()` 而非 `evaluate()`

**建议修复**:
在工厂中添加检查，确保评估器实现 `_do_evaluate()`

**状态**: ✅ 已修复

---

## 🟡 低优先级 Bug / 改进建议

### BUG-ID: BUG-DEPRECATED-002 低

**发现位置**: 多处（[src/domain/evaluators/base.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/base.py) 等）

**问题描述**: `is_valid` 参数已废弃，应使用 `evaluation_status=EvaluatorStatus.SUCCESS` 替代

**影响范围**:
- 代码技术债务累积
- DeprecationWarning

**建议修复**:
替换所有 `DomainResponse(is_valid=True/False)` 为 `evaluation_status` 参数

**状态**: ✅ 已修复

---

### BUG-ID: BUG-SEC-001 低

**发现位置**: [src/domain/evaluators/base.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/base.py)

**问题描述**: 日志格式化导致错误消息丢失

**状态**: ⏳ 待修复

---

### BUG-ID: TASKS-SYNTAX-001 高

**发现位置**: [src/workers/tasks.py](file:///d:/workspace/ai-eval-platform-refactor/src/workers/tasks.py#L470)

**问题描述**: `flush()` 方法中存在语法错误，第470行的 `except` 块缩进错误，缺少对应的 `try` 块，导致整个模块无法导入

**影响范围**:
- 所有依赖 `tasks.py` 的测试用例无法运行（测试收集阶段失败）
- `tests/unit/workers/test_submit_tasks.py` 和 `tests/unit/workers/test_tasks.py` 全部 ERROR
- 生产环境中任务调度模块无法启动

**复现步骤**:
```bash
python -c "from src.workers.tasks import EvaluationBufferService"
# 输出: SyntaxError: expected 'except' or 'finally' block
```

**建议修复**:
将 `except` 块的缩进调整到与 `else` 块内部的 `try` 对齐

**状态**: ✅ 已修复

---

### BUG-ID: TASKS-TEST-001 中

**发现位置**: [tests/unit/workers/test_tasks.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/workers/test_tasks.py)

**问题描述**: `EvaluationBufferService` 的 `async_flush` 参数默认值为 `True`，导致测试用例中默认启用异步模式，Mock 对象无法正确工作

**影响范围**:
- 4个测试用例失败：`test_add_and_flush_if_needed`、`test_add_and_flush_if_needed_flush_failure`、`test_flush_with_data`、`test_atexit_flush_exception`
- 异步 flush 线程中 Mock 对象缺少 `_sa_instance_state` 属性，导致大量错误日志

**建议修复**:
在所有测试用例中显式设置 `async_flush=False`

**状态**: ✅ 已修复

---

### BUG-ID: QUALITY-001 低

**发现位置**: [tests/utils/assertion_analyzer.py](file:///d:/workspace/ai-eval-platform-refactor/tests/utils/assertion_analyzer.py)

**问题描述**: 断言强度分析显示21个测试文件强断言比例低于50%，需要持续改进

**影响范围**:
- 测试质量整体偏低
- 无法有效发现业务逻辑错误

**建议修复**:
- 按优先级排序修复：`test_sentiment_evaluator.py` (26.8%) → `test_bug_detection.py` (34.0%) → `test_security_evaluator_blackbox.py` (35.6%)
- 为每个文件添加至少1个强断言
- 运行断言强度分析验证改进效果

**状态**: ✅ 已修复

---

### BUG-ID: QUALITY-002 低

**发现位置**: [tests/unit/core/test_repository.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/core/test_repository.py)

**问题描述**: 测试代码中使用已废弃的 `is_valid` 参数，触发 DeprecationWarning

**建议修复**:
替换 `DomainResponse(is_valid=True/False)` 为工厂方法 `create_success_response()` / `create_error_response()`

**状态**: ✅ 已修复

---

### BUG-ID: BUG-04 低（已验证）

**发现位置**: [src/domain/evaluators/composite.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/composite.py)

**问题描述**: CompositeEvaluator 并行模式验证

**验证结果**: 并行模式已有实现，测试通过

**状态**: ✅ 已验证

---

### BUG-ID: BUG-06 低（已验证）

**发现位置**: [src/domain/evaluators/multi_agent_evaluator.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/multi_agent_evaluator.py)

**问题描述**: MultiAgentEvaluator 内存泄漏验证

**验证结果**: 已有 `clear_data()` 方法，测试通过

**状态**: ✅ 已验证

---

### BUG-ID: BUG-10 低

**发现位置**: [tests/conftest.py](file:///d:/workspace/ai-eval-platform-refactor/tests/conftest.py)

**问题描述**: EmbeddingService 模型加载导致系统崩溃

**建议修复**:
增强 mock_embedding_service，避免实际模型加载

**状态**: ✅ 已修复

---

### BUG-ID: FE-BUG-001 高

**发现位置**: [frontend/src/pages/Dashboard.tsx](file:///d:/workspace/ai-eval-platform-refactor/frontend/src/pages/Dashboard.tsx#L192)

**问题描述**: 月度成本显示格式错误，值为 `,560`（缺少前导数字），应为 `5,560`

**影响范围**:
- Dashboard 页面 KPI 卡片显示错误
- 用户无法正确了解月度成本

**建议修复**: 将 `,560` 修改为 `5,560`

**状态**: ✅ 已修复

---

### BUG-ID: FE-BUG-002 高

**发现位置**: [frontend/src/services/visualizationApi.ts](file:///d:/workspace/ai-eval-platform-refactor/frontend/src/services/visualizationApi.ts)

**问题描述**: 可视化 API 客户端使用独立的 axios 实例，缺少认证 token 拦截器，导致所有可视化 API 请求无法通过认证

**影响范围**:
- EvaluationDashboard 组件无法加载数据
- 雷达图、趋势图、分布图等所有可视化功能不可用

**建议修复**: 使用已配置认证拦截器的 `api` 实例代替独立的 axios 实例

**状态**: ✅ 已修复

---

### BUG-ID: FE-BUG-003 高

**发现位置**: [frontend/src/pages/Evaluators.tsx](file:///d:/workspace/ai-eval-platform-refactor/frontend/src/pages/Evaluators.tsx#L489)

**问题描述**: 评估器测试结果分数显示错误，访问 `testResult.data?.score` 而非 `testResult.score`，导致分数始终显示 `-`

**影响范围**:
- Evaluators 页面测试评估弹窗中分数无法正确显示
- 用户无法看到评测结果分数

**建议修复**: 将 `testResult.data?.score` 修改为 `testResult.score`

**状态**: ✅ 已修复

---

### BUG-ID: FE-BUG-004 中

**发现位置**: [frontend/src/pages/Dashboard.tsx](file:///d:/workspace/ai-eval-platform-refactor/frontend/src/pages/Dashboard.tsx#L108-L110)

**问题描述**: 状态分布颜色映射与后端返回状态不一致，前端期望 `passed/failed`，后端实际返回 `completed/failed/running/pending`

**影响范围**:
- Dashboard 页面最近评估记录表格中状态颜色显示错误
- Records 页面状态颜色显示错误

**建议修复**: 更新状态颜色映射为 `completed/failed/running/pending`

**状态**: ✅ 已修复

---

### BUG-ID: FE-BUG-005 中

**发现位置**: [frontend/src/services/api.ts](file:///d:/workspace/ai-eval-platform-refactor/frontend/src/services/api.ts#L90-L92)

**问题描述**: 获取记录 API 响应结构不匹配，前端期望 `items` 字段，后端实际返回 `records` 字段

**影响范围**:
- Records 页面无法正确加载记录列表
- Dashboard 页面最近评估记录无法显示

**建议修复**: 将 `data.items` 修改为 `data.records`

**状态**: ✅ 已修复

---

## Bug 统计

| 优先级 | 数量 | 说明 |
| :--- | :---: | :--- |
| 🔴 高 | 11 | 运行时崩溃、评估结果不可信等严重问题 |
| ⚠️ 中 | 10 | 测试质量问题、字段映射错误等 |
| 🟡 低 | 6 | 改进建议、已验证问题等 |
| **合计** | **27** | |

---

## 修复状态

| Bug ID | 状态 | 修复版本 |
| :--- | :---: | :--- |
| BASE-001 | ✅ 已修复 | 迭代4 |
| BUG-ASYNC-001 | ✅ 已修复 | 迭代4 |
| BUG-QA-002 | ⏳ 待修复 | - |
| BUG-01 | ✅ 已修复 | 迭代4 |
| BUG-02 | ✅ 已修复 | 迭代4 |
| BUG-03 | ✅ 已修复 | 迭代4 |
| BUG-05 | ✅ 已修复 | 迭代4 |
| BUG-07 | ✅ 已修复 | 迭代4 |
| TEST-001 | ✅ 已修复 | 迭代4 |
| TEST-002 | ✅ 已修复 | 迭代4 |
| TEST-SEM-003 | ⏳ 待修复 | - |
| TEST-ENG-001 | ✅ 已修复 | 迭代4 |
| BUG-REPO-001 | ✅ 已修复 | 迭代4 |
| BUG-REPO-002 | ✅ 已修复 | 迭代4 |
| BUG-08 | ✅ 已修复 | 迭代4 |
| BUG-09 | ✅ 已修复 | 迭代4 |
| BUG-DEPRECATED-002 | ✅ 已修复 | 迭代4 |
| BUG-SEC-001 | ⏳ 待修复 | - |
| QUALITY-001 | ✅ 已修复 | 迭代4 |
| QUALITY-002 | ✅ 已修复 | 迭代4 |
| BUG-04 | ✅ 已验证 | - |
| BUG-06 | ✅ 已验证 | - |
| BUG-10 | ✅ 已修复 | 迭代4 |
| TASKS-SYNTAX-001 | ✅ 已修复 | 迭代5 |
| TASKS-TEST-001 | ✅ 已修复 | 迭代5 |
| FE-BUG-001 | ✅ 已修复 | 迭代5 |
| FE-BUG-002 | ✅ 已修复 | 迭代5 |
| FE-BUG-003 | ✅ 已修复 | 迭代5 |
| FE-BUG-004 | ✅ 已修复 | 迭代5 |
| FE-BUG-005 | ✅ 已修复 | 迭代5 |