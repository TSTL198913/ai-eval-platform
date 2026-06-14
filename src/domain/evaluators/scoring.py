import re
from difflib import SequenceMatcher
from typing import Optional

PASS_THRESHOLD = 0.8


def score_numeric_match(output: str, expected: Optional[str]) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    expected_nums = re.findall(r"\d+\.?\d*", expected)
    if expected_nums:
        matched = sum(1 for num in expected_nums if num in output)
        return matched / len(expected_nums)

    return 1.0 if expected.lower() in output.lower() else 0.0


def score_text_similarity(output: str, expected: Optional[str]) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    ratio = SequenceMatcher(None, output.lower(), expected.lower()).ratio()
    keyword_score = score_keyword_overlap(output, expected)
    return max(ratio, keyword_score)


def score_keyword_overlap(output: str, expected: Optional[str]) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    expected_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", expected.lower()))
    output_tokens = set(re.findall(r"[\w\u4e00-\u9fff]+", output.lower()))
    if not expected_tokens:
        return 1.0 if expected.lower() in output.lower() else 0.0

    matched = expected_tokens & output_tokens
    return len(matched) / len(expected_tokens)


def is_passing(score: float, threshold: float = PASS_THRESHOLD) -> bool:
    return score >= threshold
