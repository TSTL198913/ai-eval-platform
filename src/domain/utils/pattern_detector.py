"""
模式检测工具类
用于统一的安全检测逻辑
"""

import re
from typing import Any


class PatternDetector:
    """模式检测工具类 - 统一的安全检测逻辑"""

    @staticmethod
    def detect(
        patterns: list[str],
        text: str,
        penalty: float = 0.3,
        case_insensitive: bool = True,
    ) -> dict[str, Any]:
        """
        检测文本中匹配的模式

        Args:
            patterns: 正则表达式模式列表
            text: 待检测文本
            penalty: 每次匹配扣分
            case_insensitive: 是否大小写不敏感

        Returns:
            dict: {
                "score": float,  # 分数，初始1.0，匹配越多越低
                "detected": bool,  # 是否检测到
                "patterns": list[str],  # 匹配到的模式
                "risk_level": str,  # high/medium/low
            }
        """
        score = 1.0
        detected_patterns = []

        search_text = text.lower() if case_insensitive else text

        for pattern in patterns:
            try:
                if re.search(pattern, search_text, re.IGNORECASE if case_insensitive else 0):
                    detected_patterns.append(pattern)
                    score -= penalty
            except re.error:
                continue

        return {
            "score": max(0.0, score),
            "detected": len(detected_patterns) > 0,
            "patterns": detected_patterns,
            "risk_level": PatternDetector._calculate_risk_level(len(detected_patterns)),
        }

    @staticmethod
    def _calculate_risk_level(match_count: int) -> str:
        """根据匹配数量计算风险等级"""
        if match_count >= 3:
            return "high"
        elif match_count >= 1:
            return "medium"
        return "low"

    @staticmethod
    def detect_multi_category(
        categories: dict[str, list[str]],
        text: str,
        default_penalty: float = 0.3,
    ) -> dict[str, Any]:
        """
        多类别模式检测

        Args:
            categories: 类别字典，key为类别名，value为模式列表
            text: 待检测文本
            default_penalty: 默认扣分值

        Returns:
            dict: {
                "overall_score": float,
                "detected": bool,
                "details": {category: detection_result},
                "risk_level": str,
            }
        """
        overall_score = 1.0
        details = {}
        total_detected = 0

        for category, patterns in categories.items():
            result = PatternDetector.detect(patterns, text, default_penalty)
            details[category] = result
            if result["detected"]:
                total_detected += 1
                overall_score -= default_penalty

        return {
            "overall_score": max(0.0, overall_score),
            "detected": total_detected > 0,
            "details": details,
            "risk_level": PatternDetector._calculate_risk_level(total_detected),
        }
