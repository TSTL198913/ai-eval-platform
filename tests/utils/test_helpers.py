"""
测试工具函数库

提供：
1. pytest.approx() 封装 - 处理浮点分数比较
2. 字段级断言辅助 - 替代对象级断言
3. 评估器响应断言 - 统一的响应验证
4. 数据驱动测试辅助 - 参数化和数据加载
"""

import pytest
from typing import Any, Dict, List, Optional, Tuple, Union

from src.schemas.evaluation import DomainResponse, EvaluatorStatus


def approx_score(expected: float, rel: float = 0.05, abs: float = 0.01) -> pytest.approx:
    """
    分数近似比较（默认相对误差5%，绝对误差0.01）
    
    使用示例：
        assert result.score == approx_score(0.8)
        assert result.score == approx_score(0.5, rel=0.1)
    """
    return pytest.approx(expected, rel=rel, abs=abs)


def approx_confidence(expected: float, rel: float = 0.1, abs: float = 0.05) -> pytest.approx:
    """
    置信度近似比较（默认相对误差10%，绝对误差0.05）
    """
    return pytest.approx(expected, rel=rel, abs=abs)


def assert_response_valid(response: DomainResponse, 
                          expected_status: EvaluatorStatus = None,
                          min_score: float = None,
                          max_score: float = None,
                          expected_score: float = None,
                          min_confidence: float = None,
                          max_confidence: float = None):
    """
    字段级响应断言 - 验证DomainResponse的关键属性
    
    参数：
        response: DomainResponse对象
        expected_status: 预期的评估状态
        min_score: 最小分数
        max_score: 最大分数
        expected_score: 精确分数（使用approx比较）
        min_confidence: 最小置信度
        max_confidence: 最大置信度
    """
    assert response is not None, "响应不能为空"
    assert response.score is not None, "score不能为空"
    
    if expected_status is not None:
        assert response.evaluation_status == expected_status, \
            f"预期状态{expected_status}，实际{response.evaluation_status}"
    
    if min_score is not None:
        assert response.score >= min_score, \
            f"分数应≥{min_score}，实际{response.score}"
    
    if max_score is not None:
        assert response.score <= max_score, \
            f"分数应≤{max_score}，实际{response.score}"
    
    if expected_score is not None:
        assert response.score == approx_score(expected_score), \
            f"分数应≈{expected_score}，实际{response.score}"
    
    if min_confidence is not None:
        assert response.confidence >= min_confidence, \
            f"置信度应≥{min_confidence}，实际{response.confidence}"
    
    if max_confidence is not None:
        assert response.confidence <= max_confidence, \
            f"置信度应≤{max_confidence}，实际{response.confidence}"


def assert_score_between(response: DomainResponse, lower: float, upper: float):
    """
    断言分数在指定范围内
    """
    assert_response_valid(response)
    assert lower <= response.score <= upper, \
        f"分数应在[{lower}, {upper}]之间，实际{response.score}"


def assert_response_success(response: DomainResponse):
    """
    断言响应为SUCCESS状态
    """
    assert_response_valid(response, expected_status=EvaluatorStatus.SUCCESS)


def assert_response_partial(response: DomainResponse):
    """
    断言响应为PARTIAL状态（降级评估）
    """
    assert_response_valid(response, expected_status=EvaluatorStatus.PARTIAL)


def assert_response_error(response: DomainResponse):
    """
    断言响应为ERROR状态
    """
    assert_response_valid(response, expected_status=EvaluatorStatus.ERROR)


def assert_response_cannot_evaluate(response: DomainResponse):
    """
    断言响应为CANNOT_EVALUATE状态
    """
    assert_response_valid(response, expected_status=EvaluatorStatus.CANNOT_EVALUATE)


def load_test_data(file_path: str) -> List[Dict[str, Any]]:
    """
    加载JSON格式的测试数据文件
    
    文件格式示例：
    [
        {
            "id": "test_001",
            "name": "语义相同文本",
            "input": {...},
            "expected": {
                "min_score": 0.7,
                "max_score": 1.0,
                "status": "SUCCESS"
            }
        }
    ]
    """
    import json
    import os
    
    full_path = os.path.join(os.path.dirname(__file__), file_path)
    with open(full_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def status_str_to_enum(status_str: str) -> EvaluatorStatus:
    """
    将状态字符串转换为EvaluatorStatus枚举
    """
    status_map = {
        'success': EvaluatorStatus.SUCCESS,
        'partial': EvaluatorStatus.PARTIAL,
        'error': EvaluatorStatus.ERROR,
        'cannot_evaluate': EvaluatorStatus.CANNOT_EVALUATE,
    }
    return status_map.get(status_str.lower(), EvaluatorStatus.SUCCESS)