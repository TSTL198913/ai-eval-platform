import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from src.infra.db.repository import EvaluationRepository


@dataclass
class ConflictRecord:
    case_id: str
    evaluator_type: str
    score_before: float
    score_after: float
    score_diff: float
    reason: str
    detected_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "pending"

    @property
    def is_high_conflict(self) -> bool:
        return abs(self.score_diff) > 30

    @property
    def conflict_level(self) -> str:
        diff = abs(self.score_diff)
        if diff > 50:
            return "critical"
        elif diff > 30:
            return "high"
        elif diff > 15:
            return "medium"
        else:
            return "low"


class MetaEvaluator:
    def __init__(self):
        self._repository = EvaluationRepository()
        self._conflict_queue: List[ConflictRecord] = []
        self._calibration_threshold = 15.0
        self._load_pending_conflicts()

    def _load_pending_conflicts(self):
        conflicts_file = "data/meta_evaluator/conflicts.json"
        if os.path.exists(conflicts_file):
            try:
                with open(conflicts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._conflict_queue = [
                        ConflictRecord(**c) for c in data
                    ]
            except Exception:
                pass

    def _save_pending_conflicts(self):
        conflicts_file = "data/meta_evaluator/conflicts.json"
        os.makedirs(os.path.dirname(conflicts_file), exist_ok=True)
        with open(conflicts_file, "w", encoding="utf-8") as f:
            json.dump([vars(c) for c in self._conflict_queue], f, ensure_ascii=False, indent=2)

    def detect_conflicts(self, new_result: Dict[str, Any], baseline: Dict[str, Any]) -> Optional[ConflictRecord]:
        new_score = new_result.get("total_score", 0)
        baseline_score = baseline.get("total_score", 0)
        score_diff = new_score - baseline_score

        if abs(score_diff) < self._calibration_threshold:
            return None

        conflict = ConflictRecord(
            case_id=new_result.get("case_id", "unknown"),
            evaluator_type=new_result.get("evaluator_type", "llm_as_judge"),
            score_before=baseline_score,
            score_after=new_score,
            score_diff=score_diff,
            reason=self._generate_conflict_reason(new_result, baseline)
        )

        self._conflict_queue.append(conflict)
        self._save_pending_conflicts()

        return conflict

    def _generate_conflict_reason(self, new_result: Dict[str, Any], baseline: Dict[str, Any]) -> str:
        reasons = []
        new_scores = new_result.get("llm_judge_scores", {})
        base_scores = baseline.get("llm_judge_scores", {})

        for dim in new_scores:
            new_dim_score = new_scores.get(dim, {}).get("score", 0)
            base_dim_score = base_scores.get(dim, {}).get("score", 0)
            diff = abs(new_dim_score - base_dim_score)
            if diff > 20:
                reasons.append(f"{dim}维度差异{diff}分")

        return "; ".join(reasons) if reasons else "评分整体偏差较大"

    def detect_multi_model_conflicts(self, results: List[Dict[str, Any]]) -> List[Tuple[str, float, float]]:
        conflicts = []
        if len(results) < 2:
            return conflicts

        scores_by_case = {}
        for result in results:
            case_id = result.get("case_id")
            score = result.get("total_score", 0)
            if case_id not in scores_by_case:
                scores_by_case[case_id] = []
            scores_by_case[case_id].append(score)

        for case_id, scores in scores_by_case.items():
            if len(scores) >= 2:
                min_score = min(scores)
                max_score = max(scores)
                score_range = max_score - min_score
                if score_range > 25:
                    conflicts.append((case_id, min_score, max_score))

        return conflicts

    def get_pending_conflicts(self, status: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        conflicts = self._conflict_queue
        if status:
            conflicts = [c for c in conflicts if c.status == status]

        conflicts = sorted(conflicts, key=lambda x: abs(x.score_diff), reverse=True)[:limit]

        return [
            {
                "case_id": c.case_id,
                "evaluator_type": c.evaluator_type,
                "score_before": c.score_before,
                "score_after": c.score_after,
                "score_diff": c.score_diff,
                "conflict_level": c.conflict_level,
                "reason": c.reason,
                "detected_at": c.detected_at.isoformat(),
                "status": c.status,
            }
            for c in conflicts
        ]

    def resolve_conflict(self, case_id: str, resolution: str = "reviewed"):
        for conflict in self._conflict_queue:
            if conflict.case_id == case_id:
                conflict.status = resolution
        self._save_pending_conflicts()

    def get_conflict_stats(self) -> Dict[str, Any]:
        total = len(self._conflict_queue)
        by_level = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        by_status = {"pending": 0, "reviewed": 0, "resolved": 0}

        for c in self._conflict_queue:
            by_level[c.conflict_level] += 1
            by_status[c.status] += 1

        return {
            "total_conflicts": total,
            "by_level": by_level,
            "by_status": by_status,
            "high_priority_count": by_level["high"] + by_level["critical"],
        }

    def analyze_evaluator_drift(self, days: int = 7) -> Dict[str, Any]:
        all_records = self._repository.search(limit=1000)
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        recent_scores = []
        historical_scores = []

        for record in all_records:
            created_at = record.get("created_at")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    continue

            score = record.get("response_data", {}).get("total_score", 0)
            if score > 0:
                if created_at and created_at >= cutoff_date:
                    recent_scores.append(score)
                else:
                    historical_scores.append(score)

        if not recent_scores or not historical_scores:
            return {"drift_detected": False, "message": "数据不足，无法判断漂移"}

        avg_recent = sum(recent_scores) / len(recent_scores)
        avg_historical = sum(historical_scores) / len(historical_scores)
        drift = avg_recent - avg_historical

        return {
            "drift_detected": abs(drift) > 10,
            "avg_recent_score": round(avg_recent, 2),
            "avg_historical_score": round(avg_historical, 2),
            "drift_amount": round(drift, 2),
            "recent_sample_count": len(recent_scores),
            "historical_sample_count": len(historical_scores),
        }


meta_evaluator = MetaEvaluator()
