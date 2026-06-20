# 元测试（Meta-testing）框架设计

## 元测试概念理解

### 什么是元测试？

**元测试**是使用测试系统自身的评估器来评估测试代码质量和检测测试漂移，形成"测试评估测试"的闭环验证机制。

### 元测试的核心价值

1. **自我验证**: 测试系统验证自身的测试能力
2. **质量闭环**: 测试代码质量得到持续验证
3. **漂移检测**: 及时发现测试代码的退化
4. **自动化**: 无需人工审查，自动评估测试质量
5. **持续改进**: 形成测试质量的持续改进循环

### 元评测闭环流程

```
┌─────────────────────────────────────────────────────────┐
│          测试代码 (Test Code)                            │
│  - 单元测试                                              │
│  - 集成测试                                              │
│  - E2E测试                                               │
└──────────┬──────────────────────────────────────────────┘
           │
           ├──────────┬──────────┬──────────┐
           ▼          ▼          ▼          ▼
    CodeEvaluator  LLMAsJudge  DriftEvaluator  其他评估器
    (代码质量)      (逻辑合理性)  (测试漂移)      (覆盖率等)
           │          │          │          │
           └──────────┴──────────┴──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│          元测试报告 (Meta-test Report)                   │
│  - 测试代码质量评分                                       │
│  - 测试逻辑合理性评分                                     │
│  - 测试漂移检测结果                                       │
│  - 测试覆盖率分析                                         │
└──────────┬──────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────┐
│          测试改进 (Test Improvement)                     │
│  - 重构测试代码                                          │
│  - 补充测试场景                                          │
│  - 修复测试漂移                                          │
│  - 提升测试质量                                          │
└──────────┬──────────────────────────────────────────────┘
           │
           └──────────────────────────────────────────────┐
           │                                              │
           ▼                                              │
    更高质量的测试代码 ───────────────────────────────────┘
    更可靠的测试系统
```

---

## 元测试评估维度

### 1. CodeEvaluator - 测试代码质量评估

**评估维度**:
- **代码结构**: 测试代码的组织结构、模块化程度
- **命名规范**: 测试函数命名是否清晰、符合规范
- **断言强度**: 断言是否足够强，是否验证业务逻辑
- **Mock使用**: Mock是否正确配置，是否隔离依赖
- **代码重复**: 测试代码是否存在重复，是否需要抽取公共方法
- **可读性**: 测试代码是否易于理解，注释是否充分

**评估指标**:
```python
{
    "test_code_quality": {
        "structure_score": 0.85,  # 结构评分
        "naming_score": 0.90,     # 命名评分
        "assertion_score": 0.75,  # 断言评分
        "mock_score": 0.80,       # Mock评分
        "duplication_score": 0.70, # 重复评分
        "readability_score": 0.85, # 可读性评分
        "overall_score": 0.82     # 总体评分
    }
}
```

### 2. LLMAsJudgeEvaluator - 测试逻辑合理性评估

**评估维度**:
- **测试场景覆盖**: 是否覆盖正向、负向、边界、异常场景
- **测试逻辑正确性**: 测试逻辑是否正确，是否验证预期行为
- **测试独立性**: 测试是否相互独立，是否共享状态
- **测试可维护性**: 测试是否易于维护，是否易于修改
- **测试有效性**: 测试是否真正验证业务逻辑，是否是弱断言

**评估指标**:
```python
{
    "test_logic_quality": {
        "scenario_coverage": 0.80,  # 场景覆盖
        "logic_correctness": 0.85,  # 逻辑正确性
        "test_independence": 0.90,  # 测试独立性
        "maintainability": 0.75,    # 可维护性
        "effectiveness": 0.80,      # 有效性
        "overall_score": 0.82       # 总体评分
    }
}
```

### 3. DriftEvaluator - 测试漂移检测

**评估维度**:
- **测试行为漂移**: 测试行为是否发生变化
- **测试结果漂移**: 测试结果是否发生变化
- **测试覆盖率漂移**: 测试覆盖率是否下降
- **测试性能漂移**: 测试执行时间是否增加
- **测试依赖漂移**: 测试依赖是否发生变化

**评估指标**:
```python
{
    "test_drift_detection": {
        "behavior_drift": False,     # 行为漂移
        "result_drift": False,       # 结果漂移
        "coverage_drift": -5%,       # 覆盖率漂移(下降5%)
        "performance_drift": +10%,   # 性能漂移(增加10%)
        "dependency_drift": False,   # 依赖漂移
        "overall_drift_score": 0.85  # 总体漂移评分
    }
}
```

---

## 元测试实施方案

### Phase 1: 元测试框架搭建 (本周)

#### 1.1 创建元测试评估器

**文件**: `src/domain/evaluators/meta_test_evaluator.py`

```python
from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.code import CodeEvaluator
from src.domain.evaluators.llm_as_judge import LLMAsJudgeEvaluator
from src.domain.evaluators.drift import DriftEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class MetaTestEvaluator(BaseEvaluator):
    """元测试评估器 - 使用系统自身的评估器评估测试代码"""

    def __init__(self):
        self.code_evaluator = CodeEvaluator()
        self.llm_judge_evaluator = LLMAsJudgeEvaluator()
        self.drift_evaluator = DriftEvaluator()

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估测试代码质量"""
        test_code = self.get_payload_data(request, "test_code")
        test_results = self.get_payload_data(request, "test_results")
        baseline_results = self.get_payload_data(request, "baseline_results")

        # 1. 评估测试代码质量
        code_quality = self._evaluate_code_quality(test_code)

        # 2. 评估测试逻辑合理性
        logic_quality = self._evaluate_logic_quality(test_code)

        # 3. 检测测试漂移
        drift_detection = self._detect_test_drift(test_results, baseline_results)

        # 4. 计算总体评分
        overall_score = self._calculate_overall_score(
            code_quality, logic_quality, drift_detection
        )

        return self.create_success_response(
            text="元测试评估完成",
            score=overall_score,
            data={
                "code_quality": code_quality,
                "logic_quality": logic_quality,
                "drift_detection": drift_detection,
                "overall_score": overall_score,
                "recommendations": self._generate_recommendations(
                    code_quality, logic_quality, drift_detection
                ),
            }
        )

    def _evaluate_code_quality(self, test_code: str) -> dict:
        """使用CodeEvaluator评估测试代码质量"""
        request = EvaluationSchema(
            id="meta_test_code",
            type="code",
            payload={
                "code": test_code,
                "language": "python",
                "evaluation_criteria": [
                    "structure",
                    "naming",
                    "assertion",
                    "mock",
                    "duplication",
                    "readability"
                ]
            }
        )
        result = self.code_evaluator.evaluate(request)
        return result.data

    def _evaluate_logic_quality(self, test_code: str) -> dict:
        """使用LLMAsJudgeEvaluator评估测试逻辑合理性"""
        request = EvaluationSchema(
            id="meta_test_logic",
            type="llm_as_judge",
            payload={
                "test_code": test_code,
                "evaluation_criteria": [
                    "scenario_coverage",
                    "logic_correctness",
                    "test_independence",
                    "maintainability",
                    "effectiveness"
                ]
            }
        )
        result = self.llm_judge_evaluator.evaluate(request)
        return result.data

    def _detect_test_drift(
        self,
        test_results: dict,
        baseline_results: dict
    ) -> dict:
        """使用DriftEvaluator检测测试漂移"""
        request = EvaluationSchema(
            id="meta_test_drift",
            type="drift",
            payload={
                "current_results": test_results,
                "baseline_results": baseline_results,
                "drift_threshold": 0.05
            }
        )
        result = self.drift_evaluator.evaluate(request)
        return result.data

    def _calculate_overall_score(
        self,
        code_quality: dict,
        logic_quality: dict,
        drift_detection: dict
    ) -> float:
        """计算元测试总体评分"""
        # 加权平均
        weights = {
            "code_quality": 0.3,
            "logic_quality": 0.4,
            "drift_detection": 0.3
        }

        scores = {
            "code_quality": code_quality.get("overall_score", 1.0),
            "logic_quality": logic_quality.get("overall_score", 1.0),
            "drift_detection": drift_detection.get("overall_drift_score", 1.0)
        }

        overall_score = sum(
            scores[key] * weights[key]
            for key in scores
        )

        return overall_score

    def _generate_recommendations(
        self,
        code_quality: dict,
        logic_quality: dict,
        drift_detection: dict
    ) -> list[str]:
        """生成测试改进建议"""
        recommendations = []

        # 代码质量建议
        if code_quality.get("assertion_score", 1.0) < 0.8:
            recommendations.append("建议增强断言强度，验证业务逻辑而非仅状态")

        if code_quality.get("duplication_score", 1.0) < 0.8:
            recommendations.append("建议抽取公共测试方法，减少代码重复")

        # 逻辑质量建议
        if logic_quality.get("scenario_coverage", 1.0) < 0.8:
            recommendations.append("建议补充边界测试和异常测试场景")

        if logic_quality.get("test_independence", 1.0) < 0.8:
            recommendations.append("建议使用fixture管理共享状态，确保测试独立")

        # 漂移检测建议
        if drift_detection.get("coverage_drift", 0) < -0.05:
            recommendations.append("建议补充缺失的测试用例，恢复测试覆盖率")

        if drift_detection.get("performance_drift", 0) > 0.1:
            recommendations.append("建议优化测试性能，减少执行时间")

        return recommendations
```

#### 1.2 创建元测试API接口

**文件**: `src/api/routes/meta_test.py`

```python
from fastapi import APIRouter, Depends
from src.domain.evaluators.meta_test_evaluator import MetaTestEvaluator
from src.schemas.evaluation import EvaluationSchema

router = APIRouter(prefix="/meta-test", tags=["Meta-testing"])


@router.post("/evaluate")
async def evaluate_test_quality(request: EvaluationSchema):
    """评估测试代码质量"""
    evaluator = MetaTestEvaluator()
    result = evaluator.evaluate(request)
    return result


@router.post("/batch-evaluate")
async def batch_evaluate_test_quality(tests: list[EvaluationSchema]):
    """批量评估测试代码质量"""
    evaluator = MetaTestEvaluator()
    results = []
    for test in tests:
        result = evaluator.evaluate(test)
        results.append(result)
    return results


@router.get("/report/{test_id}")
async def get_meta_test_report(test_id: str):
    """获取元测试报告"""
    # 从数据库获取元测试报告
    # TODO: 实现数据库查询
    return {"test_id": test_id, "report": "元测试报告"}
```

---

### Phase 2: 元测试自动化集成 (下周)

#### 2.1 CI/CD集成元测试

**文件**: `.github/workflows/meta-test.yml`

```yaml
name: Meta-testing

on:
  push:
    paths:
      - 'tests/**'
  pull_request:
    paths:
      - 'tests/**'

jobs:
  meta-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run unit tests with coverage
        run: |
          pytest tests/unit/ -v \
            --cov=src \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=80

      - name: Extract test code
        run: |
          python scripts/extract_test_code.py

      - name: Run meta-test evaluation
        run: |
          python scripts/run_meta_test.py

      - name: Generate meta-test report
        run: |
          python scripts/generate_meta_test_report.py

      - name: Upload meta-test report
        uses: actions/upload-artifact@v3
        with:
          name: meta-test-report
          path: meta_test_report.html

      - name: Check meta-test quality gate
        run: |
          python scripts/check_meta_test_gate.py
```

#### 2.2 元测试报告生成

**文件**: `scripts/generate_meta_test_report.py`

```python
"""生成元测试报告"""

import json
from pathlib import Path
from datetime import datetime


def generate_meta_test_report():
    """生成HTML格式的元测试报告"""
    # 加载元测试结果
    meta_test_results = load_meta_test_results()

    # 生成HTML报告
    html_report = generate_html_report(meta_test_results)

    # 保存报告
    report_path = Path("meta_test_report.html")
    report_path.write_text(html_report)

    print(f"元测试报告已生成: {report_path}")


def load_meta_test_results():
    """加载元测试结果"""
    results_path = Path("meta_test_results.json")
    if results_path.exists():
        return json.loads(results_path.read_text())
    return {}


def generate_html_report(results: dict):
    """生成HTML报告"""
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>元测试报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .score { font-size: 24px; font-weight: bold; }
        .good { color: green; }
        .warning { color: orange; }
        .bad { color: red; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>元测试报告</h1>
    <p>生成时间: {timestamp}</p>

    <h2>总体评分</h2>
    <div class="score {score_class}">{overall_score}</div>

    <h2>代码质量评估</h2>
    <table>
        <tr><th>评估维度</th><th>评分</th><th>状态</th></tr>
        <tr><td>代码结构</td><td>{structure_score}</td><td>{structure_status}</td></tr>
        <tr><td>命名规范</td><td>{naming_score}</td><td>{naming_status}</td></tr>
        <tr><td>断言强度</td><td>{assertion_score}</td><td>{assertion_status}</td></tr>
        <tr><td>Mock使用</td><td>{mock_score}</td><td>{mock_status}</td></tr>
        <tr><td>代码重复</td><td>{duplication_score}</td><td>{duplication_status}</td></tr>
        <tr><td>可读性</td><td>{readability_score}</td><td>{readability_status}</td></tr>
    </table>

    <h2>逻辑质量评估</h2>
    <table>
        <tr><th>评估维度</th><th>评分</th><th>状态</th></tr>
        <tr><td>场景覆盖</td><td>{scenario_coverage}</td><td>{scenario_status}</td></tr>
        <tr><td>逻辑正确性</td><td>{logic_correctness}</td><td>{logic_status}</td></tr>
        <tr><td>测试独立性</td><td>{test_independence}</td><td>{independence_status}</td></tr>
        <tr><td>可维护性</td><td>{maintainability}</td><td>{maintainability_status}</td></tr>
        <tr><td>有效性</td><td>{effectiveness}</td><td>{effectiveness_status}</td></tr>
    </table>

    <h2>漂移检测结果</h2>
    <table>
        <tr><th>漂移类型</th><th>检测结果</th><th>漂移程度</th></tr>
        <tr><td>行为漂移</td><td>{behavior_drift}</td><td>{behavior_drift_level}</td></tr>
        <tr><td>结果漂移</td><td>{result_drift}</td><td>{result_drift_level}</td></tr>
        <tr><td>覆盖率漂移</td><td>{coverage_drift}</td><td>{coverage_drift_level}</td></tr>
        <tr><td>性能漂移</td><td>{performance_drift}</td><td>{performance_drift_level}</td></tr>
        <tr><td>依赖漂移</td><td>{dependency_drift}</td><td>{dependency_drift_level}</td></tr>
    </table>

    <h2>改进建议</h2>
    <ul>
        {recommendations}
    </ul>
</body>
</html>
    """.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        overall_score=results.get("overall_score", 0.0),
        score_class=get_score_class(results.get("overall_score", 0.0)),
        # ... 其他字段
    )

    return html


def get_score_class(score: float):
    """根据评分返回CSS类"""
    if score >= 0.8:
        return "good"
    elif score >= 0.6:
        return "warning"
    else:
        return "bad"


if __name__ == "__main__":
    generate_meta_test_report()
```

---

### Phase 3: 元测试能力落地 (下周)

#### 3.1 测试代码质量门禁

**文件**: `scripts/check_meta_test_gate.py`

```python
"""检查元测试质量门禁"""

import json
from pathlib import Path


def check_meta_test_gate():
    """检查元测试是否满足质量门禁"""
    # 加载元测试结果
    results_path = Path("meta_test_results.json")
    if not results_path.exists():
        print("元测试结果不存在")
        return False

    results = json.loads(results_path.read_text())

    # 检查质量门禁
    quality_gates = {
        "overall_score": 0.8,  # 总体评分≥80%
        "code_quality": 0.75,  # 代码质量≥75%
        "logic_quality": 0.80,  # 逻辑质量≥80%
        "drift_detection": 0.85,  # 漂移评分≥85%
    }

    passed = True
    for gate_name, threshold in quality_gates.items():
        actual_score = results.get(gate_name, 0.0)
        if actual_score < threshold:
            print(f"质量门禁未通过: {gate_name}={actual_score} < {threshold}")
            passed = False
        else:
            print(f"质量门禁通过: {gate_name}={actual_score} ≥ {threshold}")

    if passed:
        print("✅ 所有质量门禁通过")
    else:
        print("❌ 质量门禁未通过，请改进测试代码")

    return passed


if __name__ == "__main__":
    passed = check_meta_test_gate()
    exit(0 if passed else 1)
```

#### 3.2 元测试持续改进循环

**流程**:
```
1. 开发测试代码
2. 运行单元测试
3. 运行元测试评估
4. 生成元测试报告
5. 检查质量门禁
6. 改进测试代码
7. 重新评估
8. 达到质量标准
```

---

## 元测试应用场景

### 1. 新测试代码评估

**场景**: 开发新的测试用例时，使用元测试评估测试质量

**流程**:
```python
# 开发测试代码
test_code = """
def test_security_evaluator_injection():
    evaluator = SecurityEvaluator()
    request = EvaluationSchema(...)
    result = evaluator.evaluate(request)
    assert result.is_valid is True
"""

# 运行元测试评估
meta_test_request = EvaluationSchema(
    id="new_test",
    type="meta_test",
    payload={
        "test_code": test_code,
        "test_results": {...},
        "baseline_results": {...}
    }
)
meta_test_result = meta_test_evaluator.evaluate(meta_test_request)

# 根据元测试报告改进测试代码
```

### 2. 测试漂移监控

**场景**: 定期监控测试漂移，及时发现测试退化

**流程**:
```python
# 每周运行元测试漂移检测
baseline_results = load_baseline_results()
current_results = run_tests_and_collect_results()

drift_request = EvaluationSchema(
    id="weekly_drift",
    type="meta_test",
    payload={
        "test_results": current_results,
        "baseline_results": baseline_results
    }
)
drift_result = meta_test_evaluator.evaluate(drift_request)

# 如果检测到漂移，生成告警
if drift_result.data["drift_detection"]["coverage_drift"] < -0.05:
    send_alert("测试覆盖率下降超过5%")
```

### 3. 测试重构验证

**场景**: 重构测试代码后，使用元测试验证重构效果

**流程**:
```python
# 重构前评估
before_refactor = meta_test_evaluator.evaluate(test_code_before)

# 重构测试代码
refactored_test_code = refactor_test_code(test_code_before)

# 重构后评估
after_refactor = meta_test_evaluator.evaluate(refactored_test_code)

# 对比评估结果
improvement = after_refactor.score - before_refactor.score
print(f"重构提升: {improvement}")
```

---

## 元测试收益分析

### 量化收益

| 指标 | 当前状态 | 元测试后 | 提升 |
|------|---------|---------|------|
| 测试代码质量 | 未评估 | 自动评估 | +100% |
| 测试漂移检测 | 手动检测 | 自动检测 | +80% |
| 测试改进效率 | 低 | 高 | +50% |
| 测试可靠性 | 中 | 高 | +30% |

### 质量收益

1. **测试质量闭环**: 测试代码质量得到持续验证
2. **漂移自动检测**: 及时发现测试退化
3. **改进建议自动生成**: 无需人工审查
4. **质量门禁自动化**: CI/CD集成质量检查

---

## 实施计划

### Week 1: 元测试框架搭建

- [ ] 创建MetaTestEvaluator
- [ ] 创建元测试API接口
- [ ] 编写元测试单元测试
- [ ] 验证元测试功能

### Week 2: 元测试自动化集成

- [ ] CI/CD集成元测试
- [ ] 元测试报告生成
- [ ] 元测试质量门禁
- [ ] 元测试持续改进循环

### Week 3: 元测试能力落地

- [ ] 新测试代码评估流程
- [ ] 测试漂移监控流程
- [ ] 测试重构验证流程
- [ ] 元测试文档完善

---

## 总结

元测试是测试工程的革命性创新，将测试系统自身的评估能力应用于测试代码，形成"测试评估测试"的闭环。通过CodeEvaluator、LLMAsJudgeEvaluator、DriftEvaluator三个评估器，实现测试代码质量评估、逻辑合理性评估、测试漂移检测，形成完整的元评测闭环。

**测试专家信心**: 元测试将显著提升测试工程能力，实现测试质量的持续改进和自动化验证。

---

**文档生成时间**: 2026-06-19
**测试专家**: Trae AI Testing Expert
**下一步行动**: 实施Phase 1元测试框架搭建