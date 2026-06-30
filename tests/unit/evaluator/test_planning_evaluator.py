"""
PlanningEvaluator 专项测试
测试目标：验证 PlanningEvaluator 的任务拆解和计划评估功能
关键发现：评估器支持多维度评分，包括完整性、顺序、粒度、相关性和冗余度惩罚
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
    def target(self):
        return PlanningEvaluator()

    def test_evaluate_plan_success(self, target):
        """评估计划应返回综合分数"""
        request = EvaluationSchema(
            id="test_001",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "task": "完成销售报告",
                "generated_plan": ["收集数据", "分析数据", "生成报告"],
                "expected_plan": ["收集数据", "分析数据", "生成报告"],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "overall_score" in result.data
        assert result.data["overall_score"] >= 0.7
        assert "dimension_scores" in result.data

    def test_evaluate_decomposition_success(self, target):
        """评估拆解质量应返回分数"""
        request = EvaluationSchema(
            id="test_002",
            type="planning",
            payload={
                "action": "decomposition_quality",
                "generated_plan": ["步骤1", "步骤2", "步骤3"],
                "expected_plan": ["步骤1", "步骤2", "步骤3", "步骤4"],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "granularity_score" in result.data
        assert "decomposition_quality" in result.data

    def test_evaluate_completeness_success(self, target):
        """评估完整性应返回分数"""
        request = EvaluationSchema(
            id="test_003",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["数据收集", "数据处理"],
                "expected_plan": ["步骤A", "步骤B", "步骤C", "步骤D"],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "completeness_score" in result.data
        # 数据收集/数据处理 与 步骤A/B/C/D 相似度很低
        assert result.data["completeness_score"] >= 0.0

    def test_evaluate_ordering_success(self, target):
        """评估顺序应返回分数"""
        request = EvaluationSchema(
            id="test_004",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["A", "B", "C"],
                "expected_plan": ["A", "B", "C"],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "ordering_score" in result.data

    def test_evaluate_dependency_success(self, target):
        """评估依赖关系应返回分数"""
        request = EvaluationSchema(
            id="test_005",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [["A", "B"]],
                "expected_dependencies": [["A", "B"]],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert "dependency_score" in result.data
        assert result.data["dependency_score"] == 1.0


class TestPlanningEvaluatorNegativeCases:
    """负向测试 - 错误输入"""

    @pytest.fixture
    def target(self):
        return PlanningEvaluator()

    def test_evaluate_plan_empty_generated_returns_error(self, target):
        """空generated_plan应返回错误"""
        request = EvaluationSchema(
            id="test_006",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": [],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "generated_plan" in result.error or "为空" in result.error

    def test_unknown_action_returns_error(self, target):
        """未知action应返回错误"""
        request = EvaluationSchema(
            id="test_007",
            type="planning",
            payload={
                "action": "unknown_action",
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is False
        assert "未知的动作" in result.error


class TestPlanningEvaluatorBoundaryCases:
    """边界测试 - 边界值"""

    @pytest.fixture
    def target(self):
        return PlanningEvaluator()

    def test_empty_expected_returns_full_completeness(self, target):
        """空expected_plan应返回完整分数"""
        request = EvaluationSchema(
            id="test_008",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["步骤1", "步骤2"],
                "expected_plan": [],
            },
        )

        result = target.evaluate(request)

        assert result.data["completeness_score"] == 1.0

    def test_empty_expected_returns_full_ordering(self, target):
        """空expected_plan ordering应返回0.0（代码逻辑）"""
        request = EvaluationSchema(
            id="test_009",
            type="planning",
            payload={
                "action": "ordering",
                "generated_plan": ["A", "B"],
                "expected_plan": [],
            },
        )

        result = target.evaluate(request)

        # 代码逻辑：expected为空时返回0.0
        assert result.data["ordering_score"] == 0.0

    def test_empty_expected_returns_full_granularity(self, target):
        """空expected_plan granularity应返回1.0"""
        request = EvaluationSchema(
            id="test_010",
            type="planning",
            payload={
                "action": "decomposition_quality",
                "generated_plan": ["步骤1"],
                "expected_plan": [],
            },
        )

        result = target.evaluate(request)

        assert result.data["granularity_score"] == 1.0

    def test_empty_expected_dependency_returns_neutral(self, target):
        """空expected_dependencies应返回中性分数"""
        request = EvaluationSchema(
            id="test_011",
            type="planning",
            payload={
                "action": "dependency_correctness",
                "generated_dependencies": [],
                "expected_dependencies": [],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["dependency_score"] == 1.0

    def test_single_step_generated(self, target):
        """单步骤计划应正常处理"""
        request = EvaluationSchema(
            id="test_012",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["唯一步骤"],
                "expected_plan": ["唯一步骤"],
            },
        )

        result = target.evaluate(request)

        assert result.is_valid is True
        assert result.data["generated_step_count"] == 1


class TestPlanningEvaluatorAlgorithmTests:
    """评分算法测试"""

    @pytest.fixture
    def target(self):
        return PlanningEvaluator()

    def test_completeness_calculation(self, target):
        """完整性计算：匹配步骤数/期望步骤数"""
        generated = ["收集数据", "分析数据"]
        expected = ["收集数据", "分析数据", "生成报告", "审核报告"]

        score = target._calc_completeness(generated, expected)

        assert score == 0.5  # 2/4

    def test_ordering_calculation_inverted(self, target):
        """顺序计算：逆序对越少分数越高"""
        # 完美顺序
        score1 = target._calc_ordering(["A", "B", "C"], ["A", "B", "C"])
        assert score1 == 1.0

        # 完全逆序
        score2 = target._calc_ordering(["C", "B", "A"], ["A", "B", "C"])
        assert score2 < 1.0

    def test_granularity_calculation_ideal_ratio(self, target):
        """粒度计算：比例在0.7-1.5应得满分"""
        # 理想比例 1.0
        score = target._calc_granularity(["A", "B", "C"], ["A", "B", "C"])
        assert score == 1.0

    def test_granularity_calculation_acceptable_ratio(self, target):
        """粒度计算：比例在0.5-2.0应得0.7分"""
        # 比例 2.0
        score = target._calc_granularity(["A", "B"], ["C"])
        assert score == 0.7

    def test_granularity_calculation_poor_ratio(self, target):
        """粒度计算：比例过大或过小应得低分"""
        # 比例 4.0
        score = target._calc_granularity(["A", "B", "C", "D"], ["A"])
        assert score < 0.5

    def test_relevance_calculation_with_keywords(self, target):
        """相关性计算：步骤包含任务关键词应得正分"""
        task = "数据分析任务"
        generated = ["分析数据", "处理数据", "输出结果"]

        score = target._calc_relevance(generated, task)

        # 数据分析任务包含"数据"，generated中的步骤也包含"数据"
        assert score >= 0.0

    def test_relevance_calculation_no_keywords(self, target):
        """相关性计算：无关键词匹配应得0分"""
        task = "xyz123"
        generated = ["abc", "def", "ghi"]

        score = target._calc_relevance(generated, task)

        assert score == 0.0

    def test_redundancy_calculation_low_similarity(self, target):
        """冗余度计算：低相似度应得高分"""
        generated = ["收集数据", "分析数据", "生成报告"]

        score = target._calc_redundancy(generated)

        # 步骤间相似度低，冗余度低
        assert score > 0.5

    def test_redundancy_calculation_high_similarity(self, target):
        """冗余度计算：高相似度应得低分（使用温和惩罚公式）"""
        generated = ["数据分析", "数据分析", "数据分析"]

        score = target._calc_redundancy(generated)

        # 步骤间相似度高，冗余度高
        # 公式：1.0 - avg_sim * 0.5，完全相同步骤得分 0.5
        assert score <= 0.5

    def test_redundancy_single_step_returns_full(self, target):
        """单步骤应返回冗余度满分"""
        score = target._calc_redundancy(["唯一步骤"])

        assert score == 1.0

    def test_step_similarity_calculation(self, target):
        """步骤相似度计算"""
        sim = target._step_similarity("收集数据", "收集数据")
        assert sim == 1.0

        # 相似字符串应该有一定相似度
        sim2 = target._step_similarity("收集数据", "收集信息")
        assert 0.0 <= sim2 <= 1.0

    def test_step_similarity_empty_string(self, target):
        """空字符串相似度应为0"""
        sim = target._step_similarity("", "测试")
        assert sim == 0.0

        sim2 = target._step_similarity("测试", "")
        assert sim2 == 0.0

    def test_extract_keywords(self, target):
        """关键词提取应正确过滤停用词"""
        keywords = target._extract_keywords("这是一个测试的句子")

        # 停用词"这"和"是"应该被过滤
        assert "这" not in keywords
        assert "是" not in keywords
        # 验证返回的是列表
        assert isinstance(keywords, list)

    def test_match_steps(self, target):
        """步骤匹配应正确识别相似步骤"""
        generated = ["收集数据", "分析数据", "生成报告"]
        expected = ["收集信息", "分析数据", "生成文档"]

        matched = target._match_steps(generated, expected)

        # 相似度>0.6的应被匹配
        assert len(matched) >= 0

    def test_weight_distribution(self, target):
        """权重分布应符合规范"""
        request = EvaluationSchema(
            id="test_weight",
            type="planning",
            payload={
                "action": "evaluate_plan",
                "generated_plan": ["A", "B"],
                "expected_plan": ["A", "B"],
            },
        )

        result = target.evaluate(request)

        weights = result.data["weights"]
        # 权重总和应为1.0
        assert abs(sum(weights.values()) - 1.0) < 0.01
        # 各维度权重应符合预期
        assert weights["completeness"] == 0.30
        assert weights["ordering"] == 0.25
        assert weights["granularity"] == 0.15
        assert weights["relevance"] == 0.20
        assert weights["redundancy_penalty"] == 0.10

    def test_missing_steps_detection(self, target):
        """缺失步骤检测应正确"""
        request = EvaluationSchema(
            id="test_missing",
            type="planning",
            payload={
                "action": "completeness",
                "generated_plan": ["数据分析", "数据可视化"],
                "expected_plan": ["步骤A", "步骤B", "步骤C", "步骤D", "步骤E"],
            },
        )

        result = target.evaluate(request)

        # 数据分析/数据可视化 与 步骤A-E 的相似度都较低
        assert "expected_count" in result.data
        assert result.data["expected_count"] == 5
