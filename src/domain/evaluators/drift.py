import difflib
import hashlib
import re
import time

from src.domain.evaluators.base import BaseEvaluator
from src.domain.evaluators.evaluator_factory import EvaluatorFactory
from src.infra.db.repository import EvaluationRepository
from src.schemas.evaluation import DomainResponse, EvaluationSchema


@EvaluatorFactory.register("drift")
class DriftDetectionEvaluator(BaseEvaluator):
    """行为漂移检测评估器

    检测 Agent 输出随时间的变化，识别模型行为漂移。
    使用方法：
    - 基于历史基准分数对比
    - 基于输出文本相似度对比
    - 基于多维度指标变化检测
    """

    def __init__(self, client=None):
        super().__init__(client)
        self.repository = EvaluationRepository()

    def evaluate(self, request: EvaluationSchema) -> DomainResponse:
        user_input = self.get_input_text(request)
        actual_output = self.get_payload_data(request, "actual_output")
        baseline_output = self.get_payload_data(request, "baseline_output")
        case_id = self.get_payload_data(request, "case_id", request.id)

        if not user_input:
            return DomainResponse(is_valid=False, error="user_input/text 不能为空")

        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        detection_methods = self.get_payload_data(
            request, "methods", ["similarity", "score_comparison", "statistical"]
        )

        drift_results = {}
        overall_drift_score = 0
        method_count = 0

        if "similarity" in detection_methods and baseline_output:
            similarity_result = self._detect_by_similarity(actual_output, baseline_output)
            drift_results["similarity"] = similarity_result
            overall_drift_score += similarity_result["drift_score"]
            method_count += 1

        if "score_comparison" in detection_methods:
            score_result = self._detect_by_score_history(case_id)
            drift_results["score_comparison"] = score_result
            overall_drift_score += score_result["drift_score"]
            method_count += 1

        if "statistical" in detection_methods:
            stat_result = self._detect_by_statistics(actual_output, baseline_output)
            drift_results["statistical"] = stat_result
            overall_drift_score += stat_result["drift_score"]
            method_count += 1

        avg_drift_score = overall_drift_score / method_count if method_count > 0 else 0
        threshold = self.get_payload_data(request, "threshold", 0.2)
        drift_detected = avg_drift_score > threshold

        return DomainResponse(
            is_valid=True,
            text="漂移检测完成",
            score=1.0 - avg_drift_score,
            data={
                "drift_detected": drift_detected,
                "drift_score": avg_drift_score,
                "threshold": threshold,
                "methods": drift_results,
                "confidence": self._calculate_confidence(drift_results),
            },
        )

    def _detect_by_similarity(self, actual_output: str, baseline_output: str) -> dict:
        similarity = difflib.SequenceMatcher(None, actual_output, baseline_output).ratio()
        drift_score = 1.0 - similarity

        return {
            "method": "text_similarity",
            "similarity": similarity,
            "drift_score": drift_score,
            "detected": drift_score > 0.2,
            "confidence": 0.7,
        }

    def _detect_by_score_history(self, case_id: str) -> dict:
        try:
            recent_results = self.repository.get_recent(20)
            if len(recent_results) < 5:
                return {
                    "method": "score_history",
                    "baseline_score": None,
                    "current_score": None,
                    "drift_score": 0,
                    "detected": False,
                    "confidence": 0.3,
                    "message": "历史数据不足",
                }

            # 修复Bug：原代码使用latency_ms，应使用score字段
            # 优先从baseline_snapshot中读取基线
            baseline = self._get_or_create_baseline(case_id, recent_results)
            scores = [r.get("score", 0) for r in recent_results if r.get("score") is not None]
            if not scores:
                return {
                    "method": "score_history",
                    "drift_score": 0,
                    "detected": False,
                    "confidence": 0.3,
                    "message": "无可用分数数据",
                }

            # 使用基线（如果存在）或前10条记录的平均分
            if baseline is not None:
                baseline_score = baseline
            else:
                baseline_score = sum(scores[:10]) / len(scores[:10])

            current_score = sum(scores[-5:]) / len(scores[-5:])

            if baseline_score == 0:
                drift_score = 0
            else:
                drift_score = abs(current_score - baseline_score) / baseline_score

            return {
                "method": "score_history",
                "baseline_score": baseline_score,
                "current_score": current_score,
                "drift_score": min(drift_score, 1.0),
                "detected": drift_score > 0.2,
                "confidence": 0.85 if baseline is not None else 0.7,
            }
        except Exception:
            return {
                "method": "score_history",
                "drift_score": 0,
                "detected": False,
                "confidence": 0.2,
                "message": "数据库查询失败",
            }

    def _detect_by_statistics(self, actual_output: str, baseline_output: str | None = None) -> dict:
        actual_len = len(actual_output)
        actual_tokens = len(actual_output.split())
        actual_sentences = len(actual_output.split("."))

        stats = {
            "length": actual_len,
            "token_count": actual_tokens,
            "sentence_count": actual_sentences,
        }

        if baseline_output:
            baseline_len = len(baseline_output)
            baseline_tokens = len(baseline_output.split())

            length_diff = abs(actual_len - baseline_len) / max(baseline_len, 1)
            token_diff = abs(actual_tokens - baseline_tokens) / max(baseline_tokens, 1)

            avg_diff = (length_diff + token_diff) / 2
            drift_score = min(avg_diff, 1.0)

            stats.update({
                "baseline_length": baseline_len,
                "baseline_tokens": baseline_tokens,
                "length_drift": length_diff,
                "token_drift": token_diff,
            })
        else:
            drift_score = 0

        return {
            "method": "statistics",
            "drift_score": drift_score,
            "detected": drift_score > 0.3,
            "confidence": 0.6,
            "statistics": stats,
        }

    def _calculate_confidence(self, results: dict) -> float:
        if not results:
            return 0.5

        total_confidence = sum(r.get("confidence", 0.5) for r in results.values())
        return total_confidence / len(results)

    def _version_compare(self, request: EvaluationSchema) -> DomainResponse:
        version_a_output = self.get_payload_data(request, "version_a_output")
        version_b_output = self.get_payload_data(request, "version_b_output")
        version_a_metadata = self.get_payload_data(request, "version_a_metadata", {})
        version_b_metadata = self.get_payload_data(request, "version_b_metadata", {})

        if not version_a_output or not version_b_output:
            return DomainResponse(is_valid=False, error="version_a_output 和 version_b_output 不能为空")

        comparison = self._compare_versions(version_a_output, version_b_output, version_a_metadata, version_b_metadata)

        return DomainResponse(
            is_valid=True,
            text="版本对比完成",
            score=1.0 - comparison["drift_score"],
            data=comparison,
        )

    def _compare_versions(self, a_output: str, b_output: str, a_meta: dict, b_meta: dict) -> dict:
        text_similarity = difflib.SequenceMatcher(None, a_output, b_output).ratio()
        drift_score = 1.0 - text_similarity

        a_fingerprint = self._compute_fingerprint(a_output)
        b_fingerprint = self._compute_fingerprint(b_output)
        fingerprint_match = a_fingerprint == b_fingerprint

        a_stats = self._compute_text_stats(a_output)
        b_stats = self._compute_text_stats(b_output)
        stat_drift = self._compare_stats(a_stats, b_stats)

        semantic_drift = self._analyze_semantic_drift(a_output, b_output, "")

        return {
            "text_similarity": text_similarity,
            "drift_score": drift_score,
            "fingerprint_match": fingerprint_match,
            "version_a_fingerprint": a_fingerprint,
            "version_b_fingerprint": b_fingerprint,
            "statistical_drift": stat_drift,
            "semantic_drift": semantic_drift,
            "version_a_metadata": a_meta,
            "version_b_metadata": b_meta,
        }

    def _compute_fingerprint(self, text: str) -> str:
        normalized_text = re.sub(r'\s+', ' ', text.strip()).lower()
        return hashlib.md5(normalized_text.encode()).hexdigest()

    def _compute_text_stats(self, text: str) -> dict:
        sentences = re.split(r'[.!?]+', text)
        sentences = [s for s in sentences if s.strip()]

        words = re.findall(r'\w+', text)

        return {
            "length": len(text),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "avg_sentence_length": sum(len(s) for s in sentences) / len(sentences) if sentences else 0,
            "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
        }

    def _compare_stats(self, a: dict, b: dict) -> dict:
        diffs = {}
        for key in a.keys():
            if key in b:
                if a[key] != 0:
                    diffs[key] = abs(a[key] - b[key]) / a[key]
                else:
                    diffs[key] = 0.0

        avg_diff = sum(diffs.values()) / len(diffs) if diffs else 0.0

        return {
            "differences": diffs,
            "average_difference": avg_diff,
            "drift_detected": avg_diff > 0.2,
        }

    def _detect_semantic_drift(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        baseline_output = self.get_payload_data(request, "baseline_output")
        user_input = self.get_input_text(request)

        if not actual_output or not baseline_output:
            return DomainResponse(is_valid=False, error="actual_output 和 baseline_output 不能为空")

        drift_result = self._analyze_semantic_drift(actual_output, baseline_output, user_input)

        return DomainResponse(
            is_valid=True,
            text="语义漂移检测完成",
            score=1.0 - drift_result["drift_score"],
            data=drift_result,
        )

    def _analyze_semantic_drift(self, actual: str, baseline: str, context: str | None = None) -> dict:
        actual_keywords = self._extract_keywords(actual)
        baseline_keywords = self._extract_keywords(baseline)

        common_keywords = set(actual_keywords) & set(baseline_keywords)
        actual_only = set(actual_keywords) - set(baseline_keywords)
        baseline_only = set(baseline_keywords) - set(actual_keywords)

        keyword_overlap = len(common_keywords) / max(len(baseline_keywords), 1)

        factual_consistency = self._check_factual_consistency(actual, baseline)

        text_similarity = difflib.SequenceMatcher(None, actual, baseline).ratio()

        drift_score = (1.0 - keyword_overlap) * 0.4 + (1.0 - factual_consistency) * 0.3 + (1.0 - text_similarity) * 0.3

        return {
            "drift_score": drift_score,
            "keyword_overlap": keyword_overlap,
            "common_keywords": list(common_keywords),
            "actual_only_keywords": list(actual_only),
            "baseline_only_keywords": list(baseline_only),
            "factual_consistency": factual_consistency,
            "text_similarity": text_similarity,
            "drift_detected": drift_score > 0.25,
        }

    def _extract_keywords(self, text: str) -> list:
        words = re.findall(r'\w+', text.lower())
        stop_words = {"the", "and", "or", "but", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "could", "should",
                      "may", "might", "must", "shall", "can", "need", "dare", "ought", "used",
                      "to", "of", "in", "for", "on", "with", "at", "by", "from", "up", "about",
                      "into", "over", "after", "as", "if", "when", "than",
                      "because", "while", "although", "though", "that", "which", "who", "whom",
                      "this", "these", "those", "what", "how", "where", "why"}

        filtered = [w for w in words if w not in stop_words and len(w) > 2]

        return filtered

    def _check_factual_consistency(self, actual: str, baseline: str) -> float:
        actual_nums = re.findall(r'\d+\.?\d*', actual)
        baseline_nums = re.findall(r'\d+\.?\d*', baseline)

        if not baseline_nums:
            return 0.5

        match_count = 0
        for num in actual_nums:
            if num in baseline:
                match_count += 1

        return match_count / len(baseline_nums)

    def _behavioral_fingerprint(self, request: EvaluationSchema) -> DomainResponse:
        actual_output = self.get_payload_data(request, "actual_output")
        baseline_fingerprint = self.get_payload_data(request, "baseline_fingerprint")

        if not actual_output:
            return DomainResponse(is_valid=False, error="actual_output 不能为空")

        current_fingerprint = self._compute_full_fingerprint(actual_output)

        match_result = {}
        if baseline_fingerprint:
            match_score = self._match_fingerprints(current_fingerprint, baseline_fingerprint)
            match_result["match_score"] = match_score
            match_result["baseline_fingerprint"] = baseline_fingerprint
            match_result["fingerprint_changed"] = match_score < 0.8

        return DomainResponse(
            is_valid=True,
            text="行为指纹计算完成",
            score=match_result.get("match_score", 1.0),
            data={
                "current_fingerprint": current_fingerprint,
                **match_result,
            },
        )

    def _compute_full_fingerprint(self, text: str) -> dict:
        return {
            "text_hash": self._compute_fingerprint(text),
            "stats": self._compute_text_stats(text),
            "keywords": self._extract_keywords(text)[:20],
            "structure": self._analyze_structure(text),
        }

    def _analyze_structure(self, text: str) -> dict:
        has_json = "{" in text and "}" in text
        has_markdown = any(m in text for m in ["#", "*", "**", "- ", "1.", "2.", "3."])
        has_list = re.search(r'(\d+\.|-|\*)\s+', text) is not None
        has_table = "|" in text and re.search(r'\|.*\|', text) is not None

        return {
            "has_json": has_json,
            "has_markdown": has_markdown,
            "has_list": has_list,
            "has_table": has_table,
        }

    def _match_fingerprints(self, current: dict, baseline: dict) -> float:
        score = 0.0
        total = 0

        if current["text_hash"] == baseline.get("text_hash"):
            score += 0.4
        total += 0.4

        stats_a = current["stats"]
        stats_b = baseline.get("stats", {})
        if stats_a and stats_b:
            stat_diff = sum(abs(stats_a[k] - stats_b.get(k, 0)) / max(stats_a[k], 1) for k in stats_a if k in stats_b)
            score += max(0, 0.3 - stat_diff * 0.3)
        total += 0.3

        kw_a = set(current["keywords"])
        kw_b = set(baseline.get("keywords", []))
        if kw_a and kw_b:
            overlap = len(kw_a & kw_b) / max(len(kw_a), len(kw_b))
            score += overlap * 0.3
        total += 0.3

        return score / total if total > 0 else 0.0

    # ------------------- 基线持久化管理 -------------------
    _BASELINE_STORE: dict[str, float] = {}

    def _get_or_create_baseline(self, case_id: str, recent_results: list) -> float | None:
        """获取或创建基线分数（持久化到内存，支持导出到文件）"""
        if case_id in self._BASELINE_STORE:
            return self._BASELINE_STORE[case_id]

        # 自动从历史记录创建基线（使用前10条记录）
        valid_scores = [r.get("score", 0) for r in recent_results[:10] if r.get("score") is not None]
        if len(valid_scores) >= 3:
            baseline = sum(valid_scores) / len(valid_scores)
            self._BASELINE_STORE[case_id] = baseline
            return baseline
        return None

    def save_baseline(self, case_id: str, baseline_score: float) -> None:
        """保存基线分数到持久化存储"""
        self._BASELINE_STORE[case_id] = baseline_score
        # 异步持久化到磁盘
        try:
            import json
            from pathlib import Path
            baseline_file = Path("data/baselines.json")
            baseline_file.parent.mkdir(parents=True, exist_ok=True)
            existing = {}
            if baseline_file.exists():
                existing = json.loads(baseline_file.read_text(encoding="utf-8"))
            existing[case_id] = {
                "score": baseline_score,
                "updated_at": time.time() if "time" in dir() else 0,
            }
            baseline_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_baselines(self) -> dict[str, float]:
        """从持久化存储加载基线"""
        try:
            import json
            from pathlib import Path
            baseline_file = Path("data/baselines.json")
            if baseline_file.exists():
                data = json.loads(baseline_file.read_text(encoding="utf-8"))
                self._BASELINE_STORE = {k: v["score"] for k, v in data.items()}
                return self._BASELINE_STORE
        except Exception:
            pass
        return {}
