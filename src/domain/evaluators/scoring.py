"""
📊 src/domain/evaluators/scoring.py
纯内存计分与文本分析工具箱（纯 CPU 密集型计算，严禁引入 async）
"""

import re

PASS_THRESHOLD = 0.8

# 否定词集合（用于语义反转检测）
NEGATION_WORDS = {
    "不",
    "不是",
    "没有",
    "无",
    "非",
    "未",
    "别",
    "莫",
    "勿",
    "never",
    "not",
    "no",
    "none",
    "nothing",
    "nobody",
    "neither",
    "cannot",
    "can't",
    "won't",
    "wouldn't",
    "shouldn't",
    "don't",
    "didn't",
}


def tokenize_chinese_english(text: str) -> list[str]:
    """分词核心逻辑：中文按字切分，英文/数字按单词切分"""
    tokens = []
    i = 0
    while i < len(text):
        if "\u4e00" <= text[i] <= "\u9fff":
            tokens.append(text[i])
            i += 1
        else:
            match = re.match(r"[a-zA-Z0-9]+", text[i:])
            if match:
                tokens.append(match.group())
                i += match.end()
            else:
                i += 1
    return tokens


def tokenize_words(text: str, min_len: int = 2) -> list[str]:
    """轻量级分词：提取英文单词和中文字符，并过滤极短 token"""
    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return [w for w in words if len(w) > min_len]


def score_numeric_match(output: str, expected: str | None) -> float:
    """提取文本中的所有数字并比对匹配率"""
    if not output.strip():
        return 0.0
    if not expected:
        return 1.0

    expected_nums = re.findall(r"-?\d+\.?\d*", expected)
    if expected_nums:
        matched = sum(1 for num in expected_nums if num in output)
        return float(matched / len(expected_nums))

    return 1.0 if expected.lower() in output.lower() else 0.0


def score_text_similarity(output: str, expected: str | None) -> float:
    """
    基于字符集合的 Jaccard 相似度计算

    改进：增加否定词检测，识别语义反转
    例如："这是一个好产品" vs "这不是一个好产品" 会降低相似度

    Args:
        output: 实际输出文本
        expected: 期望输出文本

    Returns:
        相似度分数 (0.0 - 1.0)
    """
    if expected is None:
        return 1.0

    output_stripped = output.strip()
    expected_stripped = expected.strip()

    if not output_stripped and not expected_stripped:
        return 1.0
    if not output_stripped or not expected_stripped:
        return 0.0

    output_lower = output.lower()
    expected_lower = expected.lower()

    if output_lower == expected_lower:
        return 1.0

    output_chars = set(output_lower)
    expected_chars = set(expected_lower)

    intersection = len(output_chars & expected_chars)
    union = len(output_chars | expected_chars)

    if union == 0:
        return 1.0

    similarity = float(intersection / union)

    # 语义反转检测：如果一方有否定词而另一方没有，降低相似度
    output_has_negation = any(word in output_lower for word in NEGATION_WORDS)
    expected_has_negation = any(word in expected_lower for word in NEGATION_WORDS)

    if output_has_negation != expected_has_negation:
        similarity = max(0.0, similarity - 0.5)

    return similarity


def score_keyword_overlap(output: str, expected: str | None) -> float:
    """计算预期的关键词在实际输出中的覆盖率"""
    if expected is None:
        return 1.0

    output_stripped = output.strip()
    expected_stripped = expected.strip()

    if not output_stripped and not expected_stripped:
        return 1.0
    if not output_stripped or not expected_stripped:
        return 0.0

    expected_tokens = set(tokenize_chinese_english(expected.lower()))
    output_tokens = set(tokenize_chinese_english(output.lower()))
    if not expected_tokens:
        return 1.0 if expected.lower() in output.lower() else 0.0

    matched = output_tokens & expected_tokens
    return float(len(matched) / len(expected_tokens))


def is_passing(score: float, threshold: float = PASS_THRESHOLD) -> bool:
    """判定分数是否达标"""
    return score >= threshold


# ==================== 🚀 标准指标桥接层（2026 工业级） ====================


def score_bleu(output: str, expected: str | None, max_n: int = 4) -> float:
    """使用行业标准 BLEU 指标评估翻译/生成质量

    委托给 standard_metrics.BLEUMetric，支持 sacrebleu 缺失时降级。
    """
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import BLEUMetric

    metric = BLEUMetric(max_n=max_n)
    return metric.compute(output, expected)


def score_rouge(output: str, expected: str | None, rouge_type: str = "rougeL") -> float:
    """使用行业标准 ROUGE 指标评估摘要/生成质量"""
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import ROUGEMetric

    metric = ROUGEMetric(rouge_type=rouge_type)
    return metric.compute(output, expected)


def score_f1_token(output: str, expected: str | None) -> float:
    """使用 F1-Token 指标评估事实一致性（QA 任务推荐）"""
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import F1TokenMetric

    metric = F1TokenMetric()
    return metric.compute(output, expected)


def score_levenshtein(output: str, expected: str | None) -> float:
    """使用编辑距离相似度评估精确匹配（短文本推荐）"""
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import LevenshteinMetric

    metric = LevenshteinMetric()
    return metric.compute(output, expected)


def score_cosine_similarity(output: str, expected: str | None) -> float:
    """使用 Embedding 余弦相似度评估语义一致性"""
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import CosineSimilarityMetric

    metric = CosineSimilarityMetric()
    return metric.compute(output, expected)


def score_with_metric(output: str, expected: str | None, metric_name: str) -> float:
    """统一指标调度入口：通过名称调用标准指标

    Args:
        output: 实际输出
        expected: 期望输出
        metric_name: 指标名称（BLEU-4/ROUGE-L/F1-Token/Levenshtein/CosineSimilarity 等）

    Returns:
        float: 0-1 区间的标准化分数
    """
    if expected is None:
        return 1.0
    from src.domain.metrics.standard_metrics import get_metric

    metric = get_metric(metric_name)
    if metric is None:
        # 未知指标：降级到 Jaccard 相似度
        return score_text_similarity(output, expected)
    return metric.compute(output, expected)


def compute_all_standard_metrics(output: str, expected: str | None) -> dict[str, float]:
    """一键计算所有标准指标（用于综合报告生成）

    Returns:
        dict: {指标名: 分数}
    """
    if expected is None:
        return {}
    from src.domain.metrics.standard_metrics import compute_standard_metrics

    return compute_standard_metrics(output, expected)
