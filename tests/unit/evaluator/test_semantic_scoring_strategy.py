"""语义评分策略测试

测试目标：
1. 实现 SemanticMappingStrategy 语义映射策略
2. 实现 LevelParseStrategy 等级解析策略
3. 实现 KeywordFallbackStrategy 关键词降级策略
4. 验证策略链能正确解析各种语义评分格式
5. 解决 BUG-003：金融风险评估无法解析非数字评分

关键发现：
- 当前 safe_parse_score() 仅支持数字提取
- 需要扩展支持语义评分（高风险/中等风险/低风险）
- 需要扩展支持等级评分（1分/2分/3分/4分/5分）
"""

import re
from abc import ABC, abstractmethod

import pytest


class ScoreParseStrategy(ABC):
    """评分解析策略基类"""

    @abstractmethod
    def try_parse(self, text: str) -> float | None:
        """尝试解析评分，失败返回 None"""
        pass


class NumericExtractStrategy(ScoreParseStrategy):
    """数字提取策略 - 从文本中提取数字分数"""

    def try_parse(self, text: str) -> float | None:
        if not text:
            return None
        cleaned = re.sub(r"(问题\d+|答案\d+|case\d+|Case\d+|第\d+句|第\d+个|文本\d+)", "", text)
        cleaned_end = cleaned.strip().rstrip(".。，, ")

        match = re.search(r"(\d+\.?\d*)$", cleaned_end)
        if match:
            before = cleaned_end[: match.start()].strip()
            if before and before.endswith("分"):
                return None
            try:
                score = float(match.group(1))
                if score > 1.0:
                    score = score / 100.0
                if 0.0 <= score <= 1.0:
                    return score
            except ValueError:
                pass

        match = re.search(r"(\d+\.?\d*)", cleaned)
        if match:
            before = cleaned[: match.start()].strip()
            after = cleaned[match.end() :].strip()
            if before and before.endswith("分"):
                return None
            if after and after.startswith("分"):
                return None
            try:
                score = float(match.group(1))
                if score > 1.0:
                    score = score / 100.0
                if 0.0 <= score <= 1.0:
                    return score
            except ValueError:
                pass
        return None


class SemanticMappingStrategy(ScoreParseStrategy):
    """语义映射策略 - 将文字评价映射为分数"""

    SEMANTIC_MAP = {
        "较高风险": (0.3, 0.5),
        "中高风险": (0.3, 0.5),
        "中等风险": (0.5, 0.6),
        "中风险": (0.5, 0.6),
        "较低风险": (0.6, 0.8),
        "中低风险": (0.6, 0.8),
        "高风险": (0.1, 0.3),
        "高危": (0.1, 0.3),
        "严重": (0.1, 0.3),
        "低风险": (0.8, 1.0),
        "安全": (0.8, 1.0),
        "无风险": (0.8, 1.0),
        "优秀": (0.9, 1.0),
        "完美": (0.9, 1.0),
        "极佳": (0.9, 1.0),
        "良好": (0.75, 0.89),
        "不错": (0.75, 0.89),
        "较好": (0.75, 0.89),
        "一般": (0.6, 0.74),
        "中等水平": (0.6, 0.74),
        "较差": (0.4, 0.59),
        "不好": (0.4, 0.59),
        "很差": (0.0, 0.39),
        "糟糕": (0.0, 0.39),
        "极差": (0.0, 0.39),
        "完全相关": (0.9, 1.0),
        "切题": (0.9, 1.0),
        "直击要点": (0.9, 1.0),
        "基本相关": (0.7, 0.89),
        "大部分相关": (0.7, 0.89),
        "部分相关": (0.4, 0.69),
        "有些跑题": (0.4, 0.69),
        "不相关": (0.0, 0.39),
        "答非所问": (0.0, 0.39),
    }

    ENGLISH_SEMANTIC_MAP = {
        "high risk": (0.1, 0.3),
        "severe": (0.1, 0.3),
        "critical": (0.1, 0.3),
        "medium risk": (0.5, 0.6),
        "low risk": (0.8, 1.0),
        "safe": (0.8, 1.0),
        "excellent": (0.9, 1.0),
        "good": (0.75, 0.89),
        "acceptable": (0.6, 0.74),
        "poor": (0.4, 0.59),
        "very poor": (0.0, 0.39),
    }

    def try_parse(self, text: str) -> float | None:
        if not text:
            return None

        for keyword, (min_score, max_score) in sorted(
            self.SEMANTIC_MAP.items(), key=lambda x: -len(x[0])
        ):
            if keyword in text:
                return (min_score + max_score) / 2.0

        lower_text = text.lower()
        for keyword, (min_score, max_score) in sorted(
            self.ENGLISH_SEMANTIC_MAP.items(), key=lambda x: -len(x[0])
        ):
            if keyword in lower_text:
                return (min_score + max_score) / 2.0

        return None


class LevelParseStrategy(ScoreParseStrategy):
    """等级解析策略 - 解析 1-5 分制等级"""

    def try_parse(self, text: str) -> float | None:
        if not text:
            return None

        level_match = re.search(r"([一二三四五1-5])[分级]", text)
        if level_match:
            level = level_match.group(1)
            level_map = {
                "一": 1,
                "二": 2,
                "三": 3,
                "四": 4,
                "五": 5,
                "1": 1,
                "2": 2,
                "3": 3,
                "4": 4,
                "5": 5,
            }
            if level in level_map:
                return level_map[level] / 5.0

        return None


class KeywordFallbackStrategy(ScoreParseStrategy):
    """关键词降级策略 - 根据积极/消极关键词估算"""

    POSITIVE_KEYWORDS = [
        "正确",
        "准确",
        "完整",
        "合理",
        "恰当",
        "优秀",
        "良好",
        "满意",
        "通过",
        "符合",
        "有效",
        "可靠",
    ]

    NEGATIVE_KEYWORDS = [
        "错误",
        "不准确",
        "不完整",
        "不合理",
        "不恰当",
        "较差",
        "不满意",
        "未通过",
        "不符合",
        "无效",
        "错误信息",
        "幻觉",
        "虚假",
    ]

    def try_parse(self, text: str) -> float | None:
        if not text:
            return None

        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

        if pos_count > 0 or neg_count > 0:
            total = pos_count + neg_count
            score = pos_count / total
            return score

        return None


class ScoreParser:
    """可配置的评分解析器（责任链模式）"""

    def __init__(self, strategies: list[ScoreParseStrategy]):
        self.strategies = strategies

    def parse(self, text: str) -> float | None:
        for strategy in self.strategies:
            result = strategy.try_parse(text)
            if result is not None:
                return result
        return None


class TestSemanticMappingStrategy:
    """语义映射策略测试"""

    def test_high_risk_mapping(self):
        """高风险应映射为低分数"""
        strategy = SemanticMappingStrategy()
        assert 0.1 <= strategy.try_parse("高风险交易") <= 0.3
        assert 0.1 <= strategy.try_parse("高危操作") <= 0.3
        assert 0.1 <= strategy.try_parse("严重风险") <= 0.3

    def test_medium_risk_mapping(self):
        """中等风险应映射为中等分数"""
        strategy = SemanticMappingStrategy()
        assert 0.5 <= strategy.try_parse("中等风险") <= 0.6
        assert 0.5 <= strategy.try_parse("中风险") <= 0.6
        assert 0.3 <= strategy.try_parse("较高风险") <= 0.5

    def test_low_risk_mapping(self):
        """低风险应映射为高分"""
        strategy = SemanticMappingStrategy()
        assert 0.8 <= strategy.try_parse("低风险") <= 1.0
        assert 0.8 <= strategy.try_parse("安全") <= 1.0
        assert 0.8 <= strategy.try_parse("无风险") <= 1.0

    def test_quality_level_mapping(self):
        """质量等级映射"""
        strategy = SemanticMappingStrategy()
        assert 0.9 <= strategy.try_parse("优秀回答") <= 1.0
        assert 0.75 <= strategy.try_parse("良好表现") <= 0.89
        assert 0.6 <= strategy.try_parse("一般水平") <= 0.74
        assert 0.4 <= strategy.try_parse("较差质量") <= 0.59
        assert 0.0 <= strategy.try_parse("很差") <= 0.39

    def test_english_mapping(self):
        """英文语义映射"""
        strategy = SemanticMappingStrategy()
        assert 0.1 <= strategy.try_parse("High risk transaction") <= 0.3
        assert 0.8 <= strategy.try_parse("Low risk, safe operation") <= 1.0
        assert 0.9 <= strategy.try_parse("Excellent quality") <= 1.0

    def test_no_match_returns_none(self):
        """无匹配语义应返回 None"""
        strategy = SemanticMappingStrategy()
        assert strategy.try_parse("这是一段普通文本") is None


class TestLevelParseStrategy:
    """等级解析策略测试"""

    def test_chinese_level_parsing(self):
        """中文等级解析"""
        strategy = LevelParseStrategy()
        assert strategy.try_parse("评分：五分") == 1.0
        assert strategy.try_parse("等级：四级") == 0.8
        assert strategy.try_parse("评为三级") == 0.6
        assert strategy.try_parse("二级评价") == 0.4
        assert strategy.try_parse("一级") == 0.2

    def test_arabic_level_parsing(self):
        """阿拉伯数字等级解析"""
        strategy = LevelParseStrategy()
        assert strategy.try_parse("5分") == 1.0
        assert strategy.try_parse("4分") == 0.8
        assert strategy.try_parse("3分") == 0.6
        assert strategy.try_parse("2分") == 0.4
        assert strategy.try_parse("1分") == 0.2

    def test_no_level_returns_none(self):
        """无等级应返回 None"""
        strategy = LevelParseStrategy()
        assert strategy.try_parse("分数是0.8") is None


class TestKeywordFallbackStrategy:
    """关键词降级策略测试"""

    def test_positive_keywords(self):
        """积极关键词应返回高分"""
        strategy = KeywordFallbackStrategy()
        result = strategy.try_parse("回答正确、完整、合理")
        assert result is not None
        assert result > 0.5

    def test_negative_keywords(self):
        """消极关键词应返回低分"""
        strategy = KeywordFallbackStrategy()
        result = strategy.try_parse("回答错误、不完整、有幻觉")
        assert result is not None
        assert result < 0.5

    def test_mixed_keywords(self):
        """混合关键词应正确计算"""
        strategy = KeywordFallbackStrategy()
        result = strategy.try_parse("回答正确但不完整")
        assert result is not None
        assert 0.5 <= result <= 0.75

    def test_no_keywords_returns_none(self):
        """无关键词应返回 None"""
        strategy = KeywordFallbackStrategy()
        assert strategy.try_parse("普通文本") is None


class TestScoreParser:
    """评分解析器测试 - 策略链"""

    def test_strategy_chain_order(self):
        """策略链应按顺序尝试"""
        parser = ScoreParser(
            [
                LevelParseStrategy(),
                NumericExtractStrategy(),
                SemanticMappingStrategy(),
                KeywordFallbackStrategy(),
            ]
        )

        assert parser.parse("评分是0.85") == 0.85
        assert 0.8 <= parser.parse("低风险") <= 1.0
        assert parser.parse("5分") == 1.0
        assert parser.parse("正确回答") is not None

    def test_bug_003_financial_risk_semantic(self):
        """BUG-003: 金融风险语义评分解析"""
        parser = ScoreParser(
            [
                NumericExtractStrategy(),
                SemanticMappingStrategy(),
                LevelParseStrategy(),
                KeywordFallbackStrategy(),
            ]
        )

        result = parser.parse("高风险交易")
        assert result is not None
        assert 0.1 <= result <= 0.3
        assert result is not None

    def test_mixed_content_parsing(self):
        """混合内容解析"""
        parser = ScoreParser(
            [
                LevelParseStrategy(),
                NumericExtractStrategy(),
                SemanticMappingStrategy(),
            ]
        )

        assert parser.parse("0.25") == 0.25
        assert 0.1 <= parser.parse("高风险操作") <= 0.3

    def test_empty_input(self):
        """空输入应返回 None"""
        parser = ScoreParser([NumericExtractStrategy()])
        assert parser.parse("") is None
        assert parser.parse(None) is None

    def test_special_characters(self):
        """特殊字符应正确处理"""
        parser = ScoreParser([NumericExtractStrategy()])
        assert parser.parse("评分: 0.9") == 0.9
        assert parser.parse("分数是，0.85，") == 0.85


class TestIntegrationWithBaseEvaluator:
    """与基础评估器集成测试"""

    def test_semantic_score_parsing_for_financial_risk(self):
        """金融风险评估语义评分解析"""
        parser = ScoreParser(
            [
                NumericExtractStrategy(),
                SemanticMappingStrategy(),
                LevelParseStrategy(),
                KeywordFallbackStrategy(),
            ]
        )

        test_cases = [
            ("高风险交易", 0.2),
            ("中等风险", 0.55),
            ("低风险", 0.9),
            ("安全操作", 0.9),
            ("严重风险", 0.2),
        ]

        for input_text, expected_range in test_cases:
            result = parser.parse(input_text)
            assert result is not None, f"无法解析: {input_text}"
            assert abs(result - expected_range) < 0.15, f"预期 {expected_range}，实际 {result}"

    def test_backward_compatibility(self):
        """向后兼容性 - 数字评分仍应正常工作"""
        parser = ScoreParser(
            [
                NumericExtractStrategy(),
                SemanticMappingStrategy(),
            ]
        )

        assert parser.parse("0.85") == 0.85
        assert parser.parse("85") == 0.85
        assert parser.parse("0.9") == 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
