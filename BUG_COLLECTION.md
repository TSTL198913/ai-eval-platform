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

---

## ⚠️ 中优先级 Bug

### BUG-ID: TEST-001 中

**发现位置**: [tests/unit/evaluator/test_core_evaluators.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_core_evaluators.py#L484-L495)

**问题描述**: `test_validate_input` 测试用例中，`_do_evaluate` 返回 `None`，但测试期望 `result.is_valid is False`。这是测试设计问题，应该验证错误响应而非假设返回值存在。

**影响范围**: 
- 测试用例不可靠
- 无法验证正确的错误处理行为

**建议修复**:
修改测试用例，使其验证正确的错误响应：
```python
def test_validate_input(self):
    class TestEvaluator(BaseEvaluator):
        def __init__(self, client=None):
            super().__init__(client, require_input=True)
        def _do_evaluate(self, request):
            return self.create_success_response(text="ok", score=0.0)
    
    evaluator = TestEvaluator()
    request = EvaluationSchema(id="test", type="test", payload={"user_input": ""})
    result = evaluator.evaluate(request)
    assert result.is_valid is False  # 验证输入验证失败
```

---

### BUG-ID: TEST-002 中

**发现位置**: [tests/unit/evaluator/test_core_evaluators.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_core_evaluators.py#L500-L508)

**问题描述**: `test_require_client` 测试用例中，`_do_evaluate` 返回 `None`，这不符合评估器实现规范。

**影响范围**: 
- 测试用例不可靠，无法验证实际行为

**建议修复**:
修改测试用例，使 `_do_evaluate` 返回有效的 `DomainResponse`。

---

## 🟡 低优先级改进建议

### BUG-ID: QUALITY-001 低

**发现位置**: [tests/utils/assertion_analyzer.py](file:///d:/workspace/ai-eval-platform-refactor/tests/utils/assertion_analyzer.py)

**问题描述**: 断言强度分析显示21个测试文件强断言比例低于50%，需要持续改进。

**影响范围**: 
- 测试质量整体偏低
- 无法有效发现业务逻辑错误

**建议修复**:
- 按优先级排序修复：`test_sentiment_evaluator.py` (26.8%) → `test_bug_detection.py` (34.0%) → `test_security_evaluator_blackbox.py` (35.6%)
- 为每个文件添加至少1个强断言
- 运行断言强度分析验证改进效果

---

### BUG-ID: QUALITY-002 低

**发现位置**: [tests/unit/core/test_repository.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/core/test_repository.py)

**问题描述**: 测试代码中使用已废弃的 `is_valid` 参数，触发 DeprecationWarning。

**影响范围**: 
- 测试代码技术债务累积
- 测试输出被警告信息污染

**建议修复**:
替换 `DomainResponse(is_valid=True/False)` 为工厂方法 `create_success_response()` / `create_error_response()`。

---

## Bug 统计

| 优先级 | 数量 | 说明 |
| :--- | :---: | :--- |
| 🔴 高 | 1 | 运行时崩溃问题 |
| ⚠️ 中 | 2 | 测试质量问题 |
| 🟡 低 | 2 | 改进建议 |
| **合计** | **5** | |

---

## 修复状态

| Bug ID | 状态 | 修复版本 |
| :--- | :---: | :--- |
| BASE-001 | ✅ 已修复 | 迭代4 |
| TEST-001 | ✅ 已修复 | 迭代4 |
| TEST-002 | ✅ 已修复 | 迭代4 |
| QUALITY-001 | ✅ 已修复 | 迭代4 |
| QUALITY-002 | ✅ 已修复 | 迭代4 |