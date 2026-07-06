"""
生产级事件总线（Event Bus）

实现发布/订阅模式，解耦模块间的直接依赖：
- 校准模块（calibration_engine）
- 降级策略（fallback_policy）
- 监控指标（metrics）
- 评估器（evaluators）

支持：
- 同步和异步事件处理
- 线程安全
- 幂等性保障（基于事件签名去重）
- 死信队列（DLQ）+ 指数退避重试
- 速率限制（防止事件风暴）
- Redis持久化（防止进程崩溃丢失，支持分布式多实例共享）
- 优雅关闭（处理在途事件）
"""

import asyncio
import hashlib
import json
import logging
import random
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Any
from typing import Callable

logger = logging.getLogger(__name__)

REDIS_KEY_PREFIX = "event_bus:"


class EventType:
    """事件类型定义"""
    CALIBRATION_NEEDED = "calibration_needed"
    EVALUATION_COMPLETED = "evaluation_completed"
    FALLBACK_TRIGGERED = "fallback_triggered"
    DRIFT_DETECTED = "drift_detected"
    ERROR_OCCURRED = "error_occurred"
    SCORE_CALIBRATED = "score_calibrated"
    SELF_HEALING_STARTED = "self_healing_started"
    SELF_HEALING_COMPLETED = "self_healing_completed"


@dataclass
class Event:
    """事件数据结构"""
    event_type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: str = "unknown"
    event_id: str = field(default_factory=lambda: hashlib.md5(f"{time.time()}{id(object())}".encode()).hexdigest())

    def get_signature(self) -> str:
        """获取事件签名（用于幂等性检查）"""
        key_parts = [self.event_type]
        if "evaluator_name" in self.payload:
            key_parts.append(self.payload["evaluator_name"])
        if "fallback_method" in self.payload:
            key_parts.append(self.payload["fallback_method"])
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()

    def to_dict(self) -> dict:
        """转换为字典（用于持久化）"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """从字典创建事件"""
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            payload=data["payload"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source=data.get("source", "unknown"),
        )


class EventBus:
    """生产级事件总线"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(
        self,
        deduplication_ttl: int = 60,
        rate_limit_per_minute: int = 100,
        dlq_max_size: int = 1000,
        redis_client=None,
        dlq_max_retries: int = 3,
        dlq_base_delay: float = 1.0,
    ):
        if self._initialized:
            return

        self._subscribers: dict[str, list[tuple[Callable, bool]]] = defaultdict(list)
        self._shutdown_event = threading.Event()

        self._deduplication_ttl = deduplication_ttl
        self._processed_signatures: dict[str, float] = {}

        self._rate_limit_per_minute = rate_limit_per_minute
        self._event_counts: dict[str, list[float]] = defaultdict(list)

        self._dlq_max_size = dlq_max_size
        self._dead_letter_queue: list[Event] = []
        self._dlq_max_retries = dlq_max_retries
        self._dlq_base_delay = dlq_base_delay
        self._dlq_retry_counts: dict[str, int] = {}

        self._redis_client = redis_client
        if self._redis_client is None:
            try:
                from src.infra.cache import get_redis_client
                self._redis_client = get_redis_client()
            except Exception as e:
                logger.warning(f"Redis不可用，使用内存模式: {e}")

        self._recovery_done = False
        self._initialized = True
        logger.info("EventBus 初始化完成（生产级）")

    def _recover_events(self):
        """从Redis恢复未处理的事件（支持分布式多实例共享）"""
        if self._recovery_done:
            return
        try:
            if self._redis_client:
                try:
                    pending_key = f"{REDIS_KEY_PREFIX}pending_events"
                    while True:
                        event_data = self._redis_client.rpop(pending_key)
                        if not event_data:
                            break
                        try:
                            event = Event.from_dict(json.loads(event_data))
                            age = (datetime.utcnow() - event.timestamp).total_seconds()
                            if age < 3600:
                                logger.info(f"从Redis恢复事件 | type={event.event_type} | id={event.event_id}")
                                self._publish_internal(event)
                            else:
                                logger.warning(f"跳过过期事件 | type={event.event_type} | age={age}s")
                        except Exception as e:
                            logger.error(f"解析恢复事件失败: {e}")
                except Exception as e:
                    logger.warning(f"Redis恢复失败，跳过: {e}")
        except Exception as e:
            logger.error(f"事件恢复失败: {e}")
        finally:
            self._recovery_done = True

    def _persist_events(self, events: list[Event]):
        """持久化事件到Redis（防止进程崩溃丢失，支持分布式多实例共享）"""
        try:
            if self._redis_client:
                pending_key = f"{REDIS_KEY_PREFIX}pending_events"
                for event in events:
                    self._redis_client.lpush(pending_key, json.dumps(event.to_dict(), ensure_ascii=False))
                    self._redis_client.expire(pending_key, 3600)
                logger.debug(f"事件已持久化到Redis | count={len(events)}")
        except Exception as e:
            logger.error(f"事件持久化失败: {e}")

    def _is_duplicate(self, event: Event) -> bool:
        """检查事件是否重复（幂等性）"""
        signature = event.get_signature()
        now = time.time()

        with self._lock:
            if signature in self._processed_signatures:
                if now - self._processed_signatures[signature] < self._deduplication_ttl:
                    logger.debug(f"跳过重复事件 | signature={signature[:8]}")
                    return True
                del self._processed_signatures[signature]

            self._processed_signatures[signature] = now
            self._cleanup_deduplication_cache()

        return False

    def _cleanup_deduplication_cache(self):
        """清理过期的去重缓存"""
        now = time.time()
        to_remove = [
            sig for sig, timestamp in self._processed_signatures.items()
            if now - timestamp > self._deduplication_ttl * 2
        ]
        for sig in to_remove:
            del self._processed_signatures[sig]

    def _check_rate_limit(self, event_type: str) -> bool:
        """检查速率限制"""
        if self._rate_limit_per_minute <= 0:
            return True

        now = time.time()
        with self._lock:
            counts = self._event_counts[event_type]
            counts = [t for t in counts if now - t < 60]

            if len(counts) >= self._rate_limit_per_minute:
                logger.warning(f"速率限制触发 | type={event_type} | count={len(counts)}")
                return False

            counts.append(now)
            self._event_counts[event_type] = counts

        return True

    def _add_to_dlq(self, event: Event, error: Exception):
        """将失败事件添加到死信队列（带指数退避重试计数）"""
        with self._lock:
            retry_count = self._dlq_retry_counts.get(event.event_id, 0)
            if retry_count >= self._dlq_max_retries:
                logger.error(
                    f"事件已达到最大重试次数，丢弃 | type={event.event_type} | id={event.event_id} | "
                    f"retry_count={retry_count}"
                )
                return

            if len(self._dead_letter_queue) >= self._dlq_max_size:
                self._dead_letter_queue.pop(0)

            self._dead_letter_queue.append(event)
            self._dlq_retry_counts[event.event_id] = retry_count + 1
            logger.error(
                f"事件进入死信队列 | type={event.event_type} | id={event.event_id} | "
                f"error={error} | dlq_size={len(self._dead_letter_queue)} | "
                f"retry_count={retry_count + 1}"
            )

    def _calculate_retry_delay(self, event_id: str) -> float:
        """计算指数退避延迟：base_delay * 2^attempt + random_jitter"""
        retry_count = self._dlq_retry_counts.get(event_id, 0)
        delay = self._dlq_base_delay * (2 ** (retry_count - 1))
        jitter = random.uniform(0, delay * 0.1)
        return min(delay + jitter, 30.0)

    def subscribe(
        self,
        event_type: str,
        handler: Callable[..., Any],
        is_async: bool = False,
    ):
        """订阅事件"""
        with self._lock:
            self._subscribers[event_type].append((handler, is_async))
            logger.debug(f"事件订阅 | type={event_type} | handler={handler.__name__}")

    def unsubscribe(self, event_type: str, handler: Callable[..., Any]):
        """取消订阅事件"""
        with self._lock:
            subscribers = self._subscribers.get(event_type, [])
            self._subscribers[event_type] = [
                (h, is_async) for h, is_async in subscribers if h != handler
            ]
            logger.debug(f"事件取消订阅 | type={event_type} | handler={handler.__name__}")

    def _publish_internal(self, event: Event):
        """内部发布事件（带幂等性和速率限制检查）"""
        if self._shutdown_event.is_set():
            logger.warning(f"事件总线已关闭，丢弃事件 | type={event.event_type}")
            return

        if self._is_duplicate(event):
            return

        if not self._check_rate_limit(event.event_type):
            self._add_to_dlq(event, Exception("Rate limit exceeded"))
            return

        with self._lock:
            subscribers = list(self._subscribers.get(event.event_type, []))

        if not subscribers:
            logger.debug(f"无订阅者 | type={event.event_type}")
            return

        pending_events = []
        for handler, is_async in subscribers:
            try:
                if is_async:
                    asyncio.ensure_future(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"事件处理失败 | type={event.event_type} | handler={handler.__name__} | error={e}")
                pending_events.append(event)

        if pending_events:
            self._persist_events(pending_events)

    def publish(self, event_type: str, **kwargs):
        """发布事件（同步）"""
        event = Event(
            event_type=event_type,
            payload=kwargs,
            source=kwargs.get("source", "unknown"),
        )

        if not self._recovery_done:
            self._recover_events()

        self._publish_internal(event)

    async def publish_async(self, event_type: str, **kwargs):
        """发布事件（异步）"""
        event = Event(
            event_type=event_type,
            payload=kwargs,
            source=kwargs.get("source", "unknown"),
        )

        if not self._recovery_done:
            self._recover_events()

        if self._is_duplicate(event):
            return

        if not self._check_rate_limit(event.event_type):
            self._add_to_dlq(event, Exception("Rate limit exceeded"))
            return

        with self._lock:
            subscribers = list(self._subscribers.get(event.event_type, []))

        if not subscribers:
            logger.debug(f"无订阅者 | type={event.event_type}")
            return

        pending_events = []
        tasks = []
        for handler, is_async in subscribers:
            try:
                if is_async:
                    tasks.append(handler(event))
                else:
                    tasks.append(asyncio.to_thread(handler, event))
            except Exception as e:
                logger.error(f"事件处理失败 | type={event.event_type} | handler={handler.__name__} | error={e}")
                pending_events.append(event)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    handler, _ = subscribers[i]
                    logger.error(
                        f"异步事件处理失败 | type={event.event_type} | "
                        f"handler={handler.__name__} | error={result}"
                    )
                    pending_events.append(event)

        if pending_events:
            self._persist_events(pending_events)

    def get_subscriber_count(self, event_type: str) -> int:
        """获取指定事件类型的订阅者数量"""
        with self._lock:
            return len(self._subscribers.get(event_type, []))

    def list_event_types(self) -> list[str]:
        """获取所有已注册的事件类型"""
        with self._lock:
            return list(self._subscribers.keys())

    def get_dlq_size(self) -> int:
        """获取死信队列大小"""
        with self._lock:
            return len(self._dead_letter_queue)

    def get_dlq_events(self) -> list[Event]:
        """获取死信队列中的事件"""
        with self._lock:
            return list(self._dead_letter_queue)

    def retry_dlq_events(self):
        """重试死信队列中的事件（使用指数退避策略）"""
        with self._lock:
            events_to_retry = list(self._dead_letter_queue)
            self._dead_letter_queue.clear()

        logger.info(f"开始重试死信队列 | count={len(events_to_retry)}")
        for event in events_to_retry:
            try:
                delay = self._calculate_retry_delay(event.event_id)
                if delay > 0:
                    time.sleep(delay)
                self._publish_internal(event)
                with self._lock:
                    if event.event_id in self._dlq_retry_counts:
                        del self._dlq_retry_counts[event.event_id]
            except Exception as e:
                logger.error(f"重试失败 | type={event.event_type} | error={e}")
                self._add_to_dlq(event, e)

    def shutdown(self, timeout: int = 10):
        """优雅关闭事件总线"""
        logger.info("开始关闭事件总线...")
        self._shutdown_event.set()

        deadline = time.time() + timeout
        while self.get_dlq_size() > 0 and time.time() < deadline:
            time.sleep(0.5)

        logger.info(f"事件总线关闭完成 | dlq_size={self.get_dlq_size()}")

    def reset(self):
        """重置事件总线"""
        with self._lock:
            self._subscribers.clear()
            self._processed_signatures.clear()
            self._event_counts.clear()
            self._dead_letter_queue.clear()
        logger.info("EventBus 已重置")

    def health_check(self) -> dict:
        """健康检查"""
        with self._lock:
            return {
                "status": "healthy",
                "subscribers": {k: len(v) for k, v in self._subscribers.items()},
                "dlq_size": len(self._dead_letter_queue),
                "deduplication_cache_size": len(self._processed_signatures),
            }


event_bus = EventBus()


def publish_event(event_type: str, **kwargs):
    """便捷函数：发布事件"""
    event_bus.publish(event_type, **kwargs)


def subscribe_event(event_type: str, handler: Callable[..., Any], is_async: bool = False):
    """便捷函数：订阅事件"""
    event_bus.subscribe(event_type, handler, is_async)