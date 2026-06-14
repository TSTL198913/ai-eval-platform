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


def test_text_similarity():
    score = score_text_similarity("机器学习是AI分支", "机器学习是人工智能的重要分支")
    assert score > 0.3


def test_keyword_overlap():
    score = score_keyword_overlap("语法正确，无明显问题", "语法正确")
    assert score >= 0.5


def test_is_passing():
    assert is_passing(PASS_THRESHOLD) is True
    assert is_passing(PASS_THRESHOLD - 0.01) is False
