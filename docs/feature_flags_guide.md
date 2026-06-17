"""
特性开关使用指南 - 运营/产品团队版

本文档帮助运营和产品团队理解如何使用特性开关控制平台功能。

## 特性开关列表

| 开关名称 | 描述 | 默认状态 | 影响范围 |
|---------|------|---------|---------|
| PRIORITY_BUFFER | 优先级缓冲队列 | 关闭 | 任务调度 |
| ADAPTIVE_BATCH_SIZE | 自适应批量大小 | 开启 | 数据库写入 |
| ASYNC_EVALUATION | 异步评测 | 开启 | 评测执行 |
| COST_GOVERNANCE | 成本治理 | 开启 | LLM调用成本 |
| IDENTITY_CHECK | 幂等性检查 | 开启 | 请求去重 |
| CIRCUIT_BREAKER | 熔断器 | 开启 | 故障保护 |
| RATE_LIMITER | 限流 | 开启 | 流量控制 |
| CACHE_ENABLED | 缓存 | 开启 | 性能优化 |
| METRICS_ENABLED | 指标监控 | 开启 | 监控系统 |
| TRACING_ENABLED | 分布式追踪 | 开启 | 链路追踪 |

## 使用方式

### 方式1: 环境变量配置

在 `.env` 文件中设置：
```
FEATURE_PRIORITY_BUFFER=true
FEATURE_ADAPTIVE_BATCH_SIZE=true
FEATURE_ASYNC_EVALUATION=true
```

### 方式2: 运行时动态切换

```python
from src.infra.feature_flags import feature_manager, FeatureFlag

# 开启特性
feature_manager.enable(FeatureFlag.PRIORITY_BUFFER)

# 关闭特性
feature_manager.disable(FeatureFlag.CACHE_ENABLED)

# 切换状态
feature_manager.toggle(FeatureFlag.ASYNC_EVALUATION)

# 获取所有特性状态
print(feature_manager.get_all_features())
```

## 灰度发布流程

### 标准流程

1. **开发完成**: 新功能开发并通过测试
2. **特性开关创建**: 在 `feature_flags.py` 中添加新开关，默认关闭
3. **内部测试**: 开启开关，内部团队测试
4. **灰度开启**: 通过环境变量逐步开启（如先50%流量）
5. **全量上线**: 确认无问题后永久开启

### 回滚策略

如果新功能出现问题：
```python
# 立即关闭特性
feature_manager.disable(FeatureFlag.NEW_FEATURE)
```

## 注意事项

### 开启前检查

- [ ] 相关测试用例已通过
- [ ] 监控指标已配置
- [ ] 回滚方案已确认

### 性能影响

| 特性 | 开启影响 | 关闭影响 |
|------|---------|---------|
| CACHE_ENABLED | 提升响应速度 | 响应变慢 |
| CIRCUIT_BREAKER | 故障保护 | 无保护 |
| RATE_LIMITER | 防止过载 | 可能过载 |

### 依赖关系

某些特性依赖其他特性：

```
ASYNC_EVALUATION → CACHE_ENABLED (推荐)
COST_GOVERNANCE → METRICS_ENABLED (必需)
CIRCUIT_BREAKER → TRACING_ENABLED (推荐)
```

## 示例场景

### 场景1: 新功能灰度

```python
# 为特定用户开启新功能
if user_id in beta_users:
    feature_manager.enable(FeatureFlag.NEW_FEATURE)
```

### 场景2: 紧急关闭

```python
# 检测到异常时自动关闭
if error_rate > 0.1:
    feature_manager.disable(FeatureFlag.ASYNC_EVALUATION)
```

### 场景3: A/B测试

```python
# 根据用户ID分配到不同版本
if hash(user_id) % 2 == 0:
    feature_manager.enable(FeatureFlag.FEATURE_V2)
else:
    feature_manager.enable(FeatureFlag.FEATURE_V1)
```

## 监控与告警

### 特性开关变更日志

所有特性开关变更都会记录到日志中：
```
[INFO] Feature PRIORITY_BUFFER enabled
[INFO] Feature CACHE_ENABLED disabled
```

### 建议监控指标

- 特性开关状态变更次数
- 各特性开启/关闭时间
- 特性开启后的系统指标变化

## 维护建议

### 定期清理

- 每季度审查一次特性开关
- 移除已稳定的永久开启特性
- 更新依赖关系文档

### 文档更新

- 新增特性时更新本文档
- 特性变更时通知相关团队
- 保持文档与代码一致
"""

from src.infra.feature_flags import FeatureManager, FeatureFlag


def get_feature_status() -> dict:
    """获取所有特性状态"""
    return FeatureManager().get_all_features()


def set_feature_status(feature_name: str, enabled: bool) -> bool:
    """设置特性状态"""
    manager = FeatureManager()
    try:
        feature = FeatureFlag(feature_name)
        if enabled:
            manager.enable(feature)
        else:
            manager.disable(feature)
        return True
    except ValueError:
        return False


def toggle_feature(feature_name: str) -> bool:
    """切换特性状态"""
    manager = FeatureManager()
    try:
        feature = FeatureFlag(feature_name)
        return manager.toggle(feature)
    except ValueError:
        return False
