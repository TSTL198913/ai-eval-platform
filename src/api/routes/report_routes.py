"""
报告路由模块
包含报告列表、报告详情、报告生成等端点
"""

import logging
import os

from fastapi import APIRouter, Response, status
from fastapi.responses import FileResponse

from src.api.common import _get_data_service, error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["报告"])


@router.get("")
async def get_reports():
    """获取报告列表"""
    try:
        report_dir = "reports"
        if os.path.exists(report_dir):
            reports = []
            for filename in sorted(os.listdir(report_dir)):
                if filename.endswith(".html"):
                    filepath = os.path.join(report_dir, filename)
                    reports.append(
                        {
                            "filename": filename,
                            "path": f"/api/v1/reports/{filename}",
                            "size": os.path.getsize(filepath),
                            "created_at": os.path.getmtime(filepath),
                        }
                    )
            return success_response({"reports": reports})
        return success_response({"reports": []})
    except Exception as e:
        logger.error(f"Failed to get reports: {e}")
        return error_response(500, "获取报告列表失败")


@router.get("/{filename}")
async def get_report(filename: str, response: Response):
    """获取单个报告"""
    try:
        report_dir = os.path.abspath("reports")
        filepath = os.path.normpath(os.path.join(report_dir, filename))

        if not filepath.startswith(report_dir):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return error_response(400, "Invalid filename")

        if os.path.exists(filepath):
            return FileResponse(filepath)
        response.status_code = status.HTTP_404_NOT_FOUND
        return error_response(404, f"Report '{filename}' not found")
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        return error_response(500, "获取报告失败")


@router.post("/generate")
async def generate_report_endpoint(filter_params: dict = None):
    """生成评测报告"""
    try:
        from src.domain.reports.report_generator import generate_report_from_records

        svc = _get_data_service()
        if filter_params:
            records = svc.search(**filter_params)
        else:
            records = svc.get_recent(limit=100)

        report_path = generate_report_from_records(records)
        return success_response(
            {
                "message": "Report generated successfully",
                "path": report_path,
                "url": f"/api/v1/reports/{os.path.basename(report_path)}",
            }
        )
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        return error_response(500, "生成报告失败")
