"""
Phase 0 验证测试 - 显式模式声明和模型冲突检测
覆盖: evaluate_mode默认行为、ONLINE模式推理、模型冲突警告
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
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


class TestEvaluateModeDefaults:
    """评估模式默认行为测试"""

    def test_default_evaluate_mode_is_offline(self):
        """默认 evaluate_mode 应为 OFFLINE"""
        request = EvaluationSchema(id="test_1", type="test_pass", payload={})
        assert request.evaluate_mode == EvaluationMode.OFFLINE
        assert request.evaluate_mode.value == "offline"

    def test_offline_mode_does_not_trigger_inference(self):
        """OFFLINE 模式不应触发推理"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_2",
            type="test_pass",
            payload={"actual_output": "test output", "expected_output": "expected"},
        )
        result = engine.run(request)

        client.chat.assert_not_called()
        assert result.status == EvaluationStatus.PASSED


class TestOnlineModeInference:
    """ONLINE 模式推理测试"""

    def test_online_mode_triggers_inference_when_no_actual_output(self):
        """ONLINE 模式且无 actual_output 时应触发推理"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_3",
            type="test_pass",
            evaluate_mode=EvaluationMode.ONLINE,
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )
        result = engine.run(request)

        client.chat.assert_called_once_with("test prompt")
        assert result.status == EvaluationStatus.PASSED

    def test_online_mode_skips_inference_when_actual_output_exists(self):
        """ONLINE 模式但已有 actual_output 时应跳过推理"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_4",
            type="test_pass",
            evaluate_mode=EvaluationMode.ONLINE,
            payload={"actual_output": "provided output", "expected_output": "expected"},
        )
        result = engine.run(request)

        client.chat.assert_not_called()
        assert result.status == EvaluationStatus.PASSED


class TestModelConflictDetection:
    """模型冲突检测测试"""

    def test_no_warning_when_models_different(self):
        """推理模型和评估模型不同时不应产生警告"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "eval-model"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_5",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="deepseek",
            model_name="eval-model",
            inference_model_provider="openai",
            inference_model_name="inference-model",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_not_called()

        assert result.status == EvaluationStatus.PASSED

    def test_warning_when_models_identical(self):
        """推理模型和评估模型相同时应产生警告"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_6",
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
            assert "deepseek:deepseek-chat" in mock_warning.call_args[0][0]

        assert result.status == EvaluationStatus.PASSED

    def test_no_warning_for_non_conflict_types(self):
        """非 llm_as_judge/general/qa 类型不应产生警告"""
        EvaluatorFactory.register("code")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_7",
            type="code",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_not_called()

        assert result.status == EvaluationStatus.PASSED


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_request_without_evaluate_mode_works(self):
        """不指定 evaluate_mode 的请求应正常工作"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request_dict = {"id": "test_8", "type": "test_pass", "payload": {"actual_output": "test"}}
        request = EvaluationSchema(**request_dict)
        result = engine.run(request)

        assert request.evaluate_mode == EvaluationMode.OFFLINE
        assert result.status == EvaluationStatus.PASSED

    def test_hybrid_mode_reserved_for_future(self):
        """HYBRID 模式目前行为同 OFFLINE（保留供未来使用）"""
        EvaluatorFactory.register("test_pass")(MockPassingEvaluator)
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "test-model"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_9",
            type="test_pass",
            evaluate_mode=EvaluationMode.HYBRID,
            payload={"actual_output": "test output"},
        )
        result = engine.run(request)

        client.chat.assert_not_called()
        assert result.status == EvaluationStatus.PASSED