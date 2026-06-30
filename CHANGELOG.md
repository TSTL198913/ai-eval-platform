# AI Eval Platform - Changelog

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

#### 数据库迁移 (SQLite→PostgreSQL)
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
- 测试框架（1800+测试用例）