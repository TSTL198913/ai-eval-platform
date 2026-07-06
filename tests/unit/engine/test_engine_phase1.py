"""
Phase 1 验证测试 - InferenceService 抽取与双模型配置
覆盖: InferenceService独立测试、双客户端配置、模型冲突阻断策略
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.services.inference_service import InferenceService
from src.engine import EvaluationEngine
from src.schemas.evaluation import EvaluationMode, EvaluationSchema
from src.schemas.schemas import EvaluationStatus


class MockPassingEvaluator(BaseEvaluator):
    """模拟通过的评估器"""

    def _do_evaluate(self, request):
        return self.create_success_response(text="good", score=0.95)


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试前重置注册表"""
    EvaluatorFactory._registry = {}
    yield
    EvaluatorFactory._registry = {}


class TestInferenceService:
    """推理服务独立测试"""

    def test_generate_sync(self):
        """同步生成应调用 client.chat"""
        client = MagicMock()
        client.chat.return_value = "generated output"
        
        service = InferenceService(client)
        result = service.generate("test prompt")
        
        assert result == "generated output"
        client.chat.assert_called_once_with("test prompt")

    def test_generate_async_with_achat(self):
        """异步生成优先使用 achat"""
        client = MagicMock()
        
        async def mock_achat(prompt):
            return "async generated output"
        
        client.achat = mock_achat
        
        service = InferenceService(client)
        
        import asyncio
        result = asyncio.run(service.generate_async("test prompt"))
        
        assert result == "async generated output"

    def test_generate_async_fallback_to_chat(self):
        """异步生成在无 achat 时回退到 to_thread"""
        client = MagicMock()
        del client.achat
        client.chat.return_value = "sync fallback output"
        
        service = InferenceService(client)
        
        import asyncio
        result = asyncio.run(service.generate_async("test prompt"))
        
        assert result == "sync fallback output"
        client.chat.assert_called_once_with("test prompt")

    def test_model_name_property(self):
        """model_name 属性应正确返回"""
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"
        
        service = InferenceService(client)
        assert service.model_name == "test-model"


class TestEngineDualClient:
    """双客户端配置测试"""

    def test_engine_with_different_inference_client(self):
        """使用不同的推理客户端和评估客户端"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"
        
        inference_client = MagicMock()
        inference_client.config = MagicMock()
        inference_client.config.model_name = "inference-model"
        inference_client.chat.return_value = "inferred output"

        engine = EvaluationEngine(eval_client, inference_client=inference_client)
        request = EvaluationSchema(
            id="test_dual",
            type="test_pass",
            evaluate_mode=EvaluationMode.ONLINE,
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )
        result = engine.run(request)

        inference_client.chat.assert_called_once()
        assert result.status == EvaluationStatus.PASSED

    def test_engine_fallback_to_eval_client_when_no_inference_client(self):
        """无推理客户端时回退到评估客户端"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"
        eval_client.chat.return_value = "eval output"

        engine = EvaluationEngine(eval_client)
        request = EvaluationSchema(
            id="test_fallback",
            type="test_pass",
            evaluate_mode=EvaluationMode.ONLINE,
            payload={"prompt": "test prompt"},
        )
        result = engine.run(request)

        eval_client.chat.assert_called_once()
        assert result.status == EvaluationStatus.PASSED

    def test_engine_with_inference_service(self):
        """使用自定义 InferenceService"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"
        
        inference_client = MagicMock()
        inference_client.config = MagicMock()
        inference_client.config.model_name = "inference-model"
        inference_client.chat.return_value = "service output"

        inference_service = InferenceService(inference_client)
        engine = EvaluationEngine(eval_client, inference_service=inference_service)
        request = EvaluationSchema(
            id="test_service",
            type="test_pass",
            evaluate_mode=EvaluationMode.ONLINE,
            payload={"prompt": "test prompt"},
        )
        result = engine.run(request)

        inference_client.chat.assert_called_once()
        assert result.status == EvaluationStatus.PASSED


class TestModelConflictBlocking:
    """模型冲突阻断策略测试"""

    def test_conflict_warning_only_when_block_disabled(self):
        """阻断策略关闭时仅输出警告"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_warning",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_called_once()
            assert "模型自我评估风险" in mock_warning.call_args[0][0]

        assert result.status == EvaluationStatus.PASSED

    def test_conflict_block_when_enabled(self):
        """阻断策略开启时返回错误"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.response.error == "MODEL_CONFLICT"

    def test_no_block_when_models_different(self):
        """推理模型和评估模型不同时不阻断"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"
        
        inference_client = MagicMock()
        inference_client.config = MagicMock()
        inference_client.config.model_name = "inference-model"
        inference_client.chat.return_value = "generated output"

        engine = EvaluationEngine(eval_client, inference_client=inference_client)
        request = EvaluationSchema(
            id="test_no_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="openai",
            model_name="eval-model",
            inference_model_provider="deepseek",
            inference_model_name="inference-model",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.PASSED