# 架构师审查报告：10个失败测试分析

> **审查目标**：确认设计意图，决定是修复测试还是修改实现
> **审查时间**：2026-06-19
> **测试结果**：102个通过，10个失败

---

## 一、失败测试清单

| # | 测试文件 | 测试名称 | 失败原因 |
|---|---------|---------|---------|
| 1 | test_golden_dataset.py | test_correct_sample_partial_scores | KeyError: 'correctness' |
| 2 | test_golden_dataset.py | test_get_few_shot_examples_sorted_by_update_time | sample_id不在示例中 |
| 3 | test_adaptive_calibration.py | test_pre_execution_check_no_version_warns | 状态不符预期 |
| 4 | test_drift_evaluator.py | test_detect_score_history_no_drift | KeyError: 'baseline_score' |
| 5 | test_drift_evaluator.py | test_detect_score_history_with_drift | drift_score=0 |
| 6 | test_drift_evaluator.py | test_detect_statistics_with_baseline | drift_score<0.5 |
| 7 | test_drift_evaluator.py | test_statistics_computation | token_count不存在 |
| 8 | test_drift_evaluator.py | test_keyword_extraction | 关键词提取行为不符预期 |
| 9 | test_evaluator_version.py | test_check_calibration_status_threshold_calculation | 参数不支持 |
| 10 | test_closed_loop.py | test_full_loop_execute_feedback_analyze_optimize | can_proceed=True |

---

## 二、详细分析（按优先级排序）

### 🔴 P0：核心功能设计问题

#### 问题1：correct_sample覆盖行为（test_golden_dataset.py）

**测试代码**：
```python
# tests/domain/test_golden_dataset.py:227
def test_correct_sample_partial_scores(self, manager_with_sample):
    """校正样本可以只更新部分评分"""
    manager, dataset = manager_with_sample

    # 只校正safety分数，correctness保持不变
    corrected_sample = manager.correct_sample(
        sample_id="sample_001",
        corrected_scores={"safety": 95},  # 只更新safety
        corrected_by="expert_user"
    )

    assert corrected_sample.scores["safety"] == 95
    assert corrected_sample.scores["correctness"] == 70  # 保持原值 ❌ KeyError
```

**实现代码**：
```python
# src/domain/golden_dataset.py:74
def correct_sample(self, sample_id: str, corrected_scores: Dict[str, float], corrected_by: str) -> Optional[GoldenSample]:
    sample = self._sample_index.get(sample_id)
    if not sample:
        return None
    sample.scores = corrected_scores  # ❌ 直接覆盖，而非合并
    sample.human_corrected = True
    sample.corrected_by = corrected_by
    sample.corrected_at = datetime.utcnow()
    return sample
```

**问题分析**：
- **预期行为**：校正只更新指定维度，保留其他维度
- **实际行为**：校正完全覆盖原有scores
- **影响范围**：人工校正功能，可能导致数据丢失

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 改为合并而非覆盖 | 需修改golden_dataset.py |
| **B. 修改测试** | 测试预期改为覆盖行为 | 需更新测试断言 |
| **C. 新增方法** | 新增`merge_sample_scores()`方法 | 保持现有行为 |

**建议**：选择A，修改实现为合并行为，避免数据丢失。

---

#### 问题2：pre_execution_check无版本时状态（test_adaptive_calibration.py）

**测试代码**：
```python
# tests/domain/test_adaptive_calibration.py:227
def test_pre_execution_check_no_version_warns(self, calibrator):
    """无版本注册应警告"""
    with patch('src.domain.adaptive_calibration.evaluator_version_manager') as mock_version_mgr:
        mock_version_mgr.get_current_version.return_value = None

        check = calibrator.pre_execution_check("test_evaluator")

        assert check.can_proceed is True
        assert check.status == CalibrationStatus.NOT_CALIBRATED  # ❌ 实际返回CALIBRATED
        assert "未注册版本" in check.message
```

**实现代码**：
```python
# src/domain/adaptive_calibration.py:324
# 没有指定数据集，检查全局校准状态
calibration_status = evaluator_version_manager.check_calibration_status(evaluator_name)
can_proceed = calibration_status.get("can_proceed", True)

if not calibration_status.get("calibration_score"):
    return PreExecutionCheck(
        evaluator_name=evaluator_name,
        evaluator_version=evaluator_version,
        can_proceed=True,  # 允许执行，但会提示
        status=CalibrationStatus.NOT_CALIBRATED,
        message="评估器尚未校准，建议先在黄金数据集上校准",
        warnings=["评估结果可能不可靠"]
    )
```

**问题分析**：
- **预期行为**：无版本时返回NOT_CALIBRATED
- **实际行为**：返回CALIBRATED（因为check_calibration_status返回"no_version"）
- **影响范围**：闭环决策逻辑

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 无版本时返回NOT_CALIBRATED | 需修改adaptive_calibration.py |
| **B. 修改测试** | 测试预期改为CALIBRATED | 需更新测试断言 |
| **C. 新增状态** | 新增NO_VERSION状态 | 更清晰的状态区分 |

**建议**：选择C，新增NO_VERSION状态，更清晰区分"未校准"和"无版本"。

---

### 🔴 P0：完整闭环逻辑问题

#### 问题3：完整闭环测试失败（test_closed_loop.py）

**测试代码**：
```python
# tests/domain/test_closed_loop.py:403
def test_full_loop_execute_feedback_analyze_optimize(self, loop_components):
    # ... 完整闭环流程 ...

    # 4.2 检查优化决策
    check = calibrator.pre_execution_check("llm_as_judge")

    # 漂移时拒绝执行
    assert check.can_proceed is False  # ❌ 实际返回True
    assert check.status == CalibrationStatus.DRIFTED
```

**问题分析**：
- **预期行为**：漂移后pre_execution_check应返回can_proceed=False
- **实际行为**：返回can_proceed=True（因为未指定dataset_id）
- **影响范围**：闭环优化阶段的决策逻辑

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改测试** | 测试传入dataset_id | 测试需更新 |
| **B. 修改实现** | 无dataset时也检查全局状态 | 实现需修改 |
| **C. 修改闭环逻辑** | 优化后必须指定dataset校准 | 业务流程需确认 |

**建议**：选择A，测试需传入dataset_id以触发校准检查。

---

### 🟡 P1：API设计一致性

#### 问题4：_compute_text_stats命名（test_drift_evaluator.py）

**测试代码**：
```python
# tests/domain/test_drift_evaluator.py:207
def test_statistics_computation(self, evaluator):
    """统计特征计算"""
    text = "这是第一句。这是第二句。这是第三句。"
    stats = evaluator._compute_text_stats(text)

    assert "length" in stats
    assert "token_count" in stats  # ❌ 实际是word_count
    assert "sentence_count" in stats
```

**实现代码**：
```python
# src/domain/evaluators/drift.py:245
def _compute_text_stats(self, text: str) -> dict:
    return {
        "length": len(text),
        "word_count": len(words),  # 使用word_count
        "sentence_count": len(sentences),
        "avg_sentence_length": ...,
        "avg_word_length": ...,
    }
```

**问题分析**：
- **预期行为**：返回token_count
- **实际行为**：返回word_count
- **影响范围**：命名一致性

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 改为token_count | 需修改drift.py |
| **B. 修改测试** | 测试使用word_count | 需更新测试 |
| **C. 保持现状** | word_count语义正确 | 无需修改 |

**建议**：选择C，word_count语义正确（统计单词数而非token数）。

---

#### 问题5：漂移检测返回字段（test_drift_evaluator.py）

**测试代码**：
```python
# tests/domain/test_drift_evaluator.py:151
def test_detect_score_history_no_drift(self, evaluator, mock_repository):
    result = evaluator._detect_by_score_history("case_001")

    assert result["baseline_score"] is not None  # ❌ KeyError
```

**实现代码**：
```python
# src/domain/evaluators/drift.py:95
def _detect_by_score_history(self, case_id: str) -> dict:
    # ...
    return {
        "method": "score_history",
        "baseline_score": baseline_score,  # 存在
        "current_score": current_score,
        "drift_score": min(drift_score, 1.0),
        "detected": drift_score > 0.2,
        "confidence": 0.85,
    }
```

**问题分析**：
- **预期行为**：返回baseline_score字段
- **实际行为**：历史数据不足时返回不同结构（无baseline_score）
- **影响范围**：API契约

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 历史不足时也返回baseline_score=None | API一致性 |
| **B. 修改测试** | 测试检查历史数据充足场景 | 测试需更新 |

**建议**：选择B，测试应检查历史数据充足场景。

---

### 🟡 P1：阈值设置合理性

#### 问题6：漂移检测阈值（test_drift_evaluator.py）

**测试代码**：
```python
# tests/domain/test_drift_evaluator.py:169
def test_detect_score_history_with_drift(self, evaluator):
    # 基线分数0.9，当前分数0.5，变化45%
    result = evaluator._detect_by_score_history("case_new")

    assert result["drift_score"] > 0.2  # ❌ 实际返回0
```

**问题分析**：
- **预期行为**：分数变化45%应检测为漂移
- **实际行为**：drift_score=0（因为实现逻辑不同）
- **影响范围**：漂移检测准确性

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 调整漂移检测算法 | 需修改drift.py |
| **B. 修改测试** | 测试使用正确场景 | 测试需更新 |
| **C. 确认阈值** | 确认0.2阈值是否合理 | 需业务验证 |

**建议**：选择B+C，测试需使用正确场景，阈值需业务验证。

---

#### 问题7：校准阈值参数（test_evaluator_version.py）

**测试代码**：
```python
# tests/domain/test_evaluator_version.py:231
def test_check_calibration_status_threshold_calculation(self, manager):
    version = manager.register_version(
        evaluator_name="test_evaluator",
        version="1.0.0",
        code_hash="hash1",
        config={},
        calibration_threshold=10.0  # ❌ 参数不支持
    )
```

**实现代码**：
```python
# src/domain/evaluator_version.py:97
def register_version(
    self,
    evaluator_name: str,
    version: str,
    code_hash: str,
    config: Dict[str, Any],
    changelog: str = "",
    created_by: str = "system"
) -> EvaluatorVersion:
    # 不支持calibration_threshold参数
```

**问题分析**：
- **预期行为**：注册时可设置校准阈值
- **实际行为**：不支持参数传入
- **影响范围**：阈值灵活性

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 新增calibration_threshold参数 | 需修改evaluator_version.py |
| **B. 修改测试** | 测试使用默认阈值 | 测试需更新 |
| **C. 配置管理** | 阈值从config中读取 | 灵活配置 |

**建议**：选择C，阈值从config中读取，保持灵活性。

---

### 🟢 P2：次要问题

#### 问题8：Few-shot示例格式（test_golden_dataset.py）

**测试代码**：
```python
# tests/domain/test_golden_dataset.py:322
def test_get_few_shot_examples_sorted_by_update_time(self, manager_with_corrected_samples):
    examples = manager.get_few_shot_examples(dataset.id, limit=5)

    assert "sample_001" in examples[0] or "sample_000" in examples[0]  # ❌ sample_id不在示例中
```

**实现代码**：
```python
# src/domain/golden_dataset.py:26
def to_few_shot_example(self) -> str:
    scores_str = ', '.join([f'{k}: {v}/100' for k, v in self.scores.items()])
    return f'示例开始\n用户问题: {self.user_input}\n模型输出: {self.actual_output}...\n示例结束\n'
    # 不包含sample_id
```

**问题分析**：
- **预期行为**：示例包含sample_id
- **实际行为**：示例不包含sample_id
- **影响范围**：用户理解

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 示例包含sample_id | 需修改golden_dataset.py |
| **B. 修改测试** | 测试不检查sample_id | 测试需更新 |
| **C. 产品确认** | 确认用户是否需要sample_id | 需PM确认 |

**建议**：选择C，需产品经理确认用户需求。

---

#### 问题9：关键词提取行为（test_drift_evaluator.py）

**测试代码**：
```python
# tests/domain/test_drift_evaluator.py:477
def test_keyword_extraction(self, evaluator):
    text = "人工智能是计算机科学的一个重要分支"
    keywords = evaluator._extract_keywords(text)

    assert "人工智能" in keywords or "人工" in keywords  # ❌ 实际返回完整短语
```

**实现代码**：
```python
# src/domain/evaluators/drift.py:320
def _extract_keywords(self, text: str) -> list:
    words = re.findall(r'\w+', text.lower())
    # ...
    return filtered  # 返回完整短语而非拆分
```

**问题分析**：
- **预期行为**：拆分关键词
- **实际行为**：保留完整短语
- **影响范围**：语义分析准确性

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 拆分关键词 | 需修改drift.py |
| **B. 修改测试** | 测试检查完整短语 | 测试需更新 |
| **C. 保持现状** | 完整短语语义更准确 | 无需修改 |

**建议**：选择C，完整短语语义更准确。

---

#### 问题10：统计漂移阈值（test_drift_evaluator.py）

**测试代码**：
```python
# tests/domain/test_drift_evaluator.py:198
def test_detect_statistics_with_baseline(self, evaluator):
    result = evaluator._detect_by_statistics(
        actual_output="短文本",  # 3字符
        baseline_output="这是一段比较长的文本内容..."  # 约30字符
    )

    assert result["drift_score"] > 0.5  # ❌ 实际返回0.4375
```

**问题分析**：
- **预期行为**：长度差异大时drift_score>0.5
- **实际行为**：drift_score=0.4375（差异10倍，但分数未超过0.5）
- **影响范围**：统计漂移检测阈值

**架构师决策点**：
| 选项 | 说明 | 影响 |
|------|------|------|
| **A. 修改实现** | 调整统计漂移算法 | 需修改drift.py |
| **B. 修改测试** | 测试使用正确阈值 | 测试需更新 |
| **C. 确认阈值** | 确认统计漂移阈值是否合理 | 需业务验证 |

**建议**：选择B+C，测试需使用正确阈值，阈值需业务验证。

---

## 三、架构师决策汇总表

| # | 问题 | 建议选项 | 优先级 | 需修改文件 |
|---|------|---------|--------|-----------|
| 1 | correct_sample覆盖行为 | A. 修改实现 | P0 | golden_dataset.py |
| 2 | pre_execution_check状态 | C. 新增NO_VERSION状态 | P0 | adaptive_calibration.py |
| 3 | 完整闭环测试失败 | A. 修改测试 | P0 | test_closed_loop.py |
| 4 | _compute_text_stats命名 | C. 保持现状 | P2 | 无需修改 |
| 5 | 漂移检测返回字段 | B. 修改测试 | P1 | test_drift_evaluator.py |
| 6 | 漂移检测阈值 | B+C. 修改测试+确认阈值 | P1 | test_drift_evaluator.py |
| 7 | 校准阈值参数 | C. 配置管理 | P1 | evaluator_version.py |
| 8 | Few-shot示例格式 | C. 产品确认 | P2 | 需PM确认 |
| 9 | 关键词提取行为 | C. 保持现状 | P2 | 无需修改 |
| 10 | 统计漂移阈值 | B+C. 修改测试+确认阈值 | P2 | test_drift_evaluator.py |

---

## 四、建议的修改方案

### 需修改实现（2个）

1. **golden_dataset.py**：correct_sample改为合并而非覆盖
2. **adaptive_calibration.py**：新增NO_VERSION状态

### 需修改测试（5个）

1. **test_closed_loop.py**：传入dataset_id
2. **test_drift_evaluator.py**：检查历史数据充足场景
3. **test_drift_evaluator.py**：使用正确漂移场景
4. **test_drift_evaluator.py**：使用正确统计阈值
5. **test_evaluator_version.py**：使用默认阈值

### 需产品确认（3个）

1. Few-shot示例是否需要sample_id
2. 漂移检测阈值0.2是否合理
3. 统计漂移阈值是否合理

---

**请架构师确认以上分析，并决策修改方案。**
