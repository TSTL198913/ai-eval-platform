"""评分计算工具测试"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.domain.evaluators.scoring_utils import ScoreCalculator


class TestScoreCalculatorPositiveCases:
    """正向测试 - 正常评分计算"""

    def test_initial_score_default(self):
        """默认初始分数为1.0"""
        calculator = ScoreCalculator()
        assert calculator.score == 1.0

    def test_initial_score_custom(self):
        """自定义初始分数"""
        calculator = ScoreCalculator(initial_score=0.8)
        assert calculator.score == 0.8

    def test_deduct_reduces_score(self):
        """扣分操作"""
        calculator = ScoreCalculator(initial_score=1.0)
        calculator.deduct(0.3)
        assert calculator.score == 0.7

    def test_add_increases_score(self):
        """加分操作"""
        calculator = ScoreCalculator(initial_score=0.5)
        calculator.add(0.3)
        assert calculator.score == 0.8

    def test_get_score_returns_current(self):
        """获取当前分数"""
        calculator = ScoreCalculator(initial_score=0.9)
        assert calculator.get_score() == 0.9


class TestScoreCalculatorBoundaryCases:
    """边界测试"""

    def test_deduct_to_zero(self):
        """扣分到零"""
        calculator = ScoreCalculator(initial_score=0.5)
        calculator.deduct(1.0)
        assert calculator.score == 0.0

    def test_add_to_one(self):
        """加分到一"""
        calculator = ScoreCalculator(initial_score=0.9)
        calculator.add(0.5)
        assert calculator.score == 1.0

    def test_score_cannot_go_negative(self):
        """分数不能为负"""
        calculator = ScoreCalculator(initial_score=0.3)
        calculator.deduct(10.0)
        assert calculator.score == 0.0

    def test_score_cannot_exceed_one(self):
        """分数不能超过1"""
        calculator = ScoreCalculator(initial_score=0.9)
        calculator.add(10.0)
        assert calculator.score == 1.0

    def test_get_score_clamps_to_valid_range(self):
        """get_score限制在有效范围"""
        calculator = ScoreCalculator(initial_score=-0.5)
        assert calculator.get_score() == 0.0
        assert calculator.get_score() >= 0.0
        assert calculator.get_score() <= 1.0


class TestScoreCalculatorRiskLevel:
    """风险等级测试"""

    def test_high_risk_level(self):
        """低分对应高风险"""
        calculator = ScoreCalculator(initial_score=0.3)
        assert calculator.get_risk_level() == "high"

    def test_medium_risk_level(self):
        """中等分数对应中等风险"""
        calculator = ScoreCalculator(initial_score=0.6)
        assert calculator.get_risk_level() == "medium"

    def test_low_risk_level(self):
        """高分对应低风险"""
        calculator = ScoreCalculator(initial_score=0.9)
        assert calculator.get_risk_level() == "low"

    def test_boundary_low_risk(self):
        """边界值：0.8为低风险"""
        calculator = ScoreCalculator(initial_score=0.8)
        assert calculator.get_risk_level() == "low"

    def test_boundary_medium_risk(self):
        """边界值：0.5为中等风险"""
        calculator = ScoreCalculator(initial_score=0.5)
        assert calculator.get_risk_level() == "medium"

    def test_boundary_high_risk(self):
        """边界值：0.49为高风险"""
        calculator = ScoreCalculator(initial_score=0.49)
        assert calculator.get_risk_level() == "high"


class TestScoreCalculatorWeightedAverage:
    """加权平均计算测试"""

    def test_weighted_average_basic(self):
        """基本加权平均"""
        scores = {"a": 1.0, "b": 0.5}
        weights = {"a": 1.0, "b": 1.0}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        assert result == 0.75

    def test_weighted_average_with_different_weights(self):
        """不同权重的加权平均"""
        scores = {"a": 1.0, "b": 0.0}
        weights = {"a": 3.0, "b": 1.0}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        assert result == 0.75

    def test_weighted_average_empty_scores(self):
        """空分数返回1.0"""
        scores = {}
        weights = {}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        assert result == 1.0

    def test_weighted_average_partial_weights(self):
        """部分有权重的计算 - 其他key默认权重1.0"""
        scores = {"a": 1.0, "b": 0.5, "c": 0.0}
        weights = {"a": 1.0}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        # weighted = 1.0*1.0 + 0.5*1.0 + 0.0*1.0 = 1.5
        # total_weight = 1.0 + 1.0 + 1.0 = 3.0
        # result = 1.5 / 3.0 = 0.5
        assert result == 0.5

    def test_weighted_average_missing_weight_defaults_to_one(self):
        """缺失权重默认为1.0"""
        scores = {"a": 0.8, "b": 0.6}
        weights = {"a": 2.0}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        expected = (0.8 * 2.0 + 0.6 * 1.0) / (2.0 + 1.0)
        assert result == expected

    def test_weighted_average_all_zeros(self):
        """全零分数零权重"""
        scores = {"a": 0.0, "b": 0.0}
        weights = {"a": 0.0, "b": 0.0}
        result = ScoreCalculator.calculate_weighted_average(scores, weights)
        assert result == 1.0  # 除以0时返回1.0
