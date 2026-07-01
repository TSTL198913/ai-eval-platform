"""
系统核心功能测试 - EvaluationEngine
测试目标：验证评估引擎的同步/异步调度、Payload校验、结果构建、异常处理等核心机制
覆盖场景：正常测试、边界值测试、异常测试、空值测试、参数组合测试
"""

import pytest

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.engine import EvaluationEngine
from src.exceptions import ContractValidationError, DomainLogicError, InfrastructureError
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from src.schemas.schemas import EvaluationResult, EvaluationStatus as EvaluationRecordStatus


class TestEvaluationEngineSync:
    """同步评估测试"""

    def test_run_with_actual_output(self):
        """已有actual_output时应直接评估"""
        @EvaluatorFactory.register("test_engine_sync_eval")
        class TestEngineSyncEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                actual = request.payload.get("actual_output", "")
                expected = request.payload.get("expected_output", "")
                score = 1.0 if actual == expected else 0.5
                return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, score=score)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_sync",
            type="test_engine_sync_eval",
            payload={
                "actual_output": "正确答案",
                "expected_output": "正确答案",
            },
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED
        assert result.response.score == 1.0
        assert result.response.is_valid is True

    def test_run_without_actual_output(self):
        """没有actual_output但有prompt时应调用LLM生成"""
        @EvaluatorFactory.register("test_engine_sync_no_output")
        class TestEngineSyncNoOutputEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, score=0.7)

        mock_client = type('MockClient', (), {
            'chat': lambda *args, **kwargs: '生成的响应',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_sync_no_output",
            type="test_engine_sync_no_output",
            payload={
                "prompt": "测试提示词",
                "expected_output": "期望输出",
            },
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED
        assert result.response.score == 0.7

    def test_run_with_invalid_payload(self):
        """无效payload应返回错误"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_invalid_payload",
            type="nonexistent_eval_type",
            payload={},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR

    def test_run_with_nonexistent_evaluator(self):
        """评估器不存在应返回错误"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_nonexistent",
            type="definitely_nonexistent_evaluator_xyz",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR

    def test_run_with_empty_payload(self):
        """空payload应返回错误"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_empty_payload",
            type="test",
            payload={},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR


class TestEvaluationEngineErrorHandling:
    """异常处理测试"""

    def test_run_with_contract_validation_error(self):
        """契约验证错误应正确处理"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        @EvaluatorFactory.register("test_engine_contract_error")
        class TestEngineContractErrorEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise ContractValidationError("契约验证失败")

        request = EvaluationSchema(
            id="test_engine_contract_error",
            type="test_engine_contract_error",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR
        assert result.adapter_name == "contract_validator"

    def test_run_with_domain_logic_error(self):
        """领域逻辑错误应正确处理"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        @EvaluatorFactory.register("test_engine_domain_error")
        class TestEngineDomainErrorEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise DomainLogicError("领域逻辑错误")

        request = EvaluationSchema(
            id="test_engine_domain_error",
            type="test_engine_domain_error",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR
        assert result.adapter_name == "domain_handler"

    def test_run_with_infrastructure_error(self):
        """基础设施错误应正确处理"""
        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        @EvaluatorFactory.register("test_engine_infra_error")
        class TestEngineInfraErrorEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise InfrastructureError("基础设施错误")

        request = EvaluationSchema(
            id="test_engine_infra_error",
            type="test_engine_infra_error",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR
        assert result.adapter_name == "infra_handler"

    def test_run_with_generic_exception(self):
        """通用异常应被safe_evaluate捕获并返回错误"""
        mock_client = type('MockClient', (), {
            'chat': lambda *args, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        @EvaluatorFactory.register("test_engine_generic_error")
        class TestEngineGenericErrorEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise ValueError("未知错误")

        request = EvaluationSchema(
            id="test_engine_generic_error",
            type="test_engine_generic_error",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR
        assert result.response.evaluation_status == EvaluatorStatus.ERROR


class TestEvaluationEngineResponseBuilding:
    """结果构建测试"""

    def test_build_result_with_success(self):
        """SUCCESS状态应转换为PASSED"""
        @EvaluatorFactory.register("test_engine_build_success")
        class TestEngineBuildSuccessEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, score=0.9)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_build_success",
            type="test_engine_build_success",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED

    def test_build_result_with_partial(self):
        """PARTIAL状态应转换为PASSED"""
        @EvaluatorFactory.register("test_engine_build_partial")
        class TestEngineBuildPartialEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.PARTIAL, score=0.7)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_build_partial",
            type="test_engine_build_partial",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED

    def test_build_result_with_error(self):
        """ERROR状态应转换为ERROR"""
        @EvaluatorFactory.register("test_engine_build_error")
        class TestEngineBuildErrorEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(
                    evaluation_status=EvaluatorStatus.ERROR,
                    error="测试错误",
                    metadata={"error_code": "TEST_ERROR"}
                )

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_build_error",
            type="test_engine_build_error",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR

    def test_build_result_with_cannot_evaluate(self):
        """CANNOT_EVALUATE状态应转换为ERROR"""
        @EvaluatorFactory.register("test_engine_build_cannot_eval")
        class TestEngineBuildCannotEvalEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.CANNOT_EVALUATE)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_build_cannot_eval",
            type="test_engine_build_cannot_eval",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.ERROR


class TestEvaluationEngineNormalization:
    """Payload标准化测试"""

    def test_normalize_code_payload(self):
        """code类型应正确标准化"""
        @EvaluatorFactory.register("test_engine_normalize_code")
        class TestEngineNormalizeCodeEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, score=0.8)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_normalize_code",
            type="test_engine_normalize_code",
            payload={
                "actual_output": "print('hello')",
                "language": "python",
            },
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED

    def test_normalize_non_code_payload(self):
        """非code类型不应改变"""
        @EvaluatorFactory.register("test_engine_normalize_non_code")
        class TestEngineNormalizeNonCodeEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(evaluation_status=EvaluatorStatus.SUCCESS, score=0.7)

        mock_client = type('MockClient', (), {
            'chat': lambda x, **kwargs: 'response',
            'config': type('Config', (), {'model_name': 'test-model'})()
        })()
        engine = EvaluationEngine(client=mock_client)

        request = EvaluationSchema(
            id="test_engine_normalize_non_code",
            type="test_engine_normalize_non_code",
            payload={"user_input": "test"},
        )

        result = engine.run(request)
        assert result.status == EvaluationRecordStatus.PASSED
