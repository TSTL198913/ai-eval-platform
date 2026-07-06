import re


class TextAnalysisService:
    NEGATION_PAIRS = [
        ("是", "不是"), ("有", "没有"), ("能", "不能"), ("会", "不会"),
        ("可以", "不可以"), ("应该", "不应该"), ("正确", "错误"),
        ("可行", "不可行"), ("好", "坏"), ("高", "低"), ("大", "小"),
        ("真", "假"), ("正", "负"), ("上", "下"), ("左", "右"),
        ("前", "后"), ("内", "外"), ("多", "少"), ("长", "短"),
        ("强", "弱"), ("快", "慢"), ("亮", "暗"), ("热", "冷"),
        ("喜欢", "讨厌"), ("满意", "不满意"), ("支持", "反对"),
        ("同意", "不同意"), ("成功", "失败"), ("安全", "危险"),
    ]

    ENTITY_REPLACEMENT_PAIRS = [
        ("特朗普", "拜登"), ("拜登", "特朗普"),
        ("北京", "上海"), ("上海", "北京"),
        ("北京", "广州"), ("广州", "北京"),
        ("上海", "深圳"), ("深圳", "上海"),
        ("中国", "美国"), ("美国", "中国"),
        ("中国", "日本"), ("日本", "中国"),
        ("苹果", "谷歌"), ("谷歌", "苹果"),
        ("腾讯", "阿里"), ("阿里", "腾讯"),
        ("华为", "小米"), ("小米", "华为"),
        ("张三", "李四"), ("李四", "张三"),
        ("男", "女"), ("女", "男"),
        ("正确", "错误"), ("错误", "正确"),
        ("可行", "不可行"), ("不可行", "可行"),
        ("好", "坏"), ("坏", "好"),
        ("高", "低"), ("低", "高"),
        ("大", "小"), ("小", "大"),
        ("真", "假"), ("假", "真"),
        ("珠江", "黄河"), ("黄河", "珠江"),
        ("长江", "黄河"), ("黄河", "长江"),
        ("珠江", "长江"), ("长江", "珠江"),
        ("太平洋", "大西洋"), ("大西洋", "太平洋"),
        ("太平洋", "印度洋"), ("印度洋", "太平洋"),
        ("泰山", "珠穆朗玛峰"), ("珠穆朗玛峰", "泰山"),
        ("泰山", "黄山"), ("黄山", "泰山"),
        ("亚洲", "欧洲"), ("欧洲", "亚洲"),
        ("亚洲", "非洲"), ("非洲", "亚洲"),
        ("北美洲", "南美洲"), ("南美洲", "北美洲"),
        ("太阳能", "风能"), ("风能", "太阳能"),
        ("可再生能源", "不可再生能源"), ("不可再生能源", "可再生能源"),
        ("市场经济", "计划经济"), ("计划经济", "市场经济"),
    ]

    OPPOSITE_PAIRS = [
        ("可行", "不可行"), ("可能", "不可能"), ("好", "坏"), ("好", "差"), ("好", "糟"),
        ("正确", "错误"), ("是", "不是"), ("有", "没有"), ("能", "不能"),
        ("高", "低"), ("多", "少"), ("大", "小"), ("长", "短"),
        ("对", "错"), ("是", "否"), ("正", "反"),
        ("积极", "消极"), ("正面", "负面"),
        ("增加", "减少"), ("上升", "下降"),
        ("成功", "失败"),
        ("喜欢", "讨厌"), ("喜欢", "不喜欢"),
        ("爱", "恨"), ("满意", "不满"), ("满意", "失望"),
        ("安全", "危险"), ("正常", "异常"),
        ("支持", "反对"), ("接受", "拒绝"),
        ("有效", "无效"), ("有用", "没用"),
        ("会", "不会"), ("可以", "不可以"),
        ("在", "不在"),
        ("快", "慢"), ("热", "冷"),
        ("出色", "一般"), ("出色", "差"), ("出色", "糟"), ("出色", "很差"),
        ("友好", "恶劣"), ("友好", "差"), ("友好", "冷淡"), ("友好", "冷漠"),
        ("迅速", "缓慢"), ("迅速", "慢"),
        ("合理", "不合理"), ("合理", "贵"), ("合理", "便宜"),
        ("完善", "不完善"), ("完善", "差"), ("完善", "弱"),
        ("强大", "弱"), ("强大", "差"), ("强大", "不足"),
        ("优良", "差"), ("优良", "糟"), ("优良", "很差"),
        ("优质", "差"), ("优质", "差"),
        ("清晰", "模糊"), ("清晰", "不清楚"),
        ("通俗易懂", "晦涩"), ("通俗易懂", "难懂"),
        ("便捷", "复杂"), ("便捷", "麻烦"),
        ("简单", "复杂"), ("简单", "麻烦"),
        ("方便", "不便"), ("方便", "麻烦"),
        ("准时", "迟到"), ("准时", "延误"),
        ("准时", "延迟"),
        ("准确", "错误"), ("准确", "不正确"),
        ("可靠", "不可靠"), ("可靠", "不稳定"),
        ("稳定", "不稳定"), ("稳定", "波动"),
        ("可靠", "不可靠"), ("可靠", "不稳定"),
        ("稳定", "不稳定"), ("稳定", "波动"),
    ]

    def tokenize_chinese(self, text: str) -> set[str]:
        tokens = set()
        for word in re.findall(r"[a-zA-Z]{2,}", text.lower()):
            tokens.add(word)
        for num in re.findall(r"\d+\.?\d*", text):
            tokens.add(num)
        for char in re.findall(r"[\u4e00-\u9fff]", text):
            tokens.add(char)
        chinese_segments = re.findall(r"[\u4e00-\u9fff]+", text)
        for segment in chinese_segments:
            for i in range(len(segment)):
                for j in range(i + 2, min(i + 6, len(segment) + 1)):
                    tokens.add(segment[i:j])
        return tokens

    def calculate_text_similarity(self, actual: str, expected: str) -> float:
        actual_tokens = self.tokenize_chinese(actual)
        expected_tokens = self.tokenize_chinese(expected)

        if not expected_tokens:
            return 0.0

        overlap = actual_tokens & expected_tokens

        expected_numbers = {t for t in expected_tokens if re.match(r"\d+\.?\d*", t)}
        actual_numbers = {t for t in actual_tokens if re.match(r"\d+\.?\d*", t)}

        for exp_num in expected_numbers:
            if exp_num not in overlap:
                try:
                    exp_float = float(exp_num)
                    for act_num in actual_numbers:
                        try:
                            act_float = float(act_num)
                            if abs(exp_float - act_float) / max(abs(exp_float), 1e-9) < 0.1:
                                overlap.add(exp_num)
                                break
                        except ValueError:
                            pass
                except ValueError:
                    pass

        if not overlap:
            return 0.0

        expected_long_words = {t for t in expected_tokens if len(t) >= 3}
        overlap_long_words = {t for t in overlap if len(t) >= 3}

        if expected_long_words:
            long_word_score = len(overlap_long_words) / len(expected_long_words)
        else:
            long_word_score = 1.0

        coverage = len(overlap) / len(expected_tokens)
        weighted_score = 0.6 * coverage + 0.4 * long_word_score

        expected_len = len(expected)
        actual_len = len(actual)
        if expected_len > 0:
            len_ratio = actual_len / expected_len
            if len_ratio < 0.2:
                weighted_score *= 0.5
            elif len_ratio > 3.0:
                weighted_score *= 0.7

        negation_count = 0
        for positive, negative in self.NEGATION_PAIRS:
            if positive in expected and negative in actual:
                negation_count += 1
            elif negative in expected and positive in actual:
                negation_count += 1

        if negation_count >= 2:
            weighted_score *= 0.1
        elif negation_count == 1:
            weighted_score *= 0.3

        return round(max(0.0, min(1.0, weighted_score)), 4)

    def detect_entity_replacement(self, evidence: str, actual_output: str) -> float:
        replacement_count = 0
        for entity_a, entity_b in self.ENTITY_REPLACEMENT_PAIRS:
            if entity_a in evidence and entity_b in actual_output and entity_a not in actual_output:
                replacement_count += 1

        if replacement_count >= 2:
            return 0.0
        elif replacement_count == 1:
            return 0.1

        evidence_tokens = self.tokenize_chinese(evidence)
        output_tokens = self.tokenize_chinese(actual_output)

        if not evidence_tokens:
            return 1.0

        replaced_count = 0
        total_important = 0

        evidence_multi_char = {t for t in evidence_tokens if len(t) >= 2}
        output_multi_char = {t for t in output_tokens if len(t) >= 2}

        for token in evidence_multi_char:
            total_important += 1
            if token not in output_multi_char:
                replaced_count += 1

        if total_important == 0:
            return 1.0

        replacement_ratio = replaced_count / total_important
        if replacement_ratio > 0.5:
            return 0.2
        elif replacement_ratio > 0.2:
            return 0.5
        else:
            return 1.0

    def detect_over_inference(self, evidence: str, actual_output: str) -> float:
        evidence_numbers = set(re.findall(r"\d+\.?\d*", evidence))
        output_numbers = set(re.findall(r"\d+\.?\d*", actual_output))

        extra_numbers = output_numbers - evidence_numbers
        if extra_numbers:
            has_close_match = False
            for extra_num in extra_numbers:
                try:
                    extra_float = float(extra_num)
                    for evidence_num in evidence_numbers:
                        try:
                            evidence_float = float(evidence_num)
                            if abs(extra_float - evidence_float) / max(abs(evidence_float), 1e-9) < 0.15:
                                has_close_match = True
                                break
                        except ValueError:
                            pass
                    if has_close_match:
                        break
                except ValueError:
                    pass
            if not has_close_match:
                return 0.0

        evidence_tokens = self.tokenize_chinese(evidence)
        output_tokens = self.tokenize_chinese(actual_output)

        evidence_multi_char = {t for t in evidence_tokens if len(t) >= 2}
        output_multi_char = {t for t in output_tokens if len(t) >= 2}

        extra_tokens = output_multi_char - evidence_multi_char

        if len(extra_tokens) > len(evidence_multi_char) * 0.5:
            return 0.3

        if len(extra_tokens) > len(evidence_multi_char) * 0.2:
            return 0.6

        return 1.0

    def detect_opposite_meaning(self, actual: str, expected: str) -> bool:
        """检测是否包含反义词含义

        修复：统一使用词边界正则匹配，避免"高血压"vs"低血压"被误判
        要求最小词长≥2，确保只有独立的词才被匹配
        """
        actual_lower = actual.lower()
        expected_lower = expected.lower()
        
        for word1, word2 in self.OPPOSITE_PAIRS:
            min_len = min(len(word1), len(word2))
            if min_len < 2:
                continue
            
            pattern1 = re.compile(r'(?:^|[^\u4e00-\u9fff])' + re.escape(word1) + r'(?:$|[^\u4e00-\u9fff])')
            pattern2 = re.compile(r'(?:^|[^\u4e00-\u9fff])' + re.escape(word2) + r'(?:$|[^\u4e00-\u9fff])')
            
            has_word1_in_actual = bool(pattern1.search(actual_lower))
            has_word2_in_actual = bool(pattern2.search(actual_lower))
            has_word1_in_expected = bool(pattern1.search(expected_lower))
            has_word2_in_expected = bool(pattern2.search(expected_lower))
            
            if (has_word1_in_actual and has_word2_in_expected) or (has_word2_in_actual and has_word1_in_expected):
                return True
        
        return False

    def calculate_answer_coverage(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0
        expected_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}", expected))
        actual_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}", actual))
        if not expected_keywords:
            return 0.0
        covered = expected_keywords & actual_keywords
        return len(covered) / len(expected_keywords)

    def calculate_question_relevance(self, question: str, answer: str) -> float:
        if not question or not answer:
            return 0.0
        question_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}", question))
        answer_keywords = set(re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}", answer))
        if not question_keywords:
            return 0.5
        stop_words = {"的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那",
                      "the", "a", "an", "is", "are", "of", "to", "and", "in", "for", "on", "with",
                      "什么", "怎么样", "如何", "多少", "哪里", "谁", "什么时候"}
        question_keywords = question_keywords - stop_words
        if not question_keywords:
            return 0.5
        matched = question_keywords & answer_keywords
        return len(matched) / len(question_keywords)


text_analysis_service = TextAnalysisService()