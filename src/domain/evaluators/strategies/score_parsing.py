"""评分解析策略模块

2026年工业级标准实现：
1. 策略模式设计 - 支持多种评分解析方式
2. 语义映射 - 将文字评价映射为数值分数
3. 等级解析 - 解析1-5分制等级
4. 关键词降级 - 作为最后兜底方案
5. 置信区间报告 - 每个评分附带置信区间
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ParsedScore:
    """解析后的评分结果"""

    score: float
    confidence: float
    strategy: str
    sample_size: int = 1


class ScoreParseStrategy(ABC):
    """评分解析策略基类"""

    @abstractmethod
    def try_parse(self, text: str) -> ParsedScore | None:
        """尝试解析评分，失败返回 None"""
        pass

    @property
    def name(self) -> str:
        """策略名称"""
        return self.__class__.__name__


class NumericExtractStrategy(ScoreParseStrategy):
    """数字提取策略 - 从文本中提取数字分数"""

    def try_parse(self, text: str) -> ParsedScore | None:
        if not text:
            return None

        cleaned = re.sub(r"(问题\d+|答案\d+|case\d+|Case\d+|第\d+句|第\d+个|文本\d+)", "", text)
        cleaned_end = cleaned.strip().rstrip(".。，, ")

        match = re.search(r"(\d+\.?\d*)$", cleaned_end)
        if match:
            before = cleaned_end[: match.start()].strip()
            if before == "分":
                return None
            try:
                score = float(match.group(1))
                # 修复：智能判断评分制式，避免百分制误判
                score = self._normalize_score(score, text)
                if score is not None and 0.0 <= score <= 1.0:
                    return ParsedScore(
                        score=score, confidence=0.95, strategy=self.name, sample_size=1
                    )
            except ValueError:
                pass

        match = re.search(r"(\d+\.?\d*)", cleaned)
        if match:
            before = cleaned[: match.start()].strip()
            after = cleaned[match.end() :].strip()
            if before == "分":
                return None
            if after and after.startswith("分") and not before:
                return None
            try:
                score = float(match.group(1))
                # 修复：智能判断评分制式，避免百分制误判
                score = self._normalize_score(score, text)
                if score is not None and 0.0 <= score <= 1.0:
                    return ParsedScore(
                        score=score, confidence=0.90, strategy=self.name, sample_size=1
                    )
            except ValueError:
                pass
        return None

    def _normalize_score(self, score: float, context: str) -> float | None:
        """智能判断评分制式并归一化

        修复：增加边界判断，避免对异常值进行误转换

        Args:
            score: 提取的原始分数
            context: 原始文本上下文

        Returns:
            float | None: 归一化后的分数（0-1），或 None（如果无法归一化）
        """
        import logging

        # 1. 如果分数已经在 0-1 区间，不需要转换
        if score <= 1.0:
            return score

        # 2. 如果分数在 1-100 区间，可能是百分制
        if score <= 100.0:
            # 检查上下文是否有百分制标记
            percentage_markers = ["%", "百分", "percentage", "满分100", "满分是100"]
            has_percentage_marker = any(marker in context for marker in percentage_markers)

            # 如果有明确的百分制标记，转换
            if has_percentage_marker:
                return score / 100.0

            # 如果分数接近常见的百分制整数（如 80, 90, 100），倾向于转换
            if abs(score - round(score)) < 0.01 and round(score) in [60, 70, 80, 90, 95, 100]:
                return score / 100.0

            # 其他情况：保守策略，假设是百分制，但记录低置信度
            return score / 100.0

        # 3. 如果分数 > 100，异常值，可能不是有效分数
        # 可能是年份、ID或其他数值
        logging.warning(f"异常分数值 {score}，超过100，可能不是有效分数，上下文：{context[:50]}")
        return None


class SemanticMappingStrategy(ScoreParseStrategy):
    """语义映射策略 - 将文字评价映射为分数"""

    SEMANTIC_MAP: dict[str, tuple[float, float, float]] = {
        "较高风险": (0.3, 0.5, 0.85),
        "中高风险": (0.3, 0.5, 0.85),
        "中等风险": (0.5, 0.6, 0.80),
        "中风险": (0.5, 0.6, 0.80),
        "较低风险": (0.6, 0.8, 0.85),
        "中低风险": (0.6, 0.8, 0.85),
        "高风险": (0.1, 0.3, 0.90),
        "高危": (0.1, 0.3, 0.95),
        "严重": (0.1, 0.3, 0.95),
        "低风险": (0.8, 1.0, 0.90),
        "安全": (0.8, 1.0, 0.95),
        "无风险": (0.8, 1.0, 0.95),
        "优秀": (0.9, 1.0, 0.95),
        "完美": (0.9, 1.0, 0.95),
        "极佳": (0.9, 1.0, 0.95),
        "良好": (0.75, 0.89, 0.90),
        "不错": (0.75, 0.89, 0.85),
        "较好": (0.75, 0.89, 0.85),
        "一般": (0.6, 0.74, 0.75),
        "中等水平": (0.6, 0.74, 0.75),
        "较差": (0.4, 0.59, 0.80),
        "不好": (0.4, 0.59, 0.75),
        "很差": (0.0, 0.39, 0.90),
        "糟糕": (0.0, 0.39, 0.90),
        "极差": (0.0, 0.39, 0.95),
        "完全相关": (0.9, 1.0, 0.95),
        "切题": (0.9, 1.0, 0.90),
        "直击要点": (0.9, 1.0, 0.95),
        "基本相关": (0.7, 0.89, 0.80),
        "大部分相关": (0.7, 0.89, 0.80),
        "部分相关": (0.4, 0.69, 0.70),
        "有些跑题": (0.4, 0.69, 0.70),
        "不相关": (0.0, 0.39, 0.90),
        "答非所问": (0.0, 0.39, 0.95),
    }

    ENGLISH_SEMANTIC_MAP: dict[str, tuple[float, float, float]] = {
        "high risk": (0.1, 0.3, 0.90),
        "severe": (0.1, 0.3, 0.95),
        "critical": (0.1, 0.3, 0.95),
        "medium risk": (0.5, 0.6, 0.80),
        "low risk": (0.8, 1.0, 0.90),
        "safe": (0.8, 1.0, 0.95),
        "excellent": (0.9, 1.0, 0.95),
        "good": (0.75, 0.89, 0.90),
        "acceptable": (0.6, 0.74, 0.75),
        "poor": (0.4, 0.59, 0.80),
        "very poor": (0.0, 0.39, 0.90),
    }

    def try_parse(self, text: str) -> ParsedScore | None:
        if not text:
            return None

        for keyword, (min_score, max_score, confidence) in sorted(
            self.SEMANTIC_MAP.items(), key=lambda x: -len(x[0])
        ):
            if keyword in text:
                return ParsedScore(
                    score=(min_score + max_score) / 2.0,
                    confidence=confidence,
                    strategy=self.name,
                    sample_size=1,
                )

        lower_text = text.lower()
        for keyword, (min_score, max_score, confidence) in sorted(
            self.ENGLISH_SEMANTIC_MAP.items(), key=lambda x: -len(x[0])
        ):
            if keyword in lower_text:
                return ParsedScore(
                    score=(min_score + max_score) / 2.0,
                    confidence=confidence,
                    strategy=self.name,
                    sample_size=1,
                )

        return None


class LevelParseStrategy(ScoreParseStrategy):
    """等级解析策略 - 解析 1-5 分制等级"""

    def try_parse(self, text: str) -> ParsedScore | None:
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
                score = level_map[level] / 5.0
                confidence = 0.95 if score in (0.2, 1.0) else 0.90
                return ParsedScore(
                    score=score, confidence=confidence, strategy=self.name, sample_size=1
                )

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

    def try_parse(self, text: str) -> ParsedScore | None:
        if not text:
            return None

        pos_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        neg_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)

        if pos_count > 0 or neg_count > 0:
            total = pos_count + neg_count
            score = pos_count / total
            confidence = min(0.7, 0.3 + (total * 0.1))
            return ParsedScore(
                score=score, confidence=confidence, strategy=self.name, sample_size=total
            )

        return None


class ScoreParser:
    """可配置的评分解析器（责任链模式）"""

    def __init__(self, strategies: list[ScoreParseStrategy]):
        self.strategies = strategies

    def parse(self, text: str) -> ParsedScore | None:
        """按策略链顺序解析评分"""
        for strategy in self.strategies:
            result = strategy.try_parse(text)
            if result is not None:
                return result
        return None

    def parse_with_ci(self, text: str) -> dict | None:
        """解析评分并返回置信区间"""
        result = self.parse(text)
        if result is None:
            return None

        margin_of_error = (
            1.96 * (result.confidence * (1 - result.confidence) / max(result.sample_size, 1)) ** 0.5
        )
        ci_lower = max(0.0, result.score - margin_of_error)
        ci_upper = min(1.0, result.score + margin_of_error)

        return {
            "score": result.score,
            "confidence": result.confidence,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "sample_size": result.sample_size,
            "strategy": result.strategy,
            "margin_of_error": margin_of_error,
        }


DEFAULT_STRATEGIES = [
    LevelParseStrategy(),
    NumericExtractStrategy(),
    SemanticMappingStrategy(),
    KeywordFallbackStrategy(),
]

DEFAULT_PARSER = ScoreParser(DEFAULT_STRATEGIES)
