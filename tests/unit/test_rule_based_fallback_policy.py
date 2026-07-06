"""RuleBasedFallbackPolicy测试

验证规则引擎降级策略的正确性和事件发布。
"""

import pytest
from unittest.mock import Mock, patch

from src.domain.evaluators.fallback_policy import RuleBasedFallbackPolicy, FallbackPolicyFactory
from src.domain.evaluators.base import BaseEvaluator


class TestRuleBasedFallbackPolicy:
    """规则引擎降级策略测试"""

    def test_get_policy_registration(self):
        """验证策略已注册到工厂"""
        policy = FallbackPolicyFactory.get_policy("rule_based")
        assert isinstance(policy, RuleBasedFallbackPolicy)

    def test_should_fallback_returns_true(self):
        """验证should_fallback返回True"""
        policy = RuleBasedFallbackPolicy()
        assert policy.should_fallback(Exception("test")) is True

    def test_get_fallback_score_with_rule_based_qa(self):
        """验证使用_rule_based_qa获取分数"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(return_value=0.8)
        mock_evaluator._rule_based_factuality = Mock(return_value=0.6)
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.8
        mock_evaluator._rule_based_qa.assert_called_once_with("question", "actual", "expected")
        mock_evaluator._rule_based_factuality.assert_not_called()
        
        BaseEvaluator.set_current_evaluator(None)

    def test_get_fallback_score_falls_back_to_factuality(self):
        """验证_rule_based_qa返回None时使用_rule_based_factuality"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(return_value=None)
        mock_evaluator._rule_based_factuality = Mock(return_value=0.7)
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.7
        mock_evaluator._rule_based_qa.assert_called_once()
        mock_evaluator._rule_based_factuality.assert_called_once()
        
        BaseEvaluator.set_current_evaluator(None)

    def test_get_fallback_score_no_evaluator(self):
        """验证无当前评估器时返回0"""
        policy = RuleBasedFallbackPolicy()
        BaseEvaluator.set_current_evaluator(None)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.0

    def test_get_fallback_score_no_rule_methods(self):
        """验证评估器无规则方法时返回0"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.0
        
        BaseEvaluator.set_current_evaluator(None)

    def test_get_fallback_score_rule_qa_exception(self):
        """验证_rule_based_qa异常时返回0"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(side_effect=RuntimeError("Test error"))
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.0
        
        BaseEvaluator.set_current_evaluator(None)

    def test_get_fallback_score_rule_factuality_exception(self):
        """验证_rule_based_factuality异常时返回0"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(return_value=None)
        mock_evaluator._rule_based_factuality = Mock(side_effect=RuntimeError("Test error"))
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = policy.get_fallback_score("actual", "expected", "question")
        
        assert score == 0.0
        
        BaseEvaluator.set_current_evaluator(None)

    def test_get_confidence(self):
        """验证置信度返回0.6"""
        policy = RuleBasedFallbackPolicy()
        assert policy.get_confidence() == 0.6

    def test_get_fallback_metadata(self):
        """验证元数据"""
        policy = RuleBasedFallbackPolicy()
        metadata = policy.get_fallback_metadata()
        
        assert metadata["mode"] == "fallback_rule_based"
        assert metadata["confidence"] == 0.6
        assert "使用规则引擎降级评估" in metadata["warning"]

    @pytest.mark.asyncio
    async def test_get_fallback_score_async(self):
        """验证异步方法调用同步实现"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(return_value=0.8)
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        score = await policy.get_fallback_score_async("actual", "expected", "question")
        
        assert score == 0.8
        
        BaseEvaluator.set_current_evaluator(None)

    def test_fallback_event_published(self):
        """验证降级事件被发布"""
        policy = RuleBasedFallbackPolicy()
        
        mock_evaluator = Mock()
        mock_evaluator._rule_based_qa = Mock(return_value=0.75)
        
        BaseEvaluator.set_current_evaluator(mock_evaluator)
        
        with patch.object(policy, '_publish_fallback_event') as mock_publish:
            score = policy.get_fallback_score("actual", "expected", "question")
            
            assert score == 0.75
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args[0]
            assert call_args[2] == 0.75
        
        BaseEvaluator.set_current_evaluator(None)