"""
🏷️ src/api/routes/annotation_routes.py
人工标注 API 路由 - 2026 工业级实现

端点设计：
- POST /api/v1/annotations/tasks - 创建标注任务
- POST /api/v1/annotations/tasks/bulk - 批量创建
- GET /api/v1/annotations/tasks - 查询任务列表
- GET /api/v1/annotations/tasks/{task_id} - 查询任务详情
- PATCH /api/v1/annotations/tasks/{task_id}/status - 更新任务状态
- POST /api/v1/annotations/tasks/{task_id}/results - 提交标注结果
- POST /api/v1/annotations/results/{result_id}/review - 审核标注
- POST /api/v1/annotations/tasks/{task_id}/golden - 提交黄金样本
- GET /api/v1/annotations/agreement/{evaluator_type} - 计算一致性
- GET /api/v1/annotations/annotators/{annotator_id}/stats - 标注员绩效
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.api.common import error_response, success_response
from src.services.annotation_svc import (
    AnnotationService,
    AnnotationServiceError,
    DuplicateAnnotationError,
    InvalidScoreError,
    TaskNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/annotations", tags=["人工标注"])


# ==================== Request/Response Schemas ====================


class AnnotationTaskCreateRequest(BaseModel):
    case_id: str = Field(..., min_length=1, max_length=100)
    evaluator_type: str = Field(..., min_length=1, max_length=50)
    question: str = ""
    actual_output: str = ""
    expected_output: str = ""
    context: str = ""
    priority: int = Field(default=5, ge=1, le=10)
    required_annotators: int = Field(default=1, ge=1, le=10)
    due_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnnotationTaskBulkCreateRequest(BaseModel):
    cases: list[AnnotationTaskCreateRequest] = Field(..., min_length=1, max_length=500)


class AnnotationResultSubmitRequest(BaseModel):
    annotator_id: str = Field(..., min_length=1, max_length=100)
    annotator_name: str = ""
    score: float = Field(..., ge=0.0, le=1.0)
    label: str = ""
    comment: str = ""
    tags: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)
    time_spent_seconds: int | None = None

    @field_validator("dimensions")
    @classmethod
    def _validate_dimensions(cls, v: dict[str, float]) -> dict[str, float]:
        for key, val in v.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"dimensions[{key}] 必须在 [0, 1] 区间")
        return v


class AnnotationReviewRequest(BaseModel):
    reviewer_id: str = Field(..., min_length=1, max_length=100)
    review_comment: str = ""
    is_valid: bool = True


class TaskStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|cancelled)$")


# ==================== 任务管理端点 ====================


@router.post("/tasks", response_model=None)
async def create_task(req: AnnotationTaskCreateRequest):
    """创建标注任务"""
    try:
        with AnnotationService() as svc:
            task = svc.create_task(
                case_id=req.case_id,
                evaluator_type=req.evaluator_type,
                question=req.question,
                actual_output=req.actual_output,
                expected_output=req.expected_output,
                context=req.context,
                priority=req.priority,
                required_annotators=req.required_annotators,
                due_at=req.due_at,
                metadata=req.metadata,
            )
            return success_response(data=task.to_dict(), message="标注任务创建成功")
    except Exception as e:
        logger.exception(f"创建标注任务失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"创建失败: {e}"))


@router.post("/tasks/bulk", response_model=None)
async def bulk_create_tasks(req: AnnotationTaskBulkCreateRequest):
    """批量创建标注任务"""
    try:
        with AnnotationService() as svc:
            tasks = svc.bulk_create_tasks([c.model_dump() for c in req.cases])
            return success_response(
                data={"task_count": len(tasks), "task_ids": [t.id for t in tasks]},
                message=f"成功创建 {len(tasks)} 个标注任务",
            )
    except Exception as e:
        logger.exception(f"批量创建标注任务失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"批量创建失败: {e}"))


@router.get("/tasks", response_model=None)
async def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    evaluator_type: str | None = None,
    annotator_id: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """查询标注任务列表"""
    try:
        with AnnotationService() as svc:
            tasks = svc.list_tasks(
                status=status_filter,
                evaluator_type=evaluator_type,
                annotator_id=annotator_id,
                skip=skip,
                limit=limit,
            )
            return success_response(
                data={"total": len(tasks), "tasks": [t.to_dict() for t in tasks]},
                message="查询成功",
            )
    except Exception as e:
        logger.exception(f"查询标注任务失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"查询失败: {e}"))


@router.get("/tasks/{task_id}", response_model=None)
async def get_task(task_id: int):
    """查询任务详情"""
    try:
        with AnnotationService() as svc:
            task = svc.get_task(task_id)
            results = svc.list_results(task_id)
            data = task.to_dict()
            data["results"] = [r.to_dict() for r in results]
            return success_response(data=data, message="查询成功")
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=error_response(404, str(e)))
    except Exception as e:
        logger.exception(f"查询任务详情失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"查询失败: {e}"))


@router.patch("/tasks/{task_id}/status", response_model=None)
async def update_task_status(task_id: int, req: TaskStatusUpdateRequest):
    """更新任务状态"""
    try:
        with AnnotationService() as svc:
            task = svc.update_task_status(task_id, req.status)
            return success_response(data=task.to_dict(), message="状态更新成功")
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=error_response(404, str(e)))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=error_response(400, str(e)))
    except Exception as e:
        logger.exception(f"更新任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"更新失败: {e}"))


# ==================== 标注提交端点 ====================


@router.post("/tasks/{task_id}/results", response_model=None)
async def submit_result(task_id: int, req: AnnotationResultSubmitRequest):
    """提交标注结果"""
    try:
        with AnnotationService() as svc:
            result = svc.submit_result(
                task_id=task_id,
                annotator_id=req.annotator_id,
                score=req.score,
                annotator_name=req.annotator_name,
                label=req.label,
                comment=req.comment,
                tags=req.tags,
                dimensions=req.dimensions,
                time_spent_seconds=req.time_spent_seconds,
            )
            return success_response(data=result.to_dict(), message="标注结果提交成功")
    except TaskNotFoundError as e:
        raise HTTPException(status_code=404, detail=error_response(404, str(e)))
    except DuplicateAnnotationError as e:
        raise HTTPException(status_code=409, detail=error_response(409, str(e)))
    except InvalidScoreError as e:
        raise HTTPException(status_code=400, detail=error_response(400, str(e)))
    except Exception as e:
        logger.exception(f"提交标注结果失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"提交失败: {e}"))


@router.post("/results/{result_id}/review", response_model=None)
async def review_result(result_id: int, req: AnnotationReviewRequest):
    """审核标注结果"""
    try:
        with AnnotationService() as svc:
            result = svc.review_result(
                result_id=result_id,
                reviewer_id=req.reviewer_id,
                review_comment=req.review_comment,
                is_valid=req.is_valid,
            )
            return success_response(data=result.to_dict(), message="审核完成")
    except AnnotationServiceError as e:
        raise HTTPException(status_code=404, detail=error_response(404, str(e)))
    except Exception as e:
        logger.exception(f"审核标注结果失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"审核失败: {e}"))


@router.post("/tasks/{task_id}/golden", response_model=None)
async def submit_golden_sample(task_id: int, req: AnnotationResultSubmitRequest):
    """提交黄金样本标注（用于标注员校准）"""
    try:
        with AnnotationService() as svc:
            result = svc.submit_golden_sample(
                task_id=task_id,
                annotator_id=req.annotator_id,
                golden_score=req.score,
            )
            return success_response(data=result, message="黄金样本提交完成")
    except Exception as e:
        logger.exception(f"黄金样本提交失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"提交失败: {e}"))


# ==================== 统计端点 ====================


@router.get("/agreement/{evaluator_type}", response_model=None)
async def compute_agreement(evaluator_type: str):
    """计算指定评估器类型的标注一致性（Cohen's Kappa）"""
    try:
        with AnnotationService() as svc:
            agreement = svc.compute_agreement(evaluator_type)
            if agreement is None:
                return success_response(
                    data={
                        "evaluator_type": evaluator_type,
                        "sample_size": 0,
                        "message": "数据不足",
                    },
                    message="暂无可计算一致性的样本",
                )
            return success_response(data=agreement.to_dict(), message="一致性计算完成")
    except Exception as e:
        logger.exception(f"一致性计算失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"计算失败: {e}"))


@router.get("/annotators/{annotator_id}/stats", response_model=None)
async def get_annotator_stats(annotator_id: str):
    """查询标注员绩效统计"""
    try:
        with AnnotationService() as svc:
            stats = svc.get_annotator_stats(annotator_id)
            return success_response(data=stats, message="查询成功")
    except Exception as e:
        logger.exception(f"查询标注员绩效失败: {e}")
        raise HTTPException(status_code=500, detail=error_response(500, f"查询失败: {e}"))
