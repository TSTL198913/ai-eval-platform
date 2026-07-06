"""
分类(Classification)评估器 - 2026 工业级标准重构版

用于评估分类系统的输出质量，包括：
- 标签准确性评估
- 置信度量化
- 边界情况处理

工业级特性：
- LLM-as-a-Judge 置信度评分
- 多维度文本相似度匹配（token重叠率、序列相似度、关键词覆盖率）
- 完整类型注解
- 降级链路统一交由基类 safe_evaluate 按 fallback_policy 处理
"""

import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import RuleBasedFallbackPolicy
from src.schemas.evaluation import DomainResponse
from src.schemas.evaluation import EvaluationSchema

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("classification")
class ClassificationEvaluator(BaseEvaluator):
    # 标签同义词映射：用于处理语义相近的标签
    LABEL_SYNONYMS = {
        "positive": ["positive", "正类", "正面", "积极", "正向", "是"],
        "negative": ["negative", "负类", "负面", "消极", "负向", "否"],
        "neutral": ["neutral", "中性", "中立"],
        "spam": ["spam", "垃圾", "广告", "骚扰"],
        "ham": ["ham", "正常", "合法"],
        "汽车": ["汽车", "轿车", "车辆", "车"],
        "手机": ["手机", "智能手机", "移动电话", "电话"],
        "电脑": ["电脑", "计算机", "笔记本", "台式机"],
        "电子产品": ["电子产品", "电子设备", "数码产品"],
        "服装": ["服装", "衣服", "服饰", "穿戴"],
        "食品": ["食品", "食物", "餐饮", "美食"],
        "体育": ["体育", "运动", "健身"],
        "娱乐": ["娱乐", "游戏", "休闲"],
        "新闻": ["新闻", "资讯", "消息"],
        "科技": ["科技", "技术", "互联网"],
        "健康": ["健康", "医疗", "养生"],
        "教育": ["教育", "学习", "培训"],
        "财经": ["财经", "金融", "经济"],
        "政治": ["政治", "政策", "政府"],
        "军事": ["军事", "国防", "军队"],
        "文化": ["文化", "艺术", "文艺"],
        "旅游": ["旅游", "旅行", "出行"],
        "音乐": ["音乐", "歌曲", "音频"],
        "电影": ["电影", "影视", "影片"],
        "书籍": ["书籍", "图书", "读物"],
    }

    def __init__(self, client=None):
        super().__init__(client, fallback_policy=RuleBasedFallbackPolicy(), require_input=True)

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        if error := self.validate_input(request):
            return error

        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        expected_label = self.get_payload_data(request, "expected_label")
        labels = self.get_payload_data(request, "labels", [])

        if not expected_label:
            return self.create_error_response(
                error_message="expected_label 不能为空",
                error_code="MISSING_EXPECTED_LABEL",
            )

        if not actual_output:
            return self.create_error_response(
                error_message="actual_output 不能为空",
                error_code="MISSING_ACTUAL_OUTPUT",
            )

        if self.client and hasattr(self.client, "chat"):
            labels_str = ", ".join(labels) if labels else "正类, 负类"

            prompt = self._build_evaluation_prompt(
                user_input, actual_output, expected_label, labels_str
            )

            llm_output = self.client.chat(prompt)
            score = self.safe_parse_score(llm_output)

            if score is None:
                logger.error(f"分类评估响应数字提取失败: '{llm_output}'")
                score = self._calculate_fallback_score(actual_output, expected_label, labels)
                return self.create_partial_response(
                    text=actual_output,
                    score=score,
                    dimensions_evaluated=["text_similarity"],
                    dimensions_skipped=["llm_judgment"],
                    skip_reasons={"llm_judgment": "LLM returned unparseable score"},
                    data={
                        "user_input": user_input,
                        "actual_output": actual_output,
                        "expected_label": expected_label,
                        "predicted_label": actual_output,
                        "all_labels": labels,
                        "raw_output": llm_output,
                        "evaluator": "classification",
                        "warning": "LLM评分解析失败，使用多维度文本相似度降级评分",
                    },
                    confidence=0.3,
                    evaluation_method="fallback",
                )

            return self.create_success_response(
                text=actual_output,
                score=score,
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_label": expected_label,
                    "predicted_label": actual_output,
                    "all_labels": labels,
                    "raw_output": llm_output,
                    "evaluator": "classification",
                },
                metadata={"mode": "llm_as_judge"},
            )
        else:
            score = self._calculate_fallback_score(actual_output, expected_label, labels)
            return self.create_partial_response(
                text=actual_output,
                score=score,
                dimensions_evaluated=["rule_based_classification"],
                dimensions_skipped=["llm_judgment"],
                skip_reasons={"llm_judgment": "LLM client not available"},
                data={
                    "user_input": user_input,
                    "actual_output": actual_output,
                    "expected_label": expected_label,
                    "predicted_label": actual_output,
                    "all_labels": labels,
                    "evaluator": "classification",
                    "warning": "LLM客户端不可用，使用规则降级评估",
                },
                confidence=0.4,
                evaluation_method="fallback",
            )

    def _build_evaluation_prompt(
        self, user_input: str, actual_output: str, expected_label: str, labels_str: str
    ) -> str:
        """构建分类评估 Prompt"""
        return (
            "你是一个严谨的分类评测专家。请评估以下分类结果的质量。\n"
            "评估标准：\n"
            "- 完全匹配期望标签：1.0分\n"
            "- 语义相近（如'汽车'与'轿车'）：0.7-0.9分\n"
            "- 部分相关（如'电子产品'与'手机'）：0.3-0.6分\n"
            "- 完全无关：0.0分\n"
            "输出一个 0.0 到 1.0 的分数。\n\n"
            f"【分类标签】：{labels_str}\n"
            f"【输入文本】：{user_input}\n"
            f"【期望标签】：{expected_label}\n"
            f"【实际分类】：{actual_output}\n\n"
            "最终评分（仅输出数字）："
        )

    def _calculate_fallback_score(
        self, actual_output: str, expected_label: str, labels: list
    ) -> float:
        """降级评分：基于多维度文本比较（标签实体提取、token重叠率、序列相似度、关键词覆盖率）

        评分层次：
        1. 精确匹配（含大小写归一化）→ 1.0
        2. 标签同义词匹配 → 0.8-0.9
        3. 标签实体提取匹配：从 actual_output 中提取候选标签实体再与 expected_label 比对
           - 提取到期望标签 → 1.0
           - 提取到其他候选标签 → 0.1（明确分类错误）
        4. expected_label 作为子串出现在 actual_output 中 → 0.8（强信号）
        5. 多维度文本相似度加权综合（连续值，处理部分匹配场景）
        """
        actual_lower = actual_output.lower().strip()
        expected_lower = expected_label.lower().strip()

        # 维度1：精确匹配（大小写归一化后整串相等）
        if actual_lower == expected_lower:
            return 1.0

        # 维度1.5：标签同义词匹配
        synonym_score = self._check_label_synonym(actual_output, expected_label)
        if synonym_score > 0:
            return synonym_score

        # 维度2：标签实体提取与匹配
        extracted_label = self._extract_label_from_output(actual_output, labels)
        if extracted_label is not None:
            if extracted_label.lower().strip() == expected_lower:
                return 1.0
            # 匹配到了候选标签中的其他标签，说明分类明确错误
            return 0.1

        # 维度3：expected_label 直接作为子串出现在 actual_output 中（强信号）
        if expected_lower and expected_lower in actual_lower:
            return 0.8

        # 维度4：多维度文本相似度综合评分（连续值）
        token_overlap = self._calculate_text_similarity(actual_output, expected_label)
        sequence_sim = self._calculate_sequence_similarity(actual_lower, expected_lower)
        keyword_coverage = self._calculate_keyword_coverage(actual_output, expected_label)

        # 加权综合：token重叠率(0.4) + 序列相似度(0.3) + 关键词覆盖率(0.3)
        combined_score = (
            token_overlap * 0.4
            + sequence_sim * 0.3
            + keyword_coverage * 0.3
        )

        return round(combined_score, 4)

    def _check_label_synonym(self, actual_output: str, expected_label: str) -> float:
        """检查实际输出与期望标签是否为同义词

        Returns:
            - 0.9：直接同义词匹配
            - 0.8：同属于一个标签组
            - 0.0：无同义词关系
        """
        actual_lower = actual_output.lower().strip()
        expected_lower = expected_label.lower().strip()

        for label_group, synonyms in self.LABEL_SYNONYMS.items():
            synonyms_lower = [s.lower() for s in synonyms]
            actual_in_group = actual_lower in synonyms_lower
            expected_in_group = expected_lower in synonyms_lower

            if actual_in_group and expected_in_group:
                if actual_lower == expected_lower:
                    return 1.0
                return 0.85

        return 0.0

    def _extract_label_from_output(self, actual_output: str, labels: list) -> str | None:
        """从 actual_output 中提取标签实体

        优先级：
        1. actual_output 本身就是某个候选标签 → 直接返回该标签
        2. actual_output 包含某个候选标签 → 返回该标签（按长度降序匹配，避免短标签误匹配）
        3. 无候选标签或均未命中 → 返回 None，交由多维度相似度评分

        Returns:
            提取到的标签字符串；未提取到时返回 None
        """
        actual_lower = actual_output.lower().strip()

        # 优先级1：actual_output 直接等于某个候选标签
        for label in labels:
            if actual_lower == label.lower().strip():
                return label

        # 优先级2：actual_output 包含某个候选标签
        # 按长度降序匹配，优先匹配长标签，避免短标签（如"正"）误匹配到长文本中
        sorted_labels = sorted(labels, key=len, reverse=True)
        for label in sorted_labels:
            label_lower = label.lower().strip()
            if label_lower and label_lower in actual_lower:
                return label

        return None

    def _calculate_sequence_similarity(self, actual: str, expected: str) -> float:
        """计算字符级序列相似度（基于最长公共子序列 LCS）

        相比纯子串匹配，LCS 能识别字符顺序一致但存在插入/删除的近似匹配。
        返回 0-1 的相似度分数，1 表示完全相同，0 表示无公共字符。
        """
        if not actual or not expected:
            return 0.0

        m, n = len(actual), len(expected)
        # 空间优化：仅保留两行，避免 O(m*n) 内存占用
        prev = [0] * (n + 1)
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if actual[i - 1] == expected[j - 1]:
                    curr[j] = prev[j - 1] + 1
                else:
                    curr[j] = max(prev[j], curr[j - 1])
            prev, curr = curr, prev
        lcs_len = prev[n]

        return lcs_len / max(m, n)

    def _calculate_keyword_coverage(self, actual: str, expected: str) -> float:
        """计算 expected 的关键词在 actual 中的覆盖率

        优先统计多字符关键词（≥2字符），单字符噪音大；若无多字符关键词则退化为全 token 覆盖率。
        返回 0-1 的覆盖率分数，1 表示所有关键词均被覆盖。
        """
        expected_tokens = self._tokenize_chinese(expected)
        if not expected_tokens:
            return 0.0

        actual_tokens = self._tokenize_chinese(actual)

        # 优先统计多字符关键词的覆盖率（单字符噪音大）
        expected_keywords = {t for t in expected_tokens if len(t) >= 2}
        if not expected_keywords:
            # 退化为全 token 覆盖率
            covered = expected_tokens & actual_tokens
            return len(covered) / len(expected_tokens)

        covered_keywords = expected_keywords & actual_tokens
        return len(covered_keywords) / len(expected_keywords)
