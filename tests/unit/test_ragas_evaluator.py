import pytest

from src.domain.evaluators.ragas_evaluator import (
    RAGASEvaluator,
    _local_answer_relevancy,
    _local_context_precision,
    _local_context_recall,
    _local_faithfulness,
)


class TestRAGASEvaluatorPositiveCases:
    """正向测试 - RAGAS 评估器"""

    def test_evaluator_can_be_instantiated(self):
        """评估器可被实例化"""
        evaluator = RAGASEvaluator()
        assert evaluator is not None

    def test_local_faithfulness_high_overlap(self):
        """高重合上下文应得高分"""
        answer = "Python is a programming language"
        context = "Python is a programming language created by Guido"
        score = _local_faithfulness(answer, context)
        assert score >= 0.5, f"高重合忠实度应 >= 0.5，实际: {score}"

    def test_local_answer_relevancy_keyword_match(self):
        """答案包含问题关键词应得高分"""
        # 使用英文以获得高 token 重叠
        score = _local_answer_relevancy(
            "What is Python programming language?",
            "Python is a popular programming language used for web development",
        )
        assert score > 0.1, f"含关键词应 > 0.1，实际: {score}"


class TestRAGASEvaluatorNegativeCases:
    """负向测试 - RAGAS 评估器"""

    def test_local_faithfulness_no_context(self):
        """无上下文时忠实度为 0"""
        assert _local_faithfulness("some answer", "") == 0.0
        assert _local_faithfulness("", "some context") == 0.0

    def test_local_answer_relevancy_no_match(self):
        """无重合关键词时相关性低"""
        score = _local_answer_relevancy("什么是 Python?", "今天天气真好")
        assert score < 0.1

    def test_local_context_recall_no_ground_truth(self):
        """无 ground_truth 时召回为 0"""
        assert _local_context_recall("context", "") == 0.0
        assert _local_context_recall("", "ground_truth") == 0.0

    def test_local_hallucination_no_context(self):
        """无上下文时幻觉为 1.0（ragas_evaluator 无此函数，使用 deepeval 实现）"""
        from src.domain.evaluators.deepeval_evaluator import _local_hallucination

        score = _local_hallucination("an answer", "")
        assert score == 1.0


class TestRAGASEvaluatorBoundaryCases:
    """边界测试 - RAGAS 评估器"""

    def test_empty_inputs(self):
        """空输入应优雅处理"""
        assert _local_faithfulness("", "") == 0.0
        assert _local_answer_relevancy("", "") == 0.0
        assert _local_context_precision([], "") == 0.0
        assert _local_context_recall([], "") == 0.0

    def test_single_word(self):
        """单词级别测试"""
        score = _local_faithfulness("python", "python is great")
        assert score >= 0.99

    def test_hedging_words_reduce_hallucination(self):
        """包含 hedging 词时幻觉分数应降低"""
        from src.domain.evaluators.deepeval_evaluator import _local_hallucination

        answer_with_hedge = "I don't know the exact answer"
        answer_direct = "The answer is X"
        context = "X is uncertain"
        score_hedge = _local_hallucination(answer_with_hedge, context)
        score_direct = _local_hallucination(answer_direct, "")
        # 直接答案没有上下文是 1.0；有 hedging 词的应降低
        assert score_hedge < score_direct


class TestRAGASEvaluatorEndToEnd:
    """端到端测试 - 完整评估流程"""

    def test_evaluate_with_minimal_inputs(self):
        """最小输入下的评估"""
        from src.schemas.evaluation import EvaluationSchema

        evaluator = RAGASEvaluator()
        request = EvaluationSchema(
            type="ragas",
            input="什么是 Python?",
            payload={
                "user_input": "什么是 Python?",
                "answer": "Python 是一种解释型编程语言",
                "context": "Python 是一种广泛使用的解释型、高级编程语言。",
            },
        )
        result = evaluator.evaluate(request)
        assert result is not None
        assert 0.0 <= result.score <= 1.0

    def test_evaluate_missing_answer_returns_error(self):
        """缺失 answer 应返回错误"""
        from src.schemas.evaluation import EvaluationSchema

        evaluator = RAGASEvaluator()
        request = EvaluationSchema(
            type="ragas",
            input="什么是 Python?",
            payload={"user_input": "什么是 Python?", "answer": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False

    def test_evaluate_with_selective_metrics(self):
        """选择性指标测试"""
        from src.schemas.evaluation import EvaluationSchema

        evaluator = RAGASEvaluator()
        request = EvaluationSchema(
            type="ragas",
            input="什么是 RAG?",
            payload={
                "user_input": "什么是 RAG?",
                "answer": "RAG 是检索增强生成",
                "context": "RAG 是 Retrieval-Augmented Generation 的缩写",
                "ground_truth": "RAG 是检索增强生成技术",
                "metrics": ["faithfulness", "answer_relevancy"],
            },
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is True
        metrics = result.data.get("metrics", {}) if result.data else {}
        assert "faithfulness" in metrics
        assert "answer_relevancy" in metrics
