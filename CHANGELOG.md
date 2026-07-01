# AI Eval Platform - Changelog

## [2.2.0] - 2026-07-01

### Security & Data Validation

#### LLM Guard Security Scanner
- 新增 `LLMGuardEvaluator` 安全扫描评估器
- 集成 llm-guard 库，检测 OWASP Top 10 for LLM 风险
- 支持的扫描类型：PromptInjection、Toxicity、TokenLimit、Code、Bias、Relevance、Sensitive、Language
- 输出综合安全分数、风险等级（low/medium/high/critical）、详细扫描结果

#### Great Expectations Data Validator
- 新增 `GoldenDatasetValidator` 数据验证层
- 使用 great-expectations 验证 Golden Dataset Schema
- 验证规则：必需字段检查、字段类型检查、分数范围检查（0-1）、ID唯一性、类型枚举值验证
- 输出验证报告、通过率统计、错误/警告列表

### Auto-Calibration Mechanism

#### AdaptiveCalibrator
- 新增 `AdaptiveCalibrator` 自适应校准器（单例模式）
- 实时监控评估器输出与期望值的偏差
- 偏差超过 5% 时触发警报（支持严重级别：low/medium/high/critical）
- 支持自动校准和手动校准模式
- 提供校准报告和趋势分析
- 线程安全实现，支持并发访问

#### Configuration Updates
- 新增 `golden_dataset_path` 配置项
- 新增 `calibration_threshold` 配置项（默认0.05）
- 新增 `calibration_min_samples` 配置项（默认5）

### Test Quality Improvements

- 新增 `test_llm_guard_evaluator.py` - 安全扫描评估器测试
- 新增 `test_data_validator.py` - 数据验证器测试
- 新增 `test_adaptive_calibrator.py` - 自适应校准器测试
- 按优先级提升前5个低质量测试文件的强断言比例
- `test_bug_detection.py` 强断言比例从 34.0% → A级（≥50%）
- `test_security_evaluator_blackbox.py` 强断言比例从 35.6% → 38.9%

### Bug Fixes

- 修复 `BaseEvaluator.evaluate()` 和 `evaluate_async()` 中添加 None 检查
- 修复熔断器锁机制，统一使用 `threading.RLock`
- 修复全局变量 `_sync_task_results` 线程安全问题
- 修复状态转换逻辑一致性问题，移除 `is_valid` 回退
- 修复 great-expectations API 兼容性问题

## [2.1.0] - 2026-07-01

### Major Changes

#### 评估器状态机 (EvaluatorStatus)
- 引入 `EvaluatorStatus` 枚举：SUCCESS/CANNOT_EVALUATE/PARTIAL/ERROR
- 明确区分"评估失败"与"无法评估"场景
- 状态转换规则：EvaluatorStatus → EvaluationRecordStatus
- 修改 `DomainResponse` 添加 `evaluation_status` 字段

#### 置信度系统 (ConfidenceLevel)
- 引入 `ConfidenceLevel` 枚举：HIGH/MEDIUM/LOW/VERY_LOW
- 置信度自动计算：基于 confidence 值通过 `@model_validator(mode="after")` 计算
- 置信度阈值：≥0.9(HIGH), ≥0.7(MEDIUM), ≥0.5(LOW), <0.5(VERY_LOW)
- 修改 `DomainResponse` 添加 `confidence` 和 `confidence_level` 字段

#### 安全评估入口 (safe_evaluate)
- 在 `BaseEvaluator` 中添加 `safe_evaluate()` 和 `safe_evaluate_async()` 方法
- 异常分层处理：业务异常向上传播，非业务异常捕获并转换为 DomainResponse
- 统一日志记录：每次评估记录结构化日志（timestamp、evaluator_type、score、confidence、evaluation_status等）
- engine.py 调用 `safe_evaluate` 而非 `evaluate`，确保日志记录和异常处理

#### 结构化日志记录
- 添加 `_log_evaluation_result()` 方法，记录评估结果详细日志
- 日志格式：JSON 结构，包含输入输出、分数、状态、置信度、评估维度覆盖情况
- 支持 Phase 1.5 诊断期要求：记录原始输入、输出、评估维度覆盖情况

#### Pydantic 模型规范
- 修改 `DomainResponse` 使用 `@model_validator(mode="after")` 替代直接修改 `__dict__`
- 修改 `EvaluationSchema` 使用 `ConfigDict(frozen=True)` 并通过 `model_copy` 修改字段
- 修复 `response.data.get("confidence")` 读取路径错误，改为直接读取 `response.confidence`

### Architecture Improvements

- 修复 engine.py 中 `EvaluationStatus` 导入冲突，别名为 `EvaluationRecordStatus`
- 修复 `_normalize_payload_fields` 修改 frozen 对象问题，改用 `model_copy`
- 修复 `_build_evaluation_result` 状态映射逻辑，区分业务失败(FAILED)和系统错误(ERROR)
- 修复 `safe_evaluate` 异常捕获逻辑，仅捕获非业务异常

### Code Quality

- 修复 Pydantic 模型字段修改方式，符合最佳实践
- 修复日志读取路径，确保置信度正确记录
- 修复状态机转换逻辑，符合预期行为

### Documentation

- 更新 `ARCHITECTURE.md` 添加状态机、置信度系统、安全评估入口等章节
- 更新 `.trae/rules/ai_engineer/RULES.md` 添加评估器状态机规范、Pydantic模型使用规范、安全评估入口规范、日志记录规范、配置管理规范、测试核心哲学等章节

---

## [2.0.0] - 2026-06-29

### Major Changes

#### 评估器精简 (37→15)
- 保留15个核心评估器：general, code, code_review, security, memory, semantic, qa, factuality, risk, classification, composite, function_call, multi_agent, llm_as_judge, robustness
- 将22个评估器移至候选列表（重复功能、待完善、外部依赖）
- 添加`_EVALUATOR_BLACKLIST`机制控制评估器注册
- 修改`EvaluatorFactory.register()`支持`force`参数绕过黑名单

#### API路由聚合 (27→5)
- 创建v2 API路由聚合层，按功能域分组：
  - `/v2/evaluation/` - 评估相关
  - `/v2/models/` - 模型管理
  - `/v2/data/` - 数据管理
  - `/v2/analytics/` - 分析报表
  - `/v2/config/` - 配置管理
- 原v1路由保留，支持渐进式迁移

#### 数据库迁移(SQLite→PostgreSQL)
- 将默认数据库从SQLite改为PostgreSQL
- 测试环境自动切换回SQLite（`TESTING=1`）
- 代码已支持`QueuePool`连接池配置

#### RBAC安全增强
- 创建`fastapi_rbac.py`实现真正的权限验证
- 添加`require_permission`依赖注入
- 添加`require_role`依赖注入
- 添加`RBACMiddleware`中间件
- 集成到FastAPI应用

### Performance Improvements

- 将`reset_evaluator_registry` fixture改为session级别
- 添加pytest-xdist并行化支持（`pytest -n auto`）
- 优化评估器注册逻辑，减少模块重新加载次数

### Bug Fixes

- 修复API路由测试注册表为空问题
- 修复MemoryEvaluator相似度计算问题
- 修复评估器注册测试隔离问题
- 修复SecurityEvaluator正则匹配问题

### Code Quality

- Ruff修复34个代码问题
- isort导入排序
- 添加类型注解

### Documentation

- 创建`docs/TESTING_STRATEGY.md`测试策略文档
- 更新`pytest.ini`添加并行化配置

---

## [1.0.0] - 2026-06-20

### Initial Release

- 基础评估器框架
- 37个评估器实现
- 27个API路由
- SQLite数据库
- 熔断器、限流、幂等性机制
- 测试框架，800+测试用例