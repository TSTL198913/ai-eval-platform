"""
🏷️ src/services/annotation_svc.py
人工标注服务层 - 2026 工业级实现

提供：
- 标注任务创建/分配/查询
- 标注结果提交
- 标注一致性计算（Cohen's Kappa / Fleiss' Kappa）
- 黄金样本校验
- 标注员绩效统计
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.infra.db.models import (
    AnnotationAgreementModel,
    AnnotationResultModel,
    AnnotationTaskModel,
)
from src.infra.db.session import SessionLocal

logger = logging.getLogger(__name__)


# ==================== 异常定义 ====================


class AnnotationServiceError(Exception):
    """标注服务异常基类"""


class TaskNotFoundError(AnnotationServiceError):
    """标注任务未找到"""


class DuplicateAnnotationError(AnnotationServiceError):
    """同一标注员重复标注"""


class InvalidScoreError(AnnotationServiceError):
    """分数非法"""


# ==================== 服务实现 ====================


class AnnotationService:
    """标注服务"""

    def __init__(self, db: Session | None = None):
        self.db = db or SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()

    # ==================== 任务管理 ====================

    def create_task(
        self,
        case_id: str,
        evaluator_type: str,
        question: str = "",
        actual_output: str = "",
        expected_output: str = "",
        context: str = "",
        priority: int = 5,
        required_annotators: int = 1,
        due_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AnnotationTaskModel:
        """创建标注任务"""
        task = AnnotationTaskModel(
            case_id=case_id,
            evaluator_type=evaluator_type,
            question=question,
            actual_output=actual_output,
            expected_output=expected_output,
            context=context,
            priority=priority,
            required_annotators=required_annotators,
            due_at=due_at,
            metadata_json=metadata or {},
            status="pending",
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        logger.info(f"标注任务创建成功: id={task.id}, case_id={case_id}")
        return task

    def bulk_create_tasks(self, cases: list[dict[str, Any]]) -> list[AnnotationTaskModel]:
        """批量创建标注任务

        cases 每项至少包含 case_id, evaluator_type；可选 question/actual_output/expected_output
        """
        tasks = []
        for c in cases:
            task = AnnotationTaskModel(
                case_id=c["case_id"],
                evaluator_type=c["evaluator_type"],
                question=c.get("question", ""),
                actual_output=c.get("actual_output", ""),
                expected_output=c.get("expected_output", ""),
                context=c.get("context", ""),
                priority=c.get("priority", 5),
                required_annotators=c.get("required_annotators", 1),
                metadata_json=c.get("metadata", {}),
                status="pending",
            )
            self.db.add(task)
            tasks.append(task)
        self.db.commit()
        logger.info(f"批量创建标注任务: {len(tasks)} 个")
        return tasks

    def list_tasks(
        self,
        status: str | None = None,
        evaluator_type: str | None = None,
        annotator_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AnnotationTaskModel]:
        """查询标注任务列表"""
        query = self.db.query(AnnotationTaskModel)
        if status:
            query = query.filter(AnnotationTaskModel.status == status)
        if evaluator_type:
            query = query.filter(AnnotationTaskModel.evaluator_type == evaluator_type)
        if annotator_id:
            query = query.join(AnnotationResultModel).filter(
                AnnotationResultModel.annotator_id == annotator_id
            )
        return (
            query.order_by(
                AnnotationTaskModel.priority.desc(), AnnotationTaskModel.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_task(self, task_id: int) -> AnnotationTaskModel:
        """获取标注任务详情"""
        task = self.db.query(AnnotationTaskModel).filter(AnnotationTaskModel.id == task_id).first()
        if task is None:
            raise TaskNotFoundError(f"标注任务 {task_id} 不存在")
        return task

    def update_task_status(self, task_id: int, status: str) -> AnnotationTaskModel:
        """更新任务状态"""
        task = self.get_task(task_id)
        if status not in {"pending", "in_progress", "completed", "cancelled"}:
            raise ValueError(f"非法状态: {status}")
        task.status = status
        task.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(task)
        return task

    # ==================== 标注提交 ====================

    def submit_result(
        self,
        task_id: int,
        annotator_id: str,
        score: float,
        annotator_name: str = "",
        label: str = "",
        comment: str = "",
        tags: list[str] | None = None,
        dimensions: dict[str, float] | None = None,
        time_spent_seconds: int | None = None,
    ) -> AnnotationResultModel:
        """提交标注结果

        Args:
            task_id: 任务ID
            annotator_id: 标注员ID
            score: 标注分数（0-1）
            其他: 可选标注信息

        Raises:
            TaskNotFoundError: 任务不存在
            DuplicateAnnotationError: 同一标注员已标注
            InvalidScoreError: 分数超出 [0, 1] 范围
        """
        if not (0.0 <= score <= 1.0):
            raise InvalidScoreError(f"score 必须在 [0, 1] 区间，当前: {score}")

        task = self.get_task(task_id)

        # 查重
        existing = (
            self.db.query(AnnotationResultModel)
            .filter(
                and_(
                    AnnotationResultModel.task_id == task_id,
                    AnnotationResultModel.annotator_id == annotator_id,
                )
            )
            .first()
        )
        if existing is not None:
            raise DuplicateAnnotationError(
                f"标注员 {annotator_id} 已对任务 {task_id} 标注过（result_id={existing.id}）"
            )

        result = AnnotationResultModel(
            task_id=task_id,
            annotator_id=annotator_id,
            annotator_name=annotator_name,
            score=score,
            label=label,
            comment=comment,
            tags=tags or [],
            dimensions=dimensions or {},
            time_spent_seconds=time_spent_seconds,
            is_valid=True,
        )
        self.db.add(result)
        self.db.flush()  # 触发 autoflush，使 count() 包含本次新增

        # 推进任务状态
        if task.status == "pending":
            task.status = "in_progress"
        # 注：count() 已通过 flush() 包含本次新增，无需 +1
        current_count = (
            self.db.query(AnnotationResultModel)
            .filter(AnnotationResultModel.task_id == task_id)
            .count()
        )
        if current_count >= task.required_annotators:
            task.status = "completed"
        task.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(result)
        logger.info(
            f"标注结果提交: task_id={task_id}, annotator={annotator_id}, score={score}, status={task.status}"
        )
        return result

    def list_results(self, task_id: int) -> list[AnnotationResultModel]:
        """查询任务的标注结果"""
        return (
            self.db.query(AnnotationResultModel)
            .filter(AnnotationResultModel.task_id == task_id)
            .order_by(AnnotationResultModel.created_at.asc())
            .all()
        )

    def review_result(
        self,
        result_id: int,
        reviewer_id: str,
        review_comment: str = "",
        is_valid: bool = True,
    ) -> AnnotationResultModel:
        """审核标注结果"""
        result = (
            self.db.query(AnnotationResultModel)
            .filter(AnnotationResultModel.id == result_id)
            .first()
        )
        if result is None:
            raise AnnotationServiceError(f"标注结果 {result_id} 不存在")
        result.reviewer_id = reviewer_id
        result.review_comment = review_comment
        result.is_valid = is_valid
        self.db.commit()
        self.db.refresh(result)
        return result

    # ==================== 一致性计算 ====================

    @staticmethod
    def _cohens_kappa(rater1: list, rater2: list) -> float | None:
        """计算 Cohen's Kappa 系数（两个标注员）

        解释：
        - 1.0: 完全一致
        - 0.81-1.0: almost perfect
        - 0.61-0.80: substantial
        - 0.41-0.60: moderate
        - 0.21-0.40: fair
        - 0.0-0.20: poor
        - < 0: 一致性低于随机
        """
        if len(rater1) != len(rater2) or len(rater1) == 0:
            return None

        n = len(rater1)
        categories = set(rater1) | set(rater2)
        po = sum(1 for a, b in zip(rater1, rater2, strict=False) if a == b) / n

        # 期望一致率 pe
        pe = 0.0
        for cat in categories:
            p1 = sum(1 for a in rater1 if a == cat) / n
            p2 = sum(1 for a in rater2 if a == cat) / n
            pe += p1 * p2

        if pe == 1.0:
            return 1.0

        kappa = (po - pe) / (1 - pe)
        return max(-1.0, min(1.0, kappa))

    @staticmethod
    def _kappa_to_level(kappa: float) -> str:
        """Kappa 值转一致性等级"""
        if kappa < 0:
            return "worse_than_chance"
        if kappa < 0.21:
            return "poor"
        if kappa < 0.41:
            return "fair"
        if kappa < 0.61:
            return "moderate"
        if kappa < 0.81:
            return "substantial"
        return "almost_perfect"

    def compute_agreement(self, evaluator_type: str) -> AnnotationAgreementModel | None:
        """计算指定评估器类型的标注一致性（两两 Cohen's Kappa 聚合）"""
        # 拉取已完成的任务，且至少有 2 个标注结果
        tasks = (
            self.db.query(AnnotationTaskModel)
            .filter(
                and_(
                    AnnotationTaskModel.evaluator_type == evaluator_type,
                    AnnotationTaskModel.status == "completed",
                )
            )
            .all()
        )
        if not tasks:
            return None

        # 收集每个任务的多标注员分数
        per_task_scores: dict[int, dict[str, float]] = {}
        for task in tasks:
            results = (
                self.db.query(AnnotationResultModel)
                .filter(
                    and_(
                        AnnotationResultModel.task_id == task.id,
                        AnnotationResultModel.is_valid.is_(True),
                    )
                )
                .all()
            )
            if len(results) < 2:
                continue
            per_task_scores[task.id] = {r.annotator_id: r.score for r in results}

        if not per_task_scores:
            return None

        # 两两配对计算 Cohen's Kappa（基于分数分箱为 5 档）
        def to_bin(score: float) -> int:
            """将 0-1 分数分箱为 0-4 五档"""
            return min(4, max(0, int(score * 5)))

        annotator_pairs: dict[tuple[str, str], list[tuple[int, int]]] = {}
        for scores in per_task_scores.values():
            items = list(scores.items())
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    pair = tuple(sorted([items[i][0], items[j][0]]))
                    annotator_pairs.setdefault(pair, []).append(
                        (to_bin(items[i][1]), to_bin(items[j][1]))
                    )

        if not annotator_pairs:
            return None

        kappas = []
        for (_a, _b), labels in annotator_pairs.items():
            rater1 = [x[0] for x in labels]
            rater2 = [x[1] for x in labels]
            k = self._cohens_kappa(rater1, rater2)
            if k is not None:
                kappas.append(k)

        if not kappas:
            return None

        avg_kappa = sum(kappas) / len(kappas)
        level = self._kappa_to_level(avg_kappa)

        agreement = AnnotationAgreementModel(
            evaluator_type=evaluator_type,
            sample_size=len(per_task_scores),
            kappa_score=avg_kappa,
            agreement_level=level,
            annotator_count=len({a for pair in annotator_pairs.keys() for a in pair}),
            metric_payload={
                "pair_count": len(annotator_pairs),
                "kappas": kappas,
            },
        )
        self.db.add(agreement)
        self.db.commit()
        self.db.refresh(agreement)
        return agreement

    # ==================== 黄金样本校验 ====================

    def submit_golden_sample(
        self,
        task_id: int,
        annotator_id: str,
        golden_score: float,
    ) -> dict[str, Any]:
        """提交黄金样本标注，返回是否通过

        Args:
            task_id: 黄金样本任务ID
            annotator_id: 标注员ID
            golden_score: 黄金样本的标准分数

        Returns:
            dict: 包含 pass/fail、偏差、是否需要重新培训
        """
        result = self.submit_result(
            task_id=task_id,
            annotator_id=annotator_id,
            score=golden_score,
            comment="[GOLDEN_SAMPLE]",
        )
        # 标记为黄金样本
        result.is_golden = True
        self.db.commit()

        # 读取任务的标准答案作为对照
        task = self.get_task(task_id)
        expected = task.expected_output or ""
        # 简化处理：黄金样本的 expected_output 应包含标准分数
        try:
            true_score = float(expected.strip())
        except (ValueError, TypeError):
            true_score = golden_score  # 无对照则视为通过

        deviation = abs(golden_score - true_score)
        is_pass = deviation < 0.1

        return {
            "task_id": task_id,
            "annotator_id": annotator_id,
            "submitted_score": golden_score,
            "true_score": true_score,
            "deviation": round(deviation, 4),
            "pass": is_pass,
            "needs_retraining": not is_pass,
        }

    # ==================== 标注员绩效 ====================

    def get_annotator_stats(self, annotator_id: str) -> dict[str, Any]:
        """统计标注员绩效"""
        results = (
            self.db.query(AnnotationResultModel)
            .filter(AnnotationResultModel.annotator_id == annotator_id)
            .all()
        )
        if not results:
            return {
                "annotator_id": annotator_id,
                "total_annotations": 0,
            }

        valid_results = [r for r in results if r.is_valid]
        avg_score = (
            sum(r.score for r in valid_results) / len(valid_results) if valid_results else 0.0
        )
        avg_time = (
            sum(r.time_spent_seconds or 0 for r in valid_results) / len(valid_results)
            if valid_results
            else 0.0
        )
        golden_results = [r for r in valid_results if r.is_golden]

        # 黄金样本通过率
        golden_pass = 0
        for g in golden_results:
            task = self.get_task(g.task_id)
            try:
                true_score = float((task.expected_output or "0").strip())
                if abs(g.score - true_score) < 0.1:
                    golden_pass += 1
            except (ValueError, TypeError):
                pass
        golden_pass_rate = golden_pass / len(golden_results) if golden_results else None

        return {
            "annotator_id": annotator_id,
            "annotator_name": results[0].annotator_name,
            "total_annotations": len(results),
            "valid_annotations": len(valid_results),
            "avg_score": round(avg_score, 4),
            "avg_time_seconds": round(avg_time, 2),
            "golden_count": len(golden_results),
            "golden_pass_rate": round(golden_pass_rate, 4)
            if golden_pass_rate is not None
            else None,
        }


__all__ = [
    "AnnotationService",
    "AnnotationServiceError",
    "TaskNotFoundError",
    "DuplicateAnnotationError",
    "InvalidScoreError",
]
