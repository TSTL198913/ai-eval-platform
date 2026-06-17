import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from src.distributed.queue import (
    QueueType,
    MessagePriority,
    QueueMessage,
    QueueConfig,
    BaseQueue,
    RedisListQueue,
)


class TestQueueType:
    def test_queue_type_values(self):
        assert QueueType.RABBITMQ.value == 'rabbitmq'
        assert QueueType.KAFKA.value == 'kafka'
        assert QueueType.REDIS_STREAM.value == 'redis_stream'
        assert QueueType.REDIS_LIST.value == 'redis_list'

    def test_queue_type_count(self):
        assert len(list(QueueType)) == 4


class TestMessagePriority:
    def test_priority_values(self):
        assert MessagePriority.LOW.value == 1
        assert MessagePriority.NORMAL.value == 5
        assert MessagePriority.HIGH.value == 10
        assert MessagePriority.CRITICAL.value == 15

    def test_priority_order(self):
        assert MessagePriority.LOW.value < MessagePriority.NORMAL.value
        assert MessagePriority.NORMAL.value < MessagePriority.HIGH.value
        assert MessagePriority.HIGH.value < MessagePriority.CRITICAL.value


class TestQueueMessage:
    def test_message_creation(self):
        msg = QueueMessage(message_id='1', payload={'data': 'test'})
        assert msg.message_id == '1'
        assert msg.payload == {'data': 'test'}
        assert msg.priority == MessagePriority.NORMAL
        assert msg.retry_count == 0

    def test_message_with_priority(self):
        msg = QueueMessage(
            message_id='1',
            payload='test',
            priority=MessagePriority.HIGH
        )
        assert msg.priority == MessagePriority.HIGH

    def test_message_to_dict(self):
        msg = QueueMessage(message_id='1', payload={'key': 'value'})
        result = msg.to_dict()
        assert result['message_id'] == '1'
        assert result['payload'] == {'key': 'value'}
        assert result['priority'] == 5

    def test_message_from_dict(self):
        data = {
            'message_id': '1',
            'payload': 'test',
            'priority': 10,
            'created_at': '2024-01-01T00:00:00',
            'trace_id': 'trace1',
            'headers': {'key': 'value'},
            'retry_count': 1,
            'max_retries': 5
        }
        msg = QueueMessage.from_dict(data)
        assert msg.message_id == '1'
        assert msg.priority == MessagePriority.HIGH
        assert msg.retry_count == 1

    def test_message_with_trace_id(self):
        msg = QueueMessage(message_id='1', payload='test', trace_id='trace123')
        assert msg.trace_id == 'trace123'

    def test_message_with_headers(self):
        msg = QueueMessage(
            message_id='1',
            payload='test',
            headers={'Content-Type': 'application/json'}
        )
        assert msg.headers['Content-Type'] == 'application/json'

    def test_message_max_retries(self):
        msg = QueueMessage(message_id='1', payload='test', max_retries=5)
        assert msg.max_retries == 5


class TestQueueConfig:
    def test_default_config(self):
        config = QueueConfig()
        assert config.queue_type == QueueType.REDIS_LIST
        assert config.queue_name == 'eval_tasks'
        assert config.dead_letter_queue == 'eval_tasks_dlq'
        assert config.prefetch_count == 10
        assert config.auto_ack is False
        assert config.durable is True

    def test_custom_config(self):
        config = QueueConfig(
            queue_type=QueueType.KAFKA,
            queue_name='custom_queue',
            prefetch_count=20
        )
        assert config.queue_type == QueueType.KAFKA
        assert config.queue_name == 'custom_queue'
        assert config.prefetch_count == 20


class TestRedisListQueue:
    def test_queue_initialization(self):
        mock_redis = MagicMock()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        assert queue.redis == mock_redis
        assert queue.config == config

    def test_get_priority_key(self):
        mock_redis = MagicMock()
        config = QueueConfig(queue_name='test_queue')
        queue = RedisListQueue(mock_redis, config)
        key = queue._get_priority_key(MessagePriority.HIGH)
        assert 'test_queue' in key
        assert '10' in key

    @pytest.mark.asyncio
    async def test_publish_message(self):
        mock_redis = MagicMock()
        mock_redis.rpush = MagicMock(return_value=1)
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload={'data': 'test'})
        result = await queue.publish(msg)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_queue_size(self):
        mock_redis = MagicMock()
        mock_redis.llen = MagicMock(return_value=10)
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        size = await queue.get_queue_size()
        # get_queue_size sums all priority queues (4 priorities)
        assert size == 40

    @pytest.mark.asyncio
    async def test_close(self):
        mock_redis = MagicMock()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        await queue.close()
        # close() does nothing as Redis connection is managed externally
