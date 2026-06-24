"""
属性测试 - 核心模块边界情况覆盖
=====================================
使用 Hypothesis 生成随机测试数据，验证系统在各种边界情况下的行为。
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import json
import time

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.domain.evaluators.scoring import is_passing, score_keyword_overlap, score_text_similarity
from src.domain.evaluators.security import SecurityEvaluator
from src.schemas.evaluation import DomainResponse, EvaluationSchema


class TestSecurityEvaluatorProperty:
    """SecurityEvaluator 属性测试"""

    @given(st.text(min_size=0, max_size=5000))
    @settings(max_examples=50, deadline=5000)
    def test_evaluator_never_crashes(self, user_input):
        """安全评估器对任意字符串输入都不应崩溃"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="test-property", type="security", payload={"user_input": user_input}
        )
        result = evaluator.safe_evaluate(request)

        assert isinstance(result, DomainResponse)
        assert result.is_valid is not None

    @given(st.text(min_size=1000, max_size=10000))
    @settings(max_examples=10, deadline=10000)
    def test_evaluator_handles_long_input(self, user_input):
        """安全评估器应能处理超长输入"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="test-long", type="security", payload={"user_input": user_input}
        )
        result = evaluator.safe_evaluate(request)

        assert isinstance(result, DomainResponse)
        assert result.is_valid is True

    @given(st.text(alphabet=st.characters(whitelist_categories=("Cc", "Cf"))))
    @settings(max_examples=30, deadline=5000)
    def test_evaluator_handles_control_characters(self, user_input):
        """安全评估器应能处理控制字符"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="test-control", type="security", payload={"user_input": user_input}
        )
        result = evaluator.safe_evaluate(request)

        assert isinstance(result, DomainResponse)

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=50)
    def test_score_is_bounded(self, user_input):
        """安全评估器的分数应在0-1之间"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="test-bounded", type="security", payload={"user_input": user_input}
        )
        result = evaluator.safe_evaluate(request)

        if result.is_valid and result.score is not None:
            assert 0.0 <= result.score <= 1.0, f"Score {result.score} out of bounds"


class TestScoringProperty:
    """评分工具属性测试"""

    @given(st.text(), st.text())
    @settings(max_examples=100)
    def test_similarity_score_bounded(self, text1, text2):
        """文本相似度分数应在0-1之间"""
        score = score_text_similarity(text1, text2)
        assert 0.0 <= score <= 1.0, f"Similarity score {score} out of bounds"

    @given(st.text())
    @settings(max_examples=50)
    def test_similarity_reflexive(self, text):
        """文本与自身的相似度应为1.0"""
        score = score_text_similarity(text, text)
        assert score == pytest.approx(1.0, abs=0.01), f"Reflexive property failed: {score}"

    @given(st.text(), st.text())
    @settings(max_examples=50)
    def test_similarity_symmetric(self, text1, text2):
        """文本相似度应具有对称性"""
        score1 = score_text_similarity(text1, text2)
        score2 = score_text_similarity(text2, text1)
        assert score1 == pytest.approx(score2, abs=0.001), f"Symmetry failed: {score1} vs {score2}"

    @given(st.text(), st.text())
    @settings(max_examples=100)
    def test_keyword_overlap_bounded(self, output, expected):
        """关键词重叠分数应在0-1之间"""
        score = score_keyword_overlap(output, expected)
        assert 0.0 <= score <= 1.0, f"Keyword overlap score {score} out of bounds"

    @given(st.text())
    @settings(max_examples=50)
    def test_keyword_overlap_reflexive(self, text):
        """文本与自身的关键词重叠应为1.0"""
        score = score_keyword_overlap(text, text)
        assert score == pytest.approx(1.0, abs=0.01), f"Reflexive property failed: {score}"

    @given(st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=50)
    def test_is_passing_monotonic(self, score):
        """is_passing函数应单调递增"""
        if score >= 0.8:
            assert is_passing(score) is True
        else:
            assert is_passing(score) is False

    @given(st.floats(min_value=-100.0, max_value=100.0))
    @settings(max_examples=30)
    def test_is_passing_edge_cases(self, score):
        """is_passing对边界值的处理"""
        if score >= 0.8:
            assert is_passing(score) is True
        else:
            assert is_passing(score) is False


class TestDomainResponseProperty:
    """DomainResponse 属性测试"""

    @given(
        st.booleans(),
        st.floats(min_value=0.0, max_value=1.0) | st.none(),
        st.text() | st.none(),
        st.text() | st.none(),
        st.dictionaries(st.text(), st.text(), max_size=50) | st.none(),
        st.dictionaries(st.text(), st.text(), max_size=50) | st.none(),
    )
    @settings(max_examples=50)
    def test_response_construction(self, is_valid, score, text, error, data, metadata):
        """DomainResponse应能接受任意合法参数"""
        response = DomainResponse(
            is_valid=is_valid, score=score, text=text, error=error, data=data, metadata=metadata
        )

        assert response.is_valid == is_valid
        assert response.score == score
        assert response.text == text
        assert response.error == error
        assert response.data == data
        assert response.metadata == metadata

    @given(st.none() | st.text(min_size=1000, max_size=5000))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow])
    def test_response_handles_large_text(self, text):
        """DomainResponse应能处理大文本"""
        response = DomainResponse(is_valid=True, score=0.85, text=text)

        assert response.text == text
        if text is not None:
            assert len(response.text) == len(text)


class TestEvaluationSchemaProperty:
    """EvaluationSchema 属性测试"""

    @given(
        st.text(min_size=1, max_size=100),
        st.text(min_size=1, max_size=100),
        st.dictionaries(st.text(), st.text(), max_size=50),
    )
    @settings(max_examples=50)
    def test_schema_accepts_valid_input(self, request_id, eval_type, payload):
        """EvaluationSchema应能接受合法输入"""
        schema = EvaluationSchema(id=request_id, type=eval_type, payload=payload)

        assert schema.id == request_id
        assert schema.type == eval_type
        assert schema.payload == payload

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=30)
    def test_schema_empty_payload(self, request_id):
        """EvaluationSchema应能处理空payload"""
        schema = EvaluationSchema(id=request_id, type="security", payload={})

        assert schema.payload == {}

    @given(st.text(min_size=1000, max_size=5000))
    @settings(max_examples=5)
    def test_schema_large_payload(self, large_text):
        """EvaluationSchema应能处理大payload"""
        schema = EvaluationSchema(
            id="test-large", type="security", payload={"user_input": large_text}
        )

        assert schema.payload["user_input"] == large_text


class TestJSONParsingProperty:
    """JSON解析属性测试"""

    @given(st.text())
    @settings(max_examples=100, deadline=5000)
    def test_json_parse_safe(self, input_text):
        """JSON解析应安全处理任意输入"""
        try:
            result = json.loads(input_text)
            assert isinstance(result, dict | list | str | int | float | bool | None)
        except json.JSONDecodeError:
            pass

    @given(st.dictionaries(st.text(), st.text(), max_size=50))
    @settings(max_examples=50)
    def test_json_roundtrip(self, data):
        """JSON序列化/反序列化应保持数据完整性"""
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed == data

    @given(st.text())
    @settings(max_examples=50)
    def test_json_dumps_safe(self, text):
        """JSON序列化应安全处理任意字符串"""
        try:
            result = json.dumps({"text": text})
            assert isinstance(result, str)
        except Exception:
            pass


class TestEdgeCaseProperty:
    """边界情况属性测试"""

    @given(st.text())
    @settings(max_examples=50)
    def test_empty_string_detection(self, input_text):
        """空字符串应被检测到"""
        evaluator = SecurityEvaluator()
        if len(input_text.strip()) == 0:
            request = EvaluationSchema(
                id="test-empty-detect", type="security", payload={"user_input": input_text}
            )
            result = evaluator.safe_evaluate(request)
            if not result.is_valid:
                assert result.error is not None

    @given(st.text(min_size=1000, max_size=5000))
    @settings(max_examples=10)
    def test_long_input_performance(self, user_input):
        """超长输入应在合理时间内处理"""
        evaluator = SecurityEvaluator()
        request = EvaluationSchema(
            id="test-performance", type="security", payload={"user_input": user_input}
        )

        start = time.time()
        result = evaluator.safe_evaluate(request)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Processing took {elapsed:.2f}s"
        assert isinstance(result, DomainResponse)

    @given(st.text())
    @settings(max_examples=30)
    def test_special_characters(self, user_input):
        """特殊字符应被正确处理"""
        evaluator = SecurityEvaluator()
        special_chars = ["'", '"', "\\", "<", ">", "&", ";", "`", "$", "@"]
        if any(char in user_input for char in special_chars):
            request = EvaluationSchema(
                id="test-special", type="security", payload={"user_input": user_input}
            )
            result = evaluator.safe_evaluate(request)
            assert isinstance(result, DomainResponse)


pytestmark = pytest.mark.property
