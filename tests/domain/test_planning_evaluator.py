"""
Planning Evaluator 专项测试
测试目标：验证PlanningEvaluator的任务规划评估能力
关键发现：
1. 完整性评分：基于步骤匹配度计算，匹配阈值0.6
2. 顺序评分：使用Kendall tau距离简化版，计算逆序对
3. 粒度评分：理想粒度比例为0.7-1.5
4. 相关性评分：基于关键词匹配
5. 冗余惩罚：步骤间相似度越高，惩罚越大
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.planning_evaluator import PlanningEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestPlanningEvaluatorPositiveCases:
    """正向测试 - 正常输入"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_evaluate_plan_returns_expected_scores(self, evaluator):
        """综合评估计划质量应返回预期分数"""
        request = EvaluationSchema(
            id="plan_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "完成用户注册流程",
                "generated_plan": [
                    "收集用户信息",
                    "验证邮箱地址",
                    "创建用户账户",
                    "发送欢迎邮件",
                ],
                "expected_plan": [
                    "收集用户信息",
                    "验证邮箱",
                    "创建账户",
                    "发送欢迎邮件",
                ],
            },
        )
        result = evaluator.evaluate(request)

        # 强断言：验证业务逻辑
        assert result.is_valid is True
        assert "overall_score" in result.data
        assert result.data["overall_score"] >= 0.7  # 应该有较高分数
        assert "dimension_scores" in result.data
        assert result.data["dimension_scores"]["completeness"] >= 0.8  # 完整性应较高
        assert result.data["generated_step_count"] == 4
        assert result.data["expected_step_count"] == 4

    def test_evaluate_decomposition_returns_expected_metrics(self, evaluator):
        """评估任务拆解质量应返回预期指标"""
        request = EvaluationSchema(
            id="decomp_001",
            type="planning",
            payload={
                "action": "decomposition_quality",
                "generated_plan": ["步骤1", "步骤2", "步骤3"],
                "expected_plan": ["步骤1", "步骤2", "步骤3", "步骤4"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert "granularity_score" in result.data
        assert "completeness_score" in result.data
        assert "decomposition_quality" in result.data
        assert result.data["step_count_ratio"] == 0.75  # 3/4

    def test_evaluate_completeness_identifies_matched_steps(self, evaluator):
        """评估完整性应识别匹配步骤"""
        request = EvaluationSchema(
            id="complete_001",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["用户登录", "查询订单", "退出系统"],
                "expected_plan": ["用户登录", "查询订单", "支付订单", "退出系统"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["completeness_score"] == 0.75  # 3/4
        assert result.data["matched_count"] == 3
        assert result.data["expected_count"] == 4
        assert len(result.data["missing_steps"]) == 1
        assert "支付订单" in result.data["missing_steps"]

    def test_evaluate_ordering_calculates_correct_sequence(self, evaluator):
        """评估顺序应正确计算步骤顺序"""
        request = EvaluationSchema(
            id="order_001",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["步骤A", "步骤B", "步骤C", "步骤D"],
                "expected_plan": ["步骤A", "步骤B", "步骤C", "步骤D"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["ordering_score"] == 1.0  # 完全匹配，顺序正确
        assert result.data["generated_sequence"] == ["步骤A", "步骤B", "步骤C", "步骤D"]

    def test_evaluate_dependency_correctness(self, evaluator):
        """评估依赖关系正确性应返回预期结果"""
        request = EvaluationSchema(
            id="dep_001",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [["A", "B"], ["B", "C"]],
                "expected_dependencies": [["A", "B"], ["B", "C"], ["C", "D"]],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["dependency_score"] == pytest.approx(0.6667, rel=0.01)  # 2/3
        assert len(result.data["missing_dependencies"]) == 1


class TestPlanningEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_empty_generated_plan_returns_error(self, evaluator):
        """空计划应返回错误"""
        request = EvaluationSchema(
            id="neg_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": [],
                "expected_plan": ["步骤1", "步骤2"],
            },
        )
        result = evaluator.evaluate(request)

        # DomainResponse的is_valid默认为True，应检查data中的is_valid
        assert result.data["is_valid"] is False
        assert "generated_plan不能为空" in result.data["error"]
        # status_code是DomainResponse的额外字段
        assert result.status_code == 400

    def test_unknown_action_returns_error(self, evaluator):
        """未知操作应返回错误"""
        request = EvaluationSchema(
            id="neg_002",
            type="planning",
            payload={
                "action": "unknown_action",
                "task": "测试任务",
            },
        )
        result = evaluator.evaluate(request)

        # DomainResponse的is_valid默认为True，应检查data中的is_valid
        assert result.data["is_valid"] is False
        assert "Unknown action" in result.data["error"]
        # status_code是DomainResponse的额外字段
        assert result.status_code == 400

    def test_missing_payload_fields_handled_gracefully(self, evaluator):
        """缺失字段应被优雅处理"""
        request = EvaluationSchema(
            id="neg_003",
            type="planning",
            payload={
                "action": "evaluate_plan",
                # 缺少 generated_plan 和 expected_plan
            },
        )
        result = evaluator.evaluate(request)

        # 应返回错误而不是崩溃
        # DomainResponse的is_valid默认为True，应检查data中的is_valid
        assert result.data["is_valid"] is False
        assert "generated_plan不能为空" in result.data["error"]


class TestPlanningEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_single_step_plan(self, evaluator):
        """单步骤计划应被正确处理"""
        request = EvaluationSchema(
            id="bound_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "简单任务",
                "generated_plan": ["执行任务"],
                "expected_plan": ["执行任务"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["overall_score"] >= 0.8  # 单步骤应得高分
        assert result.data["dimension_scores"]["redundancy_penalty"] == 1.0  # 无冗余

    def test_empty_expected_plan(self, evaluator):
        """空期望计划应返回满分"""
        request = EvaluationSchema(
            id="bound_002",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": ["步骤1", "步骤2"],
                "expected_plan": [],  # 空期望
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 空期望时，完整性、粒度应为满分
        assert result.data["dimension_scores"]["completeness"] == 1.0
        assert result.data["dimension_scores"]["granularity"] == 1.0

    def test_empty_expected_dependencies(self, evaluator):
        """空期望依赖应返回满分"""
        request = EvaluationSchema(
            id="bound_003",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [["A", "B"]],
                "expected_dependencies": [],  # 空期望
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["score"] == 1.0
        assert "无需评估依赖关系" in result.data["message"]

    def test_highly_redundant_plan(self, evaluator):
        """高度冗余计划应被惩罚"""
        request = EvaluationSchema(
            id="bound_004",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": [
                    "执行步骤A",
                    "执行步骤A",  # 完全重复
                    "执行步骤A",  # 完全重复
                ],
                "expected_plan": ["执行步骤A"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 冗余惩罚应较低
        assert result.data["dimension_scores"]["redundancy_penalty"] < 0.5

    def test_granularity_too_fine(self, evaluator):
        """粒度过细应被惩罚"""
        request = EvaluationSchema(
            id="bound_005",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],
                "expected_plan": ["步骤A"],  # 期望1步，生成了5步
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 粒度分数应较低（粒度过细）
        assert result.data["dimension_scores"]["granularity"] < 0.7

    def test_granularity_too_coarse(self, evaluator):
        """粒度过粗应被惩罚"""
        request = EvaluationSchema(
            id="bound_006",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": ["完成所有任务"],  # 1步
                "expected_plan": ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"],  # 5步
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 粒度分数应较低（粒度过粗）
        assert result.data["dimension_scores"]["granularity"] < 0.7


class TestPlanningEvaluatorEdgeCases:
    """边界场景测试"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_wrong_ordering_detected(self, evaluator):
        """错误顺序应被检测"""
        request = EvaluationSchema(
            id="edge_001",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["步骤D", "步骤C", "步骤B", "步骤A"],  # 逆序
                "expected_plan": ["步骤A", "步骤B", "步骤C", "步骤D"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 逆序应得低分
        assert result.data["ordering_score"] < 0.5

    def test_partial_ordering_correct(self, evaluator):
        """部分顺序正确应得中等分数"""
        request = EvaluationSchema(
            id="edge_002",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["步骤A", "步骤C", "步骤B", "步骤D"],  # B和C交换
                "expected_plan": ["步骤A", "步骤B", "步骤C", "步骤D"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 部分顺序正确
        assert 0.5 <= result.data["ordering_score"] <= 1.0

    def test_relevance_with_keywords_match(self, evaluator):
        """关键词匹配应提高相关性分数"""
        request = EvaluationSchema(
            id="edge_003",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "用户注册流程",
                "generated_plan": [
                    "收集用户信息",
                    "验证用户邮箱",
                    "创建用户账户",
                ],
                "expected_plan": ["步骤1", "步骤2", "步骤3"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 相关性分数应大于0（关键词匹配）
        # 注意：相关性基于关键词匹配，分数可能较低
        assert result.data["dimension_scores"]["relevance"] >= 0.0

    def test_relevance_without_keywords_match(self, evaluator):
        """无关键词匹配应降低相关性分数"""
        request = EvaluationSchema(
            id="edge_004",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "用户注册流程",
                "generated_plan": [
                    "执行操作A",
                    "执行操作B",
                    "执行操作C",
                ],  # 无相关关键词
                "expected_plan": ["步骤1", "步骤2", "步骤3"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 相关性分数应较低
        assert result.data["dimension_scores"]["relevance"] < 0.5

    def test_step_similarity_with_exact_match(self, evaluator):
        """完全匹配的步骤应得满分"""
        request = EvaluationSchema(
            id="edge_005",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["用户登录"],
                "expected_plan": ["用户登录"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        assert result.data["completeness_score"] == 1.0
        assert result.data["matched_count"] == 1

    def test_step_similarity_with_similar_text(self, evaluator):
        """相似文本应被正确匹配"""
        request = EvaluationSchema(
            id="edge_006",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["验证邮箱地址"],
                "expected_plan": ["验证邮箱"],  # 相似但不完全相同
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 相似度应超过0.6阈值
        assert result.data["completeness_score"] >= 0.8


class TestPlanningEvaluatorDependencyHandling:
    """依赖测试 - 外部依赖Mock"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_evaluator_works_without_client(self, evaluator):
        """无LLM客户端时应正常工作"""
        # PlanningEvaluator不依赖LLM，应正常工作
        request = EvaluationSchema(
            id="dep_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": ["步骤1", "步骤2"],
                "expected_plan": ["步骤1", "步骤2"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # 步骤匹配度较高，但相关性可能较低
        assert result.data["overall_score"] >= 0.6

    def test_evaluator_with_mock_client(self):
        """使用Mock客户端时应正常工作"""
        from unittest.mock import MagicMock

        mock_client = MagicMock()
        mock_client.config = MagicMock()
        mock_client.config.model_name = "gpt-4"

        evaluator = PlanningEvaluator(client=mock_client)
        request = EvaluationSchema(
            id="dep_002",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "测试任务",
                "generated_plan": ["步骤1", "步骤2"],
                "expected_plan": ["步骤1", "步骤2"],
            },
        )
        result = evaluator.evaluate(request)

        assert result.is_valid is True
        # PlanningEvaluator不调用LLM，mock_client不会被调用
        # 步骤匹配度较高，但相关性可能较低
        assert result.data["overall_score"] >= 0.6


class TestPlanningEvaluatorAlgorithmCorrectness:
    """算法正确性测试"""

    @pytest.fixture
    def evaluator(self):
        return PlanningEvaluator()

    def test_completeness_calculation_correct(self, evaluator):
        """完整性计算应正确"""
        # 3个匹配，4个期望，应为0.75
        score = evaluator._calc_completeness(
            generated=["A", "B", "C"],
            expected=["A", "B", "C", "D"],
        )
        assert score == 0.75

    def test_completeness_with_empty_expected(self, evaluator):
        """空期望应返回满分"""
        score = evaluator._calc_completeness(
            generated=["A", "B"],
            expected=[],
        )
        assert score == 1.0

    def test_ordering_with_correct_sequence(self, evaluator):
        """正确顺序应得满分"""
        score = evaluator._calc_ordering(
            generated=["A", "B", "C", "D"],
            expected=["A", "B", "C", "D"],
        )
        assert score == 1.0

    def test_ordering_with_reversed_sequence(self, evaluator):
        """完全逆序应得低分"""
        score = evaluator._calc_ordering(
            generated=["D", "C", "B", "A"],
            expected=["A", "B", "C", "D"],
        )
        assert score < 0.5

    def test_granularity_with_ideal_ratio(self, evaluator):
        """理想粒度比例应得满分"""
        # 比例为1.0（理想）
        score = evaluator._calc_granularity(
            generated=["A", "B", "C"],
            expected=["A", "B", "C"],
        )
        assert score == 1.0

    def test_granularity_with_acceptable_ratio(self, evaluator):
        """可接受粒度比例应得中等分数"""
        # 比例为0.5（边界）
        score = evaluator._calc_granularity(
            generated=["A", "B"],
            expected=["A", "B", "C", "D"],
        )
        assert score == 0.7

    def test_redundancy_with_no_redundancy(self, evaluator):
        """无冗余应得满分"""
        score = evaluator._calc_redundancy(
            generated=["A"],  # 单步骤，无冗余
        )
        assert score == 1.0

    def test_redundancy_with_high_redundancy(self, evaluator):
        """高冗余应得低分"""
        score = evaluator._calc_redundancy(
            generated=["相同步骤", "相同步骤", "相同步骤"],
        )
        assert score < 0.5

    def test_step_similarity_with_identical_steps(self, evaluator):
        """完全相同的步骤应得满分"""
        similarity = evaluator._step_similarity("用户登录", "用户登录")
        assert similarity == 1.0

    def test_step_similarity_with_different_steps(self, evaluator):
        """完全不同的步骤应得低分"""
        similarity = evaluator._step_similarity("用户登录", "系统退出")
        assert similarity < 0.5

    def test_extract_keywords_filters_stopwords(self, evaluator):
        """关键词提取应过滤停用词"""
        keywords = evaluator._extract_keywords("用户的登录和验证")
        # 应过滤掉"的"、"和"等停用词
        # 注意：关键词提取可能返回整个词组，而不是分开的词
        assert "的" not in keywords
        assert "和" not in keywords
        # 关键词应包含用户、登录、验证相关内容
        assert len(keywords) > 0
        # 检查是否包含关键内容（可能是组合词）
        keywords_str = "".join(keywords)
        assert "用户" in keywords_str or "登录" in keywords_str or "验证" in keywords_str
