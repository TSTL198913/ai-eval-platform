"""MemoryEvaluator 单元测试"""

from src.domain.evaluators.memory import MemoryEvaluator
from src.schemas.evaluation import EvaluationSchema


class TestMemoryEvaluator:
    """MemoryEvaluator 测试类"""

    def setup_method(self):
        """设置测试环境"""
        self.evaluator = MemoryEvaluator()

    def _create_request(self, **kwargs):
        """创建测试请求"""
        return EvaluationSchema(
            id="test_case_001",
            type="memory",
            input_text=kwargs.get("input_text", ""),
            payload=kwargs.get("payload", {}),
        )

    def test_evaluate_retrieval_high_relevance(self):
        """测试检索评估 - 高相关性"""
        request = self._create_request(
            payload={
                "user_input": "machine learning neural network",
                "retrieved_context": "Machine learning neural network uses layers to process data and learn patterns",
                "expected_context": "machine learning neural network",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score >= 0.7
        assert result.data["retrieval_acceptable"] is True

    def test_evaluate_retrieval_low_relevance(self):
        """测试检索评估 - 低相关性"""
        request = self._create_request(
            payload={
                "user_input": "machine learning",
                "retrieved_context": "weather forecast sunny today",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score < 0.7
        assert result.data["retrieval_acceptable"] is False

    def test_evaluate_retrieval_missing_query(self):
        """测试检索评估 - 缺少查询参数"""
        request = self._create_request(
            payload={
                "retrieved_context": "some context",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert "不能为空" in result.error

    def test_evaluate_retrieval_missing_context(self):
        """测试检索评估 - 缺少检索上下文"""
        request = self._create_request(
            payload={
                "user_input": "test query",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert "retrieved_context" in result.error

    def test_evaluate_consistency_high(self):
        """测试一致性评估 - 高一致性"""
        request = self._create_request(
            payload={
                "action": "evaluate_consistency",
                "old_memory": "user Zhang age 30 programmer",
                "new_memory": "user Zhang age 30 programmer",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.score >= 0.7
        assert result.data["consistency_acceptable"] is True
        assert result.data["info_loss_detected"] is False
        assert result.data["contradiction_detected"] is False

    def test_evaluate_consistency_with_contradiction(self):
        """测试一致性评估 - 包含矛盾"""
        request = self._create_request(
            payload={
                "action": "evaluate_consistency",
                "old_memory": "answer is yes",
                "new_memory": "answer is no",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data["contradiction_detected"] is True
        assert result.data["consistency_acceptable"] is False

    def test_evaluate_consistency_with_info_loss(self):
        """测试一致性评估 - 信息丢失"""
        request = self._create_request(
            payload={
                "action": "evaluate_consistency",
                "old_memory": "user Zhang age 30 programmer Beijing bachelor",
                "new_memory": "user Zhang age 30",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data["info_loss_detected"] is True
        assert result.data["consistency_acceptable"] is False

    def test_evaluate_consistency_missing_memory(self):
        """测试一致性评估 - 缺少记忆数据"""
        request = self._create_request(
            payload={
                "action": "evaluate_consistency",
                "old_memory": "some memory",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert "new_memory" in result.error

    def test_evaluate_forgetting_none(self):
        """测试遗忘率评估 - 无遗忘"""
        request = self._create_request(
            payload={
                "action": "evaluate_forgetting",
                "original_memory": "user Zhang age 30 programmer",
                "current_memory": "user Zhang age 30 programmer",
                "important_facts": ["Zhang age 30", "Zhang programmer"],
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data["forgetting_rate"] <= 0.1
        assert result.data["forgetting_level"] == "none"

    def test_evaluate_forgetting_high(self):
        """测试遗忘率评估 - 高遗忘"""
        request = self._create_request(
            payload={
                "action": "evaluate_forgetting",
                "original_memory": "user Zhang age 30 programmer Beijing bachelor",
                "current_memory": "user Zhang",
            },
        )
        result = self.evaluator.evaluate(request)
        assert result.is_valid
        assert result.data["forgetting_rate"] > 0.4

    def test_evaluate_forgetting_missing_memory(self):
        """测试遗忘率评估 - 缺少记忆数据"""
        request = self._create_request(
            payload={
                "action": "evaluate_forgetting",
                "original_memory": "some memory",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert "current_memory" in result.error

    def test_evaluate_unknown_action(self):
        """测试未知 action"""
        request = self._create_request(
            payload={
                "action": "unknown_action",
            },
        )
        result = self.evaluator.evaluate(request)
        assert not result.is_valid
        assert "未知的 action" in result.error
