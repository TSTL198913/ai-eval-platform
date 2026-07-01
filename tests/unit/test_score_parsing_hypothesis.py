"""
Hypothesis 属性测试 - score_parsing.py
验证核心不变式：
1. _normalize_score 返回值要么是 None 要么在 [0.0, 1.0] 区间
2. NumericExtractStrategy.try_parse 返回的分数必须在 [0.0, 1.0] 区间
3. 所有策略处理异常输入时不会崩溃
"""

import math
from decimal import Decimal, InvalidOperation

import pytest
from hypothesis import given, strategies as st, assume, note, settings, HealthCheck


class TestNormalizeScoreInvariants:
    """测试 _normalize_score 的核心不变式"""

    @given(
        score=st.one_of(
            st.floats(min_value=-1e10, max_value=1e10),
            st.just(float("nan")),
            st.just(float("inf")),
            st.just(float("-inf")),
        ),
        context=st.text(),
    )
    def test_normalize_score_returns_valid_range_or_none(self, score, context):
        """不变式：对于任意 float 输入，_normalize_score 返回值要么是 None 要么在 [0.0, 1.0] 区间"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()

        try:
            result = strategy._normalize_score(score, context)
        except Exception as e:
            pytest.fail(f"_normalize_score 不应抛出异常，输入: {score}, 异常: {e}")

        if result is not None:
            assert isinstance(result, float), f"返回值必须是 float 或 None，实际类型: {type(result)}"
            assert math.isnan(result) is False, f"返回值不能是 NaN，输入: {score}"
            assert math.isinf(result) is False, f"返回值不能是无穷大，输入: {score}"
            assert 0.0 <= result <= 1.0, f"返回值必须在 [0.0, 1.0] 区间，输入: {score}, 返回: {result}"

    @given(score=st.floats(max_value=-0.0001))
    def test_negative_scores_return_none(self, score):
        """不变式：所有负数分数必须返回 None"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result is None, f"负数分数 {score} 必须返回 None，实际返回: {result}"

    @given(score=st.floats(min_value=0.0, max_value=1.0))
    def test_zero_to_one_range_unchanged(self, score):
        """不变式：[0, 1] 区间的分数应保持不变"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result == score, f"[0,1] 区间分数应保持不变，输入: {score}, 返回: {result}"

    @given(score=st.floats(min_value=1.0001, max_value=100.0))
    def test_one_to_hundred_normalized_to_zero_to_one(self, score):
        """不变式：(1, 100] 区间的分数应被归一化到 (0, 1]"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result is not None, f"(1,100] 区间分数不应返回 None，输入: {score}"
        assert 0.0 < result <= 1.0, f"(1,100] 区间分数应被归一化到 (0,1]，输入: {score}, 返回: {result}"

    @given(score=st.floats(min_value=100.0001))
    def test_over_hundred_returns_none(self, score):
        """不变式：大于 100 的分数必须返回 None"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result is None, f"大于 100 的分数 {score} 必须返回 None，实际返回: {result}"

    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    @given(score=st.floats(allow_nan=True))
    def test_nan_returns_none(self, score):
        """不变式：NaN 必须返回 None"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        assume(math.isnan(score))
        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result is None, f"NaN 必须返回 None，实际返回: {result}"

    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    @given(score=st.floats(allow_infinity=True))
    def test_infinity_returns_none(self, score):
        """不变式：正负无穷大必须返回 None"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        assume(math.isinf(score))
        strategy = NumericExtractStrategy()
        result = strategy._normalize_score(score, "")
        assert result is None, f"无穷大 {score} 必须返回 None，实际返回: {result}"


class TestNumericExtractStrategyInvariants:
    """测试 NumericExtractStrategy 的核心不变式"""

    @given(text=st.text())
    def test_try_parse_returns_valid_score_or_none(self, text):
        """不变式：对于任意字符串输入，try_parse 返回的 ParsedScore.score 必须在 [0.0, 1.0] 区间或返回 None"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()

        try:
            result = strategy.try_parse(text)
        except Exception as e:
            pytest.fail(f"try_parse 不应抛出异常，输入: {text[:100]}, 异常: {e}")

        if result is not None:
            assert 0.0 <= result.score <= 1.0, f"分数必须在 [0.0, 1.0] 区间，输入: {text[:100]}, 分数: {result.score}"
            assert 0.0 <= result.confidence <= 1.0, f"置信度必须在 [0.0, 1.0] 区间，输入: {text[:100]}, 置信度: {result.confidence}"

    @given(
        number=st.floats(min_value=-1000.0, max_value=1000.0),
        prefix=st.text(alphabet=st.characters(exclude_categories=("N",))),
        suffix=st.text(alphabet=st.characters(exclude_categories=("N",))),
    )
    def test_extracted_number_normalized_correctly(self, number, prefix, suffix):
        """不变式：从文本中提取的数字必须被正确归一化"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        assume(not math.isnan(number) and not math.isinf(number))

        text = f"{prefix}{number}{suffix}"
        strategy = NumericExtractStrategy()
        result = strategy.try_parse(text)

        if result is not None:
            assert 0.0 <= result.score <= 1.0, f"提取的数字 {number} 应被归一化到 [0,1]，实际分数: {result.score}"

    @given(
        integer_part=st.integers(min_value=-1000, max_value=1000),
        decimal_part=st.text(alphabet="0123456789"),
    )
    def test_decimal_number_extraction(self, integer_part, decimal_part):
        """不变式：小数形式的数字应被正确解析和归一化"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        if decimal_part:
            number_str = f"{integer_part}.{decimal_part}"
        else:
            number_str = str(integer_part)

        strategy = NumericExtractStrategy()
        result = strategy.try_parse(number_str)

        try:
            original_number = float(number_str)
        except ValueError:
            assume(False)

        if result is not None:
            assert 0.0 <= result.score <= 1.0, f"小数 {number_str} 应被归一化到 [0,1]，实际分数: {result.score}"

    @given(
        negative_num=st.floats(max_value=-0.0001),
    )
    def test_negative_numbers_not_extracted_as_valid(self, negative_num):
        """不变式：负数不应被提取为有效分数"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        assume(not math.isnan(negative_num))
        text = f"The score is {negative_num}"

        strategy = NumericExtractStrategy()
        result = strategy.try_parse(text)

        if result is not None:
            assert result.score >= 0, f"负数 {negative_num} 不应产生负分数，实际分数: {result.score}"

    @given(
        special_chars=st.text(
            alphabet=st.characters(blacklist_categories=("Cc", "Cs")), min_size=10
        ),
    )
    def test_special_characters_do_not_crash(self, special_chars):
        """不变式：特殊字符不应导致崩溃"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        try:
            result = strategy.try_parse(special_chars)
            assert result is None or 0.0 <= result.score <= 1.0
        except Exception as e:
            pytest.fail(f"特殊字符不应导致崩溃，输入: {repr(special_chars[:50])}, 异常: {e}")

    @given(
        long_text=st.text(min_size=1000, max_size=10000),
    )
    def test_long_text_do_not_crash(self, long_text):
        """不变式：超长文本不应导致崩溃"""
        from src.domain.evaluators.strategies.score_parsing import NumericExtractStrategy

        strategy = NumericExtractStrategy()
        try:
            result = strategy.try_parse(long_text)
            assert result is None or 0.0 <= result.score <= 1.0
        except Exception as e:
            pytest.fail(f"超长文本不应导致崩溃，输入长度: {len(long_text)}, 异常: {e}")


class TestScoreParserInvariants:
    """测试 ScoreParser 的核心不变式"""

    @given(text=st.text())
    def test_parse_returns_valid_score_or_none(self, text):
        """不变式：对于任意字符串输入，parse 返回的分数必须在 [0.0, 1.0] 区间或返回 None"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        try:
            result = DEFAULT_PARSER.parse(text)
        except Exception as e:
            pytest.fail(f"parse 不应抛出异常，输入: {text[:100]}, 异常: {e}")

        if result is not None:
            assert 0.0 <= result.score <= 1.0, f"分数必须在 [0.0, 1.0] 区间，输入: {text[:100]}, 分数: {result.score}"
            assert 0.0 <= result.confidence <= 1.0, f"置信度必须在 [0.0, 1.0] 区间，输入: {text[:100]}, 置信度: {result.confidence}"

    @given(text=st.text())
    def test_parse_with_ci_returns_valid_ci(self, text):
        """不变式：置信区间必须有效且包含分数"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        try:
            result = DEFAULT_PARSER.parse_with_ci(text)
        except Exception as e:
            pytest.fail(f"parse_with_ci 不应抛出异常，输入: {text[:100]}, 异常: {e}")

        if result is not None:
            score = result["score"]
            ci_lower = result["ci_lower"]
            ci_upper = result["ci_upper"]

            assert 0.0 <= ci_lower <= 1.0, f"置信区间下界必须在 [0,1]，输入: {text[:100]}, 下界: {ci_lower}"
            assert 0.0 <= ci_upper <= 1.0, f"置信区间上界必须在 [0,1]，输入: {text[:100]}, 上界: {ci_upper}"
            assert ci_lower <= score <= ci_upper, f"分数必须在置信区间内，输入: {text[:100]}, 分数: {score}, CI: [{ci_lower}, {ci_upper}]"
            assert ci_lower <= ci_upper, f"置信区间下界必须小于等于上界，输入: {text[:100]}, CI: [{ci_lower}, {ci_upper}]"


class TestAdversarialSamples:
    """对抗样本测试 - 验证系统在恶意输入下的健壮性"""

    @given(
        adversarial=st.one_of(
            st.text(alphabet="\u200b\u200c\u200d\uFEFF"),
            st.text(alphabet="\x00\x01\x02\x03"),
            st.text(alphabet="\uffff"),
            st.text().map(lambda x: x * 100),
        )
    )
    def test_adversarial_unicode(self, adversarial):
        """对抗样本：零宽字符、控制字符、重复文本不应导致崩溃"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        try:
            result = DEFAULT_PARSER.parse(adversarial)
            assert result is None or 0.0 <= result.score <= 1.0
        except Exception as e:
            pytest.fail(f"对抗样本不应导致崩溃，输入类型: {type(adversarial)}, 异常: {e}")

    @given(
        mixed=st.text(),
        number=st.floats(min_value=-1000, max_value=1000),
        garbage=st.text(alphabet="!@#$%^&*()_+-=[]{}|;:,.<>?"),
    )
    def test_mixed_inputs(self, mixed, number, garbage):
        """对抗样本：混合文本、数字和垃圾字符"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        assume(not math.isnan(number) and not math.isinf(number))

        text = f"{mixed} {number} {garbage}"
        try:
            result = DEFAULT_PARSER.parse(text)
            if result is not None:
                assert 0.0 <= result.score <= 1.0
        except Exception as e:
            pytest.fail(f"混合输入不应导致崩溃，输入: {text[:100]}, 异常: {e}")

    @given(
        nested_parens=st.recursive(
            st.text(alphabet="0123456789."),
            lambda children: st.builds(lambda x: f"({x})", children),
            max_leaves=10,
        )
    )
    def test_nested_parentheses(self, nested_parens):
        """对抗样本：深度嵌套的括号"""
        from src.domain.evaluators.strategies.score_parsing import DEFAULT_PARSER

        try:
            result = DEFAULT_PARSER.parse(nested_parens)
            if result is not None:
                assert 0.0 <= result.score <= 1.0
        except Exception as e:
            pytest.fail(f"嵌套括号不应导致崩溃，输入: {nested_parens[:100]}, 异常: {e}")