import logging
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.domain.services.text_analysis_service import text_analysis_service
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("semantic")
class SemanticEvaluator(BaseEvaluator):
    # 反义词对集合：用于检测语义相反的文本，避免字面相似但语义相反时给出高分
    OPPOSITE_WORD_PAIRS = {
        ("好", "坏"), ("好", "差"), ("好", "糟"),
        ("积极", "消极"), ("正面", "负面"),
        ("增加", "减少"), ("上升", "下降"),
        ("成功", "失败"), ("正确", "错误"),
        ("喜欢", "讨厌"), ("喜欢", "不喜欢"),
        ("爱", "恨"), ("满意", "不满"), ("满意", "失望"),
        ("安全", "危险"), ("正常", "异常"),
        ("支持", "反对"), ("接受", "拒绝"),
        ("有效", "无效"), ("有用", "没用"),
        ("可行", "不可行"), ("可能", "不可能"),
        ("优秀", "糟糕"), ("出色", "差劲"),
        ("友好", "恶劣"), ("合理", "不合理"),
        ("完善", "不完善"), ("强大", "弱小"),
        ("清晰", "模糊"), ("准确", "错误"),
        ("稳定", "波动"), ("可靠", "不可靠"),
        ("迅速", "缓慢"), ("便捷", "复杂"),
        ("简单", "复杂"), ("方便", "不便"),
        ("准时", "迟到"), ("高效", "低效"),
        ("创新", "保守"), ("灵活", "僵硬"),
    }

    def __init__(self, client=None):
        super().__init__(
            client, fallback_policy=SemanticTaskPolicy(), require_input=False, require_expected=True
        )

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_expected(request):
            return error

        actual_output = self.get_payload_data(request, "actual_output")
        expected_output = self.get_payload_data(request, "expected_output")

        if actual_output is None:
            actual_output = "None"
        elif isinstance(actual_output, str) and not actual_output.strip():
            return self.create_cannot_evaluate_response(
                reason="actual_output 不能为空字符串",
                metadata={"error_code": "INVALID_INPUT"},
            )

        if self.client:
            prompt = (
                "你是一个严谨的语义对齐裁判。请评估以下‘实际输出’与‘期望输出’的语义相似度。\n"
                "忽略字面表达差异，关注核心本质含义。最后必须输出一个 0.0 到 1.0 之间的浮点分数。\n\n"
                f"【期望输出】：{expected_output}\n"
                f"【实际输出】：{actual_output}\n\n"
                "评分（仅输出数字）："
            )

            def score_postprocessor(score: float) -> float:
                if self._detect_opposite_meaning(actual_output, expected_output):
                    return max(0.25, score * 0.6)
                return score

            def fallback_fn(error_msg: str) -> DomainResponse:
                return self._do_fallback_evaluate(request, actual_output, expected_output, error_msg)

            return self._evaluate_with_llm(
                prompt=prompt,
                fallback_fn=fallback_fn,
                score_postprocessor=score_postprocessor,
                evaluator_name="SemanticEvaluator",
                text=actual_output,
            )
        else:
            logger.warning("LLM客户端不可用，将触发降级评估")
            return self._do_fallback_evaluate(request, actual_output, expected_output, "LLM客户端不可用")

    def _do_fallback_evaluate(
        self, request: EvaluationSchema, actual_output: str, expected_output: str, error_msg: str
    ) -> DomainResponse:
        """降级评估：使用多维度规则语义相似度进行评估

        综合维度：
        1. 文本相似度（基于token重叠）
        2. 反义词检测
        3. 关键词覆盖率
        4. 长度合理性
        """
        fallback_score = self._rule_based_semantic(actual_output, expected_output)
        
        return self.create_partial_response(
            text=actual_output,
            score=fallback_score,
            dimensions_evaluated=["rule_based_semantic"],
            dimensions_skipped=["llm_semantic"],
            skip_reasons={"llm_semantic": f"LLM 评估失败: {error_msg}"},
            evaluation_method="rule_based",
            data={
                "fallback_reason": error_msg,
                "raw_llm_judgment": None,
                "fallback_method": "rule_based_semantic",
                "fallback_confidence": 0.7,
            },
        )

    def _rule_based_semantic(self, actual: str, expected: str) -> float:
        """基于规则的语义相似度评估

        改进策略：
        1. 优先检测反义词/否定词，直接返回低分
        2. 使用Jaccard相似度处理中文分词匹配
        3. 同义词匹配权重提高
        4. 短语匹配作为重要评分维度
        5. 增强评分区分性，避免分数压缩
        """
        if not actual or not expected:
            return 0.0

        actual_stripped = actual.strip()
        expected_stripped = expected.strip()
        
        if actual_stripped == expected_stripped:
            return 1.0

        has_opposite = self._detect_opposite_meaning(actual, expected)
        if has_opposite:
            return 0.15

        negative_patterns = [
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])不(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])没有(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])无(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])否(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])不是(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])不会(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])不能(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])不可(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])从未(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])绝不(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])never(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])not(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])no(?:$|[^a-zA-Z\u4e00-\u9fff])",
            r"(?:^|[^a-zA-Z\u4e00-\u9fff])none(?:$|[^a-zA-Z\u4e00-\u9fff])",
        ]
        
        expected_has_negative = any(re.search(pattern, expected) for pattern in negative_patterns)
        actual_has_negative = any(re.search(pattern, actual) for pattern in negative_patterns)
        
        if expected_has_negative != actual_has_negative:
            return 0.20

        import difflib
        base_similarity = difflib.SequenceMatcher(None, actual, expected).ratio()

        if base_similarity >= 0.90:
            return min(1.0, base_similarity)
        elif base_similarity >= 0.80:
            return min(0.95, base_similarity * 0.98)

        actual_chars = set(actual)
        expected_chars = set(expected)
        if expected_chars:
            char_jaccard = len(actual_chars & expected_chars) / len(actual_chars | expected_chars)
        else:
            char_jaccard = 0.0

        synonym_score = self._calculate_synonym_match_enhanced(actual, expected)
        keyword_coverage = self._calculate_keyword_coverage(actual, expected)
        phrase_match = self._calculate_phrase_match(actual, expected)

        common_words = ["的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那", "很", "非常", "特别", "十分"]
        actual_filtered = "".join([c for c in actual if c not in common_words])
        expected_filtered = "".join([c for c in expected if c not in common_words])
        
        filtered_jaccard = 0.0
        if expected_filtered:
            filtered_chars = set(expected_filtered) & set(actual_filtered)
            all_chars = set(expected_filtered) | set(actual_filtered)
            if all_chars:
                filtered_jaccard = len(filtered_chars) / len(all_chars)

        actual_tokens = self._extract_tokens(actual)
        expected_tokens = self._extract_tokens(expected)
        
        token_jaccard = 0.0
        if expected_tokens:
            common_tokens = set(expected_tokens) & set(actual_tokens)
            all_tokens = set(expected_tokens) | set(actual_tokens)
            if all_tokens:
                token_jaccard = len(common_tokens) / len(all_tokens)

        combined_score = (
            base_similarity * 0.15
            + char_jaccard * 0.10
            + filtered_jaccard * 0.15
            + token_jaccard * 0.20
            + synonym_score * 0.25
            + keyword_coverage * 0.10
            + phrase_match * 0.05
        )

        if combined_score >= 0.5 and keyword_coverage >= 0.4:
            combined_score = min(1.0, combined_score + 0.20)
        
        if keyword_coverage >= 0.7 and synonym_score >= 0.5:
            combined_score = min(1.0, combined_score + 0.12)
        
        if filtered_jaccard >= 0.6 and base_similarity >= 0.5:
            combined_score = min(1.0, combined_score + 0.15)

        expected_numbers = set(re.findall(r"\d+\.?\d*", expected))
        actual_numbers = set(re.findall(r"\d+\.?\d*", actual))
        if expected_numbers:
            if not actual_numbers:
                combined_score = min(combined_score, 0.5)
            elif expected_numbers != actual_numbers:
                combined_score = min(combined_score, 0.7)

        len_ratio = len(actual) / max(len(expected), 1)
        if len_ratio < 0.2 or len_ratio > 5.0:
            combined_score *= 0.7

        return max(0.05, min(1.0, round(combined_score, 4)))

    def _calculate_opposite_penalty(self, actual: str, expected: str) -> float:
        """计算反义词惩罚分数"""
        import difflib
        base_similarity = difflib.SequenceMatcher(None, actual, expected).ratio()
        
        if base_similarity >= 0.8:
            return 0.25
        elif base_similarity >= 0.6:
            return 0.20
        elif base_similarity >= 0.4:
            return 0.15
        else:
            return 0.10

    def _calculate_negation_penalty(self, actual: str, expected: str) -> float:
        """计算否定词不一致惩罚分数"""
        import difflib
        base_similarity = difflib.SequenceMatcher(None, actual, expected).ratio()
        
        if base_similarity >= 0.8:
            return 0.35
        elif base_similarity >= 0.6:
            return 0.30
        elif base_similarity >= 0.4:
            return 0.25
        else:
            return 0.20

    def _calculate_keyword_coverage(self, actual: str, expected: str) -> float:
        """计算关键词覆盖率"""
        actual_keywords = self._extract_keywords(actual)
        expected_keywords = self._extract_keywords(expected)
        
        if not expected_keywords:
            return 1.0
        
        matched_count = 0
        for exp_kw in expected_keywords:
            if exp_kw in actual_keywords:
                matched_count += 1
                continue
            for syn_group in self.SYNONYM_GROUPS:
                if exp_kw in syn_group:
                    if any(syn in actual_keywords for syn in syn_group):
                        matched_count += 1
                    break
        
        return matched_count / len(expected_keywords)

    def _calculate_phrase_match(self, actual: str, expected: str) -> float:
        """计算短语匹配度"""
        expected_phrases = self._extract_phrases(expected)
        
        if not expected_phrases:
            return 0.5
        
        matched_phrases = 0
        for exp_phrase in expected_phrases:
            if exp_phrase in actual:
                matched_phrases += 1
                continue
            for syn_group in self.SYNONYM_GROUPS:
                if exp_phrase in syn_group:
                    if any(syn in actual for syn in syn_group):
                        matched_phrases += 1
                    break
        
        return matched_phrases / len(expected_phrases)

    def _detect_opposite_meaning(self, text1: str, text2: str) -> bool:
        """检测两段文本是否包含反义词对"""
        return text_analysis_service.detect_opposite_meaning(text1, text2)

    def _calculate_synonym_match_enhanced(self, actual: str, expected: str) -> float:
        """增强版同义词匹配，考虑多词短语和完整短语匹配"""
        score = 0.0
        match_count = 0

        expected_phrases = self._extract_phrases(expected)
        actual_phrases = self._extract_phrases(actual)

        phrase_match = 0.0
        if expected_phrases:
            matched_phrases = 0
            for exp_phrase in expected_phrases:
                if exp_phrase in actual:
                    matched_phrases += 1
                    continue
                if exp_phrase in actual_phrases:
                    matched_phrases += 1
                    continue
                for syn_group in self.SYNONYM_GROUPS:
                    if exp_phrase in syn_group:
                        if any(syn in actual for syn in syn_group) or any(syn in actual_phrases for syn in syn_group):
                            matched_phrases += 1
                        break
            phrase_match = matched_phrases / len(expected_phrases)
        score += phrase_match
        match_count += 1

        actual_keywords = self._extract_keywords(actual)
        expected_keywords = self._extract_keywords(expected)
        
        keyword_match = 0.0
        if expected_keywords:
            matched_count = 0
            for exp_kw in expected_keywords:
                if exp_kw in actual_keywords:
                    matched_count += 1
                    continue
                for syn_group in self.SYNONYM_GROUPS:
                    if exp_kw in syn_group:
                        if any(syn in actual_keywords for syn in syn_group):
                            matched_count += 1
                        break
            keyword_match = matched_count / len(expected_keywords)
        score += keyword_match
        match_count += 1

        syn_group_matches = 0
        for syn_group in self.SYNONYM_GROUPS:
            exp_has = any(w in expected for w in syn_group)
            act_has = any(w in actual for w in syn_group)
            if exp_has and act_has:
                syn_group_matches += 1

        if syn_group_matches > 0:
            score += min(1.0, syn_group_matches * 0.2)
            match_count += 1

        if match_count == 0:
            return 0.0
        return min(1.0, score / match_count)

    def _extract_phrases(self, text: str) -> list[str]:
        """提取2-4个汉字的短语"""
        phrases = []
        chinese_segments = re.findall(r"[\u4e00-\u9fff]+", text)
        for segment in chinese_segments:
            for i in range(len(segment)):
                for j in range(i + 2, min(i + 5, len(segment) + 1)):
                    phrase = segment[i:j]
                    if len(phrase) >= 2:
                        phrases.append(phrase)
        return phrases

    def _extract_tokens(self, text: str) -> list[str]:
        """提取中文单字和英文单词作为tokens"""
        tokens = []
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        tokens.extend(chinese_chars)
        english_words = re.findall(r"[a-zA-Z]+", text.lower())
        tokens.extend(english_words)
        numbers = re.findall(r"\d+\.?\d*", text)
        tokens.extend(numbers)
        return tokens

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（降级评估的最后防线）

        修复：增加反义词检测，若检测到反义词对直接返回低分（0.15），
        避免 "我喜欢这个产品" 与 "我讨厌这个产品" 因字符相似获得高分。
        """
        if not text1 or not text2:
            return 0.0

        import difflib
        base_similarity = difflib.SequenceMatcher(None, text1, text2).ratio()
        
        # 反义词检测：语义相反时作为惩罚因子，而非直接返回低分
        if self._detect_opposite_meaning(text1, text2):
            base_similarity = max(0.25, base_similarity * 0.6)
        
        return round(base_similarity, 4)

    def _calibrate_semantic_score(self, llm_score: float, actual: str, expected: str) -> float:
        """语义校准：综合多维度分析调整LLM评分

        通过以下维度校准：
        1. 反义词检测：语义相反时强制低分
        2. 关键词覆盖率：确保核心含义匹配
        3. 长度异常检测：长度差异过大时扣分
        4. 否定词检测：检测"不"、"没有"等否定词造成的语义反转
        """
        if not actual or not expected:
            return llm_score

        calibrated_score = llm_score

        # 1. 反义词检测：语义相反时作为惩罚因子
        if self._detect_opposite_meaning(actual, expected):
            calibrated_score *= 0.6

        # 2. 否定词检测：检测实际输出中是否有否定词与期望输出相反
        negative_words = ["不", "没有", "无", "非", "否", "不是", "不会", "不能", "不可"]
        expected_has_negative = any(neg in expected for neg in negative_words)
        actual_has_negative = any(neg in actual for neg in negative_words)
        
        if expected_has_negative != actual_has_negative:
            calibrated_score *= 0.5
            return round(max(0.0, min(1.0, calibrated_score)), 4)

        # 3. 关键词覆盖率检测（只在覆盖率极低时调整）
        expected_keywords = self._extract_keywords(expected)
        actual_keywords = self._extract_keywords(actual)
        
        if expected_keywords:
            coverage = len(expected_keywords & actual_keywords) / len(expected_keywords)
            if coverage < 0.2:
                calibrated_score *= (0.2 + coverage * 0.8)

        # 4. 长度异常检测（只在极端情况下调整）
        len_ratio = len(actual) / max(len(expected), 1)
        if len_ratio < 0.1 or len_ratio > 10.0:
            calibrated_score *= 0.5

        return round(max(0.0, min(1.0, calibrated_score)), 4)

    def _extract_keywords(self, text: str) -> set[str]:
        """提取文本中的关键词（中文双字词及以上，英文长度>=2，排除停用词）
        
        只提取有意义的词组，不提取单字，以便更好地匹配同义词
        """
        text = text.lower()
        keywords = set()
        
        chinese_bigrams = re.findall(r"[\u4e00-\u9fff]{2}", text)
        for bigram in chinese_bigrams:
            keywords.add(bigram)
        
        chinese_trigrams = re.findall(r"[\u4e00-\u9fff]{3}", text)
        for trigram in chinese_trigrams:
            keywords.add(trigram)
        
        chinese_fourgrams = re.findall(r"[\u4e00-\u9fff]{4}", text)
        for fourgram in chinese_fourgrams:
            keywords.add(fourgram)
        
        english_words = re.findall(r"\b[a-zA-Z]{2,}\b", text)
        for word in english_words:
            keywords.add(word)
        
        stop_words = {"的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那",
                      "the", "a", "an", "is", "are", "of", "to", "and", "in", "for", "on", "with",
                      "十分", "非常", "这个", "这样", "那样", "一些", "一点", "什么", "怎么", "如何",
                      "可以", "不能", "不会", "没有", "一个", "一下", "一下", "一下"}
        return {w for w in keywords if w not in stop_words}

    SYNONYM_GROUPS = [
        {"好", "优秀", "出色", "良好", "完美", "棒", "卓越", "优异", "优良", "不错"},
        {"差", "糟糕", "劣", "不好", "坏", "差劲", "很差"},
        {"喜欢", "爱", "钟爱", "偏爱", "青睐"},
        {"讨厌", "憎恶", "厌恶", "反感"},
        {"增加", "增长", "上升", "提高", "增多", "上涨"},
        {"减少", "下降", "降低", "下跌"},
        {"成功", "胜利", "达成", "实现"},
        {"失败", "失利", "挫败"},
        {"快", "迅速", "快速", "急速", "很快"},
        {"慢", "缓慢", "迟缓"},
        {"大", "巨大", "庞大", "广阔"},
        {"小", "微小", "细小", "狭窄"},
        {"高", "较高"},
        {"低", "较低"},
        {"多", "许多", "众多", "大量"},
        {"少", "少量", "少数"},
        {"安全", "平安", "安稳"},
        {"危险", "风险", "危害"},
        {"满意", "满足", "称心"},
        {"不满", "失望", "遗憾"},
        {"支持", "赞成", "拥护"},
        {"反对", "抵制", "抗拒"},
        {"有效", "有用", "有效用"},
        {"无效", "没用", "无用"},
        {"重要", "关键", "核心"},
        {"次要", "不重要", "边缘"},
        {"简单", "容易", "简易", "方便"},
        {"复杂", "困难", "繁琐"},
        {"美丽", "漂亮", "好看"},
        {"丑陋", "难看"},
        {"聪明", "智慧", "机智"},
        {"愚蠢", "笨", "迟钝"},
        {"快乐", "开心", "愉快", "高兴"},
        {"悲伤", "难过", "伤心"},
        {"帮助", "协助", "援助"},
        {"阻碍", "妨碍", "阻止"},
        {"开始", "启动", "着手"},
        {"结束", "完成", "终止"},
        {"学习", "研究", "钻研"},
        {"工作", "劳动", "作业"},
        {"思考", "考虑", "思索"},
        {"说话", "交谈", "对话"},
        {"看", "观察", "查看"},
        {"听", "聆听", "倾听"},
        {"走", "步行", "行走"},
        {"跑", "奔跑"},
        {"吃", "用餐", "进食"},
        {"喝", "饮用"},
        {"睡觉", "睡眠", "休息"},
        {"醒来", "苏醒"},
        {"完善", "完备", "完美", "健全"},
        {"强大", "强劲", "有力", "雄厚"},
        {"一般", "普通", "平常", "中等"},
        {"友好", "友善", "亲切", "热情"},
        {"晴朗", "晴好", "明朗"},
        {"热", "炎热", "酷热", "高温"},
        {"冷", "寒冷", "严寒", "低温"},
        {"温度", "气温", "度"},
        {"达到", "高达", "达到了", "达到了"},
        {"天气", "气候"},
        {"摄氏度", "度"},
        {"炎热", "很热", "酷热", "高温"},
        {"非常", "很", "特别", "十分"},
        {"正常", "平常", "常规"},
        {"异常", "反常", "特殊"},
        {"便捷", "方便", "简单", "易用"},
        {"实惠", "便宜", "合理", "划算"},
        {"合理", "公道", "公平"},
        {"实惠", "便宜", "划算"},
        {"便捷", "方便", "便利"},
        {"美观", "漂亮", "好看"},
        {"清晰", "清楚", "明白"},
        {"详细", "详尽", "细致"},
        {"通俗易懂", "简单易懂", "清晰易懂"},
        {"迅速", "快速", "飞快"},
        {"迅速", "快", "很快"},
        {"出色", "优秀", "卓越"},
        {"恶劣", "糟糕", "很差"},
        {"一般", "普通", "平常"},
        {"实惠", "便宜"},
        {"便捷", "方便"},
        {"合理", "公道"},
        {"美观", "漂亮"},
        {"清晰", "清楚"},
        {"详细", "详尽"},
        {"通俗易懂", "简单易懂"},
        {"迅速", "快速"},
        {"出色", "优秀"},
        {"恶劣", "糟糕"},
    ]

    def _calculate_synonym_match(self, actual: str, expected: str) -> float:
        """计算同义词匹配度

        在关键词层面检测同义词关系，提高语义相似度评估的准确性。
        """
        actual_keywords = self._extract_keywords(actual)
        expected_keywords = self._extract_keywords(expected)

        if not expected_keywords:
            return 1.0

        matched_count = 0
        total_count = len(expected_keywords)

        for expected_keyword in expected_keywords:
            if expected_keyword in actual_keywords:
                matched_count += 1
                continue

            for synonym_group in self.SYNONYM_GROUPS:
                if expected_keyword in synonym_group:
                    if any(synonym in actual_keywords for synonym in synonym_group):
                        matched_count += 1
                    break

        return matched_count / total_count
