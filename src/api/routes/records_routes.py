"""
记录管理路由模块
包含记录查询、搜索、导出、更新、删除等端点
"""

import csv
import io
import json
import logging
import time

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse, PlainTextResponse

from src.api.common import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/records", tags=["记录管理"])

# Repository 单例
_repository = None


def _get_repository():
    """获取 Repository 单例"""
    global _repository
    if _repository is None:
        from src.infra.db.repository import EvaluationRepository

        _repository = EvaluationRepository()
    return _repository


# 记录更新允许的白名单字段（安全：防止伪造评测结果）
_RECORD_UPDATE_ALLOWED_FIELDS = {"model_name", "adapter_name", "status"}
_RECORD_UPDATE_ALLOWED_STATUS = {"passed", "failed", "error", "pending", "config"}


@router.get("")
async def get_recent_records(response: Response, limit: int = 10):
    """获取最近评估记录"""
    if limit < 1 or limit > 100:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")

    try:
        repo = _get_repository()
        records = repo.get_recent(limit=limit)
        return success_response({"count": len(records), "items": records})
    except Exception as e:
        logger.error(f"Failed to get records: {e}")
        return error_response(500, "获取记录失败")


@router.get("/search")
async def search_records(
    response: Response,
    evaluator: str | None = None,
    record_status: str | None = None,
    limit: int = 10,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
):
    """搜索评估记录"""
    if limit < 1 or limit > 100:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "limit must be between 1 and 100")

    if offset < 0 or offset > 10000:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "offset must be between 0 and 10000")

    try:
        repo = _get_repository()
        records = repo.search(
            evaluator=evaluator,
            status=record_status,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total = repo.count()
        return success_response(
            {
                "count": len(records),
                "total": total,
                "filters": {
                    "evaluator": evaluator,
                    "status": record_status,
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
                response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response(400, "非法参数")

        repo = _get_repository()
        records = repo.get_all_for_export()

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
        repo = _get_repository()
        record = repo.get_by_id(record_id)
        if record:
            return success_response(record)
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to get record: {0}", e)
        return error_response(500, "获取记录失败")


@router.put("/{record_id}")
async def update_record(record_id: int, update_data: dict, response: Response):
    """更新单条记录"""
    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")
    try:
        repo = _get_repository()
        success = repo.update(record_id, update_data)
        if success:
            record = repo.get_by_id(record_id)
            return success_response(record)
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found or no valid fields to update")
    except Exception as e:
        logger.error("Failed to update record: {0}", e)
        return error_response(500, "更新记录失败")


@router.delete("/{record_id}")
async def delete_record(record_id: int, response: Response):
    """删除单条记录"""
    try:
        repo = _get_repository()
        success = repo.delete(record_id)
        if success:
            return success_response({"message": "Record deleted successfully"})
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return error_response(404, "Record not found")
    except Exception as e:
        logger.error("Failed to delete record: {0}", e)
        return error_response(500, "删除记录失败")


@router.post("/batch/delete")
async def batch_delete_records(data: dict, response: Response):
    """批量删除记录"""
    record_ids = data.get("ids", [])
    if not isinstance(record_ids, list) or not record_ids:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "ids must be a non-empty list")

    try:
        repo = _get_repository()
        deleted_count = repo.batch_delete(record_ids)
        return success_response(
            {
                "message": "Batch delete completed",
                "deleted_count": deleted_count,
                "total_requested": len(record_ids),
            }
        )
    except Exception as e:
        logger.error("Batch delete failed: {0}", e)
        return error_response(500, "批量删除失败")


@router.post("/batch/update")
async def batch_update_records(data: dict, response: Response):
    """批量更新记录"""
    record_ids = data.get("ids", [])
    update_data = data.get("data", {})

    if not isinstance(record_ids, list) or not record_ids:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "ids must be a non-empty list")

    if not isinstance(update_data, dict) or not update_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, "data must be a non-empty dict")

    invalid_fields = set(update_data.keys()) - _RECORD_UPDATE_ALLOWED_FIELDS
    if invalid_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid fields: {', '.join(invalid_fields)}")
    if "status" in update_data and update_data["status"] not in _RECORD_UPDATE_ALLOWED_STATUS:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return error_response(400, f"Invalid status value: {update_data['status']}")

    try:
        repo = _get_repository()
        updated_count = repo.batch_update(record_ids, update_data)
        return success_response(
            {
                "message": "Batch update completed",
                "updated_count": updated_count,
                "total_requested": len(record_ids),
            }
        )
    except Exception as e:
        logger.error("Batch update failed: {0}", e)
        return error_response(500, "批量更新失败")
