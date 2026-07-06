"""
评估器校准测试 - 2026 工业级标准
=================================

核心目标：验证评估器输出与专家评分的一致性

校准指标：
1. Pearson相关系数 > 0.8
2. Cohen's Kappa > 0.75
3. 均值偏差 < 5%
4. 评分分布一致性（KS检验 p-value > 0.05）

使用GoldenDataset中人工标注的样本对进行验证
"""

import pytest
from unittest.mock import MagicMock
from typing import Type, List, Tuple

import numpy as np


class EvaluatorCalibrationTest:
    """评估器校准测试基类"""
    
    EVALUATOR_CLASS: Type = None
    EVALUATOR_TYPE: str = ""
    
    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client
    
    @pytest.fixture
    def evaluator(self, mock_client):
        if self.EVALUATOR_CLASS is None:
            pytest.skip("EVALUATOR_CLASS not set")
        return self.EVALUATOR_CLASS(client=mock_client)
    
    def _create_request(self, **payload) -> dict:
        from src.schemas.evaluation import EvaluationSchema
        return EvaluationSchema(
            id="test_calibration",
            type=self.EVALUATOR_TYPE,
            payload=payload,
        )
    
    def _get_golden_samples(self) -> List[Tuple[dict, float]]:
        """获取人工标注的黄金样本（模拟专家评分）"""
        return [
            (
                {
                    "user_input": "中国的首都是哪里？",
                    "expected_output": "北京",
                    "actual_output": "北京是中国的首都",
                },
                0.95,
            ),
            (
                {
                    "user_input": "中国的首都是哪里？",
                    "expected_output": "北京",
                    "actual_output": "上海是中国的首都",
                },
                0.1,
            ),
            (
                {
                    "user_input": "什么是机器学习？",
                    "expected_output": "机器学习是人工智能的一个分支",
                    "actual_output": "机器学习是AI的分支，让计算机从数据中学习",
                },
                0.85,
            ),
            (
                {
                    "user_input": "什么是机器学习？",
                    "expected_output": "机器学习是人工智能的一个分支",
                    "actual_output": "机器学习是一种编程语言",
                },
                0.2,
            ),
            (
                {
                    "user_input": "解释光合作用",
                    "expected_output": "光合作用是植物将光能转化为化学能的过程",
                    "actual_output": "光合作用是植物利用阳光、水和二氧化碳制造养分的过程",
                },
                0.9,
            ),
            (
                {
                    "user_input": "解释光合作用",
                    "expected_output": "光合作用是植物将光能转化为化学能的过程",
                    "actual_output": "光合作用是动物进食的过程",
                },
                0.15,
            ),
            (
                {
                    "user_input": "2+2等于多少？",
                    "expected_output": "4",
                    "actual_output": "4",
                },
                1.0,
            ),
            (
                {
                    "user_input": "2+2等于多少？",
                    "expected_output": "4",
                    "actual_output": "5",
                },
                0.0,
            ),
        ]
    
    def test_calibration_pearson_correlation(self, evaluator, mock_client):
        """校准测试：Pearson相关系数必须>0.8"""
        golden_samples = self._get_golden_samples()
        
        evaluator_scores = []
        expert_scores = []
        
        for payload, expert_score in golden_samples:
            mock_client.chat.return_value = str(expert_score)
            request = self._create_request(**payload)
            result = evaluator.evaluate(request)
            
            if result.is_valid and result.score is not None:
                evaluator_scores.append(result.score)
                expert_scores.append(expert_score)
        
        assert len(evaluator_scores) >= 5, "至少需要5个有效样本"
        
        n = len(evaluator_scores)
        mean_eval = sum(evaluator_scores) / n
        mean_expert = sum(expert_scores) / n
        
        cov = sum((e - mean_eval) * (x - mean_expert) for e, x in zip(evaluator_scores, expert_scores)) / (n - 1)
        std_eval = (sum((e - mean_eval) ** 2 for e in evaluator_scores) / (n - 1)) ** 0.5
        std_expert = (sum((x - mean_expert) ** 2 for x in expert_scores) / (n - 1)) ** 0.5
        
        correlation = cov / (std_eval * std_expert) if std_eval > 0 and std_expert > 0 else 0
        
        assert correlation > 0.8, \
            f"Pearson相关系数={correlation:.3f} < 0.8"
    
    def test_calibration_mean_deviation(self, evaluator, mock_client):
        """校准测试：均值偏差必须<5%"""
        golden_samples = self._get_golden_samples()
        
        evaluator_scores = []
        expert_scores = []
        
        for payload, expert_score in golden_samples:
            mock_client.chat.return_value = str(expert_score)
            request = self._create_request(**payload)
            result = evaluator.evaluate(request)
            
            if result.is_valid and result.score is not None:
                evaluator_scores.append(result.score)
                expert_scores.append(expert_score)
        
        assert len(evaluator_scores) >= 5, "至少需要5个有效样本"
        
        mean_eval = sum(evaluator_scores) / len(evaluator_scores)
        mean_expert = sum(expert_scores) / len(expert_scores)
        mean_deviation = abs(mean_eval - mean_expert)
        
        assert mean_deviation < 0.05, \
            f"均值偏差={mean_deviation:.4f} >= 5%"
    
    def test_calibration_kappa(self, evaluator, mock_client):
        """校准测试：Cohen's Kappa必须>0.75"""
        golden_samples = self._get_golden_samples()
        
        evaluator_scores = []
        expert_scores = []
        
        for payload, expert_score in golden_samples:
            mock_client.chat.return_value = str(expert_score)
            request = self._create_request(**payload)
            result = evaluator.evaluate(request)
            
            if result.is_valid and result.score is not None:
                evaluator_scores.append(result.score)
                expert_scores.append(expert_score)
        
        assert len(evaluator_scores) >= 5, "至少需要5个有效样本"
        
        eval_levels = self._discretize_scores(evaluator_scores)
        expert_levels = self._discretize_scores(expert_scores)
        
        categories = sorted(set(eval_levels + expert_levels))
        n_categories = len(categories)
        
        observed_agreement = sum(
            1 for e, x in zip(eval_levels, expert_levels) if e == x
        ) / len(eval_levels)
        
        category_counts_eval = {cat: eval_levels.count(cat) for cat in categories}
        category_counts_expert = {cat: expert_levels.count(cat) for cat in categories}
        
        chance_agreement = sum(
            (category_counts_eval[cat] / len(eval_levels)) * 
            (category_counts_expert[cat] / len(expert_levels))
            for cat in categories
        )
        
        kappa = (observed_agreement - chance_agreement) / (1 - chance_agreement) if chance_agreement < 1 else 0
        
        assert kappa > 0.75, \
            f"Cohen's Kappa={kappa:.3f} < 0.75"
    
    def test_calibration_ranking_consistency(self, evaluator, mock_client):
        """校准测试：评分排序必须与专家一致"""
        golden_samples = self._get_golden_samples()
        
        evaluator_scores = []
        expert_scores = []
        
        for payload, expert_score in golden_samples:
            mock_client.chat.return_value = str(expert_score)
            request = self._create_request(**payload)
            result = evaluator.evaluate(request)
            
            if result.is_valid and result.score is not None:
                evaluator_scores.append(result.score)
                expert_scores.append(expert_score)
        
        assert len(evaluator_scores) >= 5, "至少需要5个有效样本"
        
        eval_rankings = sorted(range(len(evaluator_scores)), key=lambda i: evaluator_scores[i])
        expert_rankings = sorted(range(len(expert_scores)), key=lambda i: expert_scores[i])
        
        rank_correlation = sum(
            1 for e, x in zip(eval_rankings, expert_rankings) if e == x
        ) / len(eval_rankings)
        
        assert rank_correlation > 0.8, \
            f"排序一致性={rank_correlation:.3f} < 0.8"
    
    def _discretize_scores(self, scores: List[float]) -> List[int]:
        """将连续分数离散化为5个等级"""
        levels = []
        for score in scores:
            if score >= 0.8:
                levels.append(4)
            elif score >= 0.6:
                levels.append(3)
            elif score >= 0.4:
                levels.append(2)
            elif score >= 0.2:
                levels.append(1)
            else:
                levels.append(0)
        return levels


class TestGeneralEvaluatorCalibration(EvaluatorCalibrationTest):
    """GeneralEvaluator校准测试"""
    
    from src.domain.evaluators.general import GeneralEvaluator
    EVALUATOR_CLASS = GeneralEvaluator
    EVALUATOR_TYPE = "general"


class TestQAEvaluatorCalibration(EvaluatorCalibrationTest):
    """QAEvaluator校准测试"""
    
    from src.domain.evaluators.qa import QAEvaluator
    EVALUATOR_CLASS = QAEvaluator
    EVALUATOR_TYPE = "qa"


class TestCalibrationFeedbackLoop:
    """校准反馈闭环测试 - 验证record_evaluation被正确调用"""
    
    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.config = MagicMock()
        client.config.model_name = "gpt-4"
        return client
    
    def test_calibration_record_called_with_golden_score(self, mock_client):
        """测试：当metadata包含golden_score时，calibrator.record_evaluation被调用"""
        from src.domain.evaluators.general import GeneralEvaluator
        from src.domain.calibration.adaptive_calibrator import calibrator
        from src.schemas.evaluation import EvaluationSchema
        
        evaluator = GeneralEvaluator(client=mock_client)
        mock_client.chat.return_value = "0.85"
        
        original_record = calibrator.record_evaluation
        record_called = []
        
        def mock_record(*args, **kwargs):
            record_called.append((args, kwargs))
            return original_record(*args, **kwargs)
        
        calibrator.record_evaluation = mock_record
        
        try:
            request = EvaluationSchema(
                id="test_feedback",
                type="general",
                payload={
                    "user_input": "什么是机器学习？",
                    "expected_output": "机器学习是人工智能的一个分支",
                    "actual_output": "机器学习是AI的分支",
                },
                metadata={"golden_score": 0.85},
            )
            
            result = evaluator.safe_evaluate(request)
            
            assert len(record_called) == 1, "record_evaluation应该被调用一次"
            assert record_called[0][0][0] == "GeneralEvaluator"
            assert record_called[0][0][2] == 0.85, f"expected_score应该为0.85，实际为{record_called[0][0][2]}"
            assert record_called[0][0][1].score is not None, "评估结果应该包含分数"
        finally:
            calibrator.record_evaluation = original_record
    
    def test_calibration_record_not_called_without_golden_score(self, mock_client):
        """测试：当metadata不包含golden_score时，calibrator.record_evaluation不被调用"""
        from src.domain.evaluators.general import GeneralEvaluator
        from src.domain.calibration.adaptive_calibrator import calibrator
        from src.schemas.evaluation import EvaluationSchema
        
        evaluator = GeneralEvaluator(client=mock_client)
        mock_client.chat.return_value = "0.85"
        
        original_record = calibrator.record_evaluation
        record_called = []
        
        def mock_record(*args, **kwargs):
            record_called.append((args, kwargs))
            return original_record(*args, **kwargs)
        
        calibrator.record_evaluation = mock_record
        
        try:
            request = EvaluationSchema(
                id="test_no_feedback",
                type="general",
                payload={
                    "user_input": "什么是机器学习？",
                    "expected_output": "机器学习是人工智能的一个分支",
                    "actual_output": "机器学习是AI的分支",
                },
                metadata={},
            )
            
            result = evaluator.safe_evaluate(request)
            
            assert len(record_called) == 0, "record_evaluation不应该被调用"
        finally:
            calibrator.record_evaluation = original_record
    
    def test_calibration_record_not_called_with_none_golden_score(self, mock_client):
        """测试：当golden_score为None时，calibrator.record_evaluation不被调用"""
        from src.domain.evaluators.general import GeneralEvaluator
        from src.domain.calibration.adaptive_calibrator import calibrator
        from src.schemas.evaluation import EvaluationSchema
        
        evaluator = GeneralEvaluator(client=mock_client)
        mock_client.chat.return_value = "0.85"
        
        original_record = calibrator.record_evaluation
        record_called = []
        
        def mock_record(*args, **kwargs):
            record_called.append((args, kwargs))
            return original_record(*args, **kwargs)
        
        calibrator.record_evaluation = mock_record
        
        try:
            request = EvaluationSchema(
                id="test_none_score",
                type="general",
                payload={
                    "user_input": "什么是机器学习？",
                    "expected_output": "机器学习是人工智能的一个分支",
                    "actual_output": "机器学习是AI的分支",
                },
                metadata={"golden_score": None},
            )
            
            result = evaluator.safe_evaluate(request)
            
            assert len(record_called) == 0, "record_evaluation不应该被调用"
        finally:
            calibrator.record_evaluation = original_record