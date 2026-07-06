"""
Phase 2 验证测试 - 模型冲突强制校验
覆盖: 评估前独立校验、llm_as_judge强制校验、OFFLINE模式冲突检测、环境变量控制
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


class TestPreEvaluationConflictValidation:
    """评估前独立校验测试"""

    def test_conflict_check_before_evaluation_offline_mode(self):
        """OFFLINE 模式下评估前也进行冲突检测"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_offline_conflict",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "provided output", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_called_once()
            assert "模型自我评估风险" in mock_warning.call_args[0][0]

        assert result.status == EvaluationStatus.PASSED

    def test_conflict_check_before_evaluation_online_mode(self):
        """ONLINE 模式下评估前进行冲突检测（生成后仍检测）"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"
        client.chat.return_value = "generated output"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_online_conflict",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.ONLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"prompt": "test prompt", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_called_once()

        assert result.status == EvaluationStatus.PASSED

    def test_no_conflict_check_for_non_conflict_types(self):
        """非冲突类型不进行模型冲突检测"""
        EvaluatorFactory.register("code")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_code_no_conflict",
            type="code",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "code", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_not_called()

        assert result.status == EvaluationStatus.PASSED


class TestLLMASJudgeEnforcedValidation:
    """llm_as_judge 强制校验测试"""

    def test_llm_as_judge_conflict_block_when_enabled(self):
        """llm_as_judge 模式下开启阻断策略时返回错误"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_llm_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.response.error == "MODEL_CONFLICT"

    def test_llm_as_judge_no_block_when_models_different(self):
        """llm_as_judge 模式下模型不同时不阻断"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"

        engine = EvaluationEngine(eval_client)
        request = EvaluationSchema(
            id="test_llm_no_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="openai",
            model_name="eval-model",
            inference_model_provider="deepseek",
            inference_model_name="inference-model",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.PASSED

    def test_general_type_conflict_block_when_enabled(self):
        """general 类型下开启阻断策略时返回错误"""
        EvaluatorFactory.register("general")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_general_block",
            type="general",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR
        assert result.response.error == "MODEL_CONFLICT"


class TestBlockingConfiguration:
    """阻断策略配置测试"""

    def test_blocking_disabled_by_default(self):
        """默认不阻断自我评估"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_default_no_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        result = engine.run(request)

        assert result.status == EvaluationStatus.PASSED

    def test_blocking_enabled_via_env_var(self):
        """通过环境变量开启阻断"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_env_block",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "true"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR

    def test_blocking_env_var_case_insensitive(self):
        """环境变量不区分大小写"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "deepseek-chat"

        engine = EvaluationEngine(client)
        request = EvaluationSchema(
            id="test_env_case",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="deepseek-chat",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch.dict(os.environ, {"BLOCK_SELF_EVALUATION": "TRUE"}):
            result = engine.run(request)

        assert result.status == EvaluationStatus.ERROR


class TestConflictDetectionWithDualClient:
    """双客户端配置下的冲突检测"""

    def test_dual_client_no_conflict(self):
        """双客户端配置下模型不同时不检测到冲突"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "eval-model"
        
        inference_client = MagicMock()
        inference_client.config = MagicMock()
        inference_client.config.model_name = "inference-model"

        engine = EvaluationEngine(eval_client, inference_client=inference_client)
        request = EvaluationSchema(
            id="test_dual_no_conflict",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="openai",
            model_name="eval-model",
            inference_model_provider="deepseek",
            inference_model_name="inference-model",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_not_called()

        assert result.status == EvaluationStatus.PASSED

    def test_dual_client_conflict_warning(self):
        """双客户端配置下模型相同时检测到冲突"""
        EvaluatorFactory.register("llm_as_judge")(MockPassingEvaluator)
        
        eval_client = MagicMock()
        eval_client.config = MagicMock()
        eval_client.config.model_name = "same-model"
        
        inference_client = MagicMock()
        inference_client.config = MagicMock()
        inference_client.config.model_name = "same-model"

        engine = EvaluationEngine(eval_client, inference_client=inference_client)
        request = EvaluationSchema(
            id="test_dual_conflict",
            type="llm_as_judge",
            evaluate_mode=EvaluationMode.OFFLINE,
            model_provider="deepseek",
            model_name="same-model",
            inference_model_provider="deepseek",
            inference_model_name="same-model",
            payload={"actual_output": "output", "expected_output": "expected"},
        )

        with patch("src.engine.logger.warning") as mock_warning:
            result = engine.run(request)
            mock_warning.assert_called_once()

        assert result.status == EvaluationStatus.PASSED