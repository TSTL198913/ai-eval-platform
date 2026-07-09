# Changelog

## v2.1.1 (2026-07-09)

### 新增功能

- 重构评估器架构，分离核心服务层（ClientFactory、InferenceService、PersistenceService）
- 增强并发安全性，修复5个并发安全Bug
- 实现统一校准引擎（UnifiedCalibrationEngine）
- 添加事件总线（EventBus）与事件订阅系统
- 重构缓存层，支持Redis集群管理
- 添加v2 API路由，支持幂等性检查和Prometheus监控
- 增强安全性，添加RBAC权限控制
- 完善测试体系，新增业务场景、回归测试和可靠性测试
- 更新配置管理，支持监控配置（Grafana/Prometheus）
- 添加demo.py演示脚本，便于面试展示

### 性能优化

- 评估器异步评估使用专用线程池
- 缓存层支持Redis集群，提升可靠性
- 事件驱动架构优化校准流程

### 修复

- 修复熔断器模式线程安全问题
- 修复评估器工厂对象池线程安全
- 修复嵌入服务单例锁问题
- 修复连接泄漏检测器精度问题
- 修复事件总线单例保护问题

### 测试

- 新增58个核心测试用例
- 新增回归测试套件（tests/regression/）
- 新增业务场景测试（tests/business/）
- 新增可靠性测试（tests/reliability/）

### 文档

- 更新ARCHITECTURE.md，添加v2.1.1版本历史
- 更新README.md，添加最新功能描述
- 更新运维手册，同步版本信息
- 添加CONTRIBUTING.md、SECURITY.md、LICENSE

### 删除废弃文件

- 清理旧版前端配置（vite.config.ts、tailwind.config.js）
- 清理废弃部署脚本
- 清理临时工具脚本

## v1.0.0 (2026-07-04)

### 新增功能

- 事件驱动架构（Event Bus）
- 智能自动化校准闭环
- 规则驱动降级策略
- O(1) LRU缓存优化
- 熔断器模式

### 性能优化

- LRU缓存从O(n)提升至O(1)，吞吐量提升347倍
- 事件持久化从JSON文件改为Redis
- DLQ指数退避重试策略

### 修复

- 修复trigger_recalibration无LLM客户端问题
- 修复模型路由熔断器测试问题
- 修复批量评估一致性问题

### 测试

- 新增端到端集成测试
- 新增性能基准测试
- 修复评估器注册问题

### 文档

- 添加Apache-2.0许可证
- 添加贡献指南
- 添加安全策略