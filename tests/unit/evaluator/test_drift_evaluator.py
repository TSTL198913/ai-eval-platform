"""DriftDetectionEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from src.domain.evaluators.drift import DriftDetectionEvaluator
from src.schemas.evaluation import EvaluationSchema, EvaluatorStatus


class TestDriftDetectionEvaluatorPositiveCases:
    """正向测试用例"""

    def test_drift_detection_with_baseline(self):
        """有基线输出时应正确检测漂移"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "这是新的输出内容",
                "baseline_output": "这是旧的输出内容",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert 0 <= response.score <= 1.0
        assert "drift_detected" in response.data
        assert "drift_score" in response.data

    def test_no_drift_when_outputs_identical(self):
        """输出相同时不应检测到漂移"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_002",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "相同的输出内容",
                "baseline_output": "相同的输出内容",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.9
        assert response.data["drift_detected"] is False

    def test_drift_detected_when_outputs_different(self):
        """输出差异较大时应检测到漂移"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "完全不同的新输出内容",
                "baseline_output": "原始的基线输出内容",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score < 0.9
        assert "drift_detected" in response.data

    def test_statistical_detection_method(self):
        """统计检测方法应正确计算文本特征差异"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_004",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "简短输出",
                "baseline_output": "这是一个非常长的基线输出内容，包含很多文字",
                "methods": ["statistical"],
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "statistical" in response.data["methods"]
        assert response.data["methods"]["statistical"]["drift_score"] > 0

    def test_robust_mean_calculation(self):
        """截断均值应正确处理异常值"""
        evaluator = DriftDetectionEvaluator()
        data = [10.0, 0.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        result = evaluator._robust_mean(data, trim_ratio=0.2)
        
        expected_simple_mean = sum(data) / len(data)
        assert result == 0.5
        assert result != expected_simple_mean

    def test_semantic_drift_detection(self):
        """语义漂移检测应基于关键词重叠"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "苹果手机很受欢迎",
                "baseline_output": "苹果公司发布了新产品",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score > 0
        assert response.score < 1.0

    def test_behavioral_fingerprint(self):
        """行为指纹计算应包含文本哈希和统计特征"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "测试输出内容",
            },
        )
        response = evaluator._behavioral_fingerprint(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "current_fingerprint" in response.data


class TestDriftDetectionEvaluatorNegativeCases:
    """负向测试用例"""

    def test_missing_actual_output(self):
        """缺少实际输出应返回错误"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="drift",
            user_input="测试输入",
            payload={
                "baseline_output": "基线输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "actual_output" in response.error

    def test_empty_actual_output(self):
        """空实际输出应返回错误"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "",
                "baseline_output": "基线输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.ERROR

    def test_database_query_failure(self):
        """数据库查询失败时应降级处理"""
        evaluator = DriftDetectionEvaluator()
        evaluator.repository = MagicMock()
        evaluator.repository.get_recent.side_effect = Exception("数据库连接失败")
        
        request = EvaluationSchema(
            id="test_case_009",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "测试输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "score_comparison" in response.data["methods"]
        assert "数据库连接失败" in response.data["methods"]["score_comparison"]["message"]


class TestDriftDetectionEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_identical_long_texts(self):
        """完全相同的长文本不应检测到漂移"""
        long_text = "测试" * 1000
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": long_text,
                "baseline_output": long_text,
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.95
        assert response.data["drift_detected"] is False

    def test_max_drift_score(self):
        """完全不同的输出应返回较低的相似度分数"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "中文文本内容",
                "baseline_output": "English text content",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score <= 0.5

    def test_no_baseline_available(self):
        """无基线时仅使用相似度检测"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_012",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "测试输出",
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score > 0.95

    def test_custom_drift_threshold(self):
        """自定义漂移阈值应生效"""
        evaluator = DriftDetectionEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="drift",
            user_input="测试输入",
            payload={
                "actual_output": "略有不同的输出",
                "baseline_output": "原始输出内容",
                "threshold": 0.5,
            },
        )
        response = evaluator.safe_evaluate(request)
        
        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.data["threshold"] == 0.5

    def test_single_method_detection(self):
        """单一检测方法应正常工作"""
        evaluator = DriftDetectionEvaluator()
        for method in ["similarity", "score_comparison", "statistical"]:
            request = EvaluationSchema(
                id=f"test_case_014_{method}",
                type="drift",
                user_input="测试输入",
                payload={
                    "actual_output": "测试输出",
                    "baseline_output": "基线输出",
                    "methods": [method],
                },
            )
            response = evaluator.safe_evaluate(request)
            
            assert response.evaluation_status == EvaluatorStatus.SUCCESS
            assert method in response.data["methods"]


class TestDriftDetectionEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory
        
        assert "drift" in EvaluatorFactory.list_evaluators()

    def test_safe_evaluate_returns_error_on_exception(self):
        """异常时应返回错误响应"""
        evaluator = DriftDetectionEvaluator()
        
        with patch.object(evaluator, '_do_evaluate', side_effect=RuntimeError("测试异常")):
            request = EvaluationSchema(
            id="test_case_015",
            type="drift",
            user_input="测试输入",
                payload={"actual_output": "测试输出"},
            )
            response = evaluator.safe_evaluate(request)
            
            assert response.evaluation_status == EvaluatorStatus.ERROR