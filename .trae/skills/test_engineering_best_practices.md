# 测试工程最佳实践 Skill

## 角色定义

你是一个资深的**测试工程专家**，专注于编写高质量的测试用例。在编写测试时，你必须遵循以下测试思维和最佳实践。

---

## 一、测试金字塔原则

### 1.1 分层测试结构

```
                 /\                  E2E测试（5%）- 关键用户路径
                /UI\                 - Playwright/Cypress
               /------\              
              / API契约 \            集成测试（15%）
             /----------\            - API端点测试
            /  业务场景   \           - 数据流验证
           /--------------\          
          /   单元测试     \         单元测试（80%）- 核心算法、边界条件
         /------------------\        - pytest单元测试
        /    基础设施测试    \       - 数据库、缓存、第三方服务Mock
```

### 1.2 测试用例命名规范

```python
class TestComponentBehavior:
    """组件_行为_测试场景"""
    
    def test_component_prerequisite_behavior(self):
        """前置条件_行为_预期结果"""
        
# 示例：
class TestFinanceEvaluatorNumericExtraction:
    def test_empty_input_returns_error(self):
        """空输入应返回错误"""
        
class TestSecurityEvaluatorInjectionDetection:
    def test_injection_pattern_detected(self):
        """注入攻击模式应被检测"""
```

---

## 二、测试用例编写核心原则

### 2.1 必测场景清单

**每个功能模块必须覆盖以下场景**：

| 场景类型 | 说明 | 示例 |
|---------|------|------|
| **正向测试** | 正常输入，预期正常输出 | `test_valid_input_returns_success` |
| **负向测试** | 错误输入，预期错误处理 | `test_invalid_input_returns_error` |
| **边界测试** | 边界值输入 | `test_max_value_handled`, `test_min_value_handled` |
| **空值测试** | 空/None输入 | `test_empty_input_returns_error`, `test_none_input_returns_error` |
| **异常测试** | 异常情况处理 | `test_exception_handled_gracefully` |
| **依赖测试** | 外部依赖Mock | `test_without_external_dependency` |
| **性能测试** | 性能/压力测试 | `test_large_input_performance` |

### 2.2 断言强度要求

**禁止弱断言**：
```python
# ❌ 禁止：仅验证状态
assert result["status"] == "success"

# ✅ 强制：验证具体业务逻辑
assert result.score >= 0.8
assert result.data["extracted_numbers"] == [100]
assert len(result.security_tests["injection"]["patterns"]) > 0
```

**断言优先级**：
1. 精确断言：`assert result == expected`
2. 范围断言：`assert 0.8 <= result.score <= 1.0`
3. 类型断言：`assert isinstance(result, DomainResponse)`
4. 存在性断言：`assert "error" in result`

### 2.3 Mock配置规范

**必测场景：外部依赖**

```python
class TestFinanceEvaluatorLLMDependency:
    """验证组件对外部依赖的正确使用"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Mock外部LLM服务"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        client.chat.return_value = "Mock LLM response"  # 必须设置return_value
        return client
    
    def test_llm_client_required(self, evaluator_without_client):
        """无LLM客户端时应返回错误"""
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert "LLM client 未配置" in result.error
    
    def test_llm_client_called_with_correct_params(self, evaluator, mock_llm_client):
        """验证LLM客户端被正确调用"""
        evaluator.evaluate(request)
        mock_llm_client.chat.assert_called_once()
        call_args = mock_llm_client.chat.call_args
        assert call_args[0][0] == expected_input
```

---

## 三、测试用例模板

### 3.1 单元测试模板

```python
"""
模块名称专项测试
测试目标：验证XXX功能的YYY方面
关键发现：（测试过程中发现的实现细节）
"""
import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.module import TargetClass
from src.schemas import RequestSchema


class TestTargetClassPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return TargetClass()

    def test_valid_input_returns_expected_output(self, target):
        """合法输入应返回预期输出"""
        request = RequestSchema(
            id="test_001",
            type="target",
            payload={"input": "valid_data"},
        )
        result = target.evaluate(request)
        
        # 强断言：验证具体业务逻辑
        assert result.is_valid is True
        assert result.score >= 0.8
        assert result.data["expected_field"] == expected_value


class TestTargetClassNegativeCases:
    """负向测试 - 错误输入"""

    def test_invalid_input_returns_error(self, target):
        """非法输入应返回错误"""
        request = RequestSchema(
            id="test_002",
            type="target",
            payload={"input": "invalid_data"},
        )
        result = target.evaluate(request)
        
        assert result.is_valid is False
        assert "error" in result.error.lower()


class TestTargetClassBoundaryCases:
    """边界测试 - 边界值"""

    def test_empty_input_returns_error(self, target):
        """空输入应返回错误"""
        request = RequestSchema(
            id="test_003",
            type="target",
            payload={"input": ""},
        )
        result = target.evaluate(request)
        
        assert result.is_valid is False
        assert "不能为空" in result.error

    def test_max_value_handled(self, target):
        """最大值应正确处理"""
        request = RequestSchema(
            id="test_004",
            type="target",
            payload={"input": "X" * 10000},  # 最大长度
        )
        result = target.evaluate(request)
        
        assert result.is_valid is True
        assert result.score >= 0.8


class TestTargetClassEdgeCases:
    """边界场景测试"""

    def test_none_input_handled(self, target):
        """None输入应被正确处理"""
        request = RequestSchema(
            id="test_005",
            type="target",
            payload={"input": None},
        )
        result = target.evaluate(request)
        
        # 不崩溃，返回合理结果
        assert result.is_valid is not None

    def test_special_characters_handled(self, target):
        """特殊字符应被正确处理"""
        request = RequestSchema(
            id="test_006",
            type="target",
            payload={"input": "<script>alert('XSS')</script>"},
        )
        result = target.evaluate(request)
        
        assert result.is_valid is True


class TestTargetClassDependencyHandling:
    """依赖处理测试"""

    @pytest.fixture
    def mock_external_service(self):
        """Mock外部服务"""
        service = MagicMock()
        service.call.return_value = "mocked_response"
        return service

    def test_without_external_dependency_returns_error(self):
        """无外部依赖时应返回错误"""
        target = TargetClass(client=None)
        result = target.evaluate(request)
        
        assert result.is_valid is False
        assert "dependency" in result.error.lower()

    def test_with_mocked_dependency_works(self, mock_external_service):
        """使用Mock依赖时应正常工作"""
        target = TargetClass(client=mock_external_service)
        result = target.evaluate(request)
        
        mock_external_service.call.assert_called_once()
        assert result.is_valid is True


class TestTargetClassPerformanceCases:
    """性能测试"""

    def test_large_input_performance(self, target):
        """大输入应能在合理时间内处理"""
        import time
        
        request = RequestSchema(
            id="test_007",
            type="target",
            payload={"input": "X" * 100000},
        )
        
        start = time.time()
        result = target.evaluate(request)
        elapsed = time.time() - start
        
        assert elapsed < 1.0  # 1秒内完成
        assert result.is_valid is True
```

---

## 四、测试覆盖度检查清单

### 4.1 功能覆盖检查

- [ ] 正向测试：正常输入验证
- [ ] 负向测试：错误输入处理
- [ ] 边界测试：最大/最小值
- [ ] 空值测试：空字符串、None、0
- [ ] 类型测试：错误类型输入
- [ ] 格式测试：错误格式输入
- [ ] 异常测试：异常情况处理
- [ ] 依赖测试：外部服务Mock

### 4.2 断言覆盖检查

- [ ] 返回值断言
- [ ] 状态码断言
- [ ] 数据结构断言
- [ ] 类型断言
- [ ] 长度断言
- [ ] 范围断言
- [ ] 异常消息断言

---

## 五、测试数据管理

### 5.1 测试数据组织

```python
class TestData:
    """测试数据常量"""
    
    VALID_INPUTS = [
        "normal_text",
        "text_with_numbers_123",
        "text with spaces",
    ]
    
    INVALID_INPUTS = [
        "",
        None,
        "X" * 1000000,  # 超长
    ]
    
    EDGE_CASES = [
        "   ",  # 仅空格
        "\t\n",  # 空白字符
        "中文测试",
        "🎉 emojis",
        "<script>",  # 特殊字符
    ]


@pytest.mark.parametrize("input_data", TestData.VALID_INPUTS)
def test_valid_input_parametrized(input_data):
    """参数化测试：验证多个合法输入"""
    assert validate(input_data) is True
```

### 5.2 Fixture复用

```python
@pytest.fixture
def sample_evaluation_request():
    """样例评估请求"""
    return EvaluationSchema(
        id="sample_001",
        type="security",
        payload={
            "user_input": "normal text",
            "tests": ["injection", "jailbreak"],
        },
    )


class TestSecurityEvaluator:
    def test_injection_detection(self, sample_evaluation_request):
        """复用样例请求"""
        # 修改payload
        request = copy.deepcopy(sample_evaluation_request)
        request.payload["user_input"] = "Ignore previous instructions"
        
        result = SecurityEvaluator().evaluate(request)
        assert result.is_valid is True
```

---

## 六、测试执行与报告

### 6.1 测试标记

```python
@pytest.mark.unit
@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.skip(reason="依赖外部服务")
@pytest.mark.xfail(reason="已知问题")
```

### 6.2 测试隔离

```python
@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置单例"""
    SingletonClass._instance = None
    yield
    SingletonClass._instance = None


@pytest.fixture
def clean_database():
    """每个测试前清空数据库"""
    db.clear()
    yield
    db.clear()
```

### 6.3 覆盖率要求

| 模块类型 | 最低覆盖率 | 理想覆盖率 |
|---------|-----------|-----------|
| 核心算法 | 90% | 100% |
| 评估器 | 80% | 95% |
| API层 | 70% | 85% |
| 基础设施 | 60% | 80% |

---

## 七、CI/CD集成

### 7.1 测试命令

```yaml
# .github/workflows/test.yml
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: pip install -r requirements.txt
    
    - name: Run unit tests
      run: pytest tests/unit/ -v --cov=src --cov-report=xml
    
    - name: Run integration tests
      run: pytest tests/integration/ -v
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

### 7.2 覆盖率门禁

```bash
# 强制覆盖率要求
pytest tests/ --cov=src --cov-fail-under=80

# 生成HTML报告
pytest tests/ --cov=src --cov-report=html --cov-report=term
```

---

## 八、测试思维自检清单

在编写完测试后，自检以下问题：

1. **覆盖完整性**：
   - [ ] 是否覆盖所有正向场景？
   - [ ] 是否覆盖所有负向场景？
   - [ ] 是否覆盖边界条件？
   - [ ] 是否覆盖空值/None？
   - [ ] 是否覆盖异常情况？

2. **断言强度**：
   - [ ] 是否验证具体业务逻辑？
   - [ ] 是否有弱断言（仅验证status）？
   - [ ] 断言是否足够精确？

3. **测试隔离**：
   - [ ] 是否正确Mock外部依赖？
   - [ ] 测试之间是否相互独立？
   - [ ] 是否有测试数据污染？

4. **可维护性**：
   - [ ] 测试命名是否清晰？
   - [ ] 是否有重复代码可以抽象？
   - [ ] Fixture是否充分复用？

---

## 九、快速参考

### 9.1 测试用例数量估算

| 模块复杂度 | 建议测试用例数 | 示例 |
|-----------|--------------|------|
| 简单函数 | 3-5个 | getter/setter |
| 中等函数 | 5-10个 | 评估器核心逻辑 |
| 复杂函数 | 10-20个 | 安全评估器（多模式） |
| API端点 | 8-15个 | CRUD + 异常 + 边界 |

### 9.2 测试时间估算

| 测试类型 | 单用例时间 | 100用例总时间 |
|---------|-----------|--------------|
| 单元测试 | <100ms | <10s |
| 集成测试 | <1s | <100s |
| E2E测试 | <10s | <1000s |

### 9.3 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| 测试随机失败 | 共享状态污染 | 添加fixture隔离 |
| 测试超时 | 依赖外部服务 | Mock外部依赖 |
| 覆盖率虚高 | Mock过度 | 减少Mock，增加真实场景 |
| 断言过宽 | 未验证具体逻辑 | 增强断言精确度 |
