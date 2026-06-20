"""
仪表盘路由模块
提供仪表盘相关的API端点
"""

from typing import Any

from fastapi import APIRouter

from src.domain.evaluators import EVALUATOR_REGISTRY
from src.infra.db.repository import EvaluationRepository

router = APIRouter(prefix="/api/v1/dashboard", tags=["仪表盘"])


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    """成功响应"""
    return {"code": 0, "message": message, "data": data}


def error_response(code: int, message: str) -> dict[str, Any]:
    """错误响应"""
    return {"code": code, "message": message, "data": None}


@router.get("/stats")
async def get_dashboard_stats():
    """获取仪表盘统计数据"""
    try:
        repo = EvaluationRepository()
        record_count = repo.count()
        recent_records = repo.get_recent(limit=5)
        evaluator_types = list(EVALUATOR_REGISTRY.keys())

        status_counts = {}
        for record in recent_records:
            status = record.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        return success_response(
            {
                "total_records": record_count,
                "evaluator_types": len(evaluator_types),
                "recent_records": recent_records,
                "status_distribution": status_counts,
            }
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get stats: {e}")
        return error_response(500, "获取统计信息失败")


@router.get("/overview")
async def get_dashboard_overview():
    """获取评估看板概览"""
    try:
        from src.domain.golden_dataset import golden_dataset_manager
        from src.domain.meta_evaluator import meta_evaluator

        repo = EvaluationRepository()
        recent_records = repo.get_recent(limit=100)

        conflict_stats = meta_evaluator.get_conflict_stats()
        golden_datasets = golden_dataset_manager.list_datasets()

        avg_score = 0
        if recent_records:
            scores = [
                r.get("response_data", {}).get("total_score", 0)
                for r in recent_records
                if r.get("response_data", {}).get("total_score", 0) > 0
            ]
            if scores:
                avg_score = sum(scores) / len(scores)

        return success_response(
            {
                "total_evaluations": repo.count(),
                "recent_count": len(recent_records),
                "avg_score": round(avg_score, 1),
                "high_priority_conflicts": conflict_stats.get("high_priority_count", 0),
                "golden_datasets_count": len(golden_datasets),
                "system_status": (
                    "healthy"
                    if conflict_stats.get("high_priority_count", 0) < 5
                    else "attention_needed"
                ),
            }
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get dashboard overview: {e}")
        return error_response(500, "获取看板数据失败")


@router.get("/trust")
async def get_trust_dashboard():
    """获取可信度仪表盘"""
    try:
        from src.domain.evaluator_version import evaluator_version_manager
        from src.domain.golden_dataset import golden_dataset_manager

        repo = EvaluationRepository()

        # 收集所有评估器的校准状态
        evaluators = set()
        records = repo.search(limit=1000)
        for record in records:
            if record.get("adapter_name"):
                evaluators.add(record["adapter_name"])

        calibration_status = []
        for evaluator in evaluators:
            status = evaluator_version_manager.check_calibration_status(evaluator)
            calibration_status.append({"evaluator_name": evaluator, **status})

        # 黄金数据集统计
        datasets = golden_dataset_manager.list_datasets()
        dataset_stats = [
            {
                "id": d.id,
                "name": d.name,
                "samples_count": len(d.samples),
                "corrected_count": d.corrected_count,
            }
            for d in datasets
        ]

        return success_response(
            {
                "calibration_status": calibration_status,
                "total_evaluators": len(calibration_status),
                "calibrated_count": sum(1 for s in calibration_status if s.get("can_proceed")),
                "golden_datasets": dataset_stats,
                "system_trust_score": _calculate_trust_score(calibration_status),
            }
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get trust dashboard: {e}")
        return error_response(500, "获取可信度仪表盘失败")


def _calculate_trust_score(calibration_status: list) -> float:
    """计算系统信任分数"""
    if not calibration_status:
        return 0.0

    scores = []
    for status in calibration_status:
        if status.get("can_proceed"):
            if status.get("status") == "calibrated":
                scores.append(100)
            elif status.get("status") == "not_calibrated":
                scores.append(50)
            else:
                scores.append(30)
        else:
            scores.append(0)

    return round(sum(scores) / len(scores), 1)
