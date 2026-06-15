"""测试 workers/* 模块"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from src.workers.tasks import (
    EvaluationBufferService,
    WindowsUltimateSoloTask,
    buffer_service,
)


class TestEvaluationBufferService:
    """测试评测结果缓冲服务"""

    def test_initial_state(self):
        service = EvaluationBufferService()
        assert service.buffer == []
        assert service.batch_size == 1000
        assert service.last_flush_time is not None

    def test_add_item(self):
        service = EvaluationBufferService()
        mock_item = Mock()
        count = service.add(mock_item)
        assert count == 1
        assert len(service.buffer) == 1

    def test_add_multiple_items(self):
        service = EvaluationBufferService()
        for _i in range(5):
            service.add(Mock())
        assert len(service.buffer) == 5

    def test_thread_safety(self):
        service = EvaluationBufferService()
        counts = []

        def add_items():
            for _ in range(100):
                counts.append(service.add(Mock()))

        threads = [threading.Thread(target=add_items) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(service.buffer) == 500

    def test_flush_empty_buffer(self):
        service = EvaluationBufferService()
        mock_session = Mock()
        result = service.flush(db_session=mock_session)
        assert result is None

    def test_flush_with_items(self):
        service = EvaluationBufferService()
        for _ in range(5):
            service.add(Mock())

        mock_session = Mock()
        service.flush(db_session=mock_session)
        mock_session.bulk_save_objects.assert_called_once()
        mock_session.commit.assert_called_once()
        assert len(service.buffer) == 0

    def test_flush_rollback(self):
        service = EvaluationBufferService()
        for _ in range(5):
            service.add(Mock())

        mock_session = Mock()
        mock_session.bulk_save_objects.side_effect = Exception("DB error")
        mock_session.rollback = Mock()

        with pytest.raises(Exception):
            service.flush(db_session=mock_session)

        mock_session.rollback.assert_called_once()
        assert len(service.buffer) == 5

    def test_flush_external_session_not_closed(self):
        service = EvaluationBufferService()
        service.add(Mock())

        mock_session = Mock()
        service.flush(db_session=mock_session)
        mock_session.close.assert_not_called()

    def test_flush_internal_session_closed(self):
        service = EvaluationBufferService()
        service.add(Mock())

        with patch("src.workers.tasks.get_session_local") as mock_get_session_local:
            mock_session = Mock()
            mock_get_session_local.return_value = Mock(return_value=mock_session)
            service.flush()
            mock_session.close.assert_called_once()

    def test_flush_updates_timestamp(self):
        service = EvaluationBufferService()
        service.add(Mock())

        old_time = service.last_flush_time
        time.sleep(0.01)

        mock_session = Mock()
        service.flush(db_session=mock_session)
        assert service.last_flush_time > old_time


class TestWindowsUltimateSoloTask:
    """测试 Windows 终极独立任务"""

    def test_flush_method(self):
        task = WindowsUltimateSoloTask()
        mock_session = Mock()
        task.flush(db_session=mock_session)


class TestBufferServiceSingleton:
    """测试缓冲服务单例"""

    def test_singleton(self):
        assert buffer_service is not None
        assert isinstance(buffer_service, EvaluationBufferService)
