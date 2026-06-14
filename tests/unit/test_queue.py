"""测试 distributed/queue.py - 消息队列核心模块"""

import json
import sys
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.distributed.queue import (
    BaseQueue,
    MessagePriority,
    QueueConfig,
    QueueMessage,
    QueueType,
    RedisListQueue,
    create_queue,
)


class TestQueueMessage:
    """测试消息实体"""

    def test_message_creation(self):
        msg = QueueMessage(
            message_id="test-001",
            payload={"data": "test"},
            priority=MessagePriority.HIGH,
        )
        assert msg.message_id == "test-001"
        assert msg.priority == MessagePriority.HIGH
        assert msg.retry_count == 0
        assert msg.max_retries == 3

    def test_message_to_dict(self):
        msg = QueueMessage(
            message_id="test-002",
            payload={"key": "value"},
            priority=MessagePriority.CRITICAL,
            trace_id="trace-123",
            headers={"source": "test"},
        )
        data = msg.to_dict()
        assert data["message_id"] == "test-002"
        assert data["priority"] == 15
        assert data["trace_id"] == "trace-123"
        assert data["headers"]["source"] == "test"

    def test_message_from_dict(self):
        original = QueueMessage(
            message_id="test-003",
            payload={"data": "value"},
        )
        data = original.to_dict()
        restored = QueueMessage.from_dict(data)
        assert restored.message_id == original.message_id
        assert restored.payload == original.payload

    def test_message_priority_values(self):
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 10
        assert MessagePriority.CRITICAL.value == 15

    def test_message_default_timestamp(self):
        msg = QueueMessage(message_id="ts-test", payload={})
        assert isinstance(msg.created_at, datetime)


class TestQueueConfig:
    """测试队列配置"""

    def test_default_config(self):
        config = QueueConfig()
        assert config.queue_type == QueueType.REDIS_LIST
        assert config.queue_name == "eval_tasks"
        assert config.dead_letter_queue == "eval_tasks_dlq"
        assert config.prefetch_count == 10
        assert config.auto_ack is False
        assert config.durable is True

    def test_custom_config(self):
        config = QueueConfig(
            queue_type=QueueType.RABBITMQ,
            queue_name="custom_queue",
            prefetch_count=50,
            auto_ack=True,
        )
        assert config.queue_type == QueueType.RABBITMQ
        assert config.queue_name == "custom_queue"
        assert config.prefetch_count == 50


class TestBaseQueue:
    """测试队列基类"""

    def test_abstract_methods(self):
        with pytest.raises(TypeError):
            BaseQueue(QueueConfig())


class TestRedisListQueue:
    """测试 Redis List 队列实现"""

    @pytest.fixture
    def mock_redis(self):
        return Mock()

    @pytest.fixture
    def queue(self, mock_redis):
        config = QueueConfig(queue_name="test_queue")
        return RedisListQueue(mock_redis, config)

    async def test_publish_success(self, queue, mock_redis):
        mock_redis.lpush.return_value = 1
        msg = QueueMessage(message_id="msg-1", payload={"test": "data"})
        result = await queue.publish(msg)
        assert result is True
        mock_redis.lpush.assert_called_once()

    async def test_publish_failure(self, queue, mock_redis):
        mock_redis.lpush.side_effect = Exception("Redis error")
        msg = QueueMessage(message_id="msg-2", payload={})
        result = await queue.publish(msg)
        assert result is False

    async def test_publish_to_dlq_when_max_retries(self, queue, mock_redis):
        mock_redis.lpush.return_value = 1
        msg = QueueMessage(
            message_id="msg-dlq",
            payload={},
            retry_count=3,
            max_retries=3,
        )
        result = await queue.publish(msg)
        assert result is True
        assert mock_redis.lpush.call_count == 2

    async def test_consume_message(self, queue, mock_redis):
        msg_data = {
            "message_id": "msg-3",
            "payload": {"data": "test"},
            "priority": 5,
            "created_at": datetime.utcnow().isoformat(),
        }
        mock_redis.rpop.return_value = json.dumps(msg_data)

        callback_called = False

        async def callback(message):
            nonlocal callback_called
            callback_called = True
            assert message.message_id == "msg-3"

        await queue.consume(callback)
        assert callback_called

    async def test_consume_empty_queue(self, queue, mock_redis):
        mock_redis.rpop.return_value = None
        callback = Mock()
        await queue.consume(callback)
        callback.assert_not_called()

    async def test_consume_callback_error(self, queue, mock_redis):
        msg_data = {
            "message_id": "msg-invalid",
            "payload": {},
            "priority": 5,
            "created_at": datetime.utcnow().isoformat(),
        }
        mock_redis.rpop.return_value = json.dumps(msg_data)

        async def bad_callback(message):
            raise ValueError("callback error")

        # 内部捕获异常，不应抛出
        await queue.consume(bad_callback)

    async def test_ack(self, queue):
        msg = QueueMessage(message_id="ack-test", payload={})
        result = await queue.ack(msg)
        assert result is None

    async def test_nack_requeue(self, queue, mock_redis):
        mock_redis.lpush.return_value = 1
        msg = QueueMessage(message_id="nack-test", payload={})
        await queue.nack(msg, requeue=True)
        assert msg.retry_count == 1
        mock_redis.lpush.assert_called_once()

    async def test_nack_dlq(self, queue, mock_redis):
        mock_redis.lpush.return_value = 1
        msg = QueueMessage(message_id="nack-dlq", payload={})
        await queue.nack(msg, requeue=False)
        mock_redis.lpush.assert_called_once()

    async def test_get_queue_size(self, queue, mock_redis):
        mock_redis.llen.return_value = 10
        size = await queue.get_queue_size()
        assert size == 40  # 4 priorities * 10

    async def test_get_dlq_size(self, queue, mock_redis):
        mock_redis.llen.return_value = 5
        size = await queue.get_dlq_size()
        assert size == 5

    async def test_close(self, queue):
        result = await queue.close()
        assert result is None

    def test_priority_key_generation(self, queue):
        key = queue._get_priority_key(MessagePriority.HIGH)
        assert "queue:priority:test_queue:10" in key


class TestCreateQueue:
    """测试队列工厂函数"""

    def test_create_redis_list_queue(self):
        mock_redis = Mock()
        config = QueueConfig()
        queue = create_queue(QueueType.REDIS_LIST, config, redis_client=mock_redis)
        assert isinstance(queue, RedisListQueue)

    def test_create_redis_without_client(self):
        config = QueueConfig()
        with pytest.raises(ValueError, match="redis_client is required"):
            create_queue(QueueType.REDIS_LIST, config)

    def test_create_rabbitmq_queue(self):
        # Mock pika module to avoid import error
        mock_pika = Mock()
        mock_pika.PlainCredentials = Mock
        mock_pika.BlockingConnection = Mock
        mock_pika.ConnectionParameters = Mock
        with patch.dict(sys.modules, {"pika": mock_pika}):
            config = QueueConfig()
            queue = create_queue(QueueType.RABBITMQ, config)
            assert queue is not None
