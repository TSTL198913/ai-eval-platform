# 业务逻辑断言规范（强制执行）

## 一、断言强度分级

### 🔴 弱断言（禁止单独使用）
- `assert result.is_valid is True` — 只验证状态，不验证业务逻辑
- `assert result.score is not None` — 只验证存在性，不验证正确性
- `assert mock_client.chat.assert_called_once()` — 只验证调用，不验证参数
- `assert 0.0 <= result.score <= 1.0` — 只验证范围，不验证具体值

### 🟡 中等断言（可辅助使用）
- `assert result.score >= 0.8` — 验证分数区间
- `assert result.data["method"] == "llm_judge"` — 验证调用路径
- `assert result.error is not None` — 验证错误存在

### 🟢 强断言（必须包含至少1个）
- `assert result.score == pytest.approx(0.85, abs=0.01)` — 验证精确分数
- `assert result.score_full > result.score_partial > result.score_unrelated` — 验证单调性
- `assert "关键词" in mock_client.chat.call_args[0][0]` — 验证Prompt内容
- `assert result.data["risk_level"] == "high"` — 验证业务规则结果

## 二、评估器测试强制要求

每个评估器测试文件必须满足以下条件：

### 1. 每个测试类至少包含1个强断言
```python
# ✅ 正确：验证精确业务逻辑
def test_exact_score(self):
    result = evaluator.evaluate(request)
    assert result.score == pytest.approx(0.85, abs=0.01)  # 强断言
    assert result.data["method"] == "llm_judge"           # 中等断言

# ❌ 错误：只有弱断言
def test_valid_input(self):
    result = evaluator.evaluate(request)
    assert result.is_valid is True  # 弱断言
    assert result.score is not None # 弱断言
```

### 2. 必须验证调用路径和参数
```python
# ✅ 正确：验证Prompt构建
def test_prompt_contains_key_fields(self):
    evaluator.evaluate(request)
    call_args = mock_client.chat.call_args
    prompt = call_args[0][0]
    assert "期望输出" in prompt     # 强断言：验证Prompt内容
    assert "实际输出" in prompt     # 强断言：验证Prompt内容
    assert "评估维度" in prompt     # 强断言：验证Prompt结构
```

### 3. 必须验证业务规则单调性
```python
# ✅ 正确：验证评分单调性
def test_monotonicity(self):
    score_full = evaluator.evaluate(request_full).score
    score_partial = evaluator.evaluate(request_partial).score
    score_unrelated = evaluator.evaluate(request_unrelated).score
    
    assert score_full > score_partial     # 强断言：完全一致 > 部分一致
    assert score_partial > score_unrelated # 强断言：部分一致 > 不相关
```

### 4. 必须验证降级策略
```python
# ✅ 正确：验证降级逻辑
def test_fallback_strategy(self):
    mock_client.chat.return_value = "invalid"  # 触发降级
    result = evaluator.evaluate(request)
    
    assert result.is_valid is True              # 中等断言
    assert result.data["method"] == "rule_based_fallback"  # 强断言：验证降级路径
    assert result.data["fallback_reason"] is not None      # 中等断言
```

### 5. 必须验证边界条件
```python
# ✅ 正确：验证边界行为
def test_boundary_case(self):
    long_text = "测试" * 1000
    result = evaluator.evaluate(request_with_long_text)
    
    assert result.is_valid is True  # 中等断言
    assert result.score >= 0.9      # 强断言：完全相同应得高分
```

## 三、断言覆盖率统计

### 强制要求
- **正向测试**：至少2个强断言 + 1个中等断言
- **负向测试**：至少1个强断言（验证错误消息内容）+ 1个中等断言
- **边界测试**：至少1个强断言（验证边界行为）
- **依赖测试**：至少1个强断言（验证参数传递）
- **降级测试**：至少2个强断言（验证降级路径和结果）

### 评分标准
| 强断言数量 | 评分 | 状态 |
|-----------|------|------|
| ≥3个/测试类 | ⭐⭐⭐⭐⭐ | 优秀 |
| 2个/测试类 | ⭐⭐⭐⭐ | 良好 |
| 1个/测试类 | ⭐⭐⭐ | 及格 |
| 0个/测试类 | ⭐⭐ | 不及格 |

## 四、代码审查检查清单

```markdown
# 测试代码审查检查清单

- [ ] 每个测试类至少有1个强断言
- [ ] Mock调用必须验证参数内容（不仅仅是调用次数）
- [ ] 评分结果必须验证具体值或区间关系
- [ ] 业务规则必须验证单调性或精确逻辑
- [ ] 降级路径必须验证method字段和fallback_reason
- [ ] 错误测试必须验证错误消息具体内容
- [ ] 边界测试必须验证边界行为的正确性
- [ ] 没有单独使用弱断言的测试用例
```

## 五、QA门禁规则

### 规则1：断言强度门槛
- 评估器测试的强断言比例必须 ≥ 50%
- 低于50%的测试文件不允许合并

### 规则2：变异测试门槛
- 核心评估器的变异测试得分必须 ≥ 80%
- 变异测试未通过的代码不允许合并

### 规则3：回归测试门槛
- 任何代码变更必须通过所有现有测试
- 测试失败率必须 = 0%

## 六、示例：从弱断言到强断言

### 改造前（弱断言）
```python
def test_qa_evaluation(self):
    result = evaluator.evaluate(request)
    assert result.is_valid is True  # ❌ 弱断言
    assert 0.0 <= result.score <= 1.0  # ❌ 弱断言
```

### 改造后（强断言）
```python
def test_qa_evaluation(self):
    result = evaluator.evaluate(request)
    assert result.is_valid is True              # 中等断言
    assert result.score == pytest.approx(0.85, abs=0.01)  # ✅ 强断言：精确分数
    assert result.data["method"] == "llm_judge" # ✅ 强断言：调用路径
    assert "raw_llm_judgment" in result.data   # 中等断言：数据完整性
```

---

**生效日期**：2026-07-01  
**适用范围**：所有评估器测试文件  
**执行者**：所有开发人员和代码审查人员