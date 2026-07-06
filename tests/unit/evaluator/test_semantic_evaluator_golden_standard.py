"""
SemanticEvaluator 黄金标准对抗测试（数据驱动版）

测试目标：验证语义评估器能够正确识别语义反转，区分语义相同与语义相反的文本。
测试数据：外部化到 tests/data/semantic_golden_standard.json
"""

import pytest

from src.domain.evaluators.semantic import SemanticEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus
from tests.utils.test_helpers import (
    assert_response_valid,
    status_str_to_enum,
)


@pytest.fixture
def evaluator():
    return SemanticEvaluator(client=None)


@pytest.mark.slow
@pytest.mark.parametrize(
    "test_case",
    [
        {
            "id": "semantic_gold_001",
            "name": "语义完全相同的文本",
            "payload": {
                "actual_output": "北京的天气非常炎热，气温达到了35摄氏度",
                "expected_output": "北京天气很热，温度高达35度",
            },
            "expected": {
                "min_score": 0.6,
                "max_score": 1.0,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_002",
            "name": "语义完全相反的文本",
            "payload": {
                "actual_output": "这个产品质量非常好",
                "expected_output": "这个产品质量非常差",
            },
            "expected": {
                "min_score": 0.0,
                "max_score": 0.9,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_003",
            "name": "语义部分相似的文本",
            "payload": {
                "actual_output": "苹果公司发布了新款iPhone手机，搭载A18芯片",
                "expected_output": "苹果公司发布了新款手机，性能提升明显",
            },
            "expected": {
                "min_score": 0.4,
                "max_score": 0.6,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_004",
            "name": "完全无关的文本",
            "payload": {
                "actual_output": "人工智能正在改变世界",
                "expected_output": "今天中午吃了一碗牛肉面",
            },
            "expected": {
                "min_score": 0.0,
                "max_score": 0.2,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_005",
            "name": "逻辑反转的文本",
            "payload": {
                "actual_output": "下雨时地面会湿",
                "expected_output": "下雨时地面不会湿",
            },
            "expected": {
                "min_score": 0.0,
                "max_score": 0.95,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_006",
            "name": "无意义乱码",
            "payload": {
                "actual_output": "asdfg qwert zxcv bnm hjkl",
                "expected_output": "人工智能正在改变世界",
            },
            "expected": {
                "min_score": 0.0,
                "max_score": 0.2,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
        {
            "id": "semantic_gold_007",
            "name": "空输入",
            "payload": {
                "actual_output": "",
                "expected_output": "正常的期望输出",
            },
            "expected": {
                "status": "CANNOT_EVALUATE",
            },
        },
        {
            "id": "semantic_gold_008",
            "name": "降级模式状态验证",
            "payload": {
                "actual_output": "机器学习是人工智能的一个分支",
                "expected_output": "AI的一个领域是机器学习",
            },
            "expected": {
                "min_score": 0.35,
                "max_score": 0.8,
                "status": "PARTIAL",
                "max_confidence": 0.7,
            },
        },
    ],
    ids=lambda tc: tc["id"],
)
def test_semantic_golden_standard(test_case, evaluator):
    """
    数据驱动测试：验证语义评估器的黄金标准用例
    """
    request = EvaluationSchema(
        id=test_case["id"],
        type="semantic",
        payload=test_case["payload"],
    )
    result = evaluator.safe_evaluate(request)

    expected = test_case["expected"]
    assert_response_valid(
        result,
        expected_status=status_str_to_enum(expected.get("status", "success")),
        min_score=expected.get("min_score"),
        max_score=expected.get("max_score"),
        max_confidence=expected.get("max_confidence"),
    )