from src.domain.evaluators.standard_metric_evaluator import (
    SUPPORTED_METRICS,
    MultiMetricEvaluator,
    StandardMetricEvaluator,
)
from src.schemas.evaluation import EvaluationSchema


def make_request(type_name: str, payload: dict) -> EvaluationSchema:
    """辅助函数：构造评估请求"""
    # user_input/text 字段必须非空才能通过 validate_input
    if "user_input" not in payload:
        payload = {**payload, "user_input": "测试输入"}
    return EvaluationSchema(type=type_name, input="测试", payload=payload)


class TestStandardMetricEvaluatorPositiveCases:
    """正向测试"""

    def test_supported_metrics(self):
        """支持的指标集合"""
        expected = {
            "BLEU-4",
            "BLEU-2",
            "ROUGE-1",
            "ROUGE-2",
            "ROUGE-L",
            "F1-Token",
            "Levenshtein",
            "CosineSimilarity",
        }
        assert expected.issubset(SUPPORTED_METRICS.keys())

    def test_evaluate_with_bleu(self):
        """BLEU 评估"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "the cat is on the mat",
                "expected_output": "the cat is on the mat",
                "metric": "BLEU-4",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.99

    def test_evaluate_with_rouge(self):
        """ROUGE 评估"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "Paris is the capital of France",
                "expected_output": "Paris is the capital of France",
                "metric": "ROUGE-L",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score >= 0.99

    def test_evaluate_with_levenshtein(self):
        """Levenshtein 评估"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "hello",
                "expected_output": "hello",
                "metric": "Levenshtein",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0


class TestStandardMetricEvaluatorNegativeCases:
    """负向测试"""

    def test_unsupported_metric_returns_error(self):
        """不支持的指标应返回错误"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "text",
                "expected_output": "text",
                "metric": "UNKNOWN_METRIC",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False


class TestStandardMetricEvaluatorBoundaryCases:
    """边界测试"""

    def test_empty_inputs(self):
        """空输入 - 应返回验证错误而非崩溃"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "",
                "expected_output": "",
                "metric": "BLEU-4",
            },
        )
        result = evaluator.evaluate(request)
        # 空 expected_output 应触发 validate_expected 错误
        assert result.is_valid is False
        assert result.error is not None
        assert "expected_output" in result.error or "不能为空" in result.error

    def test_whitespace_only_expected(self):
        """纯空白 expected_output 应被拒绝"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "the cat",
                "expected_output": "   ",
                "metric": "Levenshtein",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
        assert result.error is not None

    def test_minimal_non_empty_inputs(self):
        """最小非空输入应正常评估"""
        evaluator = StandardMetricEvaluator()
        request = make_request(
            "standard_metric",
            {
                "actual_output": "a",
                "expected_output": "a",
                "metric": "Levenshtein",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.score == 1.0


class TestMultiMetricEvaluatorPositiveCases:
    """正向测试 - 多指标"""

    def test_evaluate_all_default(self):
        """默认全量计算"""
        evaluator = MultiMetricEvaluator()
        request = make_request(
            "multi_metric",
            {
                "actual_output": "Paris is the capital of France",
                "expected_output": "Paris is the capital of France",
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["metric_count"] > 0
        assert "composite_score" in result.data

    def test_evaluate_with_selected_metrics(self):
        """选择性指标"""
        evaluator = MultiMetricEvaluator()
        request = make_request(
            "multi_metric",
            {
                "actual_output": "the quick brown fox",
                "expected_output": "the quick brown fox",
                "metrics": ["BLEU-4", "ROUGE-L", "F1-Token"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        assert result.data["metric_count"] == 3


class TestMultiMetricEvaluatorNegativeCases:
    """负向测试 - 多指标"""

    def test_empty_metrics_list(self):
        """空指标列表"""
        evaluator = MultiMetricEvaluator()
        request = make_request(
            "multi_metric",
            {
                "actual_output": "text",
                "expected_output": "text",
                "metrics": [],
            },
        )
        result = evaluator.evaluate(request)
        # 空 metrics 参数应使用默认全部
        assert result.is_valid is True


class TestMetricResolution:
    """指标解析测试"""

    def test_resolve_known_metric(self):
        """已知指标解析"""
        metric = StandardMetricEvaluator._resolve_metric("BLEU-4")
        assert metric is not None
        assert metric.get_name() == "BLEU-4"

    def test_resolve_unknown_metric(self):
        """未知指标解析返回 None"""
        metric = StandardMetricEvaluator._resolve_metric("DOES_NOT_EXIST_XYZ")
        assert metric is None
