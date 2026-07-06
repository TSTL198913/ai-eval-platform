import logging
import re

from src.domain.services.text_analysis_service import text_analysis_service

logger = logging.getLogger(__name__)


class FallbackScoringService:
    """标准化降级评分服务 - 统一跨评估器的降级评分公式，使评分可比"""

    INVALID_ANSWERS = {"不知道", "不清楚", "无法回答", "不了解", "none", "n/a", "错误", "不确定"}

    UNCERTAINTY_PATTERNS = {"不太确定", "可能是"}

    SCORING_WEIGHTS = {
        "general": {
            "text_similarity": 0.65,
            "answer_coverage": 0.18,
            "question_relevance": 0.10,
            "number_match": 0.07,
        },
        "qa": {
            "base_score": 0.3,
            "text_similarity": 0.3,
            "answer_coverage": 0.2,
            "question_relevance": 0.2,
        },
        "default": {
            "text_similarity": 0.4,
            "answer_coverage": 0.3,
            "question_relevance": 0.2,
            "number_match": 0.1,
        },
    }

    LENGTH_PENALTY_CONFIG = {
        "general": {"min_ratio": 0.15, "min_penalty": 0.03, "max_ratio": 4.0, "max_penalty": 0.02},
        "qa": {"min_ratio": 0.2, "min_penalty": 0.3, "max_ratio": 3.0, "max_penalty": 0.1},
        "default": {"min_ratio": 0.2, "min_penalty": 0.1, "max_ratio": 3.0, "max_penalty": 0.05},
    }

    THRESHOLDS = {
        "general": {
            "opposite_score": 0.28,
            "invalid_answer_score": 0.15,
            "number_zero_max": 0.75,
            "low_relevance_max": 0.60,
            "min_score": 0.12,
            "high_score_cap": 0.95,
            "high_score_factor": 0.99,
        },
        "qa": {
            "opposite_score": 0.05,
            "invalid_answer_score": 0.05,
            "invalid_answer_long_score": 0.15,
            "uncertainty_score": 0.25,
            "number_low_factor": 0.5,
            "number_low_threshold": 0.5,
            "low_relevance_factor": 0.3,
            "low_relevance_threshold": 0.2,
            "min_score": 0.0,
            "high_score_cap": 1.0,
            "high_score_factor": 1.0,
        },
        "default": {
            "opposite_score": 0.20,
            "invalid_answer_score": 0.10,
            "number_zero_max": 0.80,
            "low_relevance_max": 0.50,
            "min_score": 0.05,
            "high_score_cap": 0.99,
            "high_score_factor": 0.99,
        },
    }

    NUMBER_TOLERANCE_CONFIG = {
        "exact_match_threshold": 0.05,
        "partial_match_threshold": 0.3,
    }

    def calculate_fallback_score(
        self,
        user_input: str | None,
        expected_output: str,
        actual_output: str,
        evaluator_type: str = "default",
    ) -> float:
        if not actual_output or not expected_output:
            return 0.0

        if actual_output.strip() == expected_output.strip():
            return 1.0

        actual_stripped = actual_output.strip()

        if evaluator_type == "qa":
            if actual_stripped in ["不知道", "不清楚", "无法回答", "不了解", "", "不确定", "可能吧"]:
                return self.THRESHOLDS["qa"]["invalid_answer_score"]

            if any(phrase in actual_stripped for phrase in ["不知道", "不清楚", "无法回答", "不了解"]):
                if len(actual_stripped) < 15:
                    return self.THRESHOLDS["qa"]["invalid_answer_score"]
                else:
                    return self.THRESHOLDS["qa"]["invalid_answer_long_score"]

            if any(phrase in actual_stripped for phrase in self.UNCERTAINTY_PATTERNS):
                return self.THRESHOLDS["qa"]["uncertainty_score"]
        else:
            if actual_stripped.lower() in self.INVALID_ANSWERS:
                return self.THRESHOLDS[evaluator_type]["invalid_answer_score"]

        if text_analysis_service.detect_opposite_meaning(actual_output, expected_output):
            return self.THRESHOLDS[evaluator_type]["opposite_score"]

        text_similarity = text_analysis_service.calculate_text_similarity(expected_output, actual_output)
        answer_coverage = text_analysis_service.calculate_answer_coverage(actual_output, expected_output)
        question_relevance = (
            text_analysis_service.calculate_question_relevance(user_input, actual_output)
            if user_input
            else 0.9
        )

        number_match = self._calculate_number_match(expected_output, actual_output)

        len_ratio = len(actual_output) / max(len(expected_output), 1)
        length_penalty = self._calculate_length_penalty(len_ratio, evaluator_type)

        weights = self.SCORING_WEIGHTS[evaluator_type]

        if evaluator_type == "qa":
            actual_tokens = text_analysis_service.tokenize_chinese(actual_output)
            expected_tokens = text_analysis_service.tokenize_chinese(expected_output)

            if not expected_tokens:
                return 0.0

            overlap = actual_tokens & expected_tokens
            token_coverage = len(overlap) / len(expected_tokens)

            base_score = max(
                0.0,
                min(1.0, token_coverage - (1 - number_match) * 0.5 - length_penalty),
            )
            negative_penalty = self._detect_negative_inversion(actual_output, expected_output)
            base_score = max(0.0, base_score - negative_penalty)

            score = (
                base_score * weights["base_score"]
                + text_similarity * weights["text_similarity"]
                + answer_coverage * weights["answer_coverage"]
                + question_relevance * weights["question_relevance"]
            )

            thresholds = self.THRESHOLDS[evaluator_type]
            if number_match < thresholds["number_low_threshold"] and self._has_numbers(expected_output):
                score *= thresholds["number_low_factor"]
            if question_relevance < thresholds["low_relevance_threshold"]:
                score *= thresholds["low_relevance_factor"]

        else:
            score = (
                text_similarity * weights["text_similarity"]
                + answer_coverage * weights["answer_coverage"]
                + question_relevance * weights["question_relevance"]
                + number_match * weights["number_match"]
            )

            score = max(0.0, score - length_penalty)

            thresholds = self.THRESHOLDS[evaluator_type]
            if number_match == 0.0 and self._has_numbers(expected_output):
                score = min(score, thresholds["number_zero_max"])
            if question_relevance < 0.15:
                score = min(score, thresholds["low_relevance_max"])
            if score > thresholds["high_score_cap"]:
                score = score * thresholds["high_score_factor"]

        return round(max(thresholds["min_score"], min(1.0, score)), 4)

    def _calculate_number_match(self, expected: str, actual: str) -> float:
        expected_numbers = set(re.findall(r"\d+\.?\d*", expected))
        actual_numbers = set(re.findall(r"\d+\.?\d*", actual))

        if not expected_numbers:
            return 1.0

        matched_numbers = 0.0
        for exp_num in expected_numbers:
            try:
                exp_float = float(exp_num)
                for act_num in actual_numbers:
                    try:
                        act_float = float(act_num)
                        rel_diff = abs(exp_float - act_float) / max(abs(exp_float), 1e-9)
                        if rel_diff < self.NUMBER_TOLERANCE_CONFIG["exact_match_threshold"]:
                            matched_numbers += 1.0
                            break
                        elif rel_diff < self.NUMBER_TOLERANCE_CONFIG["partial_match_threshold"]:
                            matched_numbers += 0.5
                            break
                    except ValueError:
                        pass
            except ValueError:
                if exp_num in actual_numbers:
                    matched_numbers += 1.0

        return matched_numbers / len(expected_numbers)

    def _has_numbers(self, text: str) -> bool:
        return bool(re.search(r"\d+", text))

    def _calculate_length_penalty(self, len_ratio: float, evaluator_type: str) -> float:
        config = self.LENGTH_PENALTY_CONFIG[evaluator_type]
        if len_ratio < config["min_ratio"]:
            return config["min_penalty"]
        elif len_ratio > config["max_ratio"]:
            return config["max_penalty"]
        return 0.0

    def _detect_negative_inversion(self, actual: str, expected: str) -> float:
        negative_words = ["不", "没有", "无", "非", "否", "不是", "不会", "不能", "不可"]

        expected_has_negative = any(neg in expected for neg in negative_words)
        actual_has_negative = any(neg in actual for neg in negative_words)

        if expected_has_negative != actual_has_negative:
            return 0.3
        return 0.0

    def get_scoring_weights(self, evaluator_type: str) -> dict[str, float]:
        return self.SCORING_WEIGHTS.get(evaluator_type, self.SCORING_WEIGHTS["default"])

    def get_thresholds(self, evaluator_type: str) -> dict[str, float]:
        return self.THRESHOLDS.get(evaluator_type, self.THRESHOLDS["default"])


fallback_scoring_service = FallbackScoringService()
