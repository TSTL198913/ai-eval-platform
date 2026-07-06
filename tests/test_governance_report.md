# 测试治理报告 - Mock同义反复检测

## 问题概述

现有测试用例中存在大量Mock同义反复测试，即：
- Mock返回值与断言期望值完全一致
- 验证的是"Mock穿透性"而非"业务逻辑正确性"
- 无法发现真实业务问题

## 标记规则

| 标记 | 含义 | 处理方式 |
|------|------|----------|
| `@pytest.mark.technical_debt` | Mock同义反复测试 | 保留但标记，后续逐步替换 |
| `@pytest.mark.weak_assertion` | 纯弱断言测试 | 考虑删除或增强 |
| `@pytest.mark.invariant` | 业务不变式测试 | 优先保留和扩展 |

## 需要标记的测试文件

### 1. tests/unit/evaluator/test_general_evaluator.py

| 测试方法 | 问题类型 | 建议 |
|----------|----------|------|
| `test_valid_input_returns_exact_score` | Mock同义反复 | 标记为technical_debt |
| `test_text_field_instead_of_user_input_works` | Mock同义反复 | 标记为technical_debt |
| `test_with_expected_output_returns_exact_score` | Mock同义反复 | 标记为technical_debt |

### 2. tests/unit/evaluator/test_qa_evaluator.py

| 测试方法 | 问题类型 | 建议 |
|----------|----------|------|
| `test_qa_valid_input_returns_exact_score` | Mock同义反复 | 标记为technical_debt |

### 3. tests/unit/evaluator/test_code_evaluator.py

| 测试方法 | 问题类型 | 建议 |
|----------|----------|------|
| `test_code_valid_input_returns_score` | Mock同义反复 | 标记为technical_debt |

## 已创建的高质量测试

### 业务不变式测试
- [test_evaluator_invariants_template.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_evaluator_invariants_template.py)
  - 语义排序不变式
  - Mock验证不变式
  - 对抗性断言
  - 分数边界不变式
  - 一致性不变式

### 校准测试
- [test_evaluator_calibration.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_evaluator_calibration.py)
  - Pearson相关系数检验
  - Cohen's Kappa检验
  - 均值偏差检验
  - 排序一致性检验

### 黄金标准测试（已存在）
- [test_code_evaluator_golden_standard.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_code_evaluator_golden_standard.py)
- [test_security_evaluator_golden_standard.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_security_evaluator_golden_standard.py)
- [test_semantic_evaluator_golden_standard.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_semantic_evaluator_golden_standard.py)
- [test_llm_as_judge_golden_standard.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_llm_as_judge_golden_standard.py)
- [test_composite_evaluator_golden_standard.py](file:///d:/workspace/ai-eval-platform-refactor/tests/unit/evaluator/test_composite_evaluator_golden_standard.py)

## 测试分层优先级

| 层级 | 测试类型 | 数量占比目标 | 作用 |
|------|----------|--------------|------|
| **P0** | 黄金标准测试 | 10-15% | 捕捉核心业务Bug |
| **P1** | 业务不变式测试 | 30-40% | 验证业务正确性 |
| **P2** | 校准测试 | 10-15% | 发现评估器偏见和漂移 |
| **P3** | 属性测试（Hypothesis） | 20-30% | 发现边界和对抗场景 |
| **P4** | Mock同义反复测试（技术债） | <10% | 快速回归验证 |

## 后续行动计划

1. **短期（1-2周）**：在现有测试文件中添加`@pytest.mark.technical_debt`标记
2. **中期（3-4周）**：用业务不变式测试替换Mock同义反复测试
3. **长期（1个月）**：运行变异测试，验证测试有效性，清理无效测试
4. **持续**：在CI/CD中集成断言强度分析，阻止新的Mock同义反复测试提交