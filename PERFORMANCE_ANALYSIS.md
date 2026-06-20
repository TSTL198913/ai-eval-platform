# AI Eval Platform 性能分析报告

> 生成时间：2026-06-16
> 分析范围：全项目代码
> 状态：待优化

---

## 一、项目架构概览

### 核心组件

| 模块 | 文件路径 | 职责 |
|-----|---------|------|
| API 服务 | `src/api/server.py` | HTTP 入口，同步/异步评测 |
| 评估引擎 | `src/engine.py` | 核心评测逻辑 |
| LLM 客户端 | `src/domain/models/base.py` | 大模型调用封装 |
| 异步任务 | `src/workers/tasks.py` | Celery 任务处理 |
| 消息队列 | `src/distributed/queue.py` | Redis/RabbitMQ 队列 |
| 性能优化 | `src/infra/performance.py` | 缓存、批处理、连接池 |
| 熔断器 | `src/distributed/circuit_breaker.py` | 防止级联失败 |
| 限流器 | `src/distributed/rate_limiter.py` | 分布式限流 |

### 当前资源配置

| 资源 | 当前配置 | 评估 |
|-----|---------|------|
| 数据库连接池 | `pool_size=10`, `max_overflow=20` | ⚠️ 偏小 |
| 缓存大小 | `max_size=2000`, `ttl=600s` | ✅ 合理 |
| 批量大小 | `batch_size=1000` | ⚠️ 偏大 |
| 批量超时 | `batch_timeout=0.1s` | ✅ 合理 |
| 限流 | `max_tokens=100`, `refill_rate=10` | ⚠️ 偏保守 |

---

## 二、性能问题清单

### 🔴 Critical：高优先级问题

#### P0-01：每次任务创建新的 LLM 客户端和引擎实例

**位置**：`src/workers/tasks.py#L231`

```python
# 问题代码
engine = EvaluationEngine(create_llm_client())
```

**影响**：
- LLM 客户端包含 HTTP 连接池，频繁创建/销毁导致连接开销
- 每个任务的初始化时间增加约 **50-200ms**
- 高并发下可能导致端口耗尽

**建议方案**：引入客户端池或单例模式，复用 LLM 客户端实例

---

#### P0-02：同步数据库操作阻塞 Celery Worker

**位置**：`src/workers/tasks.py#L239-L246`

```python
# 问题代码
db_record = _result_to_model(result)
count = buffer_service.add(db_record)
if count >= buffer_service.batch_size:
    buffer_service.flush()  # 同步 flush 阻塞 Worker
```

**影响**：
- `flush()` 中的 `bulk_save_objects` 和 `commit` 是同步操作
- 数据库写入延迟导致 Worker 无法处理下一个任务
- 批量大小为 1000，可能导致内存占用过高

**建议方案**：使用异步数据库驱动（如 `asyncpg`）或独立写入线程

---

#### P0-03：Redis 连接未复用

**位置**：`src/workers/monitor_queue.py#L6`

```python
# 问题代码
def check_backlog(host, port, db):
    r = redis.Redis(host=host, port=port, db=db)  # 每次调用新建连接
```

**影响**：每次检查都建立新连接，频繁操作时开销显著

**建议方案**：创建全局 Redis 连接池

---

### 🟡 Major：中等优先级问题

#### P1-01：LRU 缓存的 O(n) 删除操作

**位置**：`src/infra/performance.py#L81-L83`

```python
# 问题代码
if key in self._access_order:
    self._access_order.remove(key)  # list.remove() 是 O(n)
```

**影响**：
- 缓存命中率高时，每次访问都需要 O(n) 时间更新顺序
- 缓存大小为 2000 时，最坏情况每次访问耗时显著

**建议方案**：使用 `collections.OrderedDict`（Python 3.7+ 保持插入顺序）或双向链表

---

#### P1-02：缓存键生成使用 JSON 序列化

**位置**：`src/infra/performance.py#L171`

```python
# 问题代码
key = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
```

**影响**：
- `json.dumps` 开销较大，尤其参数复杂时
- 没有使用更高效的哈希算法

**建议方案**：使用 `hashlib` 或 `repr` 替代 JSON 序列化

---

#### P1-03：批量处理器的锁竞争

**位置**：`src/infra/performance.py#L215-L220`

```python
# 问题代码
async with self._lock:
    self._pending.append((item, future))
    if len(self._pending) >= self._batch_size:
        await self._process_batch()  # 锁内执行批量处理
```

**影响**：`_process_batch` 在锁内执行，其他请求必须等待批量处理完成

**建议方案**：锁外执行批量处理，仅保护 `_pending` 列表的修改

---

### 🟢 Minor：低优先级问题

#### P2-01：延迟追踪的同步排序

**位置**：`src/infra/performance_breakthrough.py#L51`

```python
# 问题代码
sorted_latencies = sorted(self._latencies)  # O(n log n)
```

**影响**：窗口大小为 1000 时，每次计算百分位数都需要排序

**建议方案**：使用分位数估计算法（如 t-digest）或维护有序列表

---

#### P2-02：RedisListQueue 的顺序扫描

**位置**：`src/distributed/queue.py#L177-L202`

```python
# 问题代码
for priority in priorities:  # 按优先级逐个检查
    result = await asyncio.to_thread(self.redis.rpop, priority_key)
```

**影响**：低优先级消息需要遍历所有高优先级队列后才能被处理

**建议方案**：使用 Redis Stream 的消费者组功能

---

#### P2-03：EvaluationRepository 单条插入效率低

**位置**：`src/infra/db/repository.py#L17-L37`

```python
# 问题代码
def save(self, result: EvaluationResult) -> int:
    with get_db_session() as session:
        session.add(db_record)
        session.flush()
        session.commit()  # 每条记录单独提交
```

**影响**：大量单条插入时数据库事务开销大

**建议方案**：与 buffer_service 的批量写入机制统一

---

## 三、迭代计划

### 第一阶段：核心路径优化（预期收益：50%+）

| 序号 | 任务 | 优先级 | 预估工时 | 依赖 |
|-----|------|-------|---------|------|
| 1 | LLM 客户端池化/单例模式 | P0 | 4h | 无 |
| 2 | Redis 连接池全局化 | P0 | 2h | 无 |
| 3 | 缓存键生成优化 | P1 | 2h | 无 |

**目标**：减少任务初始化开销，提升吞吐量

---

### 第二阶段：数据层优化（预期收益：30%+）

| 序号 | 任务 | 优先级 | 预估工时 | 依赖 |
|-----|------|-------|---------|------|
| 4 | 异步数据库写入改造 | P0 | 8h | 阶段一 |
| 5 | 批量处理器锁优化 | P1 | 3h | 无 |
| 6 | LRU 缓存结构优化 | P1 | 4h | 无 |

**目标**：消除数据库写入阻塞，提升 Worker 利用率

---

### 第三阶段：基础设施优化（预期收益：15%+）

| 序号 | 任务 | 优先级 | 预估工时 | 依赖 |
|-----|------|-------|---------|------|
| 7 | 延迟追踪算法优化 | P2 | 3h | 无 |
| 8 | Redis Stream 队列升级 | P2 | 6h | 阶段二 |
| 9 | 数据库连接池调优 | P2 | 2h | 阶段二 |

**目标**：完善监控体系，支持更高并发

---

## 四、优化收益预估

| 优化项 | 优化前 | 优化后 | 提升幅度 |
|-------|-------|-------|---------|
| LLM 客户端初始化 | 50-200ms/任务 | <1ms | **95%+** |
| 缓存访问（高频） | O(n) | O(1) | **10x** |
| 缓存键生成 | JSON 序列化 | hash | **5x** |
| Worker 吞吐量 | 受 DB 阻塞 | 异步写入 | **30%+** |
| 百分位计算 | O(n log n) | O(1) 估算 | **显著** |

---

## 五、风险评估

| 风险 | 等级 | 描述 | 缓解措施 |
|-----|------|------|---------|
| LLM 客户端并发安全 | 高 | 共享客户端可能存在线程安全问题 | 使用连接池，每个连接独立 |
| 异步写入数据一致性 | 高 | 异步写入可能导致数据丢失 | 使用 WAL 或消息队列持久化 |
| 缓存一致性 | 中 | 缓存过期策略可能导致脏数据 | 设置合理 TTL，提供手动失效 |
| Redis Stream 迁移 | 中 | 队列类型变更影响兼容性 | 提供双写迁移方案 |

---

## 六、现有性能组件评估

| 组件 | 文件 | 状态 | 评估 |
|-----|------|------|------|
| LRU 缓存 | `src/infra/performance.py` | ✅ 已实现 | 基本功能完整，实现效率待优化 |
| 批处理器 | `src/infra/performance.py` | ✅ 已实现 | 架构设计合理，锁竞争需优化 |
| 连接池监控 | `src/infra/performance.py` | ✅ 已实现 | 监控指标完善，缺少实际优化动作 |
| 延迟追踪 | `src/infra/performance_breakthrough.py` | ✅ 已实现 | 追踪功能完善，计算效率待优化 |
| 熔断器 | `src/distributed/circuit_breaker.py` | ✅ 已实现 | 功能完整，支持 Redis 持久化 |
| 限流器 | `src/distributed/rate_limiter.py` | ✅ 已实现 | 支持多种策略，多维度限流 |

---

## 七、后续行动

1. **优先级确认**：与团队确认优化优先级和排期
2. **性能基线**：建立性能测试基线，记录优化前后对比数据
3. **分步实施**：按迭代计划逐步实施，每次变更后运行测试验证
4. **持续监控**：部署后持续监控关键指标，及时调整配置

---

*报告结束*
