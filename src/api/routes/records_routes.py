"""
记录管理路由模块
包含记录查询、搜索、导出、更新、删除、批量重新评估等端点
"""

import csv
import io
import json
import logging
import time

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette import status as status_module

from src.api.common import error_response, success_response
from src.schemas.schemas import BatchDeleteRequest, BatchUpdateRequest, RecordUpdateRequest
from src.services.data_svc import get_data_service
from src.services.evaluator_svc import run_evaluation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/records", tags=["记录管理"])


def _get_data_service():
    """获取数据服务单例"""
    return get_data_service()


# 记录更新允许的白名单字段（安全：防止伪造评测结果）
_RECORD_UPDATE_ALLOWED_FIELDS = {"model_name", "adapter_name", "status"}
_RECORD_UPDATE_ALLOWED_STATUS = {"passed", "failed", "error", "pending", "config"}


class BatchReevaluateRequest(BaseModel):
    """批量重新评估请求"""

    record_ids: list[int] = Field(..., min_length=1, description="要重新评估的记录ID列表")


class BatchReevaluateResponse(BaseModel):
    """批量重新评估响应"""

    total: int
    success_count: int
    failed_count: int
    results: list[dict]


@router.get("")
async def get_recent_records(response: Response, limit: int = 10):
    """获取最近评估记录"""
    if limit < 1 or limit > 100:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")

    try:
        svc = _get_data_service()
        records = svc.get_recent(limit=limit)
        return success_response({"count": len(records), "items": records})
    except Exception as e:
        logger.error(f"Failed to get records: {e}")
        return error_response(500, "获取记录失败")


@router.get("/search")
async def search_records(
    response: Response,
    evaluator: str | None = None,
    status: str | None = None,
    record_status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """搜索评估记录"""
    if limit < 1 or limit > 100:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")

    if offset < 0 or offset > 10000:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, "offset must be between 0 and 10000")

    actual_status = status or record_status

    try:
        svc = _get_data_service()
        records = svc.search(
            evaluator=evaluator,
            status=actual_status,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = svc.count()
        return success_response(
            {
                "count": len(records),
                "total": total,
                "filters": {
                    "evaluator": evaluator,
                    "status": actual_status,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                    "sort_order": sort_order,
                },
                "records": records,
            }
        )
    except Exception as e:
        logger.error("Search failed: {0}", e)
        return error_response(500, "搜索失败")


@router.get("/export")
async def export_records(format: str = "csv", response: Response = None):
    """导出评估记录(支持CSV和JSON格式)"""
    try:
        # 路径遍历防护 - 只允许csv或json格式
        if format.lower() not in ["csv", "json"]:
            if response:
                response.status_code = status_module.HTTP_400_BAD_REQUEST
            return error_response(400, "非法参数")

        svc = _get_data_service()
        records = svc.get_all_for_export()

        if format.lower() == "json":
            content = json.dumps(records, ensure_ascii=False, indent=2)
            return JSONResponse(
                content=json.loads(content),
                headers={
                    "Content-Disposition": f"attachment; filename=eval_records_{int(time.time())}.json"
                },
                media_type="application/json",
            )
        elif format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            if records:
                headers = list(records[0].keys())
                writer.writerow(headers)

                for record in records:
                    row = []
                    for key in headers:
                        value = record.get(key)
                        if isinstance(value, dict):
                            row.append(json.dumps(value, ensure_ascii=False))
                        elif value is None:
                            row.append("")
                        else:
                            row.append(str(value))
                    writer.writerow(row)

            return PlainTextResponse(
                content=output.getvalue(),
                headers={
                    "Content-Disposition": f"attachment; filename=eval_records_{int(time.time())}.csv"
                },
                media_type="text/csv",
            )
        else:
            return error_response(400, "format must be 'csv' or 'json'")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return error_response(500, "导出失败")


@router.get("/{record_id}")
async def get_record_detail(record_id: int, response: Response):
    """获取单条记录详情"""
    try:
        svc = _get_data_service()
        record = svc.get_by_id(record_id)
        if record:
            return success_response(record)
        else:
            response.status_code = status_module.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to get record: {0}", e)
        return error_response(500, "获取记录失败")


@router.put("/{record_id}")
async def update_record(record_id: int, data: RecordUpdateRequest, response: Response):
    """更新单条记录"""
    update_data = data.model_dump(exclude_none=True)
    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")
    try:
        svc = _get_data_service()
        success = svc.update(record_id, update_data)
        if success:
            record = svc.get_by_id(record_id)
            return success_response(record)
        else:
            response.status_code = status_module.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found or no valid fields to update")
    except Exception as e:
        logger.error("Failed to update record: {0}", e)
        return error_response(500, "更新记录失败")


@router.delete("/{record_id}")
async def delete_record(record_id: int, response: Response):
    """删除单条记录"""
    try:
        svc = _get_data_service()
        success = svc.delete(record_id)
        if success:
            return success_response({"message": "Record deleted successfully"})
        else:
            response.status_code = status_module.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to delete record: {0}", e)
        return error_response(500, "删除记录失败")


@router.post("/batch/delete")
async def batch_delete_records(data: BatchDeleteRequest, response: Response):
    """批量删除记录"""
    try:
        svc = _get_data_service()
        deleted_count = svc.batch_delete(data.ids)
        return success_response(
            {
                "message": "Batch delete completed",
                "deleted_count": deleted_count,
                "total_requested": len(data.ids),
            }
        )
    except Exception as e:
        logger.error("Batch delete failed: {0}", e)
        return error_response(500, "批量删除失败")


@router.post("/batch/update")
async def batch_update_records(data: BatchUpdateRequest, response: Response):
    """批量更新记录"""
    update_data = data.data

    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status_module.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")

    try:
        svc = _get_data_service()
        updated_count = svc.batch_update(data.ids, update_data)
        return success_response(
            {
                "message": "Batch update completed",
                "updated_count": updated_count,
                "total_requested": len(data.ids),
            }
        )
    except Exception as e:
        logger.error("Batch update failed: {0}", e)
        return error_response(500, "批量更新失败")


@router.post("/batch/reevaluate")
async def batch_reevaluate_records(data: BatchReevaluateRequest, response: Response):
    """批量重新评估记录

    根据记录ID列表重新执行评估任务，返回新的评估结果。
    """
    results = []
    success_count = 0
    failed_count = 0

    try:
        svc = _get_data_service()

        for record_id in data.record_ids:
            try:
                # 获取原始记录
                record = svc.get_by_id(record_id)
                if not record:
                    results.append(
                        {
                            "record_id": record_id,
                            "status": "error",
                            "message": "记录不存在",
                        }
                    )
                    failed_count += 1
                    continue

                # 从原始记录中提取评估参数
                response_data = record.get("response_data", {})
                payload = response_data.get("payload", {})

                # 构建评估请求
                eval_request = {
                    "id": f"reeval_{record_id}_{int(time.time())}",
                    "type": record.get("adapter_name", "general"),
                    "payload": payload,
                }

                # 执行评估
                result = run_evaluation_service(eval_request)

                results.append(
                    {
                        "record_id": record_id,
                        "case_id": eval_request["id"],
                        "status": result.get("status", "error"),
                        "score": result.get("data", {}).get("score"),
                        "latency_ms": result.get("latency_ms"),
                    }
                )
                success_count += 1

            except Exception as e:
                logger.error(f"Reevaluate record {record_id} failed: {e}")
                results.append(
                    {
                        "record_id": record_id,
                        "status": "error",
                        "message": str(e),
                    }
                )
                failed_count += 1

        return success_response(
            {
                "total": len(data.record_ids),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results,
            }
        )

    except Exception as e:
        logger.error(f"Batch reevaluate failed: {e}")
        return error_response(500, "批量重新评估失败")
