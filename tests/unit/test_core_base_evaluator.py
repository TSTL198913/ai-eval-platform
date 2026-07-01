"""
系统核心功能测试 - BaseEvaluator
测试目标：验证评估器基类的评估流程、熔断机制、降级策略、响应创建等核心机制
覆盖场景：正常测试、边界值测试、异常测试、空值测试、参数组合测试
"""

import pytest

from src.domain.evaluators.base import BaseEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


class TestEvaluatorResponseCreation:
    """响应创建测试"""

    def test_create_error_response(self):
        """创建错误响应应正确"""
        @EvaluatorFactory.register("test_error_response_eval")
        class TestErrorResponseEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestErrorResponseEvaluator()
        response = evaluator.create_error_response(
            error_message="测试错误",
            error_code="TEST_ERROR",
        )
        assert response.error == "测试错误"
        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert response.metadata.get("error_code") == "TEST_ERROR"
        assert response.confidence == 0.0
        assert response.score is None
        assert response.is_valid is False

    def test_create_success_response(self):
        """创建成功响应应正确"""
        @EvaluatorFactory.register("test_success_response_eval")
        class TestSuccessResponseEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestSuccessResponseEvaluator()
        response = evaluator.create_success_response(
            text="评估完成",
            score=0.85,
            data={"key": "value"},
        )
        assert response.text == "评估完成"
        assert response.score == 0.85
        assert response.data == {"key": "value"}
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.confidence == 0.95
        assert response.is_valid is True

    def test_create_partial_response(self):
        """创建部分评估响应应正确"""
        @EvaluatorFactory.register("test_partial_response_eval")
        class TestPartialResponseEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestPartialResponseEvaluator()
        response = evaluator.create_partial_response(
            text="部分评估",
            score=0.7,
            dimensions_evaluated=["accuracy"],
            dimensions_skipped=["fluency"],
            skip_reasons={"fluency": "LLM失败"},
            evaluation_method="embedding",
        )
        assert response.text == "部分评估"
        assert response.score == 0.7
        assert response.evaluation_status == EvaluatorStatus.PARTIAL
        assert response.data["dimensions_evaluated"] == ["accuracy"]
        assert response.data["dimensions_skipped"] == ["fluency"]
        assert response.data["skip_reasons"] == {"fluency": "LLM失败"}
        assert response.confidence == pytest.approx(0.55, abs=0.01)

    def test_create_cannot_evaluate_response(self):
        """创建无法评估响应应正确"""
        @EvaluatorFactory.register("test_cannot_eval_response_eval")
        class TestCannotEvalResponseEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestCannotEvalResponseEvaluator()
        response = evaluator.create_cannot_evaluate_response(
            reason="缺少必要输入",
            dimensions_skipped=["all"],
        )
        assert response.text == "无法评估: 缺少必要输入"
        assert response.score is None
        assert response.evaluation_status == EvaluatorStatus.CANNOT_EVALUATE
        assert response.data["dimensions_skipped"] == ["all"]


class TestEvaluatorInputValidation:
    """输入验证测试"""

    def test_validate_input_with_required_input(self):
        """require_input=True时应验证输入"""
        @EvaluatorFactory.register("test_validate_input_eval")
        class TestValidateInputEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestValidateInputEvaluator(require_input=True)
        request = EvaluationSchema(
            id="test_validate_input",
            type="test",
            payload={},
        )
        result = evaluator.validate_input(request)
        assert result is not None
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "不能为空" in result.error

    def test_validate_input_without_required_input(self):
        """require_input=False时不应验证输入"""
        @EvaluatorFactory.register("test_no_validate_input_eval")
        class TestNoValidateInputEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestNoValidateInputEvaluator(require_input=False)
        request = EvaluationSchema(
            id="test_no_validate_input",
            type="test",
            payload={},
        )
        result = evaluator.validate_input(request)
        assert result is None

    def test_validate_expected_with_required_expected(self):
        """require_expected=True时应验证期望输出"""
        @EvaluatorFactory.register("test_validate_expected_eval")
        class TestValidateExpectedEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestValidateExpectedEvaluator(require_expected=True)
        request = EvaluationSchema(
            id="test_validate_expected",
            type="test",
            payload={"user_input": "test"},
        )
        result = evaluator.validate_expected(request)
        assert result is not None
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "不能为空" in result.error

    def test_validate_expected_without_required_expected(self):
        """require_expected=False时不应验证期望输出"""
        @EvaluatorFactory.register("test_no_validate_expected_eval")
        class TestNoValidateExpectedEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestNoValidateExpectedEvaluator(require_expected=False)
        request = EvaluationSchema(
            id="test_no_validate_expected",
            type="test",
            payload={"user_input": "test"},
        )
        result = evaluator.validate_expected(request)
        assert result is None

    def test_require_client_with_error(self):
        """没有客户端时应返回错误"""
        @EvaluatorFactory.register("test_require_client_eval")
        class TestRequireClientEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestRequireClientEvaluator(client=None)
        result = evaluator.require_client_with_error()
        assert result is not None
        assert result.evaluation_status == EvaluatorStatus.ERROR
        assert "CLIENT_REQUIRED" in result.metadata.get("error_code", "")

    def test_require_client_success(self):
        """有客户端时应返回None"""
        @EvaluatorFactory.register("test_client_success_eval")
        class TestClientSuccessEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        mock_client = type('MockClient', (), {'chat': lambda x: 'response'})()
        evaluator = TestClientSuccessEvaluator(client=mock_client)
        result = evaluator.require_client_with_error()
        assert result is None


class TestEvaluatorScoreParsing:
    """评分解析测试"""

    def test_safe_parse_score_with_number(self):
        """解析包含数字的输出应正确"""
        @EvaluatorFactory.register("test_parse_score_eval")
        class TestParseScoreEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestParseScoreEvaluator()
        score = evaluator.safe_parse_score("评分: 0.85")
        assert score is not None
        assert 0.0 <= score <= 1.0

    def test_safe_parse_score_with_none(self):
        """解析无法提取数字的输出应返回None"""
        @EvaluatorFactory.register("test_parse_score_none_eval")
        class TestParseScoreNoneEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestParseScoreNoneEvaluator()
        score = evaluator.safe_parse_score("无法评估")
        assert score is None

    def test_safe_parse_category(self):
        """解析分类输出应正确"""
        @EvaluatorFactory.register("test_parse_category_eval")
        class TestParseCategoryEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestParseCategoryEvaluator()
        category = evaluator.safe_parse_category(
            "分类结果：positive",
            allowed_categories=["positive", "negative", "neutral"],
        )
        assert category == "positive"

    def test_safe_parse_category_not_found(self):
        """解析不在允许列表中的分类应返回None"""
        @EvaluatorFactory.register("test_parse_category_not_found_eval")
        class TestParseCategoryNotFoundEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestParseCategoryNotFoundEvaluator()
        category = evaluator.safe_parse_category(
            "分类结果：unknown",
            allowed_categories=["positive", "negative"],
        )
        assert category is None


class TestEvaluatorPayloadAccess:
    """Payload访问测试"""

    def test_get_payload_data(self):
        """获取payload数据应正确"""
        @EvaluatorFactory.register("test_get_payload_eval")
        class TestGetPayloadEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestGetPayloadEvaluator()
        request = EvaluationSchema(
            id="test_get_payload",
            type="test",
            payload={"key": "value", "number": 42},
        )
        assert evaluator.get_payload_data(request, "key") == "value"
        assert evaluator.get_payload_data(request, "number") == 42
        assert evaluator.get_payload_data(request, "missing", "default") == "default"

    def test_get_input_text(self):
        """获取输入文本应正确"""
        @EvaluatorFactory.register("test_get_input_eval")
        class TestGetInputEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True)

        evaluator = TestGetInputEvaluator()
        request1 = EvaluationSchema(
            id="test_get_input_1",
            type="test",
            payload={"user_input": "hello"},
        )
        assert evaluator.get_input_text(request1) == "hello"

        request2 = EvaluationSchema(
            id="test_get_input_2",
            type="test",
            payload={"text": "world"},
        )
        assert evaluator.get_input_text(request2) == "world"

        request3 = EvaluationSchema(
            id="test_get_input_3",
            type="test",
            payload={},
        )
        assert evaluator.get_input_text(request3) == ""


class TestEvaluatorSafeEvaluate:
    """安全评估测试"""

    def test_safe_evaluate_success(self):
        """安全评估成功应返回响应"""
        @EvaluatorFactory.register("test_safe_eval_success")
        class TestSafeEvalSuccessEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                return DomainResponse(is_valid=True, score=0.8)

        evaluator = TestSafeEvalSuccessEvaluator()
        request = EvaluationSchema(
            id="test_safe_eval",
            type="test",
            payload={"user_input": "test"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.is_valid is True
        assert response.score == 0.8

    def test_safe_evaluate_catches_exception(self):
        """安全评估应捕获非业务异常"""
        @EvaluatorFactory.register("test_safe_eval_exception")
        class TestSafeEvalExceptionEvaluator(BaseEvaluator):
            def _do_evaluate(self, request):
                raise RuntimeError("运行时错误")

        evaluator = TestSafeEvalExceptionEvaluator()
        request = EvaluationSchema(
            id="test_safe_eval_exception",
            type="test",
            payload={"user_input": "test"},
        )
        response = evaluator.safe_evaluate(request)
        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert response.error is not None


# Import here to avoid circular import
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
