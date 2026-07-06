"""
评估结果导出服务 - 2026 工业级标准

用于导出评估结果，支持：
- CSV 格式导出
- JSON 格式导出
- Excel 格式导出
- 支持过滤和排序
- 支持分页导出
- 支持自定义导出字段

设计原则：
- 支持多种格式，便于不同场景使用
- 支持过滤条件，按需导出数据
- 支持大文件导出，避免内存溢出
- 完整的错误处理和日志记录
"""

import csv
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from src.infra.db.repository import EvaluationRepository

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """导出格式"""

    CSV = "csv"
    JSON = "json"
    EXCEL = "excel"


class EvaluationExportService:
    """评估结果导出服务"""

    def __init__(self):
        self._repository = EvaluationRepository()

    def export(
        self,
        format: ExportFormat,
        filters: Optional[Dict[str, Any]] = None,
        fields: Optional[List[str]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        filename: Optional[str] = None,
    ) -> str:
        """
        导出评估结果

        Args:
            format: 导出格式
            filters: 过滤条件
            fields: 导出字段列表
            sort_by: 排序字段
            sort_order: 排序顺序
            filename: 导出文件名

        Returns:
            导出文件路径
        """
        data = self._fetch_data(filters, sort_by, sort_order)
        data = self._filter_fields(data, fields)

        if isinstance(format, str):
            format = ExportFormat(format.lower())

        if not filename:
            filename = self._generate_filename(format)

        if format == ExportFormat.CSV:
            return self._export_csv(data, filename)
        elif format == ExportFormat.JSON:
            return self._export_json(data, filename)
        elif format == ExportFormat.EXCEL:
            return self._export_excel(data, filename)

        raise ValueError(f"不支持的导出格式: {format}")

    def _fetch_data(
        self,
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Dict[str, Any]]:
        """
        获取评估数据

        Args:
            filters: 过滤条件
            sort_by: 排序字段
            sort_order: 排序顺序

        Returns:
            评估数据列表
        """
        if not filters:
            filters = {}

        return self._repository.search(
            evaluator=filters.get("evaluator"),
            status=filters.get("status"),
            type=filters.get("type"),
            limit=filters.get("limit", 10000),
            offset=filters.get("offset", 0),
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def _filter_fields(
        self, data: List[Dict[str, Any]], fields: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """
        过滤导出字段

        Args:
            data: 原始数据
            fields: 需要导出的字段列表

        Returns:
            过滤后的数据
        """
        if not fields:
            return data

        filtered_data = []
        for item in data:
            filtered_item = {field: item.get(field) for field in fields if field in item}
            filtered_data.append(filtered_item)

        return filtered_data

    def _generate_filename(self, format: ExportFormat) -> str:
        """
        生成导出文件名

        Args:
            format: 导出格式

        Returns:
            文件名
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = "xlsx" if format == ExportFormat.EXCEL else format.value
        return f"evaluation_results_{timestamp}.{ext}"

    def _export_csv(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        导出为 CSV 格式

        Args:
            data: 评估数据
            filename: 文件名

        Returns:
            文件路径
        """
        if not data:
            logger.warning("没有数据可导出")
            return filename

        try:
            import os

            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)

            logger.info(f"CSV 导出成功: {filepath}, 记录数: {len(data)}")
            return filepath
        except Exception as e:
            logger.error(f"CSV 导出失败: {e}")
            raise

    def _export_json(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        导出为 JSON 格式

        Args:
            data: 评估数据
            filename: 文件名

        Returns:
            文件路径
        """
        try:
            import os

            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

            logger.info(f"JSON 导出成功: {filepath}, 记录数: {len(data)}")
            return filepath
        except Exception as e:
            logger.error(f"JSON 导出失败: {e}")
            raise

    def _export_excel(self, data: List[Dict[str, Any]], filename: str) -> str:
        """
        导出为 Excel 格式

        Args:
            data: 评估数据
            filename: 文件名

        Returns:
            文件路径
        """
        try:
            import os

            try:
                from openpyxl import Workbook
            except ImportError:
                logger.warning("openpyxl 未安装，回退到 CSV 格式")
                return self._export_csv(data, filename.replace(".xlsx", ".csv"))

            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            wb = Workbook()
            ws = wb.active
            ws.title = "评估结果"

            if data:
                ws.append(list(data[0].keys()))

                for item in data:
                    row = []
                    for key in data[0].keys():
                        value = item.get(key)
                        if isinstance(value, (dict, list)):
                            row.append(json.dumps(value, ensure_ascii=False))
                        else:
                            row.append(value)
                    ws.append(row)

            wb.save(filepath)
            logger.info(f"Excel 导出成功: {filepath}, 记录数: {len(data)}")
            return filepath
        except Exception as e:
            logger.error(f"Excel 导出失败: {e}")
            raise

    def get_export_formats(self) -> List[str]:
        """
        获取支持的导出格式

        Returns:
            格式列表
        """
        return [format.value for format in ExportFormat]

    def get_available_fields(self) -> List[str]:
        """
        获取可用的导出字段

        Returns:
            字段列表
        """
        return [
            "id",
            "case_id",
            "model_name",
            "adapter_name",
            "status",
            "latency_ms",
            "score",
            "created_at",
        ]


evaluation_export_service = EvaluationExportService()
