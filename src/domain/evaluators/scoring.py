import re
from difflib import SequenceMatcher

PASS_THRESHOLD = 0.8


def score_numeric_match(output: str, expected: str | None) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    expected_nums = re.findall(r"-?\d+\.?\d*", expected)
    if expected_nums:
        matched = sum(1 for num in expected_nums if num in output)
        return matched / len(expected_nums)

    return 1.0 if expected.lower() in output.lower() else 0.0


def score_text_similarity(output: str, expected: str | None) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    output_lower = output.lower()
    expected_lower = expected.lower()

    if output_lower == expected_lower:
        return 1.0

    expected_chars = list(expected_lower)
    matched = 0
    all_matched = True
    
    for char in output_lower:
        if char in expected_chars:
            matched += 1
            expected_chars.remove(char)
        else:
            all_matched = False

    if all_matched:
        return 1.0
    return matched / len(output_lower) if len(output_lower) > 0 else 0.0


def score_keyword_overlap(output: str, expected: str | None) -> float:
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    def tokenize(text):
        tokens = []
        i = 0
        while i < len(text):
            if '\u4e00' <= text[i] <= '\u9fff':
                tokens.append(text[i])
                i += 1
            else:
                match = re.match(r'[a-zA-Z0-9]+', text[i:])
                if match:
                    tokens.append(match.group())
                    i += match.end()
                else:
                    i += 1
        return tokens

    expected_tokens = set(tokenize(expected.lower()))
    output_tokens = set(tokenize(output.lower()))
    if not expected_tokens:
        return 1.0 if expected.lower() in output.lower() else 0.0

    matched = output_tokens & expected_tokens
    return len(matched) / len(expected_tokens)


def is_passing(score: float, threshold: float = PASS_THRESHOLD) -> bool:
    return score >= threshold
