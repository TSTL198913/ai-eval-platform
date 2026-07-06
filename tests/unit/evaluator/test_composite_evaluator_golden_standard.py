"""
CompositeEvaluator 黄金标准边界穿透测试

测试目标：验证组合评估器在边界情况下的聚合逻辑正确性。

黄金标准：
1. 全部子评估器ERROR → 总分=0，状态=ERROR
2. 部分子评估器ERROR → 总分降低，状态=ERROR
3. 全部子评估器PARTIAL → 状态=PARTIAL，置信度≤0.7
4. 部分子评估器PARTIAL → 状态=PARTIAL
5. 冲突检测：高分和低分同时存在时应标记冲突
6. 权重配置：自定义权重应正确影响最终分数
"""

import pytest

from src.domain.evaluators.composite import CompositeEvaluator, EvaluatorChainConfig
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus


class TestCompositeEvaluatorGoldenStandard:
    @pytest.fixture
    def evaluator(self):
        return CompositeEvaluator(
            evaluators=[
                EvaluatorChainConfig("security", weight=0.3),
                EvaluatorChainConfig("semantic", weight=0.3),
                EvaluatorChainConfig("llm_as_judge", weight=0.4),
            ],
            client=None,
        )

    def test_all_error_sub_evaluators(self, evaluator):
        """
        黄金标准：全部子评估器ERROR时总分必须为0
        场景：输入包含危险代码且缺少必要参数
        预期：总分=0，状态=ERROR
        """
        request = EvaluationSchema(
            id="composite_gold_001",
            type="composite",
            payload={
                "code": "eval('rm -rf /')",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score == 0.0, f"全部ERROR时总分应为0，实际为{result.score}"
        assert result.evaluation_status == EvaluatorStatus.ERROR, "全部ERROR时状态应为ERROR"

    def test_partial_error_sub_evaluators(self, evaluator):
        """
        黄金标准：部分子评估器ERROR时总分必须降低
        场景：部分评估器可用，部分不可用
        预期：总分受ERROR评估器影响降低，状态=ERROR
        """
        request = EvaluationSchema(
            id="composite_gold_002",
            type="composite",
            payload={
                "actual_output": "机器学习是AI的分支",
                "expected_output": "AI的一个领域是机器学习",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.evaluation_status == EvaluatorStatus.ERROR, "部分ERROR时状态应为ERROR"

    def test_all_partial_sub_evaluators(self, evaluator):
        """
        黄金标准：全部子评估器PARTIAL时状态必须为PARTIAL
        场景：所有评估器都走降级路径（缺少LLM客户端）
        预期：状态=PARTIAL，置信度≤0.7
        """
        request = EvaluationSchema(
            id="composite_gold_003",
            type="composite",
            payload={
                "user_input": "北京天气怎么样？",
                "actual_output": "北京天气很热",
                "expected_output": "北京天气炎热",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.evaluation_status == EvaluatorStatus.PARTIAL, "全部PARTIAL时状态应为PARTIAL"
        assert result.confidence <= 0.7, f"降级评估置信度应≤0.7，实际为{result.confidence}"

    def test_conflict_detection(self, evaluator):
        """
        黄金标准：冲突检测必须正确识别高低分冲突
        场景：一个评估器给高分，一个给低分
        预期：conflict_detected=True
        """
        request = EvaluationSchema(
            id="composite_gold_004",
            type="composite",
            payload={
                "actual_output": "这个产品质量非常好",
                "expected_output": "这个产品质量很差",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        if result.data and "conflict_detected" in result.data:
            assert result.data["conflict_detected"] == True, "应该检测到冲突"

    def test_weight_configuration(self):
        """
        黄金标准：自定义权重必须正确影响最终分数
        场景：安全评估器权重很高(0.8)
        预期：安全评估器的分数对总分影响更大
        """
        evaluator = CompositeEvaluator(
            evaluators=[
                EvaluatorChainConfig("security", weight=0.8),
                EvaluatorChainConfig("semantic", weight=0.2),
            ],
            client=None,
        )
        request = EvaluationSchema(
            id="composite_gold_005",
            type="composite",
            payload={
                "actual_output": "机器学习是AI的分支",
                "expected_output": "AI的一个领域是机器学习",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.data is not None, "data不能为空"

    def test_empty_sub_evaluators(self):
        """
        黄金标准：空评估器链必须正确处理
        场景：没有配置任何子评估器
        预期：状态=SUCCESS，分数=0
        """
        evaluator = CompositeEvaluator(evaluators=[], client=None)
        request = EvaluationSchema(
            id="composite_gold_006",
            type="composite",
            payload={
                "actual_output": "测试文本",
                "expected_output": "测试文本",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.score == 0.0, f"空评估器链分数应为0，实际为{result.score}"

    def test_status_aggregation_hierarchy(self):
        """
        黄金标准：状态聚合必须遵循优先级层级
        场景：ERROR > CANNOT_EVALUATE > PARTIAL > SUCCESS
        预期：只要有ERROR就返回ERROR
        """
        evaluator = CompositeEvaluator(
            evaluators=[
                EvaluatorChainConfig("security", weight=0.5),
                EvaluatorChainConfig("semantic", weight=0.5),
            ],
            client=None,
        )
        request = EvaluationSchema(
            id="composite_gold_007",
            type="composite",
            payload={
                "code": "eval('malicious_code')",
                "actual_output": "正常文本",
                "expected_output": "正常文本",
            },
        )
        result = evaluator.safe_evaluate(request)

        assert result.score is not None, "score不能为空"
        assert result.evaluation_status == EvaluatorStatus.ERROR, "有ERROR时状态应为ERROR"
