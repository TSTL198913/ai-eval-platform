"""延迟导入测试"""
import os
import sys

import pytest
from unittest.mock import MagicMock, patch


class TestDelayedImports:
    """延迟导入测试"""

    def test_get_metrics(self):
        """测试延迟获取metrics"""
        from src.workers.tasks import _get_metrics
        
        metrics = _get_metrics()
        assert "BUFFER_FLUSH_LATENCY" in metrics
        assert "BUFFER_SIZE" in metrics
        assert "EVALUATION_COUNTER" in metrics
        assert "EVALUATION_ERRORS" in metrics
        assert "EVALUATION_LATENCY" in metrics

    def test_get_Task(self):
        """测试延迟获取Task"""
        from src.workers.tasks import _get_Task
        
        Task = _get_Task()
        assert Task is not None

    def test_get_celery_app(self):
        """测试延迟获取celery_app"""
        from src.workers.tasks import _get_celery_app
        
        app = _get_celery_app()
        assert app is not None

    def test_metrics_are_singletons(self):
        """测试metrics是单例"""
        from src.workers.tasks import _get_metrics
        
        metrics1 = _get_metrics()
        metrics2 = _get_metrics()
        
        assert metrics1 is metrics2

    def test_Task_is_singleton(self):
        """测试Task是单例"""
        from src.workers.tasks import _get_Task
        
        Task1 = _get_Task()
        Task2 = _get_Task()
        
        assert Task1 is Task2

    def test_celery_app_is_singleton(self):
        """测试celery_app是单例"""
        from src.workers.tasks import _get_celery_app
        
        app1 = _get_celery_app()
        app2 = _get_celery_app()
        
        assert app1 is app2

    def test_get_evaluation_engine(self):
        """测试获取评估引擎"""
        from src.workers.tasks import _get_evaluation_engine
        
        engine = _get_evaluation_engine()
        assert engine is not None

    def test_get_evaluation_engine_with_client(self):
        """测试带客户端的评估引擎"""
        from src.workers.tasks import _get_evaluation_engine
        
        mock_client = MagicMock()
        engine = _get_evaluation_engine(mock_client)
        assert engine is not None


class TestEvalCaseTask:
    """评估任务测试"""

    def test_eval_case_task_with_metrics(self, mock_llm):
        """测试评估任务（非测试模式）"""
        from src.workers.tasks import eval_case_task
        
        with patch("src.workers.tasks.IS_TESTING", False):
            with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
                mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
                    case_id="test_001",
                    model_name="mock",
                    adapter_name="default",
                    status=MagicMock(value="passed"),
                    latency_ms=100,
                    response=MagicMock(model_dump=MagicMock(return_value={})),
                )))
                
                with patch("src.workers.tasks._get_metrics") as mock_get_metrics:
                    mock_metrics = {
                        "EVALUATION_LATENCY": MagicMock(),
                        "EVALUATION_COUNTER": MagicMock(),
                        "BUFFER_SIZE": MagicMock(),
                        "BUFFER_FLUSH_LATENCY": MagicMock(),
                    }
                    mock_get_metrics.return_value = mock_metrics
                    
                    result = eval_case_task.delay({
                        "id": "test_001",
                        "type": "general",
                        "payload": {"user_input": "hello"},
                    })
                    
                    assert result is not None
                    mock_metrics["EVALUATION_LATENCY"].labels.assert_called()
                    mock_metrics["EVALUATION_COUNTER"].labels.assert_called()
                    mock_metrics["BUFFER_SIZE"].set.assert_called()

    def test_eval_case_task_error(self, mock_llm):
        """测试评估任务错误处理"""
        from src.workers.tasks import eval_case_task
        
        with patch("src.workers.tasks.IS_TESTING", False):
            with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
                mock_engine.side_effect = Exception("Test error")
                
                with patch("src.workers.tasks._get_metrics") as mock_get_metrics:
                    mock_metrics = {
                        "EVALUATION_LATENCY": MagicMock(),
                        "EVALUATION_ERRORS": MagicMock(),
                    }
                    mock_get_metrics.return_value = mock_metrics
                    
                    with pytest.raises(Exception):
                        eval_case_task.delay({
                            "id": "test_002",
                            "type": "general",
                            "payload": {"user_input": "hello"},
                        })
                    
                    mock_metrics["EVALUATION_ERRORS"].labels.assert_called()

    def test_eval_case_task_buffer_flush(self, mock_llm):
        """测试任务添加到buffer（优化后flush逻辑变化）"""
        from src.workers.tasks import buffer_service
        
        original_batch_size = buffer_service.batch_size
        buffer_service.batch_size = 100  # 设置较大batch_size避免自动flush
        buffer_service.buffer.clear()
        
        try:
            with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
                mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
                    case_id="test_003",
                    model_name="mock",
                    adapter_name="default",
                    status=MagicMock(value="passed"),
                    latency_ms=100,
                    response=MagicMock(model_dump=MagicMock(return_value={})),
                )))
                
                with patch("src.workers.tasks.IS_TESTING", False):
                    with patch("src.workers.tasks._get_metrics") as mock_get_metrics:
                        mock_metrics = {
                            "BUFFER_FLUSH_LATENCY": MagicMock(),
                            "BUFFER_SIZE": MagicMock(),
                            "EVALUATION_LATENCY": MagicMock(),
                            "EVALUATION_COUNTER": MagicMock(),
                        }
                        mock_get_metrics.return_value = mock_metrics
                        
                        # 使用delay方法调用任务
                        from src.workers.tasks import eval_case_task
                        result = eval_case_task.delay({
                            "id": "test_003",
                            "type": "general",
                            "payload": {"user_input": "hello"},
                        })
                        
                        # 验证任务返回AsyncResult
                        assert result is not None
        finally:
            buffer_service.batch_size = original_batch_size
            buffer_service.buffer.clear()


class TestApplyAsync:
    """apply_async方法测试"""

    def test_apply_async(self, mock_llm):
        """测试apply_async方法"""
        from src.workers.tasks import eval_case_task
        
        with patch("src.workers.tasks._get_evaluation_engine") as mock_engine:
            mock_engine.return_value = MagicMock(run=MagicMock(return_value=MagicMock(
                case_id="test_apply",
                model_name="mock",
                adapter_name="default",
                status=MagicMock(value="passed"),
                latency_ms=100,
                response=MagicMock(model_dump=MagicMock(return_value={})),
            )))
            
            result = eval_case_task.apply_async(args=({"id": "test_apply", "type": "general", "payload": {"user_input": "hello"}},))
            
            assert result is not None
            assert result.id is not None