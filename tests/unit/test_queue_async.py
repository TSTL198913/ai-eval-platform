import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock

from src.distributed.queue import (
    QueueType,
    MessagePriority,
    QueueMessage,
    QueueConfig,
    RedisListQueue,
)


class TestRedisListQueueAsync:
    def test_consume_empty_queue(self):
        mock_redis = MagicMock()
        mock_redis.rpop.return_value = None
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        
        async def test_consume():
            await queue.consume(lambda msg: None)
        
        asyncio.run(test_consume())
        assert mock_redis.rpop.call_count == 4

    def test_consume_with_message(self):
        mock_redis = MagicMock()
        msg_data = json.dumps({
            'message_id': '1',
            'payload': {'data': 'test'},
            'priority': 5,
            'created_at': '2024-01-01T00:00:00',
            'trace_id': '',
            'headers': {},
            'retry_count': 0,
            'max_retries': 3
        })
        mock_redis.rpop.return_value = msg_data.encode()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        
        received_msg = []
        async def callback(msg):
            received_msg.append(msg)
        
        async def test_consume():
            await queue.consume(callback)
        
        asyncio.run(test_consume())
        assert len(received_msg) == 1
        assert received_msg[0].message_id == '1'

    def test_consume_message_process_error(self):
        mock_redis = MagicMock()
        msg_data = json.dumps({
            'message_id': '1',
            'payload': {'data': 'test'},
            'priority': 5,
            'created_at': '2024-01-01T00:00:00',
            'trace_id': '',
            'headers': {},
            'retry_count': 0,
            'max_retries': 3
        })
        mock_redis.rpop.return_value = msg_data.encode()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        
        async def callback(msg):
            raise Exception('Process error')
        
        async def test_consume():
            await queue.consume(callback)
        
        asyncio.run(test_consume())

    def test_ack_message(self):
        mock_redis = MagicMock()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload='test')
        
        async def test_ack():
            await queue.ack(msg)
        
        asyncio.run(test_ack())

    def test_nack_with_requeue(self):
        mock_redis = MagicMock()
        mock_redis.lpush.return_value = 1
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload='test', retry_count=0, max_retries=3)
        
        async def test_nack():
            await queue.nack(msg, requeue=True)
        
        asyncio.run(test_nack())
        assert msg.retry_count == 1

    def test_nack_to_dlq(self):
        mock_redis = MagicMock()
        mock_redis.lpush.return_value = 1
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload='test')
        
        async def test_nack():
            await queue.nack(msg, requeue=False)
        
        asyncio.run(test_nack())
        mock_redis.lpush.assert_called_once()

    def test_get_dlq_size(self):
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 5
        config = QueueConfig(queue_name='test_queue')
        queue = RedisListQueue(mock_redis, config)
        
        async def test_size():
            size = await queue.get_dlq_size()
            assert size == 5
        
        asyncio.run(test_size())

    def test_publish_to_dlq_when_max_retries(self):
        mock_redis = MagicMock()
        mock_redis.lpush.return_value = 1
        config = QueueConfig(queue_name='test_queue')
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload='test', retry_count=3, max_retries=3)
        
        async def test_publish():
            await queue.publish(msg)
        
        asyncio.run(test_publish())
        assert mock_redis.lpush.call_count == 2

    def test_publish_failure(self):
        mock_redis = MagicMock()
        mock_redis.lpush.side_effect = Exception('Redis error')
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        msg = QueueMessage(message_id='1', payload='test')
        
        async def test_publish():
            result = await queue.publish(msg)
            assert result is False
        
        asyncio.run(test_publish())

    def test_consume_highest_priority_first(self):
        mock_redis = MagicMock()
        high_msg_data = json.dumps({
            'message_id': 'high1',
            'payload': {'data': 'high'},
            'priority': 10,
            'created_at': '2024-01-01T00:00:00',
            'trace_id': '',
            'headers': {},
            'retry_count': 0,
            'max_retries': 3
        })
        mock_redis.rpop.side_effect = [None, None, high_msg_data.encode(), None]
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        
        received = []
        async def callback(msg):
            received.append(msg)
        
        async def test_consume():
            await queue.consume(callback)
        
        asyncio.run(test_consume())
        assert mock_redis.rpop.call_count == 3
        assert len(received) == 1

    def test_close_connection(self):
        mock_redis = MagicMock()
        config = QueueConfig()
        queue = RedisListQueue(mock_redis, config)
        
        async def test_close():
            await queue.close()
        
        asyncio.run(test_close())
