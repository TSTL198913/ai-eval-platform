# AI-Native Industrial Evaluation System Rules

## 1. 系统收敛原则 (Convergence First)
- **质量门禁**：所有代码变更必须通过元测试（Meta-Testing），确保系统评估器偏差 < 5%。
- **闭环开发**：严禁仅实现功能而不完善反馈闭环（EFO）。任何功能新增都必须更新 `golden_dataset.json` 并通过回归测试。
- **非功能优先**：在编写算法前，先考虑并发安全、容错降级与性能指标。

## 2. 行为准则 (Standard Operating Procedures)
- **拒绝“快乐路径”测试**：禁止编写仅覆盖成功流程的测试，必须包含负向测试、边界测试和异常测试[cite: 1]。
- **强制使用评估器进行自测**：在代码提交前，必须使用系统内置的 27 种评估器（如 `CodeEvaluator`, `SecurityEvaluator` 等）对代码进行元测试[cite: 1]。
- **Bug 处理流程**：发现 Bug 时，禁止直接修改业务代码，必须：
  1. 更新失败样本库（Failures Database）。
  2. 编写回归测试用例。
  3. 修复代码并确保所有旧样本通过。

## 3. 交互限制
- AI 在输出代码前，必须先输出“风险评估（Risk Assessment）”：列出涉及的业务风险、边界条件及拟定的测试方案。
- 若代码逻辑漂移，AI 必须主动预警并提供“重新校准（Re-calibration）”方案[cite: 1]。

## 4. 评估器状态机规范 (Evaluator Status Machine)
- **状态定义**：所有评估器必须使用 `EvaluatorStatus` 枚举（SUCCESS/CANNOT_EVALUATE/PARTIAL/ERROR）来明确评估结果状态。
- **状态转换规则**：
  - SUCCESS：评估正常完成，返回有效分数。
  - CANNOT_EVALUATE：无法评估（如缺少必要输入），视为系统错误。
  - PARTIAL：部分评估（如降级评估），视为通过但需标记。
  - ERROR：评估失败（如业务规则不满足），视为业务失败。
- **业务异常传播**：`BasePlatformError` 及其子类（`ContractValidationError`, `DomainLogicError`, `InfrastructureError`）必须向上传播，由 `engine.py` 统一处理。
- **非业务异常捕获**：`safe_evaluate` 仅捕获非业务异常（如 `RuntimeError`），并转换为带 `error_code` 的 `DomainResponse`。

## 5. Pydantic 模型使用规范
- **禁止直接修改 `__dict__`**：Pydantic 模型字段必须通过 `model_validator`、`model_copy` 或构造函数参数进行设置，禁止直接修改 `__dict__`。
- **Frozen 模型处理**：使用 `frozen=True` 的 Pydantic 模型（如 `EvaluationSchema`）必须通过 `model_copy(update={...})` 创建新实例来修改字段。
- **后置验证器**：使用 `@model_validator(mode="after")` 实现模型创建后的计算逻辑（如 `confidence_level` 自动计算）。

## 6. 安全评估入口规范 (Safe Evaluate)
- **统一入口**：`engine.py` 必须调用 `evaluator.safe_evaluate()` / `evaluator.safe_evaluate_async()` 而非直接调用 `evaluate()`，确保日志记录和异常捕获。
- **异常分层处理**：
  - 业务异常（`BasePlatformError`）→ 向上传播到 engine 层处理。
  - 系统异常（`RuntimeError`, `ValueError` 等）→ 捕获并转换为 `DomainResponse(evaluation_status=ERROR, error_code=SYSTEM_ERROR)`。
- **日志记录**：`safe_evaluate` 必须调用 `_log_evaluation_result` 记录评估结果日志，包含评估器类型、输入输出、分数、状态、置信度等信息。

## 7. 日志记录规范
- **评估结果日志**：每次评估必须记录结构化日志，包含 timestamp、evaluator_type、request_id、score、evaluation_status、confidence、confidence_level、error 等字段。
- **置信度读取路径**：直接读取 `response.confidence`，禁止从 `response.data.get("confidence")` 读取。
- **Phase 1.5 诊断期要求**：记录原始输入、输出、评估维度覆盖情况，为基准测试和校准提供数据支持。

## 8. 配置管理规范
- **避免循环导入**：配置类（`Settings`）和配置实例（`settings`）必须放在 `src/config/__init__.py` 中，原 `src/config.py` 作为兼容性导入层。
- **延迟初始化**：`get_settings()` 使用 `@lru_cache` 实现单例模式，避免模块导入时的循环依赖。
- **环境变量**：敏感配置（如 `ADMIN_PASSWORD`）必须通过环境变量设置，默认值仅用于开发环境。

## 9. 架构约束
- **评估器实现规范**：所有评估器必须实现 `_do_evaluate()`，禁止直接重写 `evaluate()`，确保熔断器和降级机制生效。
- **状态枚举判断**：使用枚举值判断而非字符串匹配（如 `eval_status == EvaluatorStatus.SUCCESS` 而非 `eval_status.value == "success"`）。
- **降级策略状态**：降级评估结果必须返回 `PARTIAL` 状态，而非 `SUCCESS`，以便下游区分高置信和低置信评估。

## 10. 测试核心哲学
- **测试目标**：验证业务逻辑正确性、发现生产环境问题，绝不单纯追求代码覆盖率。
- **场景覆盖**：必须覆盖正向、负向、边界、异常、依赖五种场景。
- **断言要求**：断言必须验证具体业务逻辑，禁止仅验证 status 的弱断言。
- **测试位置**：测试代码只允许修改 `tests/` 下文件，禁止修改 `src/` 等业务代码。