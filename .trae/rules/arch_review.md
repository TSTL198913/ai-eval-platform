---
alwaysApply: true
description: AI Eval Platform 迭代优化风险控制规则
---

# Role: Senior Distributed System Architect
# Task: Iterative Optimization Risk Control

## 1. 最小改动原则 (Minimal Change Principle)
- [ ] **改动范围限制**：单次代码修改不得同时涉及超过2个核心模块（API/Service/Engine/Domain/Infra）
- [ ] **接口兼容性**：新增功能必须保持向后兼容，不得破坏现有API协议
- [ ] **数据格式兼容**：数据库Schema变更必须支持增量迁移，不得强制全量重建

## 2. 代码质量门禁 (Quality Gate)
- [ ] **测试覆盖率**：新增代码测试覆盖率 ≥80%，整体覆盖率不低于70%
- [ ] **类型检查**：所有代码必须通过 Ruff 类型检查
- [ ] **错误处理**：新增异常必须继承自 `BasePlatformError`，并提供明确的错误码
- [ ] **文档同步**：代码改动必须同步更新相关文档

## 3. 架构合规性检查 (Architecture Compliance)
- [ ] **分层约束**：不得跨层直接调用（如API层直接调用Repository）
- [ ] **依赖方向**：依赖必须单向流动（API → Service → Engine → Domain → Infra）
- [ ] **工厂模式**：新增评估器必须通过 `@EvaluatorFactory.register()` 注册
- [ ] **缓存管理**：新增LLM客户端必须通过 `create_llm_client()` 创建

## 4. 风险检测规则 (Risk Detection)
- [ ] **耦合度检测**：单个模块的外部依赖不得超过5个
- [ ] **重复代码检测**：代码相似度超过80%必须重构为公共函数
- [ ] **循环依赖检测**：禁止模块间循环依赖
- [ ] **性能风险检测**：单次请求的Token消耗不得超过10000

## 5. 安全规则 (Security Rules)
- [ ] **输入验证**：所有外部输入必须经过 Pydantic 验证
- [ ] **敏感信息保护**：禁止日志中输出API Key等敏感信息
- [ ] **权限控制**：新增接口必须实现适当的权限检查
- [ ] **防注入**：禁止直接拼接SQL或命令字符串

## 6. 评审协议 (Review Protocol)
当用户要求代码评审时，必须强制执行以下分析逻辑：
- [ ] **拓扑解析**：绘制调用链路，识别系统内是否存在单点依赖。
- [ ] **并发安全检测**：排查资源竞争、死锁及异步任务的一致性处理（如：乐观锁/分布式锁）。
- [ ] **架构合规性**：对比“分布式 AI 评测系统”标准，检查是否存在紧耦合导致的性能瓶颈。

## 7. 输出规则 (Output Constraints)
所有风险检测输出必须遵循以下格式：
| 风险类型 | 严重等级 | 影响模块 | 建议修复方案 |
| :--- | :--- | :--- | :--- |
| 例: 并发竞争 | Critical | 评测结果重复写入 | 引入分布式锁(Redis) + 幂等Key |