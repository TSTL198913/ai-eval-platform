"""
冒烟测试 - 评估器快速验证
执行时间: < 5s
"""

import pytest

from src.domain.evaluators import EvaluatorFactory
from src.schemas.evaluation import EvaluationSchema


@pytest.mark.smoke
class TestEvaluatorSmoke:
    """评估器冒烟测试"""

    @pytest.fixture
    def registered_evaluators(self):
        """获取所有已注册的评估器"""
        return EvaluatorFactory.list_evaluators()

    def test_evaluators_are_registered(self, registered_evaluators):
        """验证评估器已注册"""
        assert len(registered_evaluators) > 0, "应该有至少一个评估器"

    def test_code_evaluator_registered(self, registered_evaluators):
        """验证代码评估器已注册"""
        assert "code" in registered_evaluators

    def test_security_evaluator_registered(self, registered_evaluators):
        """验证安全评估器已注册"""
        assert "security" in registered_evaluators

    def test_qa_evaluator_registered(self, registered_evaluators):
        """验证问答评估器已注册"""
        assert "qa" in registered_evaluators


@pytest.mark.smoke
class TestEvaluatorInstantiation:
    """评估器实例化冒烟测试"""

    def test_code_evaluator_can_be_created(self):
        """验证可以创建代码评估器"""
        evaluator = EvaluatorFactory.get("code")
        assert evaluator is not None

    def test_security_evaluator_can_be_created(self):
        """验证可以创建安全评估器"""
        evaluator = EvaluatorFactory.get("security")
        assert evaluator is not None
