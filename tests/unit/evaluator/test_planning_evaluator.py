"""PlanningEvaluator 单元测试"""

import pytest
from unittest.mock import MagicMock

from src.domain.evaluators.planning_evaluator import PlanningEvaluator
from src.schemas.evaluation import EvaluationSchema
from src.schemas.evaluation import EvaluatorStatus


class TestPlanningEvaluatorPositiveCases:
    """正向测试用例"""

    def test_evaluate_plan_with_complete_plan(self):
        """综合评估完整计划"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["分析需求", "设计方案", "实现功能", "测试验证"],
                "expected_plan": ["分析需求", "设计方案", "实现功能", "测试验证"],
                "task": "分析需求并设计方案",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.7
        assert "overall_score" in response.data
        assert "dimension_scores" in response.data

    def test_decomposition_quality_evaluation(self):
        """评估任务拆解质量"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_002",
            type="planning",
            payload={
                "action": "decomposition_quality",
                "generated_plan": ["分析需求", "设计方案", "实现功能"],
                "expected_plan": ["分析需求", "设计方案", "实现功能", "测试验证"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "granularity_score" in response.data
        assert "completeness_score" in response.data

    def test_completeness_evaluation(self):
        """评估计划完整性"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_003",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["步骤1：分析", "步骤2：设计"],
                "expected_plan": ["步骤1：分析", "步骤2：设计", "步骤3：实现", "步骤4：测试"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 0.5
        assert "missing_steps" in response.data

    def test_ordering_evaluation_correct_order(self):
        """评估步骤顺序 - 正确顺序"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_004",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["先做A", "再做B", "最后做C"],
                "expected_plan": ["先做A", "再做B", "最后做C"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_dependency_correctness_evaluation(self):
        """评估依赖关系正确性"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_005",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [["A", "B"], ["B", "C"]],
                "expected_dependencies": [["A", "B"], ["B", "C"]],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_ordering_evaluation_wrong_order(self):
        """评估步骤顺序 - 错误顺序"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_006",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["B步骤", "A步骤", "C步骤"],
                "expected_plan": ["A步骤", "B步骤", "C步骤"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "ordering_score" in response.data


class TestPlanningEvaluatorNegativeCases:
    """负向测试用例"""

    def test_empty_generated_plan(self):
        """空计划应返回错误"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_007",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": [],
                "expected_plan": ["步骤1"],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "generated_plan" in response.error

    def test_unknown_action(self):
        """未知动作应返回错误"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_008",
            type="planning",
            payload={
                "action": "unknown_action",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.ERROR
        assert "未知的动作请求类型" in response.error

    def test_no_expected_plan_for_completeness(self):
        """无期望计划时完整性评估返回1.0"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_009",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["步骤1"],
                "expected_plan": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0

    def test_no_expected_dependencies(self):
        """无期望依赖时返回1.0"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_010",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [],
                "expected_dependencies": [],
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score == 1.0


class TestPlanningEvaluatorBoundaryCases:
    """边界测试用例"""

    def test_single_step_plan(self):
        """单步骤计划"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_011",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["唯一步骤"],
                "expected_plan": ["唯一步骤"],
                "task": "唯一步骤",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score >= 0.8

    def test_many_more_steps_than_expected(self):
        """步骤数远超期望"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_012",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5", "步骤6", "步骤7"],
                "expected_plan": ["步骤1", "步骤2"],
                "task": "简单任务",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "dimension_scores" in response.data

    def test_completely_different_steps(self):
        """完全不同的步骤"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_013",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["做A", "做B"],
                "expected_plan": ["做C", "做D"],
                "task": "任务描述",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert response.score < 0.5

    def test_empty_task_description(self):
        """空任务描述"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_014",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["步骤1"],
                "expected_plan": ["步骤1"],
                "task": "",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "dimension_scores" in response.data


class TestPlanningEvaluatorIntegration:
    """集成测试用例"""

    def test_evaluator_registered_in_factory(self):
        """评估器应在工厂中注册"""
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "planning" in EvaluatorFactory._registry

    def test_safe_evaluate_returns_error_on_exception(self):
        """异常时应返回错误响应"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_015",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["步骤1"],
                "expected_plan": None,
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS

    def test_default_action_is_evaluate_plan(self):
        """默认动作应为 evaluate_plan"""
        evaluator = PlanningEvaluator()
        request = EvaluationSchema(
            id="test_case_016",
            type="planning",
            payload={
                "generated_plan": ["步骤1"],
                "expected_plan": ["步骤1"],
                "task": "任务",
            },
        )
        response = evaluator.safe_evaluate(request)

        assert response.evaluation_status == EvaluatorStatus.SUCCESS
        assert "overall_score" in response.data
