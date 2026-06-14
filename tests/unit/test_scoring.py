from src.domain.evaluators.scoring import (
    PASS_THRESHOLD,
    is_passing,
    score_keyword_overlap,
    score_numeric_match,
    score_text_similarity,
)


def test_numeric_match():
    assert score_numeric_match("利息为30元", "30") == 1.0
    assert score_numeric_match("无法计算", "30") == 0.0


def test_numeric_match_empty_output():
    """测试空输出返回 0.0"""
    assert score_numeric_match("", "30") == 0.0
    assert score_numeric_match("   ", "30") == 0.0


def test_numeric_match_none_expected():
    """测试 expected 为 None 返回 1.0"""
    assert score_numeric_match("任意输出", None) == 1.0


def test_numeric_match_no_numbers_in_expected():
    """测试 expected 中没有数字时的匹配"""
    assert score_numeric_match("包含关键词", "关键词") == 1.0
    assert score_numeric_match("不包含", "关键词") == 0.0


def test_text_similarity():
    score = score_text_similarity("机器学习是AI分支", "机器学习是人工智能的重要分支")
    assert score > 0.3


def test_text_similarity_empty_output():
    """测试空输出返回 0.0"""
    assert score_text_similarity("", "期望文本") == 0.0
    assert score_text_similarity("   ", "期望文本") == 0.0


def test_text_similarity_none_expected():
    """测试 expected 为 None 返回 1.0"""
    assert score_text_similarity("任意输出", None) == 1.0


def test_keyword_overlap():
    score = score_keyword_overlap("语法正确，无明显问题", "语法正确")
    assert score >= 0.5


def test_keyword_overlap_empty_output():
    """测试空输出返回 0.0"""
    assert score_keyword_overlap("", "关键词") == 0.0
    assert score_keyword_overlap("   ", "关键词") == 0.0


def test_keyword_overlap_none_expected():
    """测试 expected 为 None 返回 1.0"""
    assert score_keyword_overlap("任意输出", None) == 1.0


def test_keyword_overlap_empty_tokens():
    """测试 expected_tokens 为空时的匹配"""
    # expected 中没有可提取的 token（只有符号）
    assert score_keyword_overlap("包含test", "!!!") == 0.0
    assert score_keyword_overlap("!!!", "!!!") == 1.0


def test_is_passing():
    assert is_passing(PASS_THRESHOLD) is True
    assert is_passing(PASS_THRESHOLD - 0.01) is False


def test_is_passing_custom_threshold():
    """测试自定义阈值"""
    assert is_passing(0.9, threshold=0.9) is True
    assert is_passing(0.89, threshold=0.9) is False
