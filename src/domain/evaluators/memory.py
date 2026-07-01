"""Memory 评估器 - RAG 检索准确性、记忆更新一致性、遗忘率评估"""

import difflib
import logging

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.domain.evaluators.fallback_policy import SemanticTaskPolicy
from src.schemas.evaluation import DomainResponse, EvaluationSchema, EvaluatorStatus

logger = logging.getLogger(__name__)


@EvaluatorFactory.register("memory")
class MemoryEvaluator(BaseEvaluator):
    """Memory 评估器

    用于评估 RAG 系统的记忆检索能力，包括：
    - evaluate_retrieval: 检索准确性评估
    - evaluate_consistency: 记忆更新一致性评估
    - evaluate_forgetting: 遗忘率评估
    """

    def __init__(self, client=None):
        super().__init__(client)
        self.fallback_policy = SemanticTaskPolicy()

    def _do_evaluate(self, request: EvaluationSchema) -> DomainResponse:
        action = self.get_payload_data(request, "action", "evaluate_retrieval")

        if action == "evaluate_retrieval":
            return self._evaluate_retrieval(request)
        elif action == "evaluate_consistency":
            return self._evaluate_consistency(request)
        elif action == "evaluate_forgetting":
            return self._evaluate_forgetting(request)
        else:
            return self.create_error_response(
                error_message=f"未知的 action: {action}，支持的 action: evaluate_retrieval, evaluate_consistency, evaluate_forgetting",
                error_code="INVALID_ACTION",
            )

    def _evaluate_retrieval(self, request: EvaluationSchema) -> DomainResponse:
        """评估 RAG 检索准确性"""
        query = self.get_input_text(request)
        retrieved_context = self.get_payload_data(request, "retrieved_context")
        expected_context = self.get_payload_data(request, "expected_context")
        ground_truth = self.get_payload_data(request, "ground_truth")

        if not query:
            return self.create_error_response(
                error_message="query/user_input/text 不能为空",
                error_code="MISSING_QUERY",
            )

        if not retrieved_context:
            return self.create_error_response(
                error_message="retrieved_context 不能为空",
                error_code="MISSING_CONTEXT",
            )

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

        evaluated_dims = ["relevance"]
        skipped_dims = []
        if expected_context:
            evaluated_dims.append("coverage")
        else:
            skipped_dims.append("coverage")
        if ground_truth:
            evaluated_dims.append("factual_consistency")
        else:
            skipped_dims.append("factual_consistency")

        if skipped_dims:
            return self.create_partial_response(
                text=f"检索评估完成（部分维度），检索质量: {retrieval_quality}",
                score=final_score,
                dimensions_evaluated=evaluated_dims,
                dimensions_skipped=skipped_dims,
                skip_reasons={
                    "coverage": "缺少 expected_context" if "coverage" in skipped_dims else None,
                    "factual_consistency": "缺少 ground_truth" if "factual_consistency" in skipped_dims else None,
                },
                data={
                    "relevance_score": relevance_score,
                    "coverage_score": coverage_score,
                    "factual_score": factual_score,
                    "retrieval_quality": retrieval_quality,
                    "retrieval_acceptable": final_score >= 0.7,
                },
            )

        return self.create_success_response(
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
            return self.create_error_response(
                error_message="old_memory 和 new_memory 不能为空",
                error_code="MISSING_MEMORY_DATA",
            )

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
        evaluated_dims = ["change_detection", "info_loss", "contradiction"]
        skipped_dims = []
        if update_intent:
            intent_following_score = self._evaluate_intent_following(
                old_memory, new_memory, update_intent
            )
            consistency_score = consistency_score * 0.7 + intent_following_score * 0.3
            evaluated_dims.append("intent_following")
        else:
            skipped_dims.append("intent_following")

        consistency_level = self._get_consistency_level(consistency_score)

        if skipped_dims:
            return self.create_partial_response(
                text=f"一致性评估完成（部分维度），一致性级别: {consistency_level}",
                score=consistency_score,
                dimensions_evaluated=evaluated_dims,
                dimensions_skipped=skipped_dims,
                skip_reasons={
                    "intent_following": "缺少 update_intent" if "intent_following" in skipped_dims else None,
                },
                data={
                    "change_score": change_score,
                    "info_loss_detected": info_loss,
                    "contradiction_detected": contradiction,
                    "intent_following_score": intent_following_score,
                    "consistency_level": consistency_level,
                    "consistency_acceptable": consistency_score >= 0.7,
                },
            )

        return self.create_success_response(
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
            return self.create_error_response(
                error_message="original_memory 和 current_memory 不能为空",
                error_code="MISSING_MEMORY_DATA",
            )

        # 计算记忆保留度
        retention_score = self._calculate_similarity(original_memory, current_memory)

        # 计算遗忘率
        forgetting_rate = 1.0 - retention_score

        # 检测重要事实的遗忘情况
        fact_retention_scores = []
        avg_fact_retention = retention_score
        evaluated_dims = ["retention"]
        skipped_dims = []

        if important_facts:
            for fact in important_facts:
                fact_retention = self._check_fact_retention(fact, current_memory)
                fact_retention_scores.append(fact_retention)

            avg_fact_retention = sum(fact_retention_scores) / len(fact_retention_scores)
            evaluated_dims.append("important_facts")
        else:
            skipped_dims.append("important_facts")

        forgetting_level = self._get_forgetting_level(forgetting_rate)

        if skipped_dims:
            return self.create_partial_response(
                text=f"遗忘率评估完成（部分维度），遗忘级别: {forgetting_level}",
                score=1.0 - forgetting_rate,
                dimensions_evaluated=evaluated_dims,
                dimensions_skipped=skipped_dims,
                skip_reasons={
                    "important_facts": "缺少 important_facts" if "important_facts" in skipped_dims else None,
                },
                data={
                    "retention_score": retention_score,
                    "forgetting_rate": forgetting_rate,
                    "fact_retention_scores": fact_retention_scores,
                    "avg_fact_retention": avg_fact_retention,
                    "forgetting_level": forgetting_level,
                    "forgetting_acceptable": forgetting_rate <= 0.3,
                },
            )

        return self.create_success_response(
            text=f"遗忘率评估完成，遗忘级别: {forgetting_level}",
            score=1.0 - forgetting_rate,
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
        """计算查询与检索上下文的相关性

        支持三种模式（优先级从高到低）：
        1. 如果有 LLM 客户端，使用语义相关性计算
        2. 否则使用 Embedding 向量相似度（禁止降级为字符相似度）
        3. 最后使用增强的关键词匹配 + TF-IDF 加权
        """
        # 尝试使用 LLM 进行语义相关性计算
        if self.client:
            try:
                semantic_score = self._calculate_semantic_relevance(query, context)
                if semantic_score is not None:
                    return semantic_score
            except Exception as e:
                logger.warning(f"LLM 语义相关性计算失败，降级至 Embedding: {e}")

        # 尝试使用 Embedding 向量相似度
        try:
            embedding_score = self.fallback_policy.get_fallback_score(query, context)
            if embedding_score is not None:
                return embedding_score
        except Exception as e:
            logger.warning(f"Embedding 相似度计算失败，降级至关键词匹配: {e}")

        # 增强的关键词匹配方法
        query_keywords = set(self._extract_keywords(query))
        context_keywords = set(self._extract_keywords(context))

        if not query_keywords:
            return 0.5

        # 基础关键词重叠率
        overlap = len(query_keywords & context_keywords)
        base_score = overlap / len(query_keywords)

        # 计算 TF-IDF 加权分数
        tfidf_score = self._calculate_tfidf_score(query, context)

        # 计算词序相似度
        order_score = self._calculate_word_order_similarity(query, context)

        # 综合评分：基础重叠(40%) + TF-IDF(30%) + 词序(30%)
        final_score = base_score * 0.4 + tfidf_score * 0.3 + order_score * 0.3

        return min(1.0, final_score)

    def _calculate_semantic_relevance(self, query: str, context: str) -> float | None:
        """使用 LLM 计算语义相关性"""
        if not self.client:
            return None

        try:
            prompt = f"""请评估以下查询与上下文的相关性，返回0到1之间的分数。
分数标准：
- 1.0: 完全相关，上下文直接回答了查询
- 0.7-0.9: 高度相关，上下文包含查询所需的大部分信息
- 0.4-0.6: 部分相关，上下文包含一些相关信息
- 0.1-0.3: 低度相关，上下文与查询关联较弱
- 0.0: 完全不相关

查询: {query}

上下文: {context[:2000]}  # 限制长度

请只返回分数数字，不要返回其他内容。"""

            response = self.client.generate(prompt)
            if response and response.text:
                # 提取分数
                import re

                score_match = re.search(r"(\d+\.?\d*)", response.text)
                if score_match:
                    score = float(score_match.group(1))
                    return min(1.0, max(0.0, score))
        except Exception as e:
            logger.warning(f"LLM 语义相关性计算失败: {e}")

        return None

    def _calculate_tfidf_score(self, query: str, context: str) -> float:
        """计算标准TF-IDF加权相似度

        修复：原实现仅使用词频(TF)归一化，未考虑逆文档频率(IDF)，
        导致常见词（如"的"、"是"）权重与稀有词相同，相关性评分精度不足。

        标准TF-IDF公式：tfidf(t,d) = tf(t,d) * log(N/df(t)+1)
        其中N为文档总数，df(t)为包含词t的文档数。
        在检索场景中，我们使用查询词在上下文中覆盖度作为相关度。
        """
        import math
        from collections import Counter

        query_words = self._extract_keywords(query)
        context_words = self._extract_keywords(context)

        if not query_words or not context_words:
            return 0.0

        # 计算词频
        Counter(query_words)
        context_tf = Counter(context_words)

        total_context_words = len(context_words)
        if total_context_words == 0:
            return 0.0

        # 修复：使用标准TF-IDF公式
        # 在单文档场景下，将context视为唯一文档，N=1
        # IDF: log((N+1)/(df+1)) + 1，避免log(0)
        N = 1  # 单一文档场景
        unique_query_words = set(query_words)

        weighted_sum = 0.0
        for word in unique_query_words:
            if word in context_tf:
                # TF: 词在上下文中的归一化频率
                tf = context_tf[word] / total_context_words
                # IDF: 逆文档频率（单文档场景下使用平滑公式）
                # 在多文档场景下应使用真实文档频率
                idf = math.log((N + 1) / (1 + 1)) + 1  # 平滑后的IDF
                weighted_sum += tf * idf

        # 归一化：将得分归一化到[0, 1]
        max_tfidf = sum(
            1.0 * (math.log((N + 1) / 2) + 1) / total_context_words for _ in unique_query_words
        )
        if max_tfidf > 0:
            return min(1.0, weighted_sum / max_tfidf)
        return 0.0

    def _calculate_word_order_similarity(self, query: str, context: str) -> float:
        """计算词序相似度"""
        query_words = self._extract_keywords(query)
        context_words = self._extract_keywords(context)

        if not query_words or not context_words:
            return 0.0

        query_keyword_set = set(query_words)
        context_keyword_set = set(context_words)

        if not (query_keyword_set & context_keyword_set):
            return 0.0

        consecutive_count = 0
        total_pairs = 0

        for i in range(len(query_words) - 1):
            word1, word2 = query_words[i], query_words[i + 1]
            if word1 in context_keyword_set and word2 in context_keyword_set:
                total_pairs += 1
                idx1 = context_words.index(word1)
                idx2 = context_words.index(word2)
                if abs(idx1 - idx2) <= 2:
                    consecutive_count += 1

        if total_pairs == 0:
            return 0.5

        return consecutive_count / total_pairs

    def _calculate_coverage(self, retrieved: str, expected: str) -> float:
        """计算上下文覆盖率 - 使用语义相似度"""
        try:
            embedding_score = self.fallback_policy.get_fallback_score(retrieved, expected)
            if embedding_score is not None:
                return embedding_score
        except Exception:
            pass

        expected_keywords = set(self._extract_keywords(expected))
        retrieved_keywords = set(self._extract_keywords(retrieved))

        if not expected_keywords:
            return 1.0

        if not retrieved_keywords:
            return 0.0

        overlap = len(expected_keywords & retrieved_keywords)
        return overlap / len(expected_keywords)

    def _calculate_factual_consistency(self, context: str, ground_truth: str) -> float:
        """计算事实一致性 - 扩展版本

        检测多种事实类型：
        1. 数字一致性（日期、金额、数量等）
        2. 命名实体一致性（人名、地名、组织名等）
        3. 时间一致性（日期、时间范围）
        4. 关键陈述一致性
        5. 语义一致性（使用 Embedding 或 LLM）
        """
        scores = []

        # 1. 数字一致性检测
        num_score = self._check_number_consistency(context, ground_truth)
        scores.append(("number", num_score, 0.25))

        # 2. 命名实体一致性检测
        entity_score = self._check_entity_consistency(context, ground_truth)
        scores.append(("entity", entity_score, 0.25))

        # 3. 时间一致性检测
        time_score = self._check_time_consistency(context, ground_truth)
        scores.append(("time", time_score, 0.15))

        # 4. 关键陈述一致性检测
        statement_score = self._check_statement_consistency(context, ground_truth)
        scores.append(("statement", statement_score, 0.15))

        # 5. 语义一致性（优先使用 LLM，否则使用 Embedding）
        if self.client:
            semantic_score = self._check_semantic_consistency(context, ground_truth)
            if semantic_score is not None:
                scores.append(("semantic", semantic_score, 0.20))
        else:
            try:
                embedding_score = self.fallback_policy.get_fallback_score(context, ground_truth)
                if embedding_score is not None:
                    scores.append(("semantic", embedding_score, 0.20))
            except Exception:
                pass

        # 加权平均
        total_weight = sum(weight for _, _, weight in scores)
        weighted_sum = sum(score * weight for _, score, weight in scores)
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.5

        return final_score

    def _check_number_consistency(self, context: str, ground_truth: str) -> float:
        """检测数字一致性"""
        import re

        # 提取所有数字（包括小数、百分比、金额等）
        context_nums = set(re.findall(r"\d+\.?\d*%?", context))
        truth_nums = set(re.findall(r"\d+\.?\d*%?", ground_truth))

        if not truth_nums:
            return 0.5  # 无数字时返回中性值

        if not context_nums:
            return 0.0  # 真值有数字但上下文没有

        # 计算匹配率
        matched = len(context_nums & truth_nums)
        return matched / len(truth_nums)

    def _check_entity_consistency(self, context: str, ground_truth: str) -> float:
        """检测命名实体一致性"""
        import re

        # 提取中文人名（2-4个字的中文词）
        context_names = set(re.findall(r"[\u4e00-\u9fff]{2,4}", context))
        truth_names = set(re.findall(r"[\u4e00-\u9fff]{2,4}", ground_truth))

        # 提取英文专有名词（首字母大写的词）
        context_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", context))
        truth_entities = set(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", ground_truth))

        # 提取关键词（小写）作为补充
        context_keywords = set(self._extract_keywords(context))
        truth_keywords = set(self._extract_keywords(ground_truth))

        # 合并实体和关键词
        all_context_entities = context_names | context_entities | context_keywords
        all_truth_entities = truth_names | truth_entities | truth_keywords

        if not all_truth_entities:
            return 0.5  # 无实体时返回中性值

        if not all_context_entities:
            return 0.0

        # 计算匹配率
        matched = len(all_context_entities & all_truth_entities)
        return matched / len(all_truth_entities)

    def _check_time_consistency(self, context: str, ground_truth: str) -> float:
        """检测时间一致性"""
        import re

        # 时间模式：日期、时间范围
        time_patterns = [
            r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?",  # 2024-01-15 或 2024年1月15日
            r"\d{1,2}[-/月]\d{1,2}[日]?",  # 1月15日
            r"\d{4}年",  # 2024年
            r"\d{1,2}:\d{2}(?::\d{2})?",  # 时间 14:30:00
            r"(?:上午|下午|早上|晚上|中午)\d{1,2}[点时]?",  # 上午9点
        ]

        context_times = set()
        truth_times = set()

        for pattern in time_patterns:
            context_times.update(re.findall(pattern, context))
            truth_times.update(re.findall(pattern, ground_truth))

        if not truth_times:
            return 0.5  # 无时间信息时返回中性值

        if not context_times:
            return 0.0

        matched = len(context_times & truth_times)
        return matched / len(truth_times)

    def _check_statement_consistency(self, context: str, ground_truth: str) -> float:
        """检测关键陈述一致性"""
        # 提取关键陈述（以句号分隔的句子）
        context_sentences = {s.strip() for s in context.split("。") if s.strip()}
        truth_sentences = {s.strip() for s in ground_truth.split("。") if s.strip()}

        # 同时支持英文句号
        context_sentences.update(s.strip() for s in context.split(".") if s.strip())
        truth_sentences.update(s.strip() for s in ground_truth.split(".") if s.strip())

        if not truth_sentences:
            return 0.5

        if not context_sentences:
            return 0.0

        # 计算句子级别的相似度
        matched_count = 0
        for truth_sent in truth_sentences:
            for context_sent in context_sentences:
                # 使用 difflib 计算句子相似度
                similarity = difflib.SequenceMatcher(None, truth_sent, context_sent).ratio()
                if similarity >= 0.8:  # 相似度阈值
                    matched_count += 1
                    break

        return matched_count / len(truth_sentences)

    def _check_semantic_consistency(self, context: str, ground_truth: str) -> float | None:
        """使用 LLM 检测语义一致性"""
        if not self.client:
            return None

        try:
            prompt = f"""请评估以下两段文本的语义一致性，返回0到1之间的分数。
分数标准：
- 1.0: 完全一致，表达相同的事实和含义
- 0.7-0.9: 高度一致，核心事实相同，表述略有差异
- 0.4-0.6: 部分一致，部分事实相同，存在差异
- 0.1-0.3: 低度一致，事实存在明显差异
- 0.0: 完全不一致，事实矛盾

文本1: {context[:1500]}

文本2: {ground_truth[:1500]}

请只返回分数数字，不要返回其他内容。"""

            response = self.client.generate(prompt)
            if response and response.text:
                import re

                score_match = re.search(r"(\d+\.?\d*)", response.text)
                if score_match:
                    score = float(score_match.group(1))
                    return min(1.0, max(0.0, score))
        except Exception as e:
            logger.warning(f"LLM 语义相关性计算失败: {e}")

        return None

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度，优先使用 Embedding 向量相似度"""
        try:
            embedding_score = self.fallback_policy.get_fallback_score(text1, text2)
            if embedding_score is not None:
                return embedding_score
        except Exception:
            pass

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

    def _evaluate_intent_following(self, old: str, new: str, intent: str) -> float:
        """评估是否遵循更新意图"""
        intent_lower = intent.lower()

        # 扩展意图检测
        add_keywords = ["添加", "新增", "增加", "扩展", "补充", "add", "new", "insert", "expand"]
        remove_keywords = ["删除", "移除", "去掉", "清除", "remove", "delete", "clear"]
        modify_keywords = [
            "修改",
            "更新",
            "改变",
            "调整",
            "修改",
            "modify",
            "update",
            "change",
            "revise",
        ]

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
            "的",
            "是",
            "在",
            "有",
            "和",
            "了",
            "我",
            "你",
            "他",
            "她",
            "它",
            "这",
            "那",
            "很",
            "也",
            "都",
            "要",
            "会",
            "可以",
            "能",
            "不",
            "没",
            "好",
            "就",
            "对",
            "说",
            "看",
            "想",
            "去",
            "来",
            "上",
            "下",
            "大",
            "小",
            "多",
            "少",
            "一",
            "二",
            "三",
            "四",
            "五",
            "六",
            "七",
            "八",
            "九",
            "十",
            "个",
            "位",
            "名",
            "本",
            "页",
            "条",
            "种",
            "类",
            "们",
            "等",
            "及",
            "与",
            "或",
            "但",
            "而",
            "因为",
            "所以",
            "如果",
            "虽然",
            "但是",
            "什么",
            "怎么",
            "为什么",
            "哪里",
            "多少",
            "谁",
            "哪个",
            "这个",
            "那个",
            "这些",
            "那些",
            "被",
            "把",
            "给",
            "让",
            "从",
            "向",
            "到",
            "为",
            "以",
            # 英文停用词
            "this",
            "that",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "need",
            "dare",
            "ought",
            "used",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "up",
            "about",
            "into",
            "over",
            "after",
            "and",
            "but",
            "or",
            "as",
            "if",
            "when",
            "than",
            "because",
            "while",
            "although",
            "though",
            "which",
            "who",
            "whom",
            "what",
            "how",
            "where",
            "why",
            "a",
            "an",
            "the",
            "its",
            "they",
            "their",
            "them",
            "he",
            "she",
            "him",
            "her",
            "his",
            "i",
            "me",
            "my",
            "we",
            "us",
            "our",
            "you",
            "your",
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
