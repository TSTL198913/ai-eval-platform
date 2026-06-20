"""分布式队列测试"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.distributed.queue import (
    MessagePriority,
    QueueConfig,
    QueueMessage,
    QueueType,
    RedisListQueue,
)


class TestQueueMessage:
    """消息格式测试"""

    def test_to_dict(self):
        """消息应能转换为字典"""
        message = QueueMessage(
            message_id="msg-001",
            payload={"data": "test"},
            priority=MessagePriority.HIGH,
            trace_id="trace-123",
            headers={"content-type": "application/json"},
        )
        data = message.to_dict()
        assert data["message_id"] == "msg-001"
        assert data["payload"] == {"data": "test"}
        assert data["priority"] == 10
        assert data["trace_id"] == "trace-123"
        assert data["headers"] == {"content-type": "application/json"}

    def test_from_dict(self):
        """消息应能从字典恢复"""
        data = {
            "message_id": "msg-002",
            "payload": {"result": "success"},
            "priority": 5,
            "created_at": "2024-01-01T00:00:00",
            "trace_id": "trace-456",
            "headers": {"key": "value"},
            "retry_count": 1,
            "max_retries": 3,
        }
        message = QueueMessage.from_dict(data)
        assert message.message_id == "msg-002"
        assert message.payload == {"result": "success"}
        assert message.priority == MessagePriority.NORMAL
        assert message.trace_id == "trace-456"
        assert message.retry_count == 1

    def test_default_values(self):
        """消息应使用默认值"""
        message = QueueMessage(message_id="msg-003", payload="test")
        assert message.priority == MessagePriority.NORMAL
        assert isinstance(message.created_at, datetime)
        assert message.trace_id is None
        assert message.retry_count == 0
        assert message.max_retries == 3


class TestQueueConfig:
    """队列配置测试"""

    def test_default_config(self):
        """默认配置应正确"""
        config = QueueConfig()
        assert config.queue_type == QueueType.REDIS_LIST
        assert config.queue_name == "eval_tasks"
        assert config.dead_letter_queue == "eval_tasks_dlq"
        assert config.prefetch_count == 10
        assert config.auto_ack is False
        assert config.durable is True

    def test_custom_config(self):
        """自定义配置应正确"""
        config = QueueConfig(
            queue_type=QueueType.REDIS_STREAM,
            queue_name="custom_queue",
            dead_letter_queue="custom_dlq",
            prefetch_count=5,
            auto_ack=True,
            durable=False,
        )
        assert config.queue_type == QueueType.REDIS_STREAM
        assert config.queue_name == "custom_queue"
        assert config.prefetch_count == 5
        assert config.auto_ack is True


class TestRedisListQueue:
    """Redis List 队列测试"""

    @pytest.fixture
    def mock_redis(self):
        mock = MagicMock()
        mock.lpush = MagicMock(return_value=1)
        mock.rpop = MagicMock(return_value=None)
        mock.llen = MagicMock(return_value=0)
        return mock

    @pytest.fixture
    def config(self):
        return QueueConfig(queue_name="test_queue")

    @pytest.fixture
    def queue(self, mock_redis, config):
        return RedisListQueue(mock_redis, config)

    @pytest.mark.asyncio
    async def test_publish_success(self, queue, mock_redis):
        """发布消息应成功"""
        message = QueueMessage(message_id="publish-001", payload="test_data")
        result = await queue.publish(message)
        assert result is True
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_failure(self, queue, mock_redis):
        """发布消息失败应返回False"""
        mock_redis.lpush = MagicMock(side_effect=Exception("Redis error"))
        message = QueueMessage(message_id="publish-fail", payload="test")
        result = await queue.publish(message)
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_to_dlq_when_max_retries(self, queue, mock_redis):
        """超过重试次数应发送到DLQ"""
        message = QueueMessage(
            message_id="dlq-msg",
            payload="test",
            retry_count=3,
            max_retries=3,
        )
        result = await queue.publish(message)
        assert result is True
        assert mock_redis.lpush.call_count == 2

    @pytest.mark.asyncio
    async def test_consume_with_message(self, queue, mock_redis):
        """消费消息应正确处理"""
        import json
        message = QueueMessage(message_id="consume-001", payload="test")
        mock_redis.rpop = MagicMock(return_value=json.dumps(message.to_dict()))

        received_message = []
        async def callback(msg):
            received_message.append(msg)

        await queue.consume(callback)

        assert len(received_message) == 1
        assert received_message[0].message_id == "consume-001"

    @pytest.mark.asyncio
    async def test_consume_empty_queue(self, queue, mock_redis):
        """空队列应短暂等待后返回"""
        mock_redis.rpop = MagicMock(return_value=None)

        received_message = []
        async def callback(msg):
            received_message.append(msg)

        await queue.consume(callback)

        assert len(received_message) == 0

    @pytest.mark.asyncio
    async def test_consume_with_callback_error(self, queue, mock_redis):
        """回调错误应触发nack"""
        import json
        message = QueueMessage(message_id="error-msg", payload="test")
        mock_redis.rpop = MagicMock(return_value=json.dumps(message.to_dict()))

        async def callback(msg):
            raise Exception("Callback error")

        await queue.consume(callback)

        mock_redis.lpush.assert_called()

    @pytest.mark.asyncio
    async def test_ack(self, queue):
        """ACK应记录日志"""
        message = QueueMessage(message_id="ack-msg", payload="test")
        await queue.ack(message)

    @pytest.mark.asyncio
    async def test_nack_requeue(self, queue, mock_redis):
        """NACK并重入队列应重新发布"""
        message = QueueMessage(message_id="nack-requeue", payload="test")
        await queue.nack(message, requeue=True)
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_nack_dlq(self, queue, mock_redis):
        """NACK到DLQ应发送到死信队列"""
        message = QueueMessage(message_id="nack-dlq", payload="test")
        await queue.nack(message, requeue=False)
        mock_redis.lpush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_size(self, queue, mock_redis):
        """获取队列大小应正确"""
        mock_redis.llen = MagicMock(return_value=5)
        size = await queue.get_queue_size()
        assert size == 20


class TestMessagePriority:
    """消息优先级测试"""

    def test_priority_values(self):
        """优先级值应正确"""
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 10
        assert MessagePriority.CRITICAL.value == 15


class TestQueueType:
    """队列类型测试"""

    def test_queue_type_values(self):
        """队列类型值应正确"""
        assert QueueType.RABBITMQ.value == "rabbitmq"
        assert QueueType.KAFKA.value == "kafka"
        assert QueueType.REDIS_STREAM.value == "redis_stream"
        assert QueueType.REDIS_LIST.value == "redis_list"
