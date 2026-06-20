"""元测试评估器 - 使用系统自身的评估器评估测试代码"""

from typing import Any

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.scoring_utils import ScoreCalculator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("meta_test")
class MetaTestEvaluator(BaseEvaluator):
    """元测试评估器 - 使用系统自身的评估器评估测试代码"""

    # 元测试权重配置
    META_TEST_WEIGHTS = {
        "code_quality": 0.3,  # 代码质量权重
        "logic_quality": 0.4,  # 逻辑质量权重
        "drift_detection": 0.3,  # 漂移检测权重
    }

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        """评估测试代码质量"""
        test_code = self.get_payload_data(request, "test_code")
        test_results = self.get_payload_data(request, "test_results")
        baseline_results = self.get_payload_data(request, "baseline_results")

        if not test_code:
            return self.create_error_response(
                error_message="test_code 不能为空",
                error_code="INVALID_INPUT"
            )

        # 1. 评估测试代码质量
        code_quality = self._evaluate_code_quality(test_code)

        # 2. 评估测试逻辑合理性
        logic_quality = self._evaluate_logic_quality(test_code)

        # 3. 检测测试漂移
        drift_detection = self._detect_test_drift(test_results, baseline_results)

        # 4. 计算总体评分
        overall_score = self._calculate_overall_score(
            code_quality, logic_quality, drift_detection
        )

        # 5. 生成改进建议
        recommendations = self._generate_recommendations(
            code_quality, logic_quality, drift_detection
        )

        return self.create_success_response(
            text="元测试评估完成",
            score=overall_score,
            data={
                "code_quality": code_quality,
                "logic_quality": logic_quality,
                "drift_detection": drift_detection,
                "overall_score": overall_score,
                "recommendations": recommendations,
            }
        )

    def _evaluate_code_quality(self, test_code: str) -> dict:
        """评估测试代码质量"""
        calculator = ScoreCalculator(initial_score=1.0)

        # 评估维度
        dimensions = {
            "structure": self._check_structure(test_code),
            "naming": self._check_naming(test_code),
            "assertion": self._check_assertion_strength(test_code),
            "mock": self._check_mock_usage(test_code),
            "duplication": self._check_duplication(test_code),
            "readability": self._check_readability(test_code),
        }

        # 计算各项评分
        scores = {}
        for dimension, checks in dimensions.items():
            dimension_score = sum(checks.values()) / len(checks) if checks else 1.0
            scores[f"{dimension}_score"] = dimension_score

        # 计算总体评分
        overall_score = sum(scores.values()) / len(scores) if scores else 1.0
        scores["overall_score"] = overall_score

        return scores

    def _check_structure(self, test_code: str) -> dict:
        """检查测试代码结构"""
        checks = {}

        # 检查是否有测试类
        checks["has_test_class"] = "class Test" in test_code

        # 检查是否有fixture
        checks["has_fixture"] = "@pytest.fixture" in test_code or "fixture" in test_code

        # 检查是否有setup/teardown
        checks["has_setup"] = "setup" in test_code.lower() or "setUp" in test_code

        # 检查是否有文档字符串
        checks["has_docstring"] = '"""' in test_code or "'''" in test_code

        return checks

    def _check_naming(self, test_code: str) -> dict:
        """检查测试命名规范"""
        checks = {}

        # 检查是否有test_前缀
        checks["has_test_prefix"] = "def test_" in test_code

        # 检查命名是否描述性
        # 简单检查: 是否包含常见测试场景关键词
        descriptive_keywords = [
            "valid", "invalid", "empty", "null", "error",
            "success", "fail", "boundary", "edge", "exception"
        ]
        checks["has_descriptive_name"] = any(
            keyword in test_code.lower()
            for keyword in descriptive_keywords
        )

        return checks

    def _check_assertion_strength(self, test_code: str) -> dict:
        """检查断言强度"""
        checks = {}

        # 检查是否有强断言(验证具体值)
        strong_assertions = [
            "assert result.score",
            "assert result.data",
            "assert result == ",
            "assert result.is_valid",
        ]
        checks["has_strong_assertion"] = any(
            assertion in test_code
            for assertion in strong_assertions
        )

        # 检查是否有弱断言(仅验证状态)
        weak_assertions = ["assert result", "assert response"]
        checks["has_weak_assertion"] = any(
            assertion in test_code
            for assertion in weak_assertions
        ) and not checks["has_strong_assertion"]

        # 检查是否有多个断言
        checks["has_multiple_assertions"] = test_code.count("assert") >= 2

        return checks

    def _check_mock_usage(self, test_code: str) -> dict:
        """检查Mock使用"""
        checks = {}

        # 检查是否有Mock
        checks["has_mock"] = "Mock" in test_code or "mock" in test_code

        # 检查是否有return_value设置
        checks["has_return_value"] = "return_value" in test_code

        # 检查是否有side_effect设置
        checks["has_side_effect"] = "side_effect" in test_code

        # 检查是否有assert_called
        checks["has_assert_called"] = "assert_called" in test_code

        return checks

    def _check_duplication(self, test_code: str) -> dict:
        """检查代码重复"""
        checks = {}

        # 简单检查: 是否有重复的代码块
        lines = test_code.split('\n')
        unique_lines = set(line.strip() for line in lines if line.strip())

        # 重复率 = (总行数 - 唯一行数) / 总行数
        duplication_rate = (len(lines) - len(unique_lines)) / len(lines) if lines else 0
        checks["low_duplication"] = duplication_rate < 0.2

        return checks

    def _check_readability(self, test_code: str) -> dict:
        """检查可读性"""
        checks = {}

        # 检查是否有注释
        checks["has_comments"] = "#" in test_code

        # 检查是否有文档字符串
        checks["has_docstring"] = '"""' in test_code or "'''" in test_code

        # 检查代码长度(过长可能难以理解)
        lines = test_code.split('\n')
        checks["reasonable_length"] = len(lines) < 50

        return checks

    def _evaluate_logic_quality(self, test_code: str) -> dict:
        """评估测试逻辑合理性"""
        calculator = ScoreCalculator(initial_score=1.0)

        # 评估维度
        dimensions = {
            "scenario_coverage": self._check_scenario_coverage(test_code),
            "logic_correctness": self._check_logic_correctness(test_code),
            "test_independence": self._check_test_independence(test_code),
            "maintainability": self._check_maintainability(test_code),
            "effectiveness": self._check_effectiveness(test_code),
        }

        # 计算各项评分
        scores = {}
        for dimension, checks in dimensions.items():
            dimension_score = sum(checks.values()) / len(checks) if checks else 1.0
            scores[dimension] = dimension_score

        # 计算总体评分
        overall_score = sum(scores.values()) / len(scores) if scores else 1.0
        scores["overall_score"] = overall_score

        return scores

    def _check_scenario_coverage(self, test_code: str) -> dict:
        """检查测试场景覆盖"""
        checks = {}

        # 检查是否有正向测试
        positive_keywords = ["valid", "success", "correct", "normal"]
        checks["has_positive_test"] = any(
            keyword in test_code.lower()
            for keyword in positive_keywords
        )

        # 检查是否有负向测试
        negative_keywords = ["invalid", "error", "fail", "wrong"]
        checks["has_negative_test"] = any(
            keyword in test_code.lower()
            for keyword in negative_keywords
        )

        # 检查是否有边界测试
        boundary_keywords = ["boundary", "edge", "limit", "empty", "null"]
        checks["has_boundary_test"] = any(
            keyword in test_code.lower()
            for keyword in boundary_keywords
        )

        return checks

    def _check_logic_correctness(self, test_code: str) -> dict:
        """检查测试逻辑正确性"""
        checks = {}

        # 检查是否有Arrange-Act-Assert模式
        checks["has_aaa_pattern"] = (
            "arrange" in test_code.lower() or
            "act" in test_code.lower() or
            "assert" in test_code.lower()
        )

        # 检查是否有清晰的测试步骤
        checks["has_clear_steps"] = test_code.count("assert") >= 1

        return checks

    def _check_test_independence(self, test_code: str) -> dict:
        """检查测试独立性"""
        checks = {}

        # 检查是否有fixture管理状态
        checks["has_fixture"] = "@pytest.fixture" in test_code

        # 检查是否有全局状态共享(不推荐)
        checks["no_global_state"] = "global" not in test_code.lower()

        # 检查是否有autouse清理
        checks["has_cleanup"] = "autouse" in test_code or "cleanup" in test_code.lower()

        return checks

    def _check_maintainability(self, test_code: str) -> dict:
        """检查可维护性"""
        checks = {}

        # 检查是否有参数化测试
        checks["has_parametrize"] = "@pytest.mark.parametrize" in test_code

        # 检查是否有fixture复用
        checks["has_fixture_reuse"] = "fixture" in test_code

        # 检查代码长度(过长难以维护)
        lines = test_code.split('\n')
        checks["reasonable_length"] = len(lines) < 100

        return checks

    def _check_effectiveness(self, test_code: str) -> dict:
        """检查测试有效性"""
        checks = {}

        # 检查是否有业务逻辑验证
        business_keywords = ["score", "data", "result", "output"]
        checks["has_business_logic_check"] = any(
            keyword in test_code
            for keyword in business_keywords
        )

        # 检查是否有错误处理验证
        checks["has_error_handling"] = "error" in test_code.lower() or "exception" in test_code.lower()

        return checks

    def _detect_test_drift(
        self,
        test_results: dict | None,
        baseline_results: dict | None
    ) -> dict:
        """检测测试漂移"""
        if not test_results or not baseline_results:
            return {
                "behavior_drift": False,
                "result_drift": False,
                "coverage_drift": 0.0,
                "performance_drift": 0.0,
                "dependency_drift": False,
                "overall_drift_score": 1.0,
            }

        drift_detection = {}

        # 检测行为漂移(测试通过率变化)
        current_pass_rate = test_results.get("pass_rate", 1.0)
        baseline_pass_rate = baseline_results.get("pass_rate", 1.0)
        drift_detection["behavior_drift"] = abs(current_pass_rate - baseline_pass_rate) > 0.05

        # 检测结果漂移(测试结果变化)
        current_results = test_results.get("results", [])
        baseline_results_list = baseline_results.get("results", [])
        drift_detection["result_drift"] = current_results != baseline_results_list

        # 检测覆盖率漂移
        current_coverage = test_results.get("coverage", 0.0)
        baseline_coverage = baseline_results.get("coverage", 0.0)
        drift_detection["coverage_drift"] = current_coverage - baseline_coverage

        # 检测性能漂移(执行时间变化)
        current_duration = test_results.get("duration", 0.0)
        baseline_duration = baseline_results.get("duration", 0.0)
        drift_detection["performance_drift"] = (
            (current_duration - baseline_duration) / baseline_duration
            if baseline_duration > 0 else 0.0
        )

        # 检测依赖漂移(依赖版本变化)
        current_dependencies = test_results.get("dependencies", {})
        baseline_dependencies = baseline_results.get("dependencies", {})
        drift_detection["dependency_drift"] = current_dependencies != baseline_dependencies

        # 计算总体漂移评分
        drift_score = 1.0
        if drift_detection["behavior_drift"]:
            drift_score -= 0.2
        if drift_detection["result_drift"]:
            drift_score -= 0.2
        if abs(drift_detection["coverage_drift"]) > 0.05:
            drift_score -= 0.2
        if abs(drift_detection["performance_drift"]) > 0.1:
            drift_score -= 0.2
        if drift_detection["dependency_drift"]:
            drift_score -= 0.2

        drift_detection["overall_drift_score"] = max(0.0, drift_score)

        return drift_detection

    def _calculate_overall_score(
        self,
        code_quality: dict,
        logic_quality: dict,
        drift_detection: dict
    ) -> float:
        """计算元测试总体评分"""
        # 使用加权平均
        overall_score = ScoreCalculator.calculate_weighted_average(
            {
                "code_quality": code_quality.get("overall_score", 1.0),
                "logic_quality": logic_quality.get("overall_score", 1.0),
                "drift_detection": drift_detection.get("overall_drift_score", 1.0),
            },
            self.META_TEST_WEIGHTS
        )

        return overall_score

    def _generate_recommendations(
        self,
        code_quality: dict,
        logic_quality: dict,
        drift_detection: dict
    ) -> list[str]:
        """生成测试改进建议"""
        recommendations = []

        # 代码质量建议
        if code_quality.get("assertion_score", 1.0) < 0.8:
            recommendations.append("建议增强断言强度，验证业务逻辑而非仅状态")

        if code_quality.get("duplication_score", 1.0) < 0.8:
            recommendations.append("建议抽取公共测试方法，减少代码重复")

        if code_quality.get("mock_score", 1.0) < 0.8:
            recommendations.append("建议正确配置Mock，设置return_value和side_effect")

        # 逻辑质量建议
        if logic_quality.get("scenario_coverage", 1.0) < 0.8:
            recommendations.append("建议补充边界测试和异常测试场景")

        if logic_quality.get("test_independence", 1.0) < 0.8:
            recommendations.append("建议使用fixture管理共享状态，确保测试独立")

        if logic_quality.get("effectiveness", 1.0) < 0.8:
            recommendations.append("建议验证业务逻辑而非仅验证返回值")

        # 漂移检测建议
        if drift_detection.get("coverage_drift", 0) < -0.05:
            recommendations.append("建议补充缺失的测试用例，恢复测试覆盖率")

        if drift_detection.get("performance_drift", 0) > 0.1:
            recommendations.append("建议优化测试性能，减少执行时间")

        if drift_detection.get("behavior_drift", False):
            recommendations.append("建议检查测试通过率下降原因，修复失败测试")

        return recommendations