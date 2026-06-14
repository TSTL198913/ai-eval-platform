"""
消息队列抽象层

支持 RabbitMQ、Kafka 等多种消息队列实现。
提供统一的接口，屏蔽底层差异。
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

import redis

logger = logging.getLogger(__name__)

T = TypeVar("T")


class QueueType(Enum):
    """队列类型"""
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    REDIS_STREAM = "redis_stream"
    REDIS_LIST = "redis_list"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


@dataclass
class QueueMessage(Generic[T]):
    """通用消息格式"""
    message_id: str
    payload: T
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        return {
            "message_id": self.message_id,
            "payload": self.payload,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "trace_id": self.trace_id,
            "headers": self.headers,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueueMessage":
        return cls(
            message_id=data["message_id"],
            payload=data["payload"],
            priority=MessagePriority(data.get("priority", 5)),
            created_at=datetime.fromisoformat(data["created_at"]),
            trace_id=data.get("trace_id"),
            headers=data.get("headers", {}),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
        )


@dataclass
class QueueConfig:
    """队列配置"""
    queue_type: QueueType = QueueType.REDIS_LIST
    queue_name: str = "eval_tasks"
    dead_letter_queue: str = "eval_tasks_dlq"
    prefetch_count: int = 10
    auto_ack: bool = False
    durable: bool = True


class BaseQueue(ABC):
    """消息队列基类"""

    def __init__(self, config: QueueConfig):
        self.config = config

    @abstractmethod
    async def publish(self, message: QueueMessage) -> bool:
        """发布消息"""
        pass

    @abstractmethod
    async def consume(self, callback: Callable[[QueueMessage], Any]) -> None:
        """消费消息"""
        pass

    @abstractmethod
    async def ack(self, message: QueueMessage) -> None:
        """确认消息"""
        pass

    @abstractmethod
    async def nack(self, message: QueueMessage, requeue: bool = True) -> None:
        """拒绝消息"""
        pass

    @abstractmethod
    async def get_queue_size(self) -> int:
        """获取队列长度"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """关闭连接"""
        pass


class RedisListQueue(BaseQueue):
    """
    基于 Redis List 的消息队列
    
    适用于简单的任务队列场景，部署简单。
    优先级通过分队列实现。
    """

    PRIORITY_QUEUE_PREFIX = "queue:priority:"
    DLQ_PREFIX = "queue:dlq:"

    def __init__(
        self,
        redis_client: redis.Redis,
        config: QueueConfig,
    ):
        super().__init__(config)
        self.redis = redis_client

    def _get_priority_key(self, priority: MessagePriority) -> str:
        """获取优先级队列键"""
        return f"{self.PRIORITY_QUEUE_PREFIX}{self.config.queue_name}:{priority.value}"

    async def publish(self, message: QueueMessage) -> bool:
        """发布消息到对应优先级队列"""
        try:
            priority_key = self._get_priority_key(message.priority)
            data = json.dumps(message.to_dict())
            
            # 使用 LPUSH + BLPOP 实现 FIFO
            await asyncio.to_thread(
                self.redis.lpush, priority_key, data
            )
            
            # 如果配置了 DLQ，也记录一下
            if message.retry_count >= message.max_retries:
                dlq_key = f"{self.DLQ_PREFIX}{self.config.queue_name}"
                await asyncio.to_thread(
                    self.redis.lpush, dlq_key, data
                )
            
            logger.debug(f"Published message {message.message_id} to {priority_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False

    async def consume(self, callback: Callable[[QueueMessage], Any]) -> None:
        """从最高优先级队列开始消费"""
        # 按优先级从高到低尝试获取消息
        priorities = sorted(
            [p.value for p in MessagePriority],
            reverse=True
        )
        
        for priority in priorities:
            priority_key = self._get_priority_key(MessagePriority(priority))
            
            # 尝试非阻塞获取
            result = await asyncio.to_thread(
                self.redis.rpop, priority_key
            )
            
            if result:
                try:
                    data = json.loads(result)
                    message = QueueMessage.from_dict(data)
                    
                    logger.debug(f"Consuming message {message.message_id}")
                    
                    # 执行回调
                    await callback(message)
                    
                    # 自动 ACK（实际上 Redis List 不需要显式 ACK）
                    await self.ack(message)
                    return
                except Exception as e:
                    logger.error(f"Failed to process message: {e}")
                    # 消息已经在 rpop 中移除，这里模拟 nack
                    await self.nack(QueueMessage.from_dict(json.loads(result)), requeue=False)
                    return

        # 所有队列都为空，短暂等待
        await asyncio.sleep(0.1)

    async def ack(self, message: QueueMessage) -> None:
        """ACK 消息（Redis List 模式下，rpop 已自动移除）"""
        logger.debug(f"ACK message {message.message_id}")

    async def nack(self, message: QueueMessage, requeue: bool = True) -> None:
        """NACK 消息"""
        if requeue:
            message.retry_count += 1
            await self.publish(message)
            logger.warning(
                f"NACK message {message.message_id}, requeued (retry #{message.retry_count})"
            )
        else:
            # 发送到 DLQ
            dlq_key = f"{self.DLQ_PREFIX}{self.config.queue_name}"
            await asyncio.to_thread(
                self.redis.lpush, dlq_key, json.dumps(message.to_dict())
            )
            logger.warning(f"NACK message {message.message_id} sent to DLQ")

    async def get_queue_size(self) -> int:
        """获取所有优先级队列的总长度"""
        total = 0
        for priority in MessagePriority:
            key = self._get_priority_key(priority)
            total += await asyncio.to_thread(self.redis.llen, key)
        return total

    async def get_dlq_size(self) -> int:
        """获取 DLQ 长度"""
        dlq_key = f"{self.DLQ_PREFIX}{self.config.queue_name}"
        return await asyncio.to_thread(self.redis.llen, dlq_key)

    async def close(self) -> None:
        """关闭连接"""
        # Redis 连接由外部管理，这里不需要关闭
        pass


class RabbitMQQueue(BaseQueue):
    """
    RabbitMQ 消息队列实现
    
    需要安装 pika 库。
    支持优先级队列、死信队列、消息确认等高级特性。
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5672,
        username: str = "guest",
        password: str = "guest",
        config: Optional[QueueConfig] = None,
    ):
        import pika
        super().__init__(config or QueueConfig())
        self.host = host
        self.port = port
        self.credentials = pika.PlainCredentials(username, password)
        self._connection = None
        self._channel = None

    def _ensure_connection(self):
        """确保连接可用"""
        import pika
        if not self._connection or self._connection.is_closed:
            self._connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=self.host,
                    port=self.port,
                    credentials=self.credentials,
                )
            )
        if not self._channel or self._channel.is_closed:
            self._channel = self._connection.channel()
            self._setup_queues()
        return self._channel

    def _setup_queues(self):
        """设置队列和死信队列"""
        # 声明主队列，带死信交换机
        self._channel.queue_declare(
            queue=self.config.queue_name,
            durable=self.config.durable,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": self.config.dead_letter_queue,
            },
        )
        # 声明死信队列
        self._channel.queue_declare(
            queue=self.config.dead_letter_queue,
            durable=self.config.durable,
        )

    async def publish(self, message: QueueMessage) -> bool:
        """发布消息"""
        import pika
        channel = self._ensure_connection()
        
        properties = pika.BasicProperties(
            delivery_mode=2,  # 持久化
            content_type="application/json",
            headers=message.headers,
        )
        
        try:
            channel.basic_publish(
                exchange="",
                routing_key=self.config.queue_name,
                body=json.dumps(message.to_dict()),
                properties=properties,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish to RabbitMQ: {e}")
            return False

    async def consume(self, callback: Callable[[QueueMessage], Any]) -> None:
        """消费消息"""
        channel = self._ensure_connection()
        channel.basic_qos(prefetch_count=self.config.prefetch_count)
        
        def on_message(ch, method, properties, body):
            try:
                data = json.loads(body)
                message = QueueMessage.from_dict(data)
                asyncio.run(callback(message))
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Failed to consume message: {e}")
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        
        channel.basic_consume(
            queue=self.config.queue_name,
            on_message_callback=on_message,
            auto_ack=self.config.auto_ack,
        )
        
        channel.start_consuming()

    async def ack(self, message: QueueMessage) -> None:
        """ACK 消息"""
        # RabbitMQ 的 ACK 由回调自动处理
        pass

    async def nack(self, message: QueueMessage, requeue: bool = True) -> None:
        """NACK 消息"""
        # RabbitMQ 的 NACK 由回调自动处理
        pass

    async def get_queue_size(self) -> int:
        """获取队列长度"""
        channel = self._ensure_connection()
        result = channel.queue_declare(
            queue=self.config.queue_name,
            durable=self.config.durable,
            passive=True,  # 不创建，只查询
        )
        return result.method.message_count

    async def close(self) -> None:
        """关闭连接"""
        if self._channel and self._channel.is_open:
            self._channel.close()
        if self._connection and self._connection.is_open:
            self._connection.close()


def create_queue(
    queue_type: QueueType,
    config: QueueConfig,
    **kwargs,
) -> BaseQueue:
    """
    工厂函数：创建消息队列实例
    """
    if queue_type == QueueType.REDIS_LIST:
        redis_client = kwargs.get("redis_client")
        if not redis_client:
            raise ValueError("redis_client is required for RedisListQueue")
        return RedisListQueue(redis_client, config)
    elif queue_type == QueueType.RABBITMQ:
        return RabbitMQQueue(
            host=kwargs.get("host", "localhost"),
            port=kwargs.get("port", 5672),
            username=kwargs.get("username", "guest"),
            password=kwargs.get("password", "guest"),
            config=config,
        )
    else:
        raise ValueError(f"Unsupported queue type: {queue_type}")
