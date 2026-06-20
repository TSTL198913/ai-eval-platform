# Trae IDE 测试工程配置

## 自动加载测试最佳实践的方法

### 方法1：创建测试专用提示词（推荐）

创建 `.trae/rules/test_rules.md`：

```markdown
# 测试工程规则

## 自动应用条件
当用户请求以下操作时，自动应用测试最佳实践：
- "写测试"、"添加测试"、"编写测试用例"
- "补全测试"、"补充测试用例"
- "单元测试"、"集成测试"、"E2E测试"
- "test_" 文件编辑

## 测试编写标准

### 1. 必测场景（必须覆盖）
- [ ] 正向测试：正常输入，预期正常输出
- [ ] 负向测试：错误输入，预期错误处理
- [ ] 边界测试：最大/最小值、空值、None
- [ ] 异常测试：异常情况处理
- [ ] 依赖测试：外部服务Mock验证

### 2. 断言强度（禁止弱断言）
❌ 禁止：`assert result["status"] == "success"`
✅ 强制：`assert result.score >= 0.8` + `assert result.data["expected"] == value`

### 3. Mock配置（必须设置return_value）
```python
mock_client.return_value = "mocked_response"  # 必须设置
mock_client.side_effect = Exception("error")  # 可选
```

### 4. 测试命名规范
```
test_<功能>_<场景>_<预期>
test_injection_pattern_detected
test_empty_input_returns_error
test_without_llm_client_returns_error
```

### 5. 测试用例数量标准
- 简单函数：3-5个
- 中等函数：5-10个
- 复杂函数：10-20个
- API端点：8-15个

### 6. 测试隔离要求
- 每个测试独立运行
- 使用fixture管理依赖
- 使用autouse清理共享状态

### 7. 覆盖率要求
- 单元测试覆盖率 ≥ 80%
- 核心算法覆盖率 ≥ 90%
- 评估器覆盖率 ≥ 80%

## 输出格式

编写测试时，必须包含：
1. 测试类：`Test<ClassName><Scenario>`
2. 测试用例：每个场景至少3个测试
3. 断言：至少包含2个强断言
4. 注释：说明测试目的和关键发现
```

### 方法2：创建测试模板片段

创建 `.trae/templates/test_template.py`：

```python
"""
{module_name}专项测试
测试目标：验证{module_name}的{aspect}
关键发现：（测试过程中记录）
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.{module_path} import {ClassName}


class Test{ClassName}PositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def target(self):
        return {ClassName}()

    def test_valid_input_returns_expected(self, target):
        """合法输入应返回预期输出"""
        # Arrange
        request = {SchemaName}(...)

        # Act
        result = target.evaluate(request)

        # Assert - 强断言
        assert result.is_valid is True
        assert result.score >= 0.8
        assert result.data["expected_field"] == expected_value


class Test{ClassName}NegativeCases:
    """负向测试 - 错误输入"""

    def test_invalid_input_returns_error(self, target):
        """非法输入应返回错误"""
        request = {SchemaName}(...)
        result = target.evaluate(request)
        assert result.is_valid is False
        assert "error" in result.error.lower()


class Test{ClassName}BoundaryCases:
    """边界测试 - 边界值"""

    def test_empty_input_returns_error(self, target):
        """空输入应返回错误"""
        request = {SchemaName}(...)
        result = target.evaluate(request)
        assert result.is_valid is False
        assert "不能为空" in result.error


class Test{ClassName}DependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def mock_external(self):
        service = MagicMock()
        service.call.return_value = "mocked"
        return service

    def test_without_dependency_returns_error(self):
        """无依赖时应返回错误"""
        target = {ClassName}(client=None)
        result = target.evaluate(request)
        assert result.is_valid is False
        assert "dependency" in result.error.lower()

    def test_with_mock_dependency_works(self, mock_external):
        """使用Mock依赖时应正常"""
        target = {ClassName}(client=mock_external)
        result = target.evaluate(request)
        mock_external.call.assert_called_once()
        assert result.is_valid is True
```

### 方法3：在项目根目录创建 .trae 配置文件

```json
{
  "rules": [
    "test_rules.md"
  ],
  "skills": [
    "test_engineering_best_practices.md"
  ],
  "templates": {
    "test": ".trae/templates/test_template.py"
  },
  "auto_load": {
    "test_*.py": true,
    "**/test_*.py": true
  }
}
```

## 使用方法

### 自动触发（配置后）
在编写任何 `test_*.py` 文件时，Trae会自动加载测试最佳实践规则。

### 手动触发
在需要编写测试时，发送以下消息：

```
请按照测试工程最佳实践，为 {模块名} 编写单元测试
```

### 检查清单
编写测试后，自检：
- [ ] 是否覆盖正向、负向、边界、异常、依赖测试？
- [ ] 断言是否足够强（验证业务逻辑而非仅状态）？
- [ ] Mock是否正确配置（设置return_value）？
- [ ] 测试是否相互独立？
- [ ] 覆盖率是否达标？

## 示例对话

### 用户
> 为 SecurityEvaluator 编写单元测试

### AI响应（自动遵循最佳实践）
1. 创建 `test_security_evaluator.py`
2. 覆盖5个测试类：
   - TestSecurityEvaluatorPositiveCases（正向）
   - TestSecurityEvaluatorNegativeCases（负向）
   - TestSecurityEvaluatorBoundaryCases（边界）
   - TestSecurityEvaluatorDependencyHandling（依赖）
   - TestSecurityEvaluatorPerformanceCases（性能）
3. 每个类3-5个测试用例
4. 使用强断言验证业务逻辑
5. 记录关键发现

## 集成到Trae IDE

### Step 1: 配置文件位置
```
项目根目录/
├── .trae/
│   ├── rules/
│   │   └── test_rules.md      # 测试规则
│   ├── skills/
│   │   └── test_engineering_best_practices.md  # 测试最佳实践
│   └── templates/
│       └── test_template.py   # 测试模板
└── .trae.json                 # 配置文件
```

### Step 2: 配置加载
在 `.trae.json` 中添加：
```json
{
  "workspaceRules": [
    ".trae/rules/test_rules.md"
  ]
}
```

### Step 3: 验证
创建测试文件，AI应该自动遵循测试最佳实践。
```

### 方法4：创建全局测试Skill配置

在用户的Trae IDE配置目录创建测试skill：

```markdown
# 测试工程专家 Skill

## 激活条件
当用户请求编写测试时，自动激活此skill。

## 核心原则
1. **测试金字塔**：单元测试(80%) > 集成测试(15%) > E2E测试(5%)
2. **强断言**：验证业务逻辑，禁止仅验证status
3. **完整覆盖**：正向、负向、边界、异常、依赖
4. **测试隔离**：Mock外部依赖，独立运行
5. **命名规范**：`test_<功能>_<场景>_<预期>`

## 必测场景
- [ ] 正向测试
- [ ] 负向测试
- [ ] 边界测试（空值、最大值、最小值）
- [ ] 异常测试
- [ ] 依赖测试（Mock外部服务）

## 断言标准
- 精确断言：`assert result == expected`
- 范围断言：`assert 0.8 <= score <= 1.0`
- 类型断言：`assert isinstance(result, DomainResponse)`

## Mock配置
```python
mock.return_value = "value"  # 必须设置
mock.side_effect = Exception  # 可选
```

## 输出要求
1. 每个功能至少5个测试用例
2. 每个测试至少2个强断言
3. 包含中文注释说明测试目的
4. 记录测试中发现的关键实现细节
```

---

## 快速开始

### 1. 复制配置文件到项目根目录
```bash
# 在项目根目录执行
mkdir -p .trae/rules .trae/skills .trae/templates
```

### 2. 重启Trae IDE
配置完成后，重启Trae IDE以加载新规则。

### 3. 测试验证
创建一个测试文件，验证AI是否遵循最佳实践。
