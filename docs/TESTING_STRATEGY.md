# AI Eval Platform - 测试策略文档

## 一、测试分层策�?
### 1.1 测试金字�?
```
┌─────────────────────────────────────────────────────────────�?�?                   E2E/集成测试 (17�?                      �?�? - API路由测试                                               �?�? - 外部服务集成 (LLM/Embedding)                              �?�? - 标记: @pytest.mark.external                              �?├─────────────────────────────────────────────────────────────�?�?                   单元测试 (1806�?                         �?�? - 评估器核心逻辑                                            �?�? - 工厂模式/注册中心                                         �?�? - 熔断�?限流/幂等�?                                       �?�? - 标记: @pytest.mark.unit                                  �?└─────────────────────────────────────────────────────────────�?```

### 1.2 测试隔离原则

**Test Isolation**: "Unit tests are decoupled from heavy external dependencies (e.g., Embedding models) using custom Mocks to ensure fast execution."

- Redis Mock: 防止熔断器持久化状态污�?- Embedding Mock: 模拟向量相似度计�?- LLM Mock: 模拟LLM响应

**Environment Awareness**: "System uses feature flags and markers to skip environment-dependent tests, allowing for rapid iteration on core architecture."

- `TESTING=1`: 测试环境使用SQLite
- `@pytest.mark.external`: 标记外部集成测试

**Continuous Improvement**: "Consistency issues (Kappa scores) are treated as data quality alerts, driving iterative prompt engineering cycles."

## 二、评估器精简策略 (v2.0)

### 2.1 核心评估�?(15�?

| 评估�?| 功能 | 状�?|
|--------|------|------|
| general | 通用评估 | �?通过黄金数据集验�?|
| code | 代码评估 | �?通过黄金数据集验�?|
| code_review | 代码审查 | �?通过黄金数据集验�?|
| security | 安全评估 | �?通过黄金数据集验�?|
| memory | 记忆评估 | �?通过黄金数据集验�?|
| semantic | 语义相似�?| �?通过黄金数据集验�?|
| qa | 问答评估 | �?通过黄金数据集验�?|
| factuality | 事实性评�?| �?通过黄金数据集验�?|
| risk | 风险评估 | �?通过黄金数据集验�?|
| classification | 分类评估 | �?通过黄金数据集验�?|
| composite | 组合评估 | �?通过黄金数据集验�?|
| function_call | 函数调用评估 | �?通过黄金数据集验�?|
| multi_agent | 多智能体评估 | �?通过黄金数据集验�?|
| llm_as_judge | LLM裁判评估 | �?通过黄金数据集验�?|
| robustness | 鲁棒性评�?| �?通过黄金数据集验�?|

### 2.2 候选评估器 (22�?

| 分类 | 评估�?| 状�?|
|------|--------|------|
| 重复功能 | text, text_similarity_base, sentiment, grammar, summary, translation, multilingual, fact_check, finance | 待合�?|
| 功能待完�?| drift, prompt_sensitivity, prompt_regression, judge_robustness, multi_judge_ensemble, multi_metric, standard_metric | 待完�?|
| 外部依赖 | ragas, deepeval | 依赖未安�?|
| 元评�?| meta_test | 内部使用 |
| 高级评估�?| planning, trajectory, runtime_agent, tool_use | 待验�?|

## 三、测试性能优化

### 3.1 Fixture优化

```python
# 从autouse=True（每个测试）改为session级别（一次）
@pytest.fixture(scope="session", autouse=True)
def reset_evaluator_registry_session():
    auto_discover(force=True)
```

**效果**: 测试时间�?分钟降至3-4分钟

### 3.2 并行化支�?
```bash
# 使用pytest-xdist并行�?pytest -n auto              # 自动检测CPU核心
pytest -n 4                 # 指定4个worker
pytest -n auto --dist loadscope  # 按类分组
```

## 四、运行命�?
```bash
# 默认运行单元测试（跳过external�?pytest

# 运行所有测试（包括集成测试�?pytest -m "not external"

# 仅运行集成测�?pytest -m external

# 并行化运�?pytest -n auto

# 查看测试覆盖�?pytest --cov=src/ --cov-report=html

# 查看慢测�?pytest --durations=20
```

## 五、测试质量标�?
| 指标 | 当前�?| 目标�?|
|------|--------|--------|
| 测试通过�?| 99.24% | �?9% |
| 运行时间 | 4-8分钟 | �?分钟 |
| 覆盖�?| 23% | �?0% |
| P0缺陷 | 0�?| 0�?|

## 六、CI/CD集成

```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run unit tests
        run: pytest -n auto --cov=src/ --cov-fail-under=60
      - name: Run integration tests
        run: pytest -m external
        env:
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
```
