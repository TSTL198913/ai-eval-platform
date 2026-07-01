SKILL.md: 工业级测试工程专家 (Test Engineer)
版本: 3.0.0
最后更新: 2026-07-01
适用领域: AI 评测系统、LLMOps、关键业务质量保障
触发条件: 涉及测试策略、质量门禁、缺陷分析、评估器校准的对话或任务

## 技能元数据
- **技能名称**: 工业级测试工程专家
- **技能 ID**: test-engineer-industry-4.0
- **核心定位**: 以 EFO 闭环驱动的 AI 原生测试体系，确保在 LLM 不确定性下仍满足工业级质量要求
- **适用平台**: Python 3.12+、pytest 8+、CI/CD 任意平台
- **依赖工具**: mutmut、Hypothesis、allure、OpenTelemetry、GoldenDatasetManager、AdaptiveCalibrator
- **输出物**: 测试策略、测试用例代码、质量报告、缺陷分析、校准日志、可观测性仪表板

### 实现状态汇总（截至 2026-07-01）

| 组件 | 状态 | 说明 |
|------|------|------|
| GoldenDatasetManager | ✅ 已实现 | 支持样本管理、高冲突检测、统计分析 |
| assertion_analyzer | ✅ 已实现 | 断言强度分析工具 |
| confidence_analyzer | ✅ 已实现 | 统计置信度分析工具 |
| Pre-commit 门禁 | ✅ 已实现 | 包含单元测试、断言强度、覆盖率检查 |
| OpenTelemetry | ✅ 已实现 | 评估管线完整 trace |
| Prometheus Metrics | ✅ 已实现 | 状态机监控、置信度分布 |
| AdaptiveCalibrator | ✅ 已实现 | 自动校准机制，偏差>5%触发警报 |
| llm-guard | ✅ 已实现 | 安全扫描评估器，检测 OWASP Top 10 LLM 风险 |
| GoldenDatasetValidator | ✅ 已实现 | 数据验证层，纯 Python 实现 Golden Dataset Schema 验证 |
| Prompt 变异测试 | ❌ 未实现 | 2026 增强版待实现 |
| 模型变异测试 | ❌ 未实现 | 2026 增强版待实现 |

---

## 核心能力：执行-反馈-优化 (EFO) 闭环
系统核心优势在于闭环工程化，AI 必须基于此架构进行开发：

### 执行 (Execute)
- 基于 27 种评估器自动生成并执行测试套件
- 记录代码版本、模型版本、Prompt 版本、数据切片版本，确保完全可追溯
- 执行过程中实时生成 OpenTelemetry trace，暴露评估延迟、Token 消耗、缓存命中率

### 反馈 (Feedback)
- GoldenDatasetManager 实时收集人工标注、生产环境纠偏信号、A/B 实验结果
- 自动识别高冲突样本（多评审员不一致度 > 0.3），升级为专家仲裁
- 更新专家标准答案时记录变更原因、影响范围，并通过 Data Version Control 管理

### 分析 (Analyze)
- AdaptiveCalibrator 按评估器维度持续监控偏差：均值偏差 > 5% 立即触发报警
- 漂移检测不仅关注评分分布，同时追踪 Prompt 有效性衰减与模型版本切换引入的偏移
- 每周自动生成质量趋势报告：评估器一致性、突变存活率变化、待清洗样本数量

### 优化 (Optimize)
当漂移超过阈值时，自动触发以下流程之一：
- 微调评估 Prompt（基于失败用例的反例）
- 重新校准评估器权重矩阵
- 触发回归测试套件并自动修复弱断言用例
- 优化结果形成 A/B 实验卡，确保新参数上线前通过门禁

---

## 测试覆盖准则（工业级标准，2026 增强）

| 风险级别 | 覆盖要求 | 验证方法 |
| :--- | :--- | :--- |
| **P0 - 核心算法** | 必须覆盖所有分支、异常路径、对抗样本、偏见路径 | 突变测试 + 基于属性的测试 (Hypothesis) + 公平性检查 |
| **P1 - 评估器** | 必须覆盖正向、负向、边界、异常、依赖降级、评分尺度一致性 | 边界值分析 + 元评估 + 多评审员一致性检验 |
| **P2 - API层** | 覆盖所有契约、异常注入、限流降级、幂等性 | 契约测试 + 混沌工程 (故障注入) + 并发安全测试 |
| **P3 - 数据与模型管线** | 覆盖数据分布漂移、特征缺失、模型版本不兼容 | 数据验证（Great Expectations）+ 模型签名验证 |

---

## 元测试质量门禁 (Meta-Evaluation Gates)
在代码 Merge 前，必须满足（2026 强化要求）：
- **场景覆盖率**：≥ 90%（覆盖识别的业务规则，并且覆盖至少 3 类对抗场景）
- **突变存活率**：≤ 20%（测试必须能捕捉到逻辑偏差；对评估 Prompt 的变异同样适用）
- **校准通过率**：≥ 90%（评估器均值偏差 < 5%；一致性 Kappa > 0.8）
- **幻觉检测通过率**：≥ 95%（AI 评估器输出不得包含与上下文无关的事实性错误）
- **安全扫描通过率**：OWASP Top 10 for LLM 风险扫描零高危漏洞
- **数据合规检查**：评估数据不得包含 PII 或训练数据未授权泄露

---

## 故障恢复与鲁棒性测试（2026 混沌工程扩展）

### 故障注入场景
- LLM Client 超时、429 限流、返回非 JSON 文本、返回嵌入后门
- 依赖评估器降级（如无法调用专用评估器时自动切换至通用规则）
- Golden Dataset 不可用时的兜底逻辑（使用最近快照）

### 性能基准
- 单次同步评估 ≤ 500ms（P95），异步批量评估需提供背压控制
- 并发测试需满足 QPS ≥ 100，且系统资源使用呈现线性增长，无内存泄漏

### 可观测性要求
- 所有故障恢复事件必须记录到结构化日志，并附带 trace id
- 自动生成故障演练报告，包含恢复时间 (MTTR)、影响范围

---

## 测试质量评估体系（经验总结 + AI 断言增强）

### 断言强度定义

| 类型 | 定义 | 示例 | 价值 |
| :--- | :--- | :--- | :--- |
| **强断言** | 验证精确业务逻辑、具体数值、内容匹配、语义等价 | `assert result.score == pytest.approx(0.85, abs=0.01)`，`assert evaluate_semantic_similarity(result.explanation, expected_reason) > 0.9` | ✅ 能发现业务逻辑错误 |
| **中等断言** | 验证区间、范围、包含关系、关键字存在 | `assert 0.0 <= result.score <= 1.0`，`assert "correct" in result.label.lower()` | ⚠️ 能发现严重错误 |
| **弱断言** | 仅验证状态、非空、调用次数 | `assert result.is_valid is True`, `mock_client.chat.assert_called_once()` | ❌ 无法发现业务逻辑错误 |

### 断言强度要求
- **单元测试**：每个测试类至少包含 1 个强断言
- **强断言比例**：≥ 50%（强断言数量 / 总断言数量）；核心评估器要求 ≥ 80%
- **禁止纯弱断言测试**：仅包含弱断言的测试用例视为无效，应删除或重写
- **AI 断言补充**：对自然语言输出，必须包含语义等价、关键词共现、事实一致性等至少一种强断言方法

### Mock 使用规范
- **单元测试**：允许使用 Mock 隔离外部依赖（LLM、数据库、网络等）
- **集成测试**：禁止使用 Mock（除真实不可控的外部依赖，如第三方 LLM API 在预发环境可替换为本地模拟器，但必须验证请求参数完整性和响应结构）
- **Mock 验证要求**：必须验证调用参数具体内容（prompt 模板、temperature、stop 序列等），禁止仅验证调用次数

---

## 测试审查流程（AI 辅助增强）

### 审查步骤
1. **统计分析**：自动统计测试数量、断言强度分布、被测单元复杂度
2. **AI 辅助审查**：使用代码大模型预审测试代码，标记可疑弱断言和潜在 Bug
3. **专家复核**：对 AI 标记为高风险的用例进行人工审查
4. **质量评估**：输出每个测试模块的质量评级
5. **问题分类**：
   - 无效测试：纯弱断言 → 删除
   - 错误测试：断言与业务逻辑不符 → 修正
   - 需补充测试：未被覆盖的等价类或突变 → 自动生成测试建议并记录
   - Bug 记录：发现业务代码问题 → 自动创建 issue 并链接到 bug_collection

---

## Bug 记录规范（自动化分类）

### Bug 分类（2026 扩展）

| 类别 | 定义 | 示例 |
| :--- | :--- | :--- |
| **业务代码 Bug** | 业务逻辑错误 | 评分算法错误、权限校验缺失 |
| **测试质量问题** | 测试用例不可靠 | 弱断言、用例环境依赖未隔离 |
| **数据漂移 Bug** | 因数据分布变化导致模型行为不符合预期 | 评分基线整体偏移、分类阈值失效 |
| **AI 幻觉风险** | 评估器输出包含事实性错误但格式正确 | 引用不存在的文档、捏造评分理由 |
| **改进建议** | 体系优化建议 | 引入变异测试、增加对抗样本 |

### Bug 记录格式
```markdown
### BUG-ID: <模块>-<序号> 严重程度

**发现位置**: [文件路径](file:///absolute/path)

**问题描述**: ...

**影响范围**: ...

**复现步骤**: ...

**建议修复**: ...
```

### Bug 优先级

| 优先级 | 定义 | 处理时限 |
| :--- | :--- | :--- |
| **🔴 高** | 安全漏洞、数据泄露、幻觉导致错误决策 | 立即修复 |
| **⚠️ 中** | 功能错误、API 行为不一致、测试质量差 | 下个迭代修复 |
| **🟡 低** | 改进建议、文档问题 | 规划修复 |

---

## 测试用例清理策略（经验总结 + 自动化）

### 自动清理规则引擎
- 识别纯弱断言测试 → 标记删除
- 识别重复测试（相似度 > 90%）→ 保留覆盖更完整的一个
- 识别过期测试（目标函数已删除）→ 自动移除
- 识别标记为 external 但无业务验证的测试 → 降级为手动触发

### 重写策略（AI 辅助）
- 弱断言转强断言：结合业务逻辑自动生成精确期望值
- 补全 Mock 参数验证：提取调用链中的关键参数，生成 assert_called_with 检查
- 增加公平性与鲁棒性断言

### 保留策略
- 有强断言的测试
- 边界与异常测试
- 性能与安全测试
- 历史缺陷复现测试

---

## 变异测试配置（2026 增强：Prompt 变异与模型变异）

```toml
[tool.mutmut]
paths_to_mutate = ["src/domain/evaluators"]
score_threshold = 80

# 2026 扩展：Prompt 变异测试
[tool.prompt_mutation]
enabled = true
mutation_operators = ["paraphrase", "negate_constraint", "swap_keywords", "insert_distractor"]
target_prompts_dir = "prompts/evaluation"

# 模型变异：用小模型或旧版本替换当前模型，验证鲁棒性
[tool.model_mutation]
enabled = true
candidate_models = ["gpt-4o-mini", "claude-3-haiku", "mistral-7b"]
```

---

## Pre-commit 门禁配置（2026 全栈质量门）

```yaml
- repo: local
  hooks:
    - id: unit-tests
      name: Run Unit Tests
      entry: python -m pytest tests/unit -v --tb=short --cov=src --cov-report=term
      language: system
      pass_filenames: false
      always_run: true

    - id: mutation-test
      name: Run Mutation Tests (Code + Prompt)
      entry: mutmut run --paths-to-mutate src/domain/evaluators && prompt-mutator check
      language: system
      pass_filenames: false
      always_run: false  # 触发于 release 分支

    - id: coverage-check
      name: Check Coverage (Branch + Mutation Score)
      entry: bash -c "coverage run -m pytest tests/unit && coverage report --fail-under=85 && mutmut junitxml > mutation-report.xml"
      language: system
      pass_filenames: false
      always_run: true

    - id: security-scan
      name: Scan for Prompt Injection & PII Leak
      entry: llm-guard scan --config security/llm_guard.yaml
      language: system
      pass_filenames: false
      always_run: true

    - id: data-integrity
      name: Validate Golden Dataset Schema
      entry: great_expectations checkpoint run golden_data_validation
      language: system
      pass_filenames: false
      always_run: true

    - id: calibration-check
      name: Adaptive Calibrator Quick Check
      entry: python -m calibrator check --max-deviation 0.04
      language: system
      pass_filenames: false
      always_run: false
```

---

## 持续验证与自愈流水线 (2026 工业级扩展)

- **模型上线前验证**：影子模式部署 7 天，收集真实流量结果并与当前模型对比，通过卡方检验确认无显著劣化
- **自适应采样**：根据线上决策风险自动调整采样率，高风险评估 100% 审计，低风险 5%
- **Auto-Fix 模块**：检测到弱断言测试后，自动尝试生成强断言补丁并提交 MR，人工审批后合并
- **质量债务看板**：将测试质量问题以“技术债务”形式可视化，设定偿还周期

---

## 🔧 实操工具与脚本

### 断言强度分析工具

**文件位置**: `tests/utils/assertion_analyzer.py`

**功能**: 自动分析测试文件的断言质量，统计强/中/弱断言比例

**使用方法**:
```bash
# 分析目录
python tests/utils/assertion_analyzer.py tests/unit/evaluator

# 查看帮助
python tests/utils/assertion_analyzer.py --help
```

**输出示例**:
```
ASSERTION STRENGTH ANALYSIS REPORT
Total Files: 41
Average Strong Ratio: 49.9%
Rating Distribution:
  A - Excellent (>=50%): 18
  C - Poor (<50%): 21
  D - Invalid (=0%): 2
RESULT: FAIL
```

**返回码**: 0=通过，1=失败（存在弱断言文件）

---

### 评估器测试策略映射表

| 评估器类型 | 核心测试点 | 强断言类型 | Mock验证点 | 变异测试策略 |
| :--- | :--- | :--- | :--- | :--- |
| **代码评估器** | 语法检查、代码审查、执行结果 | 精确分数、语法检查结果 | prompt包含代码内容 | 代码变异（语法错误注入） |
| **语义评估器** | 相似度计算、降级路径、embedding服务 | 精确分数、降级方法标识 | embedding调用参数 | Prompt变异、模型变异 |
| **安全评估器** | 漏洞检测、风险等级、注入攻击检测 | 检测结果、风险等级 | LLM调用参数 | 注入攻击模拟 |
| **QA评估器** | 答案匹配、事实性验证 | 精确分数、答案匹配度 | LLM调用参数 | Prompt变异 |
| **事实评估器** | 事实核查、证据引用 | 精确分数、证据匹配 | LLM调用参数 | 虚假信息注入 |
| **Prompt回归评估器** | Prompt稳定性、输出一致性 | 输出相似度、版本对比 | LLM调用参数 | Prompt变异 |
| **记忆评估器** | 上下文记忆、遗忘检测 | 精确分数、记忆保持率 | LLM调用参数 | 上下文变异 |
| **多Agent评估器** | 协作效果、角色分工 | 协作分数、任务完成度 | 各Agent调用参数 | 角色互换 |
| **漂移评估器** | 分布漂移、概念漂移 | 漂移分数、统计检验结果 | 数据源调用 | 数据分布变异 |
| **元测试评估器** | 测试用例质量、评估器自评估 | 评估器评分、一致性 | 评估器调用 | 测试用例变异 |

---

### 测试用例模板

#### 模板1：评估器单元测试模板

```python
"""<评估器名称>专项测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.<evaluator_module> import <EvaluatorClass>
from src.schemas.evaluation import EvaluationSchema


class Test<EvaluatorClass>PositiveCases:
    """正向测试"""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.chat.return_value = "<预期LLM输出>"
        return client

    @pytest.fixture
    def evaluator(self, mock_client):
        return <EvaluatorClass>(client=mock_client)

    def test_valid_input_returns_exact_score(self, evaluator, mock_client):
        """合法输入应返回精确分数"""
        request = EvaluationSchema(
            id="test_001",
            type="<evaluator_type>",
            payload={
                "user_input": "<输入>",
                "actual_output": "<实际输出>",
                "expected_output": "<期望输出>",
            },
        )
        result = evaluator.evaluate(request)

        # 强断言：验证精确分数
        assert result.is_valid is True
        assert result.score == pytest.approx(<预期分数>, abs=0.01)
        
        # 强断言：验证Mock调用参数
        mock_client.chat.assert_called_once()
        call_args = mock_client.chat.call_args
        assert "<关键内容>" in call_args[0][0]


class Test<EvaluatorClass>NegativeCases:
    """负向测试"""

    @pytest.fixture
    def evaluator(self):
        return <EvaluatorClass>(client=None)

    def test_missing_required_field_returns_error(self, evaluator):
        """缺少必填字段应返回错误"""
        request = EvaluationSchema(
            id="test_neg_001",
            type="<evaluator_type>",
            payload={"user_input": "<输入>"},
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is False
        assert "<字段名>" in result.error
        assert "不能为空" in result.error


class Test<EvaluatorClass>BoundaryCases:
    """边界测试"""

    def test_edge_case_returns_expected_score(self, evaluator, mock_client):
        """边界输入应返回预期分数"""
        request = EvaluationSchema(
            id="test_bound_001",
            type="<evaluator_type>",
            payload={
                "user_input": "<边界输入>",
                "actual_output": "<边界输出>",
                "expected_output": "<期望输出>",
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.score == pytest.approx(<预期边界分数>, abs=0.01)
```

#### 模板2：API集成测试模板

```python
"""<API名称>集成测试"""

import pytest
from httpx import AsyncClient

from src.api.server import app


@pytest.mark.asyncio
class Test<APIName>Integration:
    """API集成测试"""

    @pytest.fixture
    async def client(self):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_api_endpoint_returns_correct_response(self, client):
        """API端点应返回正确响应"""
        response = await client.post(
            "/api/v1/<endpoint>",
            json={
                "id": "test_001",
                "type": "<type>",
                "payload": {
                    "user_input": "<输入>",
                    "expected_output": "<期望输出>",
                },
            },
        )

        # 强断言：验证HTTP状态码
        assert response.status_code == 200

        # 强断言：验证业务逻辑
        data = response.json()
        assert data["is_valid"] is True
        assert data["score"] == pytest.approx(<预期分数>, abs=0.01)
        assert "<关键内容>" in data.get("text", "")
```

---

### 实施检查清单

#### 新评估器开发检查清单

```markdown
- [ ] 评估器继承 BaseEvaluator 并实现 _do_evaluate()
- [ ] 编写单元测试，包含至少 3 个强断言
- [ ] 编写集成测试，验证完整数据流
- [ ] 通过突变测试（存活率 ≤ 20%）
- [ ] 通过校准测试（偏差 < 5%）
- [ ] 在 GoldenDataset 中添加至少 5 个测试样本
- [ ] 添加到 EvaluatorFactory 注册
- [ ] 更新 API 路由文档
- [ ] 更新 ARCHITECTURE.md
```

#### 代码提交前检查清单

```markdown
- [ ] 运行单元测试：`python -m pytest tests/unit`
- [ ] 运行集成测试：`python -m pytest tests/integration`
- [ ] 检查覆盖率：`coverage report --fail-under=80`
- [ ] 运行突变测试：`mutmut run`
- [ ] 运行安全扫描：`llm-guard scan`
- [ ] 检查断言强度：`python tests/utils/assertion_analyzer.py`
- [ ] 更新 CHANGELOG.md
- [ ] 更新相关文档
```

---

### 常用命令速查

```bash
# 运行所有单元测试
python -m pytest tests/unit -v --tb=short

# 运行特定评估器测试
python -m pytest tests/unit/evaluator/test_code_evaluator.py -v

# 运行集成测试
python -m pytest tests/integration -v

# 生成覆盖率报告
coverage run -m pytest tests/unit
coverage report --fail-under=80
coverage html

# 运行突变测试
mutmut run --paths-to-mutate src/domain/evaluators

# 分析断言强度
python tests/utils/assertion_analyzer.py tests

# 运行冒烟测试
python -m pytest tests/smoke -v

# 运行可靠性测试
python -m pytest tests/reliability -v

# 运行性能测试
python -m pytest tests/performance -v

# 运行安全测试
python -m pytest tests/security -v

# 运行元测试
python -m pytest tests/meta_evaluation -v

# 运行完整测试套件
make test  # 或 python -m pytest tests/
```

---

### 工具链配置清单

| 工具 | 版本 | 配置文件 | 用途 |
| :--- | :--- | :--- | :--- |
| **pytest** | 8+ | pytest.ini | 测试框架 |
| **pytest-asyncio** | 0.23+ | pytest.ini | 异步测试支持 |
| **mutmut** | 0.23+ | pyproject.toml | 突变测试 |
| **hypothesis** | 6.99+ | conftest.py | 属性基测试 |
| **pytest-cov** | 4.1+ | pyproject.toml | 覆盖率统计 |
| **allure-pytest** | 2.13+ | pytest.ini | 测试报告 |
| **llm-guard** | 0.3+ | security/llm_guard.yaml | 安全扫描 |
| **great-expectations** | 0.18+ | great_expectations.yml | 数据验证 |
| **opentelemetry-api** | 1.20+ | src/infra/tracing.py | 可观测性 |

---

---

## 🧪 工业级收敛：非确定性与评估器偏见处理机制

### 1. 统计置信度框架（Statistical Confidence Framework）

#### 1.1 非确定性来源分析

| 非确定性来源 | 影响 | 量化指标 | 处理策略 |
| :--- | :--- | :--- | :--- |
| **LLM输出随机性** | 相同输入产生不同评分 | 评分标准差 σ | 多次采样 + 置信区间估计 |
| **Prompt敏感性** | 微小Prompt变化导致评分漂移 | 评分变化率 Δ | Prompt变异测试 + 稳定性校验 |
| **模型版本差异** | 不同模型版本输出不一致 | 一致性Kappa | 多模型交叉验证 |
| **评估器校准漂移** | 长期运行中评估器偏差累积 | 均值偏差 μ | 自适应校准 + 定期重校准 |
| **数据分布漂移** | 测试数据与生产数据分布不一致 | KS检验统计量 | 分布监控 + 样本刷新 |

#### 1.2 置信度计算方法

**贝叶斯置信区间**：
```python
from scipy import stats

def calculate_confidence_interval(scores: List[float], confidence_level: float = 0.95) -> Tuple[float, float]:
    """计算评分的置信区间"""
    n = len(scores)
    mean = sum(scores) / n
    std_error = stats.sem(scores)
    margin = std_error * stats.t.ppf((1 + confidence_level) / 2, n - 1)
    return (mean - margin, mean + margin)
```

**统计显著性检验**：
```python
def is_statistically_significant(scores: List[float], threshold: float = 0.8, alpha: float = 0.05) -> bool:
    """检验评分是否显著高于阈值（单侧t检验）"""
    t_stat, p_value = stats.ttest_1samp(scores, threshold)
    return p_value < alpha and sum(scores) / len(scores) > threshold
```

#### 1.3 测试断言中的置信度验证

```python
"""非确定性评估器测试 - 使用统计置信度"""

import pytest
from scipy import stats

class TestEvaluatorWithConfidence:
    """带统计置信度的评估器测试"""

    def test_score_is_statistically_significant(self, evaluator, mock_client):
        """评分在统计意义上显著高于阈值"""
        mock_client.chat.return_value = "0.85"
        
        scores = []
        for _ in range(10):
            request = EvaluationSchema(id="test_conf_001", type="qa", payload={...})
            result = evaluator.evaluate(request)
            scores.append(result.score)

        # 强断言：均值显著高于0.8
        mean_score = sum(scores) / len(scores)
        assert mean_score == pytest.approx(0.85, abs=0.02)
        
        # 强断言：统计显著性检验
        t_stat, p_value = stats.ttest_1samp(scores, 0.8)
        assert p_value < 0.05, f"p-value={p_value} >= 0.05，不显著"
        
        # 强断言：置信区间验证
        ci_lower, ci_upper = calculate_confidence_interval(scores)
        assert ci_lower > 0.8, f"95%置信区间下限={ci_lower} <= 0.8"

    def test_score_consistency_across_runs(self, evaluator, mock_client):
        """多次运行的评分一致性"""
        scores = [evaluator.evaluate(request).score for _ in range(20)]
        
        # 强断言：标准差控制在允许范围内
        std_dev = stats.tstd(scores)
        assert std_dev < 0.05, f"标准差={std_dev} >= 0.05，一致性差"
        
        # 强断言：变异系数控制
        cv = std_dev / (sum(scores) / len(scores))
        assert cv < 0.1, f"变异系数={cv} >= 0.1，稳定性差"
```

#### 1.4 置信度门禁标准

| 指标 | 要求 | 说明 |
| :--- | :--- | :--- |
| **样本量** | ≥ 10次 | 统计检验的最小样本量 |
| **置信水平** | ≥ 95% | 结果可信的概率 |
| **标准差** | < 0.05 | 评分一致性要求 |
| **变异系数** | < 0.1 | 相对稳定性要求 |
| **显著性p值** | < 0.05 | 统计显著性要求 |

---

### 2. 元评估器一致性机制（Meta-Evaluator Consistency）

#### 2.1 多评估器交叉验证

**评估器仲裁协议**：
```python
from enum import Enum
from typing import List, Dict

class ConsensusResult(Enum):
    CONSENSUS = "consensus"
    MAJORITY = "majority"
    CONFLICT = "conflict"

def evaluate_consensus(scores: List[float], labels: List[str], threshold: float = 0.7) -> ConsensusResult:
    """评估多评估器一致性"""
    passing_count = sum(1 for s in scores if s >= threshold)
    
    if passing_count == len(scores):
        return ConsensusResult.CONSENSUS
    elif passing_count > len(scores) // 2:
        return ConsensusResult.MAJORITY
    else:
        return ConsensusResult.CONFLICT

def calculate_fleiss_kappa(ratings: List[List[int]]) -> float:
    """计算多评估器一致性的Fleiss' Kappa系数"""
    n = len(ratings)
    k = len(ratings[0])
    categories = len(set(item for sublist in ratings for item in sublist))
    
    p_bar = sum(sum(ratings[i][j] for i in range(n)) ** 2 for j in range(categories)) / (n * k)
    p_e = sum(sum(ratings[i][j] for i in range(n)) / (n * k) ** 2 for j in range(categories))
    
    return (p_bar - p_e) / (1 - p_e)
```

#### 2.2 评估器偏见检测

**偏见类型与检测方法**：

| 偏见类型 | 描述 | 检测方法 | 量化指标 |
| :--- | :--- | :--- | :--- |
| **评分膨胀** | 倾向于给出高分 | 与专家标注对比 | 均值偏差 > 5% |
| **评分紧缩** | 倾向于给出低分 | 与专家标注对比 | 均值偏差 < -5% |
| **分布偏差** | 评分分布与基准差异显著 | KS检验 | KS统计量 > 0.1 |
| **群体偏见** | 对特定群体输入有系统性偏差 | 分层统计分析 | 群体间差异显著 |
| **顺序偏见** | 评估顺序影响评分 | 随机化实验 | 顺序效应显著 |

**偏见检测实现**：
```python
from scipy.stats import ks_2samp, ttest_ind

def detect_evaluator_bias(
    evaluator_scores: List[float],
    expert_scores: List[float],
    demographic_groups: Dict[str, List[float]] = None
) -> Dict[str, float]:
    """检测评估器偏见"""
    results = {}
    
    # 均值偏差检测
    mean_diff = sum(evaluator_scores) / len(evaluator_scores) - sum(expert_scores) / len(expert_scores)
    results["mean_deviation"] = mean_diff
    
    # 分布差异检测
    ks_stat, p_value = ks_2samp(evaluator_scores, expert_scores)
    results["ks_statistic"] = ks_stat
    results["ks_p_value"] = p_value
    
    # 群体偏见检测
    if demographic_groups:
        group_scores = list(demographic_groups.values())
        for i, (group_name, scores) in enumerate(demographic_groups.items()):
            for j, (other_name, other_scores) in enumerate(demographic_groups.items()):
                if i < j:
                    t_stat, p_val = ttest_ind(scores, other_scores)
                    results[f"{group_name}_vs_{other_name}_p_value"] = p_val
    
    return results
```

#### 2.3 偏见修正机制

**校准修正算法**：
```python
from sklearn.isotonic import IsotonicRegression

def calibrate_evaluator(
    evaluator_scores: List[float],
    expert_labels: List[int],
    method: str = "isotonic"
) -> callable:
    """校准评估器以消除偏见"""
    if method == "isotonic":
        regressor = IsotonicRegression(out_of_bounds="clip")
        regressor.fit(evaluator_scores, expert_labels)
        return lambda x: regressor.predict([x])[0]
    elif method == "linear":
        from sklearn.linear_model import LinearRegression
        regressor = LinearRegression()
        regressor.fit([[s] for s in evaluator_scores], expert_labels)
        return lambda x: regressor.predict([[x]])[0]
    else:
        raise ValueError(f"Unknown calibration method: {method}")
```

#### 2.4 元评估器一致性门禁

| 指标 | 要求 | 说明 |
| :--- | :--- | :--- |
| **Fleiss' Kappa** | > 0.8 | 多评估器一致性 |
| **Cohen's Kappa** | > 0.75 | 两两评估器一致性 |
| **仲裁通过率** | ≥ 90% | 冲突样本仲裁通过率 |
| **偏见均值偏差** | < 5% | 与专家标注的偏差 |
| **KS检验p值** | > 0.05 | 评分分布与基准无显著差异 |

---

### 3. 非确定性测试模式

#### 3.1 概率断言（Probabilistic Assertions）

```python
"""概率断言测试模式"""

import pytest
import random

class TestProbabilisticEvaluation:
    """概率断言测试"""

    def test_passing_probability_exceeds_threshold(self, evaluator, mock_client):
        """通过概率超过阈值"""
        mock_client.chat.return_value = "0.85"
        
        passing_count = 0
        total_runs = 100
        
        for _ in range(total_runs):
            request = EvaluationSchema(id="test_prob_001", type="qa", payload={...})
            result = evaluator.evaluate(request)
            if result.score >= 0.8:
                passing_count += 1
        
        passing_prob = passing_count / total_runs
        
        # 强断言：通过概率 > 90%
        assert passing_prob > 0.9, f"通过概率={passing_prob:.1%} <= 90%"
        
        # 强断言：置信区间验证
        from scipy.stats import binom_test
        p_value = binom_test(passing_count, total_runs, 0.9)
        assert p_value < 0.05, f"通过概率不显著高于90%，p-value={p_value}"

    def test_score_distribution_follows_expected_pattern(self, evaluator, mock_client):
        """评分分布符合预期模式"""
        scores = [evaluator.evaluate(request).score for _ in range(100)]
        
        # 强断言：均值在预期范围内
        mean_score = sum(scores) / len(scores)
        assert mean_score == pytest.approx(0.85, abs=0.03)
        
        # 强断言：分布形状验证
        from scipy.stats import normaltest
        stat, p_value = normaltest(scores)
        assert p_value > 0.05, "评分分布非正态，可能存在偏见"
```

#### 3.2 稳定性测试（Stability Testing）

```python
"""评估器稳定性测试"""

class TestEvaluatorStability:
    """评估器稳定性测试"""

    def test_prompt_variation_does_not_affect_score(self, evaluator, mock_client):
        """Prompt微小变化不影响评分"""
        base_prompt = "请评估这个回答"
        variations = [
            "请评估这个回答。",
            "请评价这个回答",
            "请评估一下这个回答",
            "请评估该回答",
        ]
        
        scores = []
        for variation in variations:
            mock_client.chat.return_value = "0.85"
            request = EvaluationSchema(
                id="test_stab_001",
                type="qa",
                payload={"user_input": variation, "expected_output": "答案"}
            )
            scores.append(evaluator.evaluate(request).score)
        
        # 强断言：评分标准差 < 0.03
        std_dev = sum((s - sum(scores)/len(scores))**2 for s in scores) ** 0.5 / (len(scores) - 1)
        assert std_dev < 0.03, f"Prompt变化导致评分不稳定，标准差={std_dev}"

    def test_model_version_robustness(self, evaluator):
        """不同模型版本下的鲁棒性"""
        model_versions = ["gpt-4", "gpt-4o", "gpt-4o-mini"]
        scores = []
        
        for model in model_versions:
            with patch.object(evaluator.client, 'config') as mock_config:
                mock_config.model_name = model
                mock_config.chat.return_value = "0.85"
                scores.append(evaluator.evaluate(request).score)
        
        # 强断言：跨模型评分差异 < 0.1
        max_diff = max(scores) - min(scores)
        assert max_diff < 0.1, f"跨模型评分差异={max_diff} >= 0.1"
```

#### 3.3 漂移检测测试（Drift Detection Testing）

```python
"""漂移检测测试"""

class TestEvaluatorDrift:
    """评估器漂移检测测试"""

    def test_no_drift_over_time(self, evaluator, mock_client):
        """长期运行无漂移"""
        mock_client.chat.return_value = "0.85"
        
        # 模拟不同时间点的评分
        scores_time_series = []
        for day in range(30):
            # 引入微小的模拟漂移
            drift_factor = 1 + (day * 0.001)
            mock_client.chat.return_value = str(0.85 * drift_factor)
            scores_time_series.append(evaluator.evaluate(request).score)
        
        # 强断言：线性回归斜率接近0
        from scipy.stats import linregress
        slope, intercept, r_value, p_value, std_err = linregress(range(30), scores_time_series)
        assert abs(slope) < 0.001, f"检测到漂移趋势，斜率={slope}"

    def test_drift_detection_triggers_alert(self, evaluator, mock_client):
        """漂移超过阈值时触发警报"""
        # 正常评分
        mock_client.chat.return_value = "0.85"
        baseline_scores = [evaluator.evaluate(request).score for _ in range(10)]
        baseline_mean = sum(baseline_scores) / len(baseline_scores)
        
        # 模拟漂移
        mock_client.chat.return_value = "0.6"
        drifted_scores = [evaluator.evaluate(request).score for _ in range(10)]
        
        # 强断言：检测到显著漂移
        from scipy.stats import ttest_ind
        t_stat, p_value = ttest_ind(baseline_scores, drifted_scores)
        assert p_value < 0.01, f"未检测到漂移，p-value={p_value}"
```

---

### 4. 评估器偏见测试模式

#### 4.1 公平性测试（Fairness Testing）

```python
"""评估器公平性测试"""

class TestEvaluatorFairness:
    """评估器公平性测试"""

    def test_demographic_parity(self, evaluator, mock_client):
        """不同群体的评分公平性"""
        demographic_groups = {
            "gender_male": ["他", "男", "男性"],
            "gender_female": ["她", "女", "女性"],
            "race_white": ["白人", "欧洲"],
            "race_black": ["黑人", "非洲"],
        }
        
        group_scores = {}
        for group_name, inputs in demographic_groups.items():
            scores = []
            for input_text in inputs:
                mock_client.chat.return_value = "0.85"
                request = EvaluationSchema(
                    id=f"test_fair_{group_name}",
                    type="qa",
                    payload={"user_input": f"{input_text}的回答", "expected_output": "答案"}
                )
                scores.append(evaluator.evaluate(request).score)
            group_scores[group_name] = scores
        
        # 强断言：群体间评分无显著差异
        from itertools import combinations
        for group1, group2 in combinations(demographic_groups.keys(), 2):
            t_stat, p_value = ttest_ind(group_scores[group1], group_scores[group2])
            assert p_value > 0.05, f"{group1}与{group2}存在显著评分差异，p-value={p_value}"

    def test_intersectional_fairness(self, evaluator, mock_client):
        """交叉群体公平性"""
        intersectional_cases = [
            {"gender": "male", "age": "young"},
            {"gender": "male", "age": "old"},
            {"gender": "female", "age": "young"},
            {"gender": "female", "age": "old"},
        ]
        
        # 验证交叉群体的评分一致性
        # ...（类似上述实现）
```

#### 4.2 顺序偏见测试（Order Bias Testing）

```python
"""顺序偏见测试"""

class TestEvaluatorOrderBias:
    """评估器顺序偏见测试"""

    def test_no_order_effect(self, evaluator, mock_client):
        """评估顺序不影响评分"""
        test_cases = [
            {"user_input": "问题A", "expected_output": "答案A"},
            {"user_input": "问题B", "expected_output": "答案B"},
            {"user_input": "问题C", "expected_output": "答案C"},
        ]
        
        # 随机化顺序
        import random
        scores_by_order = {}
        
        for _ in range(20):
            shuffled = test_cases.copy()
            random.shuffle(shuffled)
            
            for i, case in enumerate(shuffled):
                mock_client.chat.return_value = "0.85"
                request = EvaluationSchema(
                    id=f"test_order_{i}",
                    type="qa",
                    payload=case
                )
                score = evaluator.evaluate(request).score
                
                key = (case["user_input"], i)
                scores_by_order[key] = scores_by_order.get(key, []) + [score]
        
        # 强断言：不同位置的评分无显著差异
        for case in test_cases:
            position_scores = [scores_by_order[(case["user_input"], i)] for i in range(3)]
            f_stat, p_value = stats.f_oneway(*position_scores)
            assert p_value > 0.05, f"{case['user_input']}存在顺序偏见，p-value={p_value}"
```

---

### 5. 工业级收敛质量门禁（Industrial Convergence Gates）

#### 5.1 完整门禁矩阵

| 门禁 | 阈值 | 检测方法 | 失败处理 |
| :--- | :--- | :--- | :--- |
| **统计显著性** | p-value < 0.05 | t检验/二项检验 | 增加样本量或修复评估器 |
| **置信区间** | 95% CI下限 > 阈值 | 贝叶斯估计 | 增加采样次数 |
| **评分一致性** | σ < 0.05 | 标准差 | 优化Prompt或校准评估器 |
| **变异系数** | CV < 0.1 | 相对标准差 | 提升评估器稳定性 |
| **多评估器一致性** | Kappa > 0.8 | Fleiss' Kappa | 仲裁冲突样本 |
| **偏见偏差** | < 5% | 与专家对比 | 校准修正 |
| **分布一致性** | KS p-value > 0.05 | KS检验 | 重新校准 |
| **公平性** | 群体间p-value > 0.05 | t检验 | 消除偏见 |
| **稳定性** | Prompt变化σ < 0.03 | 标准差 | 优化Prompt |
| **漂移检测** | 斜率 < 0.001 | 线性回归 | 触发重校准 |

#### 5.2 门禁执行流程

```
代码提交
    ↓
运行单元测试（常规断言）
    ↓
运行统计置信度测试（概率断言）
    ↓
运行元评估器一致性测试（多评估器仲裁）
    ↓
运行偏见检测测试（公平性检查）
    ↓
运行稳定性测试（漂移检测）
    ↓
全部通过 → 合并
任意失败 → 生成质量报告 → 人工审核 → 修复
```

---

### 6. 工业级收敛测试工具

#### 6.1 置信度分析工具

**文件位置**: `tests/utils/confidence_analyzer.py`

**功能**: 分析评估器评分的统计置信度，包括均值、标准差、置信区间、变异系数

**使用方法**:
```bash
# 分析评分置信度
python tests/utils/confidence_analyzer.py --scores "0.85,0.87,0.83,0.86" --threshold 0.8

# 查看帮助
python tests/utils/confidence_analyzer.py --help
```

**输出示例**:
```
STATISTICAL CONFIDENCE ANALYSIS REPORT
Sample Size: 10
Mean: 0.8550
Std Dev: 0.0158
CV: 0.0185
95% CI: [0.8437, 0.8663]
Normality: SKIP (n<20)
GATE CHECKS:
  [PASS] score_consistency: std_dev=0.0158
  [PASS] cv: cv=0.0185
  [PASS] ci_lower: ci_lower=0.8437
RESULT: PASS
```

**返回码**: 0=通过，1=失败

---

## 🔍 测试失效模式与经验教训（2026 年实战总结）

### 失效模式 1：确认偏差（Confirmation Bias）
**问题描述**：测试断言只验证"系统不崩溃"，而非"业务正确性"。当测试失败时，立即修改断言去匹配实际行为，而不是先判断该行为本身是否就是 BUG。

**典型案例**：
- `special_chars_bomb` 测试中，特殊字符导致语法检查失败，系统应给出清晰错误而非静默接受，但测试被修改为"验证系统能处理特殊字符"
- 评估器返回 PARTIAL 状态时，测试只验证 `is_valid is True`，不验证降级方法是否正确触发

**预防措施**：
- 先写断言表达"正确行为应该是什么"，如果失败就追踪是 BUG 还是断言错误
- 禁止在失败后立即修改断言，必须经过"错误分析 → 确认是断言错误 → 修改"的流程
- 建立测试审查机制，识别"为通过而通过"的测试用例

### 失效模式 2：Mock 测试局限（Mock Limitation）
**问题描述**：Mock 返回什么就验证什么，等于在测试 Mock 本身而非真实逻辑。当 Mock 返回值与真实 LLM 行为不一致时，测试通过但生产环境失败。

**典型案例**：
- Mock 返回完美格式的 JSON 和数字分数，测试全部通过；但真实 LLM 返回负数、非数字、畸形 JSON 时，系统崩溃
- Mock 只验证调用次数，不验证调用参数具体内容（prompt 模板、temperature、stop 序列等）

**预防措施**：
- 必须验证调用参数具体内容，禁止仅验证调用次数
- 引入"Mock 变异测试"：随机修改 Mock 返回值（负数、非数字、超时），验证系统容错能力
- 集成测试禁止使用 Mock（除真实不可控的外部依赖）

### 失效模式 3：浅层断言（Shallow Assertion）
**问题描述**：大量 `assert result.is_valid is True` 只验证状态，不验证业务结果。这种断言无法发现业务逻辑错误，只能发现系统崩溃。

**典型案例**：
- 语义评估器返回分数 0.5，测试断言 `is_valid is True` 通过，但实际上正确分数应该是 0.85
- 代码评估器返回 `syntax_valid=True`，测试通过，但实际上代码存在严重安全漏洞

**预防措施**：
- 单元测试：每个测试类至少包含 1 个强断言
- 强断言比例要求：≥ 50%（核心评估器要求 ≥ 80%）
- 禁止纯弱断言测试：仅包含弱断言的测试用例视为无效，应删除或重写

### 失效模式 4：未测试真实边界（Untested Real-world Boundaries）
**问题描述**：没有测试 LLM 返回非法值的场景，导致生产环境中遇到真实边界时系统崩溃或返回错误结果。

**典型案例**：
- LLM 返回负数分数（如 `-0.5`），正则表达式 `(\d+\.?\d*)` 丢弃负号，错误解析为 `0.5`
- LLM 返回非数字字符串（如 `"not_a_number"`），`float()` 抛出 `ValueError`，系统崩溃
- LLM 返回大于 1 的分数（如 `"1.5"`），被当作百分制错误转换为 `0.015`

**预防措施**：
- 测试 LLM 返回负数、非数字、超范围分数的场景
- 测试 LLM 返回畸形 JSON、空字符串、超长文本的场景
- 使用属性测试（Hypothesis）生成随机输入找边界 BUG

### 失效模式 5：缺少属性测试（Missing Property-based Testing）
**问题描述**：没有使用 Hypothesis 等工具生成随机输入，依赖手动设计的测试用例，无法覆盖所有边界情况。

**典型案例**：
- 分数归一化函数 `_normalize_score` 只测试了 0-1 区间的分数，未测试负数和超范围值
- 风险评估器只测试了手动设计的场景，未测试随机组合的风险参数

**预防措施**：
- 对核心算法使用 Hypothesis 属性测试，生成随机输入验证业务不变式
- 定义业务不变式：语义评估分数必须在 [0,1]、代码评估的 `syntax_valid=True` 时 score 应 > 0、风险等级与分数应一致等
- 配置 Hypothesis 策略生成对抗样本（特殊字符、超长文本、嵌套结构等）

### 实战修复案例

#### 案例 1：分数提取正则表达式缺陷
**问题**：正则表达式 `(\d+\.?\d*)` 不包含负号，导致负数的负号被丢弃

**修复**：将正则表达式改为 `(-?\d+\.?\d*)`

**位置**：[score_parsing.py](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/strategies/score_parsing.py#L50)

#### 案例 2：分数归一化边界处理缺陷
**问题**：当分数 ≤ 1.0 时直接返回，没有检查是否小于 0，导致负数分数被当作有效分数处理

**修复**：在分数归一化前添加负数检查，负数返回 None

**位置**：[_normalize_score](file:///d:/workspace/ai-eval-platform-refactor/src/domain/evaluators/strategies/score_parsing.py#L100)

#### 案例 3：配置缺失
**问题**：`Settings` 类缺少 `CALIBRATION_THRESHOLD` 和 `CALIBRATION_MIN_SAMPLES` 属性，导致测试收集失败

**修复**：在 `Settings` 类中添加这两个字段

**位置**：[config/__init__.py](file:///d:/workspace/ai-eval-platform-refactor/src/config/__init__.py)

### 失效模式 6：Mock 路径错误（Mock Path Error）
**问题描述**：测试中 Mock 的路径与实际代码中的函数/变量名称不一致，导致 Mock 未生效，测试用例 ERROR 或行为不符合预期。

**典型案例**：
- `test_evaluation_api_integration.py` 中 Mock 路径 `src.api.routes.evaluation_routes._get_idempotency_checker` 不存在，应为 `_get_idempotency_service`，导致24个测试用例全部 ERROR
- `test_business_scenarios.py` 中 Mock 路径 `src.services.evaluator_svc._repository.save` 不存在，应为 `src.infra.db.repository.EvaluationRepository.save`

**预防措施**：
- 在编写 Mock 前，通过代码搜索确认目标函数/变量的确切路径
- 使用 `from module import function` 的方式引入目标，避免字符串路径拼写错误
- 建立 Mock 路径审查机制，在测试提交前验证 Mock 路径正确性

### 失效模式 7：评估器类型错误（Wrong Evaluator Type）
**问题描述**：测试用例中使用了错误的评估器类型，导致调用错误的评估器逻辑，测试结果不符合预期。

**典型案例**：
- `test_prompt_injection_resistance` 使用 `type: "general"` 而非 `type: "security"`，导致安全评估场景调用了通用评估器
- 缺少必要的参数（如安全评估的 `tests` 参数），导致评估器行为不符合预期

**预防措施**：
- 在测试用例中明确标注目标评估器类型
- 为每个评估器类型创建专用测试 fixture，确保参数完整性
- 建立评估器类型与参数的映射表，测试时自动验证

### 失效模式 8：评估器返回值格式错误（Wrong Return Format）
**问题描述**：Mock 返回值格式与评估器期望的格式不一致，导致评分解析失败或业务逻辑错误。

**典型案例**：
- GeneralEvaluator 期望返回数字评分（如 `"0.95"`），但 Mock 返回自然语言文本（如 `"检测到恶意输入"`），导致 `safe_parse_score` 无法提取数字，评估器返回 ERROR
- 批量评估测试中 Mock 返回非数字格式，导致评分无法正确解析

**预防措施**：
- 制定评估器测试 Mock 返回值规范：必须返回可解析的数字评分
- 在测试 fixture 中统一 Mock 返回值格式，避免每个测试用例单独设置
- 添加评分解析失败的异常处理测试，验证系统容错能力

### 案例 4：幂等性检查器 Mock 路径错误
**问题**：`test_evaluation_api_integration.py` 中 Mock 路径错误，`_get_idempotency_checker` 不存在，应为 `_get_idempotency_service`

**影响范围**：24个测试用例全部 ERROR

**修复**：将 Mock 路径改为正确的函数名称

**位置**：[test_evaluation_api_integration.py](file:///d:/workspace/ai-eval-platform-refactor/tests/integration/api/test_evaluation_api_integration.py#L35)

### 案例 5：安全评估测试评估器类型错误
**问题**：`test_prompt_injection_resistance` 使用 `type: "general"` 而非 `type: "security"`，缺少 `tests` 参数

**修复**：将评估器类型改为 `"security"`，添加 `tests: ["injection", "jailbreak", "data_leak", "tool_abuse"]` 参数

**位置**：[test_business_scenarios.py](file:///d:/workspace/ai-eval-platform-refactor/tests/integration/api/test_business_scenarios.py#L162)

### 案例 6：多轮对话测试 Mock 返回值格式错误
**问题**：Mock 返回自然语言文本而非数字评分，缺少 `actual_output` 参数

**修复**：将 Mock 返回值改为 `"0.95"`，添加 `actual_output` 参数

**位置**：[test_business_scenarios.py](file:///d:/workspace/ai-eval-platform-refactor/tests/integration/api/test_business_scenarios.py#L204)

### 集成测试 Mock 使用边界规范
**原则**：集成测试应尽可能验证真实数据流，仅在外部依赖不可控时使用 Mock

**允许 Mock 的场景**：
- 第三方 LLM API（预发环境可替换为本地模拟器）
- 数据库连接（需验证请求参数完整性和响应结构）
- Redis/消息队列等外部基础设施

**禁止 Mock 的场景**：
- 本系统内部模块（如 Service 层、Repository 层）
- 评估器核心逻辑（应通过真实调用验证）
- API 路由与 Service 层的集成（应端到端验证）

**Mock 验证要求**：
- 必须验证调用参数具体内容（prompt 模板、temperature、stop 序列等）
- 禁止仅验证调用次数
- 必须验证返回值结构与真实响应一致

### 经验来源
AI 评测系统测试审查实践 + 2026 年 LLMOps 工业落地标准 + 集成测试优化实战（2026-07-01）

### 核心原则
测试的目标是验证业务逻辑正确性、发现生产环境问题，并保障 AI 系统在不确定性下的可靠、公平与合规。绝不单纯追求代码覆盖率。

## 工业级收敛宣言
> **工业级系统不能只假设测试是通过还是失败，必须引入统计置信度和元评估器一致性。**
> 
> 在 AI 系统中，非确定性是常态而非例外。测试必须从"二进制判断"进化到"统计置信度判断"，从"单一评估器"进化到"多评估器仲裁"，从"被动发现"进化到"主动检测偏见和漂移"。