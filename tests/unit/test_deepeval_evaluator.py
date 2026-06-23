"""
🧪 tests/unit/test_deepeval_evaluator.py
DeepEval 评估器单元测试
"""

from src.domain.evaluators.deepeval_evaluator import (
    DeepEvalEvaluator,
    _local_answer_relevancy,
    _local_bias,
    _local_contextual_precision,
    _local_contextual_recall,
    _local_contextual_relevancy,
    _local_faithfulness,
    _local_hallucination,
    _local_toxicity,
)


class TestDeepEvalPositiveCases:
    """正向测试"""

    def test_evaluator_registered(self):
        from src.domain.evaluators.evaluator_factory import EvaluatorFactory

        assert "deepeval" in EvaluatorFactory.list_evaluators()

    def test_local_faithfulness_with_context(self):
        """有上下文时忠实度应 > 0"""
        score = _local_faithfulness("Python 是一种编程语言", "Python 是一种编程语言，由 Guido 创建")
        assert score > 0.5

    def test_local_contextual_relevancy_relevant(self):
        """相关内容应得高分"""
        score = _local_contextual_relevancy(
            ["Python is a programming language", "Java is also a language"],
            "What is Python?",
        )
        # 第一个上下文有 Python，应有更高重合
        assert score > 0.1

    def test_local_toxicity_clean_text(self):
        """干净文本毒性应低"""
        score = _local_toxicity("这是一个友好的问候")
        assert score == 0.0

    def test_local_bias_clean_text(self):
        """干净文本偏见应低"""
        score = _local_bias("我支持性别平等")
        assert score == 0.0


class TestDeepEvalNegativeCases:
    """负向测试"""

    def test_local_faithfulness_no_context(self):
        """无上下文忠实度为 0"""
        assert _local_faithfulness("some answer", "") == 0.0

    def test_local_contextual_precision_no_context(self):
        """无上下文时为 0"""
        assert _local_contextual_precision([], "answer") == 0.0

    def test_local_contextual_recall_no_ground_truth(self):
        """无 ground_truth 召回为 0"""
        assert _local_contextual_recall(["ctx"], "") == 0.0

    def test_local_toxicity_toxic_text(self):
        """毒性文本应被检测到"""
        score = _local_toxicity("you are stupid and idiot")
        assert score > 0.0

    def test_local_bias_biased_text(self):
        """偏见文本应被检测到"""
        score = _local_bias("男性都擅长数学")
        assert score > 0.0

    def test_local_hallucination_no_context(self):
        """无上下文时幻觉分数高"""
        score = _local_hallucination("some confident answer", "")
        assert score == 1.0


class TestDeepEvalBoundaryCases:
    """边界测试"""

    def test_empty_inputs(self):
        """空输入"""
        assert _local_faithfulness("", "") == 0.0
        assert _local_answer_relevancy("", "") == 0.0
        assert _local_contextual_relevancy([], "") == 0.0
        assert _local_bias("") == 0.0
        assert _local_toxicity("") == 0.0

    def test_chinese_and_english_mixed(self):
        """中英文混合输入"""
        score = _local_contextual_relevancy(
            ["Python 是一种编程语言", "Java is also a language"],
            "什么是 Python?",
        )
        assert 0.0 <= score <= 1.0


class TestDeepEvalEndToEnd:
    """端到端测试"""

    def test_evaluate_minimal_inputs(self):
        from src.schemas.evaluation import EvaluationSchema

        evaluator = DeepEvalEvaluator()
        request = EvaluationSchema(
            type="deepeval",
            input="什么是 AI?",
            payload={
                "actual_output": "AI 是人工智能",
                "context": "人工智能是计算机科学的一个分支",
            },
        )
        result = evaluator.evaluate(request)
        assert 0.0 <= result.score <= 1.0
        assert "implementation" in str(result.data or {})

    def test_evaluate_negative_metrics_inverted(self):
        """负面指标（偏见/毒性/幻觉）应被反转（越高越好）"""
        from src.schemas.evaluation import EvaluationSchema

        evaluator = DeepEvalEvaluator()
        request = EvaluationSchema(
            type="deepeval",
            input="你好",
            payload={
                "actual_output": "you are stupid and idiot",  # 高毒性
                "context": "some context",
                "metrics": ["toxicity", "bias"],
            },
        )
        result = evaluator.evaluate(request)
        metrics = result.data.get("metrics", {})
        tox = metrics.get("toxicity", {})
        assert tox.get("direction") == "negative"
        assert "raw_score" in tox
        assert "score" in tox

    def test_evaluate_missing_answer_returns_error(self):
        from src.schemas.evaluation import EvaluationSchema

        evaluator = DeepEvalEvaluator()
        request = EvaluationSchema(
            type="deepeval",
            input="测试",
            payload={"actual_output": ""},
        )
        result = evaluator.evaluate(request)
        assert result.is_valid is False
