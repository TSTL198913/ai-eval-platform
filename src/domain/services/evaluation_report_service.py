"""
评估统计报表服务 - 2026 工业级标准

用于生成评估结果的统计报表，支持：
- 多维度统计分析
- 趋势分析
- 模型对比分析
- 评估器性能分析
- 导出为多种格式

设计原则：
- 支持灵活的时间范围筛选
- 支持多维度分组统计
- 提供可视化数据格式
- 完整的错误处理和日志记录
"""

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


class ReportType(str, Enum):
    """报表类型"""

    SUMMARY = "summary"
    TREND = "trend"
    MODEL_COMPARISON = "model_comparison"
    EVALUATOR_PERFORMANCE = "evaluator_performance"
    DETAIL = "detail"


class EvaluationReportService:
    """评估统计报表服务"""

    def __init__(self):
        self._repository = EvaluationRepository()

    def generate_report(
        self,
        report_type: ReportType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Args:
            report_type: 报表类型
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            报表数据
        """
        if isinstance(report_type, str):
            report_type = ReportType(report_type.lower())

        if report_type == ReportType.SUMMARY:
            return self._generate_summary_report(start_date, end_date, filters)
        elif report_type == ReportType.TREND:
            return self._generate_trend_report(start_date, end_date, filters)
        elif report_type == ReportType.MODEL_COMPARISON:
            return self._generate_model_comparison_report(start_date, end_date, filters)
        elif report_type == ReportType.EVALUATOR_PERFORMANCE:
            return self._generate_evaluator_performance_report(start_date, end_date, filters)
        elif report_type == ReportType.DETAIL:
            return self._generate_detail_report(start_date, end_date, filters)

        raise ValueError(f"不支持的报表类型: {report_type}")

    def _generate_summary_report(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成汇总报表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            汇总报表数据
        """
        data = self._get_filtered_data(start_date, end_date, filters)

        if not data:
            return self._empty_report("汇总报表")

        total = len(data)
        scores = [item.get("score") for item in data if item.get("score") is not None]

        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        min_score = min(scores) if scores else 0
        score_std = self._calculate_std(scores) if len(scores) > 1 else 0

        status_counts = {}
        for item in data:
            status = item.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        latency_values = [item.get("latency_ms") for item in data if item.get("latency_ms") is not None]
        avg_latency = sum(latency_values) / len(latency_values) if latency_values else 0
        p95_latency = self._calculate_percentile(latency_values, 95) if latency_values else 0
        p99_latency = self._calculate_percentile(latency_values, 99) if latency_values else 0

        models = set(item.get("model_name", "unknown") for item in data)
        evaluators = set(item.get("adapter_name", "unknown") for item in data)

        return {
            "report_type": "summary",
            "generated_at": datetime.now().isoformat(),
            "time_range": self._format_time_range(start_date, end_date),
            "summary": {
                "total_evaluations": total,
                "unique_models": len(models),
                "unique_evaluators": len(evaluators),
            },
            "score_statistics": {
                "average_score": round(avg_score, 4),
                "max_score": round(max_score, 4),
                "min_score": round(min_score, 4),
                "std_dev": round(score_std, 4),
                "sample_size": len(scores),
            },
            "status_distribution": status_counts,
            "latency_statistics": {
                "average_ms": round(avg_latency, 2),
                "p95_ms": round(p95_latency, 2),
                "p99_ms": round(p99_latency, 2),
                "sample_size": len(latency_values),
            },
            "models": list(models),
            "evaluators": list(evaluators),
        }

    def _generate_trend_report(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成趋势报表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            趋势报表数据
        """
        data = self._get_filtered_data(start_date, end_date, filters)

        if not data:
            return self._empty_report("趋势报表")

        trend_data = {}
        for item in data:
            created_at = item.get("created_at", "")
            date_key = created_at[:10] if isinstance(created_at, str) else str(created_at)[:10]
            if date_key not in trend_data:
                trend_data[date_key] = {
                    "count": 0,
                    "scores": [],
                    "latencies": [],
                }
            trend_data[date_key]["count"] += 1
            if item.get("score") is not None:
                trend_data[date_key]["scores"].append(item.get("score"))
            if item.get("latency_ms") is not None:
                trend_data[date_key]["latencies"].append(item.get("latency_ms"))

        trend_list = []
        for date_key, values in sorted(trend_data.items()):
            scores = values["scores"]
            latencies = values["latencies"]
            trend_list.append({
                "date": date_key,
                "count": values["count"],
                "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
            })

        return {
            "report_type": "trend",
            "generated_at": datetime.now().isoformat(),
            "time_range": self._format_time_range(start_date, end_date),
            "trend_data": trend_list,
            "total_days": len(trend_list),
        }

    def _generate_model_comparison_report(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成模型对比报表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            模型对比报表数据
        """
        data = self._get_filtered_data(start_date, end_date, filters)

        if not data:
            return self._empty_report("模型对比报表")

        model_data = {}
        for item in data:
            model_name = item.get("model_name", "unknown")
            if model_name not in model_data:
                model_data[model_name] = {
                    "count": 0,
                    "scores": [],
                    "latencies": [],
                    "status_counts": {},
                }
            model_data[model_name]["count"] += 1
            if item.get("score") is not None:
                model_data[model_name]["scores"].append(item.get("score"))
            if item.get("latency_ms") is not None:
                model_data[model_name]["latencies"].append(item.get("latency_ms"))
            status = item.get("status", "unknown")
            model_data[model_name]["status_counts"][status] = (
                model_data[model_name]["status_counts"].get(status, 0) + 1
            )

        comparison_list = []
        for model_name, values in model_data.items():
            scores = values["scores"]
            latencies = values["latencies"]
            comparison_list.append({
                "model_name": model_name,
                "count": values["count"],
                "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
                "score_std": round(self._calculate_std(scores), 4) if len(scores) > 1 else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "status_distribution": values["status_counts"],
            })

        comparison_list.sort(key=lambda x: x["avg_score"], reverse=True)

        return {
            "report_type": "model_comparison",
            "generated_at": datetime.now().isoformat(),
            "time_range": self._format_time_range(start_date, end_date),
            "model_comparison": comparison_list,
            "total_models": len(comparison_list),
        }

    def _generate_evaluator_performance_report(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成评估器性能报表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            评估器性能报表数据
        """
        data = self._get_filtered_data(start_date, end_date, filters)

        if not data:
            return self._empty_report("评估器性能报表")

        evaluator_data = {}
        for item in data:
            evaluator_name = item.get("adapter_name", "unknown")
            if evaluator_name not in evaluator_data:
                evaluator_data[evaluator_name] = {
                    "count": 0,
                    "scores": [],
                    "latencies": [],
                    "status_counts": {},
                }
            evaluator_data[evaluator_name]["count"] += 1
            if item.get("score") is not None:
                evaluator_data[evaluator_name]["scores"].append(item.get("score"))
            if item.get("latency_ms") is not None:
                evaluator_data[evaluator_name]["latencies"].append(item.get("latency_ms"))
            status = item.get("status", "unknown")
            evaluator_data[evaluator_name]["status_counts"][status] = (
                evaluator_data[evaluator_name]["status_counts"].get(status, 0) + 1
            )

        performance_list = []
        for evaluator_name, values in evaluator_data.items():
            scores = values["scores"]
            latencies = values["latencies"]
            performance_list.append({
                "evaluator_name": evaluator_name,
                "count": values["count"],
                "avg_score": round(sum(scores) / len(scores), 4) if scores else 0,
                "score_std": round(self._calculate_std(scores), 4) if len(scores) > 1 else 0,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
                "p95_latency_ms": round(self._calculate_percentile(latencies, 95), 2) if latencies else 0,
                "status_distribution": values["status_counts"],
                "pass_rate": self._calculate_pass_rate(values["status_counts"]),
            })

        performance_list.sort(key=lambda x: x["count"], reverse=True)

        return {
            "report_type": "evaluator_performance",
            "generated_at": datetime.now().isoformat(),
            "time_range": self._format_time_range(start_date, end_date),
            "evaluator_performance": performance_list,
            "total_evaluators": len(performance_list),
        }

    def _generate_detail_report(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        生成详细报表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            详细报表数据
        """
        data = self._get_filtered_data(start_date, end_date, filters)

        return {
            "report_type": "detail",
            "generated_at": datetime.now().isoformat(),
            "time_range": self._format_time_range(start_date, end_date),
            "total_records": len(data),
            "records": data,
        }

    def _get_filtered_data(
        self,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        获取过滤后的数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件

        Returns:
            过滤后的数据列表
        """
        if not filters:
            filters = {}

        return self._repository.search(
            evaluator=filters.get("evaluator"),
            status=filters.get("status"),
            type=filters.get("type"),
            limit=filters.get("limit", 10000),
            offset=filters.get("offset", 0),
            sort_by="created_at",
            sort_order="desc",
        )

    def _empty_report(self, report_name: str) -> Dict[str, Any]:
        """
        生成空报表

        Args:
            report_name: 报表名称

        Returns:
            空报表数据
        """
        return {
            "report_type": report_name,
            "generated_at": datetime.now().isoformat(),
            "message": "没有找到匹配的数据",
            "data": {},
        }

    def _format_time_range(
        self, start_date: Optional[datetime], end_date: Optional[datetime]
    ) -> Dict[str, str]:
        """
        格式化时间范围

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            格式化的时间范围
        """
        return {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }

    def _calculate_std(self, values: List[float]) -> float:
        """
        计算标准差

        Args:
            values: 数值列表

        Returns:
            标准差
        """
        if not values:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """
        计算百分位数

        Args:
            values: 数值列表
            percentile: 百分位（如 95, 99）

        Returns:
            百分位数
        """
        if not values:
            return 0.0

        sorted_values = sorted(values)
        n = len(sorted_values)
        index = (percentile / 100) * (n - 1)

        lower = int(index)
        upper = min(lower + 1, n - 1)
        fraction = index - lower

        if lower == upper:
            return sorted_values[lower]

        return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])

    def _calculate_pass_rate(self, status_counts: Dict[str, int]) -> float:
        """
        计算通过率

        Args:
            status_counts: 状态计数

        Returns:
            通过率
        """
        total = sum(status_counts.values())
        passed = status_counts.get("pass", 0) + status_counts.get("SUCCESS", 0)
        return round(passed / total * 100, 2) if total > 0 else 0

    def get_report_types(self) -> List[str]:
        """
        获取支持的报表类型

        Returns:
            报表类型列表
        """
        return [report_type.value for report_type in ReportType]

    def export_report(
        self,
        report_type: ReportType,
        format: str = "json",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        filters: Optional[Dict[str, Any]] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        导出报表

        Args:
            report_type: 报表类型
            format: 导出格式
            start_date: 开始日期
            end_date: 结束日期
            filters: 过滤条件
            filename: 文件名

        Returns:
            文件路径
        """
        if isinstance(report_type, str):
            report_type = ReportType(report_type.lower())

        report_data = self.generate_report(report_type, start_date, end_date, filters)

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type.value}_report_{timestamp}.{format}"

        try:
            import os

            filepath = os.path.join("reports", filename)
            os.makedirs("reports", exist_ok=True)

            if format == "json":
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, ensure_ascii=False, indent=2)
            elif format == "csv":
                self._export_csv(report_data, filepath)
            else:
                raise ValueError(f"不支持的导出格式: {format}")

            logger.info(f"报表导出成功: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"报表导出失败: {e}")
            raise

    def _export_csv(self, report_data: Dict[str, Any], filepath: str) -> None:
        """
        导出为 CSV 格式

        Args:
            report_data: 报表数据
            filepath: 文件路径
        """
        import csv

        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            report_type = report_data.get("report_type", "")

            if report_type == "summary":
                writer.writerow(["指标", "值"])
                summary = report_data.get("summary", {})
                for key, value in summary.items():
                    writer.writerow([key, value])

                score_stats = report_data.get("score_statistics", {})
                writer.writerow([])
                writer.writerow(["分数统计"])
                for key, value in score_stats.items():
                    writer.writerow([key, value])

                status_dist = report_data.get("status_distribution", {})
                writer.writerow([])
                writer.writerow(["状态分布"])
                for key, value in status_dist.items():
                    writer.writerow([key, value])

                latency_stats = report_data.get("latency_statistics", {})
                writer.writerow([])
                writer.writerow(["延迟统计"])
                for key, value in latency_stats.items():
                    writer.writerow([key, value])

            elif report_type == "trend":
                trend_data = report_data.get("trend_data", [])
                if trend_data:
                    writer.writerow(list(trend_data[0].keys()))
                    for item in trend_data:
                        writer.writerow(list(item.values()))

            elif report_type == "model_comparison":
                model_data = report_data.get("model_comparison", [])
                if model_data:
                    writer.writerow(list(model_data[0].keys()))
                    for item in model_data:
                        row = []
                        for key in model_data[0].keys():
                            value = item[key]
                            if isinstance(value, dict):
                                row.append(json.dumps(value, ensure_ascii=False))
                            else:
                                row.append(value)
                        writer.writerow(row)

            elif report_type == "evaluator_performance":
                eval_data = report_data.get("evaluator_performance", [])
                if eval_data:
                    writer.writerow(list(eval_data[0].keys()))
                    for item in eval_data:
                        row = []
                        for key in eval_data[0].keys():
                            value = item[key]
                            if isinstance(value, dict):
                                row.append(json.dumps(value, ensure_ascii=False))
                            else:
                                row.append(value)
                        writer.writerow(row)

            elif report_type == "detail":
                records = report_data.get("records", [])
                if records:
                    writer.writerow(list(records[0].keys()))
                    for item in records:
                        writer.writerow(list(item.values()))


evaluation_report_service = EvaluationReportService()
