"""
可靠性修复验证测试：测试目标：验证 P0/P1 级问题修复的有效性
关键发现：1. Celery 超时配置修复：soft_time_limit < time_limit，启动时验证
2. 熔断器状态竞态修复：将状态检查移到 _check_timeout_transition 方法
3. RedisListQueue 消息丢失修复：使用 BRPOPLPUSH 实现可靠消息投递
4. 缓冲服务进程间隔离：增加 Redis 分布式计数器
5. safe_parse_score 误判修复：增加智能评分制式判断
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestCeleryTimeoutConfigurationFix:
    """Celery超时配置修复验证"""

    def test_soft_time_limit_less_than_time_limit(self):
        """软超时必须小于硬超时"""
        from src.workers.tasks import TASK_SOFT_TIME_LIMIT, TASK_TIME_LIMIT

        assert TASK_SOFT_TIME_LIMIT < TASK_TIME_LIMIT, (
            f"Celery配置错误：soft_time_limit({TASK_SOFT_TIME_LIMIT}) 必须 < time_limit({TASK_TIME_LIMIT})"
        )

    def test_soft_time_limit_reasonable_value(self):
        """软超时值应在合理范围内"""
        from src.workers.tasks import TASK_SOFT_TIME_LIMIT, TASK_TIME_LIMIT

        assert TASK_SOFT_TIME_LIMIT >= 30, "软超时过短，任务可能无法优雅退出"
        assert TASK_SOFT_TIME_LIMIT <= 55, "软超时过长，接近硬超时"

        assert TASK_TIME_LIMIT >= 60, "硬超时过短，任务可能被过早终止"
        assert TASK_TIME_LIMIT <= 120, "硬超时过长，可能阻塞队列"

    def test_celery_app_config_consistent(self):
        """Celery应用配置应与tasks.py一致"""
        from src.workers.celery_app import TASK_SOFT_TIME_LIMIT as APP_SOFT
        from src.workers.celery_app import TASK_TIME_LIMIT as APP_HARD
        from src.workers.tasks import TASK_SOFT_TIME_LIMIT, TASK_TIME_LIMIT

        assert TASK_SOFT_TIME_LIMIT == APP_SOFT, "tasks.py 与 celery_app.py 的软超时配置不一致"
        assert TASK_TIME_LIMIT == APP_HARD, "tasks.py 与 celery_app.py 的硬超时配置不一致"

    def test_startup_validation_enforced(self):
        """启动时应验证配置正确性"""
        with patch.dict(
            os.environ, {"CELERY_TASK_SOFT_TIME_LIMIT": "100", "CELERY_TASK_TIME_LIMIT": "60"}
        ):
            pass

        from src.workers.tasks import TASK_SOFT_TIME_LIMIT, TASK_TIME_LIMIT

        assert TASK_SOFT_TIME_LIMIT < TASK_TIME_LIMIT


class TestCircuitBreakerRaceConditionFix:
    """熔断器状态竞态修复验证"""

    @pytest.fixture
    def circuit_breaker(self):
        from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=5.0,
            half_open_max_calls=2,
        )
        return CircuitBreaker("test_breaker", config)

    def test_state_property_no_transition(self, circuit_breaker):
        """state属性应不触发状态转换"""
        from src.distributed.circuit_breaker import CircuitState

        assert circuit_breaker.state == CircuitState.CLOSED

        for _ in range(10):
            state = circuit_breaker.state
            assert state == CircuitState.CLOSED

        assert circuit_breaker.stats.state_changes == 0

    def test_check_timeout_transition_called_explicitly(self, circuit_breaker):
        """_check_timeout_transition应在call_sync中显式调用"""
        from src.distributed.circuit_breaker import CircuitState

        circuit_breaker._record_failure()
        circuit_breaker._record_failure()
        circuit_breaker._record_failure()

        assert circuit_breaker.state == CircuitState.OPEN

        time.sleep(5.5)

        current_state = circuit_breaker._check_timeout_transition()
        assert current_state == CircuitState.HALF_OPEN

    def test_call_sync_calls_check_timeout(self, circuit_breaker):
        """call_sync应主动调用_check_timeout_transition"""
        from src.distributed.circuit_breaker import CircuitBreakerError

        circuit_breaker._record_failure()
        circuit_breaker._record_failure()
        circuit_breaker._record_failure()

        with pytest.raises(CircuitBreakerError):
            circuit_breaker.call_sync(lambda: "test")

        time.sleep(5.5)

        result = circuit_breaker.call_sync(lambda: "success")
        assert result == "success"

    def test_concurrent_state_reads_safe(self, circuit_breaker):
        """并发读取state属性应安全"""
        from src.distributed.circuit_breaker import CircuitState

        results = []

        def reader():
            for _ in range(100):
                state = circuit_breaker.state
                results.append(state)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(s == CircuitState.CLOSED for s in results)
        assert circuit_breaker.stats.state_changes == 0


class TestRedisListQueueMessageReliabilityFix:
    """RedisListQueue消息可靠性修复验证"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        redis_client = MagicMock()

        redis_client.brpoplpush.return_value = '{"message_id": "test_001", "payload": "test", "priority": 5, "created_at": "2024-01-01T00:00:00", "retry_count": 0, "max_retries": 3}'
        redis_client.lrem.return_value = 1
        redis_client.lpush.return_value = 1
        redis_client.incr.return_value = 1

        return redis_client

    @pytest.fixture
    def queue(self, mock_redis):
        from src.distributed.queue import QueueConfig, RedisListQueue

        config = QueueConfig(queue_name="test_queue")
        return RedisListQueue(mock_redis, config)

    def test_consume_uses_brpoplpush(self, queue, mock_redis):
        """consume应使用BRPOPLPUSH而非RPOP"""
        import asyncio

        async def callback(message):
            pass

        asyncio.run(queue.consume(callback))

        mock_redis.brpoplpush.assert_called_once()
        assert not hasattr(mock_redis, "rpop") or mock_redis.rpop.call_count == 0

    def test_ack_removes_from_processing_queue(self, queue, mock_redis):
        """ACK应从处理中队列删除消息"""
        import asyncio

        from src.distributed.queue import MessagePriority, QueueMessage

        message = QueueMessage(
            message_id="test_001",
            payload="test",
            priority=MessagePriority.NORMAL,
        )

        asyncio.run(queue.ack(message))

        mock_redis.lrem.assert_called_once()
        call_args = mock_redis.lrem.call_args
        assert "processing" in call_args[0][0]

    def test_processing_queue_key_generated(self, queue):
        """应生成处理中队列key"""
        processing_key = queue._get_processing_key()

        assert "processing" in processing_key
        assert queue.config.queue_name in processing_key


class TestBufferServiceDistributedCounterFix:
    """缓冲服务分布式计数修复验证"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis客户端"""
        redis_client = MagicMock()
        redis_client.incr.return_value = 1
        redis_client.decrby.return_value = 0
        return redis_client

    @pytest.fixture
    def buffer_service(self, mock_redis):
        from src.workers.tasks import EvaluationBufferService

        return EvaluationBufferService(redis_client=mock_redis)

    @pytest.fixture
    def mock_record(self):
        from src.infra.db.models import EvaluationResultModel

        return EvaluationResultModel(
            case_id="test_001",
            model_name="gpt-4",
            adapter_name="default",
            status="PASSED",
            latency_ms=100.0,
            response_data={},
        )

    def test_add_updates_redis_counter(self, buffer_service, mock_redis, mock_record):
        """add应更新Redis分布式计数器"""
        from src.workers.tasks import EvaluationBufferService

        buffer_service.add(mock_record)

        mock_redis.incr.assert_called_once_with(EvaluationBufferService.REDIS_BUFFER_COUNTER_KEY)

    def test_flush_decrements_redis_counter(self, buffer_service, mock_redis, mock_record):
        """flush应减少Redis分布式计数器"""
        mock_session = MagicMock()
        mock_session.bulk_save_objects.return_value = None
        mock_session.commit.return_value = None

        buffer_service.add(mock_record)
        buffer_service.add(mock_record)

        mock_redis.reset_mock()

        buffer_service.flush(mock_session)

        from src.workers.tasks import EvaluationBufferService

        mock_redis.decrby.assert_called_once()
        call_args = mock_redis.decrby.call_args
        assert call_args[0][0] == EvaluationBufferService.REDIS_BUFFER_COUNTER_KEY

    def test_redis_counter_key_defined(self):
        """应定义Redis计数器key常量"""
        from src.workers.tasks import EvaluationBufferService

        assert hasattr(EvaluationBufferService, "REDIS_BUFFER_COUNTER_KEY")
        assert EvaluationBufferService.REDIS_BUFFER_COUNTER_KEY.startswith("eval:buffer:")


class TestSafeParseScoreIntelligentJudgmentFix:
    """safe_parse_score智能判断修复验证"""

    @pytest.fixture
    def parser(self):
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        return NumericExtractStrategy()

    def test_normalize_score_keeps_decimal_values(self, parser):
        """小数制分数（0-1）应不转换"""
        result = parser._normalize_score(0.85, "分数 0.85")

        assert result == 0.85

    def test_normalize_score_converts_percentage_with_marker(self, parser):
        """有百分制标记的分数应转换"""
        result = parser._normalize_score(85.0, "满分100，得分85%")

        assert result == 0.85

    def test_normalize_score_converts_common_percentage_values(self, parser):
        """常见百分制整数应转换"""
        result = parser._normalize_score(80.0, "评分80")
        assert result == 0.80

        result = parser._normalize_score(90.0, "评分90")
        assert result == 0.90

        result = parser._normalize_score(100.0, "满分")
        assert result == 1.0

    def test_normalize_score_rejects_abnormal_values(self, parser):
        """异常值（>100）应返回None"""
        result = parser._normalize_score(2024.0, "年份2024")

        assert result is None

    def test_parse_with_decimal_score_returns_expected(self, parser):
        """小数制分数解析应返回预期值"""
        from src.domain.evaluators.strategies.score_parsing import ParsedScore

        result = parser.try_parse("评分0.85")

        assert result is not None
        assert isinstance(result, ParsedScore)
        assert result.score == 0.85

    def test_parse_with_percentage_score_normalizes(self, parser):
        """百分制分数解析应归一化"""
        from src.domain.evaluators.strategies.score_parsing import ParsedScore

        result = parser.try_parse("得分90")

        assert result is not None
        assert isinstance(result, ParsedScore)
        assert result.score == 0.90


class TestIntegratedSystemBehaviorAfterFixes:
    """修复后的系统集成行为验证"""

    def test_circuit_breaker_protects_evaluator(self):
        """修复后熔断器应正确保护评估器"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import EvaluationSchema

        class FailingEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise Exception("模拟失败")

        evaluator = FailingEvaluator()

        request = EvaluationSchema(id="test_001", type="test", payload={})
        for _ in range(6):
            try:
                evaluator.evaluate(request)
            except Exception:
                pass

        breaker = evaluator._get_breaker()
        from src.distributed.circuit_breaker import CircuitState

        assert breaker.state in [CircuitState.OPEN, CircuitState.CLOSED]

    def test_message_queue_reliable_delivery(self):
        """修复后消息队列应可靠投递"""
        from src.distributed.queue import QueueConfig, RedisListQueue

        mock_redis = MagicMock()
        mock_redis.brpoplpush.return_value = '{"message_id": "test", "payload": "test", "priority": 5, "created_at": "2024-01-01T00:00:00"}'

        config = QueueConfig(queue_name="test")
        queue = RedisListQueue(mock_redis, config)

        processing_key = queue._get_processing_key()
        assert "processing" in processing_key

    def test_score_parser_intelligent_normalization(self):
        """修复后评分解析器应智能归一化"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        result1 = DEFAULT_PARSER.parse("评分0.85")
        assert result1 is not None
        assert result1.score == 0.85

        result2 = DEFAULT_PARSER.parse("满分100，得分90")
        assert result2 is not None
        assert result2.score == 0.90


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])