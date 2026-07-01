"""
Tasks模块专项测试
测试目标：验证EvaluationBufferService和任务注册功能
"""

import os
import signal
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

os.environ["TESTING"] = "1"

from src.infra.db.models import EvaluationResultModel
from src.schemas.schemas import EvaluationResult
from src.workers.tasks import (
    EvaluationBufferService,
    _get_celery_app,
    _get_evaluation_engine,
    _get_metrics,
    _get_Task,
    _register_task,
    _result_to_model,
    _TaskBase,
)


class TestBufferService:
    """EvaluationBufferService缓冲服务测试"""

    @pytest.fixture
    def buffer_service(self):
        return EvaluationBufferService(
            batch_size=5,
            flush_interval_seconds=0.1,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )

    def test_init(self, buffer_service):
        """初始化缓冲服务"""
        assert buffer_service.batch_size == 5
        assert buffer_service.buffer_size == 0

    def test_add(self, buffer_service):
        """添加记录到缓冲区"""
        mock_item = MagicMock(spec=EvaluationResultModel)
        count = buffer_service.add(mock_item)

        assert count == 1
        assert buffer_service.buffer_size == 1

    def test_add_priority(self):
        """添加高优先级记录"""
        buffer_service = EvaluationBufferService(batch_size=5, priority_enabled=True, async_flush=False)
        mock_item = MagicMock(spec=EvaluationResultModel)
        count = buffer_service.add(mock_item, priority=True)

        assert count == 1
        assert buffer_service.priority_buffer_size == 1

    def test_add_and_flush_if_needed(self):
        """添加记录并在达到批次大小时flush"""
        buffer_service = EvaluationBufferService(
            batch_size=2,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item1 = MagicMock(spec=EvaluationResultModel)
        mock_item2 = MagicMock(spec=EvaluationResultModel)

        with patch.object(buffer_service, "_flush_batch") as mock_flush:
            mock_flush.return_value = 2
            buffer_service.add_and_flush_if_needed(mock_item1)
            buffer_service.add_and_flush_if_needed(mock_item2)

        mock_flush.assert_called_once()
        assert buffer_service.buffer_size == 0

    def test_add_and_flush_if_needed_flush_failure(self):
        """flush失败时应恢复缓冲区"""
        buffer_service = EvaluationBufferService(
            batch_size=2,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item1 = MagicMock(spec=EvaluationResultModel)
        mock_item2 = MagicMock(spec=EvaluationResultModel)

        with patch.object(buffer_service, "_flush_batch") as mock_flush:
            mock_flush.side_effect = Exception("flush failed")

            with pytest.raises(Exception):
                buffer_service.add_and_flush_if_needed(mock_item1)
                buffer_service.add_and_flush_if_needed(mock_item2)

        assert buffer_service.buffer_size == 2

    def test_flush_empty(self, buffer_service):
        """flush空缓冲区应返回None"""
        result = buffer_service.flush()

        assert result is None

    def test_flush_with_data(self):
        """flush有数据的缓冲区"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        with patch("src.workers.tasks.get_session_local") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.return_value = mock_session

            result = buffer_service.flush()

            assert result == 1
            mock_session.bulk_save_objects.assert_called_once()
            mock_session.commit.assert_called_once()

    def test_flush_with_external_session(self):
        """使用外部session进行flush"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        mock_session = MagicMock()

        result = buffer_service.flush(db_session=mock_session)

        assert result == 1
        mock_session.bulk_save_objects.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_flush_failure_rollback(self):
        """flush失败时应回滚并恢复缓冲区"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        mock_session = MagicMock()
        mock_session.bulk_save_objects.side_effect = Exception("flush failed")

        with pytest.raises(Exception):
            buffer_service.flush(db_session=mock_session)

        mock_session.rollback.assert_called_once()
        assert buffer_service.buffer_size == 1

    def test_buffer_size_property(self, buffer_service):
        """buffer_size属性应返回正确大小"""
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        assert buffer_service.buffer_size == 1

    def test_get_flush_stats(self, buffer_service):
        """get_flush_stats应返回统计信息"""
        stats = buffer_service.get_flush_stats()

        assert stats["total_flush_count"] == 0
        assert stats["avg_flush_latency"] == 0.0

    def test_reset_stats(self, buffer_service):
        """reset_stats应重置统计信息"""
        buffer_service._total_flush_count = 10
        buffer_service._total_flush_latency = 1.0

        buffer_service.reset_stats()

        assert buffer_service._total_flush_count == 0
        assert buffer_service._total_flush_latency == 0.0

    def test_get_adaptive_batch_size(self):
        """自适应批量大小"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=True,
            min_batch_size=5,
            max_batch_size=50,
            priority_enabled=False,
            async_flush=False,
        )

        for _i in range(20):
            mock_item = MagicMock(spec=EvaluationResultModel)
            buffer_service.add(mock_item)

        adaptive_size = buffer_service._get_adaptive_batch_size()

        assert adaptive_size > 10
        assert adaptive_size <= 50

    def test_get_or_create_session(self):
        """获取或创建session"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )

        with patch("src.workers.tasks.get_session_local") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.return_value = mock_session

            session1 = buffer_service.get_or_create_session()
            session2 = buffer_service.get_or_create_session()

            assert session1 is session2

    def test_close_reusable_session(self):
        """关闭可复用session"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )

        mock_session = MagicMock()
        buffer_service._reusable_session = mock_session

        buffer_service.close_reusable_session()

        mock_session.close.assert_called_once()
        assert buffer_service._reusable_session is None

    def test_signal_handler(self):
        """信号处理器"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )

        with patch.object(buffer_service, "flush") as mock_flush:
            buffer_service._signal_handler(signal.SIGTERM, None)

        mock_flush.assert_called_once()
        assert buffer_service._closed is True

    def test_atexit_flush(self):
        """进程退出时flush"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        with patch.object(buffer_service, "flush") as mock_flush:
            buffer_service._atexit_flush()

        mock_flush.assert_called_once()

    def test_maybe_time_based_flush(self):
        """时间触发的flush"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            flush_interval_seconds=0.01,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        time.sleep(0.02)

        with patch.object(buffer_service, "_flush_batch") as mock_flush:
            mock_flush.return_value = 1
            buffer_service._maybe_time_based_flush()

    def test_maybe_time_based_flush_failure(self):
        """时间触发的flush失败时应恢复缓冲区"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            flush_interval_seconds=0.01,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        time.sleep(0.02)

        with patch.object(buffer_service, "_flush_batch") as mock_flush:
            mock_flush.side_effect = Exception("flush failed")
            buffer_service._maybe_time_based_flush()

        assert buffer_service.buffer_size == 1

    def test_flush_batch_exception(self):
        """_flush_batch异常处理"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)

        with patch("src.workers.tasks.get_session_local") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.return_value = mock_session
            mock_session.bulk_save_objects.side_effect = Exception("flush failed")

            with pytest.raises(Exception):
                buffer_service._flush_batch([mock_item])

            mock_session.rollback.assert_called_once()

    def test_close_reusable_session_exception(self):
        """关闭session异常处理"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )

        mock_session = MagicMock()
        mock_session.close.side_effect = Exception("close failed")
        buffer_service._reusable_session = mock_session

        with patch("src.workers.tasks.logger") as mock_logger:
            buffer_service.close_reusable_session()

            mock_logger.warning.assert_called_once()
            assert buffer_service._reusable_session is None

    def test_atexit_flush_exception(self):
        """atexit flush异常处理"""
        buffer_service = EvaluationBufferService(
            batch_size=10,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=False,
        )
        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        with patch.object(buffer_service, "flush") as mock_flush:
            mock_flush.side_effect = Exception("flush failed")

            with patch("src.workers.tasks.logger") as mock_logger:
                buffer_service._atexit_flush()

                mock_logger.error.assert_called_once()


class TestTaskBase:
    """_TaskBase任务基类测试"""

    def test_flush(self):
        """flush方法"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.buffer_service") as mock_buffer:
            task_base.flush()

            mock_buffer.flush.assert_called_once()

    def test_after_return_flush(self):
        """任务返回后flush"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.buffer_service") as mock_buffer:
            mock_buffer.buffer_size = 10
            task_base.after_return("SUCCESS", None, "task-1", [], {}, None)

            mock_buffer.flush.assert_called_once()

    def test_after_return_no_flush(self):
        """缓冲区为空时不flush"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.buffer_service") as mock_buffer:
            mock_buffer.buffer_size = 0
            task_base.after_return("SUCCESS", None, "task-1", [], {}, None)

            mock_buffer.flush.assert_not_called()

    def test_on_failure(self):
        """任务失败处理"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.logger") as mock_logger:
            task_base.on_failure(Exception("test error"), "task-1", [], {}, None)

            mock_logger.error.assert_called_once()

    def test_on_success(self):
        """任务成功处理"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.logger") as mock_logger:
            task_base.on_success({"status": "success"}, "task-1", [], {})

            mock_logger.debug.assert_called_once()

    def test_on_terminate(self):
        """任务终止处理"""
        task_base = _TaskBase()

        with patch("src.workers.tasks.buffer_service") as mock_buffer:
            with patch("src.workers.tasks.logger") as mock_logger:
                task_base.on_terminate()

                mock_logger.warning.assert_called_once()
                mock_buffer.flush.assert_called_once()


class TestHelperFunctions:
    """辅助函数测试"""

    def test_get_Task(self):
        """获取Task类"""
        Task = _get_Task()

        assert Task is not None

    def test_get_celery_app(self):
        """获取Celery应用"""
        app = _get_celery_app()

        assert app is not None

    def test_get_metrics(self):
        """获取metrics"""
        with patch("src.infra.monitoring.metrics.BUFFER_FLUSH_LATENCY"):
            with patch("src.infra.monitoring.metrics.BUFFER_SIZE"):
                with patch("src.infra.monitoring.metrics.EVALUATION_COUNTER"):
                    with patch("src.infra.monitoring.metrics.EVALUATION_ERRORS"):
                        with patch("src.infra.monitoring.metrics.EVALUATION_LATENCY"):
                            metrics = _get_metrics()

                            assert "BUFFER_FLUSH_LATENCY" in metrics
                            assert "BUFFER_SIZE" in metrics
                            assert "EVALUATION_COUNTER" in metrics
                            assert "EVALUATION_ERRORS" in metrics
                            assert "EVALUATION_LATENCY" in metrics

    def test_get_evaluation_engine(self):
        """获取评估引擎"""
        with patch("src.engine.EvaluationEngine") as mock_engine:
            with patch("src.domain.models.llm_factory.create_llm_client") as mock_create:
                mock_create.return_value = MagicMock()

                _get_evaluation_engine()

                mock_engine.assert_called_once()

    def test_result_to_model(self):
        """转换结果为模型"""
        from src.schemas.schemas import EvaluationStatus

        result = EvaluationResult(
            case_id="CASE_001",
            model_name="test-model",
            adapter_name="test-adapter",
            status=EvaluationStatus.PASSED,
            latency_ms=100.0,
            response=None,
        )

        model = _result_to_model(result)

        assert model.case_id == "CASE_001"
        assert model.model_name == "test-model"
        assert model.status == "passed"
        assert model.latency_ms == 100.0

    def test_register_task_test_mode(self):
        """测试模式下注册任务"""

        @_register_task()
        def test_task(self, data):
            return {"status": "success"}

        result = test_task.delay({"id": "1"})

        assert result.state == "SUCCESS"
        assert result.result == {"status": "success"}

    def test_register_task_apply_async(self):
        """测试模式下apply_async"""

        @_register_task()
        def test_task(self, data):
            return {"status": "success", "data": data}

        result = test_task.apply_async(args=({"id": "1"},))

        assert result.ready() is True
        assert result.get() == {"status": "success", "data": {"id": "1"}}


class TestBufferServiceAsyncFlush:
    """异步flush专项测试"""

    def test_async_flush_enabled(self):
        """验证异步flush模式可正常启用"""
        buffer_service = EvaluationBufferService(
            batch_size=5,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=True,
        )

        assert buffer_service._async_flush is True
        assert buffer_service._flush_thread is not None
        assert buffer_service._flush_thread.is_alive() is True

        buffer_service._closed = True
        buffer_service._flush_event.set()
        buffer_service._flush_thread.join(timeout=5)

    def test_async_flush_with_real_mock_objects(self):
        """验证异步flush使用包含_sa_instance_state属性的Mock对象"""
        from sqlalchemy.orm import InstanceState
        from unittest.mock import MagicMock, PropertyMock

        buffer_service = EvaluationBufferService(
            batch_size=5,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=True,
        )

        mock_instance_state = MagicMock(spec=InstanceState)
        mock_item = MagicMock(spec=EvaluationResultModel)
        type(mock_item)._sa_instance_state = PropertyMock(return_value=mock_instance_state)

        buffer_service.add(mock_item)

        with patch("src.workers.tasks.get_session_local") as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value.return_value = mock_session

            buffer_service.flush()

        buffer_service._closed = True
        buffer_service._flush_event.set()
        buffer_service._flush_thread.join(timeout=5)

    def test_async_flush_submits_to_background_thread(self):
        """验证flush提交到后台线程"""
        buffer_service = EvaluationBufferService(
            batch_size=5,
            adaptive_batch_size=False,
            priority_enabled=False,
            async_flush=True,
        )

        mock_item = MagicMock(spec=EvaluationResultModel)
        buffer_service.add(mock_item)

        with patch.object(buffer_service, "_submit_async_flush") as mock_submit:
            buffer_service.flush()

            mock_submit.assert_called_once()

        buffer_service._closed = True
        buffer_service._flush_event.set()
        buffer_service._flush_thread.join(timeout=5)
