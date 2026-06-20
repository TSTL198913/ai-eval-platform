"""Memory 评估器 - RAG 检索准确性、记忆更新一致性、遗忘率评估"""

import difflib
import re

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("memory")
class MemoryEvaluator(BaseEvaluator):
    """Memory 评估器

    用于评估 RAG 系统的记忆检索能力，包括：
    - evaluate_retrieval: 检索准确性评估
    - evaluate_consistency: 记忆更新一致性评估
    - evaluate_forgetting: 遗忘率评估
    """

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "evaluate_retrieval")

        if action == "evaluate_retrieval":
            return self._evaluate_retrieval(request)
        elif action == "evaluate_consistency":
            return self._evaluate_consistency(request)
        elif action == "evaluate_forgetting":
            return self._evaluate_forgetting(request)
        else:
            return DomainResponse(
                is_valid=False,
                error=f"未知的 action: {action}，支持的 action: evaluate_retrieval, evaluate_consistency, evaluate_forgetting"
            )

    def _evaluate_retrieval(self, request: EvaluationSchema) -> DomainResponse:
        """评估 RAG 检索准确性"""
        query = self.get_input_text(request)
        retrieved_context = self.get_payload_data(request, "retrieved_context")
        expected_context = self.get_payload_data(request, "expected_context")
        ground_truth = self.get_payload_data(request, "ground_truth")

        if not query:
            return DomainResponse(is_valid=False, error="query/user_input/text 不能为空")

        if not retrieved_context:
            return DomainResponse(is_valid=False, error="retrieved_context 不能为空")

        # 计算检索相关性
        relevance_score = self._calculate_relevance(query, retrieved_context)

        # 计算上下文覆盖率
        coverage_score = 0.0
        if expected_context:
            coverage_score = self._calculate_coverage(retrieved_context, expected_context)

        # 计算事实一致性
        factual_score = 0.0
        if ground_truth:
            factual_score = self._calculate_factual_consistency(retrieved_context, ground_truth)

        # 综合得分
        if expected_context and ground_truth:
            final_score = relevance_score * 0.4 + coverage_score * 0.3 + factual_score * 0.3
        elif expected_context:
            final_score = relevance_score * 0.5 + coverage_score * 0.5
        elif ground_truth:
            final_score = relevance_score * 0.5 + factual_score * 0.5
        else:
            final_score = relevance_score

        retrieval_quality = self._get_quality_level(final_score)

        return DomainResponse(
            is_valid=True,
            text=f"检索评估完成，检索质量: {retrieval_quality}",
            score=final_score,
            data={
                "relevance_score": relevance_score,
                "coverage_score": coverage_score,
                "factual_score": factual_score,
                "retrieval_quality": retrieval_quality,
                "retrieval_acceptable": final_score >= 0.7,
            },
        )

    def _evaluate_consistency(self, request: EvaluationSchema) -> DomainResponse:
        """评估记忆更新一致性"""
        old_memory = self.get_payload_data(request, "old_memory")
        new_memory = self.get_payload_data(request, "new_memory")
        update_intent = self.get_payload_data(request, "update_intent")

        if not old_memory or not new_memory:
            return DomainResponse(is_valid=False, error="old_memory 和 new_memory 不能为空")

        # 计算内容变化程度
        change_score = self._calculate_similarity(old_memory, new_memory)

        # 检测是否有信息丢失
        info_loss = self._detect_information_loss(old_memory, new_memory)

        # 检测是否有信息矛盾
        contradiction = self._detect_contradiction(old_memory, new_memory)

        # 计算一致性得分
        if info_loss or contradiction:
            consistency_score = change_score * 0.5
        else:
            consistency_score = change_score

        # 如果有更新意图，检测是否遵循了意图
        intent_following_score = 1.0
        if update_intent:
            intent_following_score = self._evaluate_intent_following(
                old_memory, new_memory, update_intent
            )
            consistency_score = consistency_score * 0.7 + intent_following_score * 0.3

        consistency_level = self._get_consistency_level(consistency_score)

        return DomainResponse(
            is_valid=True,
            text=f"一致性评估完成，一致性级别: {consistency_level}",
            score=consistency_score,
            data={
                "change_score": change_score,
                "info_loss_detected": info_loss,
                "contradiction_detected": contradiction,
                "intent_following_score": intent_following_score,
                "consistency_level": consistency_level,
                "consistency_acceptable": consistency_score >= 0.7,
            },
        )

    def _evaluate_forgetting(self, request: EvaluationSchema) -> DomainResponse:
        """评估遗忘率"""
        original_memory = self.get_payload_data(request, "original_memory")
        current_memory = self.get_payload_data(request, "current_memory")
        important_facts = self.get_payload_data(request, "important_facts", [])

        if not original_memory or not current_memory:
            return DomainResponse(is_valid=False, error="original_memory 和 current_memory 不能为空")

        # 计算记忆保留度
        retention_score = self._calculate_similarity(original_memory, current_memory)

        # 计算遗忘率
        forgetting_rate = 1.0 - retention_score

        # 检测重要事实的遗忘情况
        fact_retention_scores = []
        if important_facts:
            for fact in important_facts:
                fact_retention = self._check_fact_retention(fact, current_memory)
                fact_retention_scores.append(fact_retention)

            avg_fact_retention = sum(fact_retention_scores) / len(fact_retention_scores)
        else:
            avg_fact_retention = retention_score

        forgetting_level = self._get_forgetting_level(forgetting_rate)

        return DomainResponse(
            is_valid=True,
            text=f"遗忘率评估完成，遗忘级别: {forgetting_level}",
            score=1.0 - forgetting_rate,  # 得分越高越好
            data={
                "retention_score": retention_score,
                "forgetting_rate": forgetting_rate,
                "fact_retention_scores": fact_retention_scores,
                "avg_fact_retention": avg_fact_retention,
                "forgetting_level": forgetting_level,
                "forgetting_acceptable": forgetting_rate <= 0.3,
            },
        )

    def _calculate_relevance(self, query: str, context: str) -> float:
        """计算查询与检索上下文的相关性"""
        query_keywords = set(self._extract_keywords(query))
        context_keywords = set(self._extract_keywords(context))

        if not query_keywords:
            return 0.5

        overlap = len(query_keywords & context_keywords)
        return min(1.0, overlap / len(query_keywords))

    def _calculate_coverage(self, retrieved: str, expected: str) -> float:
        """计算上下文覆盖率"""
        expected_keywords = set(self._extract_keywords(expected))
        retrieved_keywords = set(self._extract_keywords(retrieved))

        if not expected_keywords:
            return 1.0

        overlap = len(expected_keywords & retrieved_keywords)
        return overlap / len(expected_keywords)

    def _calculate_factual_consistency(self, context: str, ground_truth: str) -> float:
        """计算事实一致性"""
        context_nums = set(re.findall(r'\d+\.?\d*', context))
        truth_nums = set(re.findall(r'\d+\.?\d*', ground_truth))

        if not truth_nums:
            return 0.5

        num_match = len(context_nums & truth_nums) / len(truth_nums)

        # 检查关键实体的一致性
        context_entities = set(re.findall(r'[A-Z][a-z]+', context))
        truth_entities = set(re.findall(r'[A-Z][a-z]+', ground_truth))

        if not truth_entities:
            entity_match = 0.5
        else:
            entity_match = len(context_entities & truth_entities) / len(truth_entities)

        return (num_match + entity_match) / 2

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """使用 difflib.SequenceMatcher 计算相似度"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _detect_information_loss(self, old: str, new: str) -> bool:
        """检测信息丢失"""
        old_keywords = set(self._extract_keywords(old))
        new_keywords = set(self._extract_keywords(new))

        if not old_keywords:
            return False

        # 超过30%的旧关键词在新版本中消失，认为有信息丢失
        lost_keywords = old_keywords - new_keywords
        loss_ratio = len(lost_keywords) / len(old_keywords)

        return loss_ratio > 0.3

    def _detect_contradiction(self, old: str, new: str) -> bool:
        """检测矛盾"""
        contradiction_pairs = [
            ("是", "不是"),
            ("有", "没有"),
            ("能", "不能"),
            ("对", "错"),
            ("真", "假"),
            ("是", "非"),
            ("yes", "no"),
            ("true", "false"),
            ("can", "cannot"),
            ("have", "have not"),
        ]

        old_lower = old.lower()
        new_lower = new.lower()

        for pos, neg in contradiction_pairs:
            pos_count_old = old_lower.count(pos)
            neg_count_old = old_lower.count(neg)
            pos_count_new = new_lower.count(pos)
            neg_count_new = new_lower.count(neg)

            # 检测语义反转
            if pos_count_old > 0 and neg_count_old == 0:
                if neg_count_new > 0:
                    return True
            elif neg_count_old > 0 and pos_count_old == 0:
                if pos_count_new > 0:
                    return True

        return False

    def _evaluate_intent_following(
        self, old: str, new: str, intent: str
    ) -> float:
        """评估是否遵循更新意图"""
        intent_lower = intent.lower()

        # 扩展意图检测
        add_keywords = ["添加", "新增", "增加", "扩展", "补充", "add", "new", "insert", "expand"]
        remove_keywords = ["删除", "移除", "去掉", "清除", "remove", "delete", "clear"]
        modify_keywords = ["修改", "更新", "改变", "调整", "修改", "modify", "update", "change", "revise"]

        # 检测意图类型
        intent_type = None
        for kw in add_keywords:
            if kw in intent_lower:
                intent_type = "add"
                break
        if not intent_type:
            for kw in remove_keywords:
                if kw in intent_lower:
                    intent_type = "remove"
                    break
        if not intent_type:
            for kw in modify_keywords:
                if kw in intent_lower:
                    intent_type = "modify"
                    break

        if not intent_type:
            return 0.5  # 无法判断

        old_keywords = set(self._extract_keywords(old))
        new_keywords = set(self._extract_keywords(new))

        if intent_type == "add":
            # 检查是否添加了新内容
            added = new_keywords - old_keywords
            if added:
                return min(1.0, len(added) / 3)  # 至少添加3个新关键词
            return 0.0

        elif intent_type == "remove":
            # 检查是否删除了内容
            removed = old_keywords - new_keywords
            if removed:
                return min(1.0, len(removed) / 3)
            return 0.0

        else:  # modify
            # 检查是否有变化
            common = old_keywords & new_keywords
            if common:
                return min(1.0, len(common) / max(len(old_keywords), 1))
            return 0.5

    def _check_fact_retention(self, fact: str, memory: str) -> float:
        """检查单个事实在记忆中的保留程度"""
        fact_keywords = set(self._extract_keywords(fact))
        memory_keywords = set(self._extract_keywords(memory))

        if not fact_keywords:
            return 1.0

        overlap = len(fact_keywords & memory_keywords)
        return overlap / len(fact_keywords)

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词，包含中英文停用词过滤"""
        import re
        words = re.findall(r"\b[a-zA-Z\u4e00-\u9fff]{2,}\b", text.lower())

        # 中英文停用词
        stop_words = {
            # 中文停用词
            "的", "是", "在", "有", "和", "了", "我", "你", "他", "她", "它", "这", "那",
            "很", "也", "都", "要", "会", "可以", "能", "不", "没", "好", "就", "对", "说",
            "看", "想", "去", "来", "上", "下", "大", "小", "多", "少", "一", "二", "三",
            "四", "五", "六", "七", "八", "九", "十", "个", "位", "名", "本", "页", "条",
            "种", "类", "们", "等", "及", "与", "或", "但", "而", "因为", "所以", "如果",
            "虽然", "但是", "什么", "怎么", "为什么", "哪里", "多少", "谁", "哪个", "这个",
            "那个", "这些", "那些", "被", "把", "给", "让", "从", "向", "到", "为", "以",
            # 英文停用词
            "this", "that", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "up", "about", "into", "over", "after", "and", "but", "or",
            "as", "if", "when", "than", "because", "while", "although", "though",
            "which", "who", "whom", "what", "how", "where", "why",
            "a", "an", "the", "its", "they", "their", "them", "he", "she", "him",
            "her", "his", "i", "me", "my", "we", "us", "our", "you", "your",
        }

        return [w for w in words if w not in stop_words][:20]

    def _get_quality_level(self, score: float) -> str:
        """获取检索质量级别"""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.8:
            return "good"
        elif score >= 0.6:
            return "fair"
        elif score >= 0.4:
            return "poor"
        else:
            return "very_poor"

    def _get_consistency_level(self, score: float) -> str:
        """获取一致性级别"""
        if score >= 0.9:
            return "highly_consistent"
        elif score >= 0.7:
            return "consistent"
        elif score >= 0.5:
            return "somewhat_consistent"
        elif score >= 0.3:
            return "inconsistent"
        else:
            return "highly_inconsistent"

    def _get_forgetting_level(self, rate: float) -> str:
        """获取遗忘级别"""
        if rate <= 0.1:
            return "none"
        elif rate <= 0.2:
            return "low"
        elif rate <= 0.4:
            return "medium"
        elif rate <= 0.6:
            return "high"
        else:
            return "critical"
