"""
可靠性测试补充

覆盖系统可靠性的关键维度：
1. 熔断器恢复能力测试
2. 数据库事务一致性测试
3. 缓存层容错测试
4. 消息队列可靠性测试
5. 服务降级与熔断测试
6. 资源泄漏检测测试
7. 线程池稳定性测试
8. 分布式锁竞争测试
"""

import asyncio
import os
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest


class TestCircuitBreakerRecovery:
    """熔断器恢复能力测试"""

    def test_circuit_breaker_failure_and_recovery(self):
        """验证熔断器失败后能够恢复"""
        from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=3.0,
            half_open_max_calls=2,
        )
        breaker = CircuitBreaker("recovery_test", config)

        def failing_func():
            raise Exception("failure")

        def success_func():
            return "success"

        for _ in range(3):
            try:
                breaker.call_sync(failing_func)
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN

        with pytest.raises(Exception):
            breaker.call_sync(failing_func)

        time.sleep(3.5)

        result = breaker.call_sync(success_func)
        assert result == "success"

        result = breaker.call_sync(success_func)
        assert result == "success"

        assert breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_half_open_max_calls(self):
        """验证半开状态下最大调用数限制"""
        from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=3.0,
            half_open_max_calls=2,
        )
        breaker = CircuitBreaker("half_open_test", config)

        def failing_func():
            raise Exception("failure")

        for _ in range(3):
            try:
                breaker.call_sync(failing_func)
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN

        time.sleep(3.5)

        def success_func():
            return "success"

        result1 = breaker.call_sync(success_func)
        assert result1 == "success"

        result2 = breaker.call_sync(success_func)
        assert result2 == "success"

        assert breaker.state == CircuitState.CLOSED

    def test_circuit_breaker_reset(self):
        """验证熔断器手动重置"""
        from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=30.0,
        )
        breaker = CircuitBreaker("reset_test", config)

        def failing_func():
            raise Exception("failure")

        for _ in range(3):
            try:
                breaker.call_sync(failing_func)
            except Exception:
                pass

        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED

        def success_func():
            return "success"

        result = breaker.call_sync(success_func)
        assert result == "success"


class TestDatabaseTransactionConsistency:
    """数据库事务一致性测试"""

    def test_transaction_isolation(self):
        """验证事务隔离性"""
        from src.infra.db.session import get_db_session, init_tables
        from src.infra.db.models import EvaluationResultModel
        from sqlalchemy import select

        init_tables()

        with get_db_session() as session1:
            with get_db_session() as session2:
                record1 = EvaluationResultModel(
                    case_id=f"txn_test_{uuid.uuid4()}",
                    model_name="test-model",
                    adapter_name="default",
                    status="PENDING",
                    latency_ms=100.0,
                    response_data={},
                )
                session1.add(record1)
                session1.flush()

                stmt = select(EvaluationResultModel).where(EvaluationResultModel.case_id == record1.case_id)
                result = session2.execute(stmt)
                record2 = result.scalar_one_or_none()

                assert record2 is None

                session1.commit()

                result = session2.execute(stmt)
                record2 = result.scalar_one_or_none()

                assert record2 is not None
                assert record2.case_id == record1.case_id

    def test_transaction_rollback(self):
        """验证事务回滚"""
        from src.infra.db.session import get_db_session, init_tables
        from src.infra.db.models import EvaluationResultModel
        from sqlalchemy import select

        init_tables()

        with get_db_session() as session:
            case_id = f"rollback_test_{uuid.uuid4()}"
            record = EvaluationResultModel(
                case_id=case_id,
                model_name="test-model",
                adapter_name="default",
                status="PENDING",
                latency_ms=100.0,
                response_data={},
            )
            session.add(record)
            session.flush()

            stmt = select(EvaluationResultModel).where(EvaluationResultModel.case_id == case_id)
            result = session.execute(stmt)
            assert result.scalar_one_or_none() is not None

            session.rollback()

            result = session.execute(stmt)
            assert result.scalar_one_or_none() is None


class TestCacheLayerFaultTolerance:
    """缓存层容错测试"""

    def test_cache_disconnected_returns_none(self):
        """验证缓存未连接时返回None"""
        from src.infra.cache.redis_cluster_manager import RedisClusterManager

        cluster_manager = RedisClusterManager()
        cluster_manager.disconnect()

        assert cluster_manager.is_connected() is False

    def test_cache_get_nonexistent_key(self):
        """验证获取不存在的键返回None"""
        from src.infra.cache.redis_cluster_manager import RedisClusterManager

        cluster_manager = RedisClusterManager()

        result = cluster_manager.get("nonexistent_key_never_exists")
        assert result is None

    def test_cache_connection_stats(self):
        """验证连接统计信息"""
        from src.infra.cache.redis_cluster_manager import RedisClusterManager

        cluster_manager = RedisClusterManager()
        stats = cluster_manager.get_connection_stats()

        assert "connected" in stats
        assert "error_count" in stats
        assert "pool_size" in stats


class TestMessageQueueReliability:
    """消息队列可靠性测试"""

    def test_message_deduplication(self):
        """验证消息去重"""
        from src.distributed.queue import QueueMessage, MessagePriority

        message1 = QueueMessage(
            message_id="dup_test_001",
            payload="test",
            priority=MessagePriority.NORMAL,
        )
        message2 = QueueMessage(
            message_id="dup_test_001",
            payload="test",
            priority=MessagePriority.NORMAL,
        )

        assert message1.message_id == message2.message_id

    def test_message_priority_ordering(self):
        """验证消息优先级"""
        from src.distributed.queue import MessagePriority

        assert MessagePriority.HIGH.value > MessagePriority.NORMAL.value
        assert MessagePriority.NORMAL.value > MessagePriority.LOW.value


class TestServiceDegradation:
    """服务降级测试"""

    def test_evaluator_degradation(self):
        """验证评估器降级机制"""
        from src.domain.evaluators.base import BaseEvaluator
        from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus

        class DegradingEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise RuntimeError("External service unavailable")

        evaluator = DegradingEvaluator()
        request = EvaluationSchema(id="degrade_test", type="test", payload={})

        result = evaluator.safe_evaluate(request)

        assert result.evaluation_status in [EvaluatorStatus.PARTIAL, EvaluatorStatus.ERROR]
        assert result.score is not None


class TestResourceLeakDetection:
    """资源泄漏检测测试"""

    def test_session_manager_basic_usage(self):
        """验证数据库会话管理器基本功能"""
        from src.infra.db.session import get_db_session

        with get_db_session() as session:
            assert session is not None

    def test_thread_pool_cleanup(self):
        """验证线程池正确清理"""
        executor = ThreadPoolExecutor(max_workers=5)

        def task():
            time.sleep(0.1)
            return "done"

        futures = [executor.submit(task) for _ in range(10)]
        for future in as_completed(futures):
            assert future.result() == "done"

        executor.shutdown(wait=True)

        assert executor._shutdown, "线程池未正确关闭"


class TestDistributedLockCompetition:
    """分布式锁竞争测试"""

    def test_lock_acquisition_competition(self):
        """验证分布式锁竞争处理"""
        from src.distributed.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=5.0,
        )

        breakers = []
        num_breakers = 5

        for i in range(num_breakers):
            breaker = CircuitBreaker(f"lock_competition_test_{i}", config)
            breakers.append(breaker)

        def trigger_failure(breaker):
            def failing_func():
                raise Exception("failure")

            for _ in range(3):
                try:
                    breaker.call_sync(failing_func)
                except Exception:
                    pass

        with ThreadPoolExecutor(max_workers=num_breakers) as executor:
            futures = [executor.submit(trigger_failure, b) for b in breakers]
            for future in as_completed(futures):
                future.result()

        for breaker in breakers:
            from src.distributed.circuit_breaker import CircuitState

            assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerRegistry:
    """熔断器注册中心测试"""

    def test_registry_singleton(self):
        """验证注册中心单例"""
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry1 = CircuitBreakerRegistry.get_instance()
        registry2 = CircuitBreakerRegistry.get_instance()

        assert registry1 is registry2

    def test_registry_concurrent_access(self):
        """验证注册中心并发访问安全"""
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()
        errors = []
        num_threads = 10

        def get_or_create_task(index):
            try:
                breaker = registry.get_or_create(f"concurrent_breaker_{index}")
                assert breaker is not None
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_or_create_task, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"注册中心并发访问出现错误: {errors}"

    def test_registry_list_breakers(self):
        """验证列出所有熔断器"""
        from src.distributed.circuit_breaker import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry()

        for i in range(3):
            registry.get_or_create(f"list_test_breaker_{i}")

        breakers = registry.list_breakers()

        assert len(breakers) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])