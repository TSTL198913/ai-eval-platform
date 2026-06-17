"""Celery任务测试"""
from unittest.mock import MagicMock, patch

import pytest


class MockEvaluationResultModel:
    """轻量级 Mock"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


from src.workers.tasks import WindowsUltimateSoloTask, buffer_service, eval_case_task


class TestWindowsUltimateSoloTask:
    """Celery任务基类测试"""

    def test_flush(self):
        """测试flush"""
        task = WindowsUltimateSoloTask()

        with patch.object(buffer_service, "flush", return_value=1) as mock_flush:
            result = task.flush()
            assert result == 1

    def test_after_return_with_buffer(self):
        """测试任务完成后flush"""
        task = WindowsUltimateSoloTask()

        buffer_service.buffer.append(MockEvaluationResultModel(case_id="c1", model_name="gpt-4"))

        with patch.object(buffer_service, "flush") as mock_flush:
            task.after_return("success", None, "task_id", [], {}, None)
            mock_flush.assert_called_once()

        buffer_service.buffer.clear()

    def test_after_return_empty_buffer(self):
        """测试空缓冲区不flush"""
        task = WindowsUltimateSoloTask()

        buffer_service.buffer.clear()

        with patch.object(buffer_service, "flush") as mock_flush:
            task.after_return("success", None, "task_id", [], {}, None)
            mock_flush.assert_not_called()

    def test_on_failure(self):
        """测试任务失败处理"""
        task = WindowsUltimateSoloTask()
        task.on_failure(Exception("test error"), "task_id", [], {}, None)

    def test_on_success(self):
        """测试任务成功处理"""
        task = WindowsUltimateSoloTask()
        task.on_success("result", "task_id", [], {})

    def test_on_terminate(self):
        """测试任务终止处理"""
        task = WindowsUltimateSoloTask()

        with patch.object(buffer_service, "flush") as mock_flush:
            task.on_terminate()
            mock_flush.assert_called_once()

    def test_on_terminate_error(self):
        """测试终止flush失败"""
        task = WindowsUltimateSoloTask()

        with patch.object(buffer_service, "flush", side_effect=Exception("flush error")):
            task.on_terminate()


class TestEvalCaseTask:
    """评估任务测试"""

    def test_eval_case_task_success(self, mock_llm):
        """测试评估任务成功执行"""
        with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
            mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
                case_id="test_001",
                model_name="mock",
                adapter_name="default",
                status=MagicMock(value="passed"),
                latency_ms=100,
                response=MagicMock(model_dump=MagicMock(return_value={})),
            )))

            result = eval_case_task.delay({
                "id": "test_task_001",
                "type": "general",
                "payload": {"user_input": "hello"},
            })

            assert result is not None
            assert result.id is not None

    def test_eval_case_task_with_buffer_flush(self, mock_llm):
        """测试任务触发buffer flush"""
        with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
            mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
                case_id="test_002",
                model_name="mock",
                adapter_name="default",
                status=MagicMock(value="passed"),
                latency_ms=100,
                response=MagicMock(model_dump=MagicMock(return_value={})),
            )))

            original_batch_size = buffer_service.batch_size
            buffer_service.batch_size = 1

            try:
                with patch.object(buffer_service, "flush") as mock_flush:
                    eval_case_task.delay({
                        "id": "test_task_002",
                        "type": "general",
                        "payload": {"user_input": "hello"},
                    })
            finally:
                buffer_service.batch_size = original_batch_size
                buffer_service.buffer.clear()

    def test_eval_case_task_error(self):
        """测试任务执行错误"""
        with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
            mock_engine.side_effect = Exception("Test error")

            with pytest.raises(Exception):
                eval_case_task.delay({
                    "id": "test_task_003",
                    "type": "general",
                    "payload": {"user_input": "hello"},
                })