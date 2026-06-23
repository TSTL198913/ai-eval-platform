"""
📈 src/infra/analytics/visualization_service.py
可视化数据服务 - 2026 工业级实现

为前端图表组件（ECharts/Chart.js）提供标准化的数据契约：

支持的图表类型：
- 雷达图 (radar): 多维度评估结果对比
- 趋势图 (trend): 模型/评估器历史表现变化
- 柱状图 (bar): 不同评估器分数对比
- 分布图 (distribution): 分数分布直方图
- 热力图 (heatmap): 评估器相关性矩阵
- 桑基图 (sankey): 评估流程流转
- 箱线图 (boxplot): 分数离散度分析

设计原则：
1. 纯数据 - 不绑定具体图表库
2. 缓存友好 - 查询结果可被 Redis 等中间件缓存
3. 轻依赖 - 仅使用 numpy/pandas 进行聚合
"""

import logging
import math
from collections import defaultdict
from datetime import datetime
from statistics import mean, median, quantiles, stdev
from typing import Any

logger = logging.getLogger(__name__)


class VisualizationService:
    """可视化数据服务

    所有方法返回的数据结构均可直接被 ECharts option 配置消费。
    """

    # ==================== 雷达图数据 ====================

    @staticmethod
    def generate_radar_chart(
        dimensions: list[str],
        series: list[dict[str, Any]],
        max_value: float = 1.0,
    ) -> dict[str, Any]:
        """生成雷达图数据

        Args:
            dimensions: 维度名称列表，如 ["准确性", "安全性", "流畅性"]
            series: 多组数据，每组 {"name": str, "values": list[float]}
            max_value: 雷达图最大值

        Returns:
            dict: ECharts radar option 数据
        """
        return {
            "chart_type": "radar",
            "title": "多维度评估雷达图",
            "indicator": [{"name": d, "max": max_value} for d in dimensions],
            "series": [
                {
                    "name": s["name"],
                    "value": s["values"],
                    "metadata": s.get("metadata", {}),
                }
                for s in series
            ],
            "legend": [s["name"] for s in series],
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def radar_from_evaluator_results(
        results: list[dict[str, Any]],
        evaluator_dimension_field: str = "data",
    ) -> dict[str, Any]:
        """从评估器结果列表自动提取多维度数据生成雷达图

        每个 result 应包含 evaluator_type 和 score 字段
        """
        if not results:
            return VisualizationService.generate_radar_chart(dimensions=[], series=[])

        # 聚合每个评估器的平均分
        by_evaluator: dict[str, list[float]] = defaultdict(list)
        for r in results:
            by_evaluator[r.get("evaluator_type", "unknown")].append(float(r.get("score", 0)))

        dimensions = sorted(by_evaluator.keys())
        series_values = [round(mean(by_evaluator[d]), 4) for d in dimensions]

        return VisualizationService.generate_radar_chart(
            dimensions=dimensions,
            series=[{"name": "评估器平均分", "values": series_values}],
        )

    # ==================== 趋势图数据 ====================

    @staticmethod
    def generate_trend_chart(
        series: list[dict[str, Any]],
        time_unit: str = "day",
    ) -> dict[str, Any]:
        """生成趋势图数据

        Args:
            series: 每组 {"name": str, "points": [(timestamp, value), ...]}
            time_unit: 时间单位（day/hour/minute）

        Returns:
            dict: ECharts line chart option
        """
        # 收集所有时间戳
        all_timestamps: set[str] = set()
        for s in series:
            for ts, _ in s["points"]:
                all_timestamps.add(ts)
        sorted_ts = sorted(all_timestamps)

        return {
            "chart_type": "line",
            "title": "历史趋势",
            "x_axis": {
                "type": "category",
                "data": sorted_ts,
                "name": "时间",
            },
            "y_axis": {
                "type": "value",
                "name": "分数",
                "min": 0.0,
                "max": 1.0,
            },
            "series": [
                {
                    "name": s["name"],
                    "type": "line",
                    "data": [
                        (ts, next((v for t, v in s["points"] if t == ts), None)) for ts in sorted_ts
                    ],
                    "smooth": True,
                    "showSymbol": False,
                }
                for s in series
            ],
            "time_unit": time_unit,
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def trend_from_evaluations(
        evaluations: list[dict[str, Any]],
        evaluator_types: list[str] | None = None,
        bucket: str = "day",
    ) -> dict[str, Any]:
        """从评估结果列表生成趋势图

        Args:
            evaluations: 评估结果列表，每项包含 evaluator_type/score/created_at
            evaluator_types: 要包含的评估器类型，None 表示全部
            bucket: 时间分桶粒度 day/hour/minute
        """
        if not evaluations:
            return VisualizationService.generate_trend_chart(series=[])

        # 按评估器和时间桶聚合
        by_type_bucket: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for e in evaluations:
            etype = e.get("evaluator_type", "unknown")
            if evaluator_types and etype not in evaluator_types:
                continue
            ts = e.get("created_at") or e.get("timestamp")
            if not ts:
                continue
            bucket_key = VisualizationService._bucket_timestamp(ts, bucket)
            by_type_bucket[etype][bucket_key].append(float(e.get("score", 0)))

        series = []
        for etype, buckets in by_type_bucket.items():
            points = sorted(
                (bucket_key, round(mean(scores), 4)) for bucket_key, scores in buckets.items()
            )
            series.append({"name": etype, "points": points})

        return VisualizationService.generate_trend_chart(series=series, time_unit=bucket)

    # ==================== 柱状图数据 ====================

    @staticmethod
    def generate_bar_chart(
        categories: list[str],
        series: list[dict[str, Any]],
        y_max: float = 1.0,
    ) -> dict[str, Any]:
        """生成柱状图数据

        Args:
            categories: 横轴分类，如评估器名称
            series: 每组 {"name": str, "values": list[float]}
        """
        return {
            "chart_type": "bar",
            "title": "评估器分数对比",
            "x_axis": {"type": "category", "data": categories},
            "y_axis": {"type": "value", "min": 0.0, "max": y_max},
            "series": [
                {
                    "name": s["name"],
                    "type": "bar",
                    "data": s["values"],
                    "label": {"show": True, "position": "top"},
                }
                for s in series
            ],
            "legend": [s["name"] for s in series],
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== 分布图数据 ====================

    @staticmethod
    def generate_distribution_chart(
        scores: list[float],
        bin_count: int = 10,
        min_val: float = 0.0,
        max_val: float = 1.0,
    ) -> dict[str, Any]:
        """生成分数分布直方图数据"""
        if not scores:
            return {
                "chart_type": "histogram",
                "bins": [],
                "counts": [],
                "stats": {},
                "generated_at": datetime.utcnow().isoformat(),
            }

        bin_width = (max_val - min_val) / bin_count
        counts = [0] * bin_count
        bin_labels = []
        for i in range(bin_count):
            low = min_val + i * bin_width
            high = low + bin_width
            bin_labels.append(f"{low:.2f}-{high:.2f}")

        for score in scores:
            if score < min_val or score > max_val:
                continue
            idx = min(bin_count - 1, int((score - min_val) / bin_width))
            counts[idx] += 1

        stats = {
            "count": len(scores),
            "mean": round(mean(scores), 4),
            "median": round(median(scores), 4),
            "stdev": round(stdev(scores), 4) if len(scores) > 1 else 0.0,
            "min": round(min(scores), 4),
            "max": round(max(scores), 4),
        }
        try:
            q = quantiles(scores, n=4)
            stats["q1"] = round(q[0], 4)
            stats["q3"] = round(q[2], 4)
        except Exception:
            pass

        return {
            "chart_type": "histogram",
            "bins": bin_labels,
            "counts": counts,
            "stats": stats,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== 箱线图数据 ====================

    @staticmethod
    def generate_boxplot(
        groups: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """生成箱线图数据

        Args:
            groups: [{"name": "评估器A", "values": [0.1, 0.2, ...]}, ...]
        """
        box_data = []
        for g in groups:
            values = g["values"]
            if not values:
                box_data.append([0, 0, 0, 0, 0])
                continue
            sorted_vals = sorted(values)
            try:
                q = quantiles(sorted_vals, n=4)
                q1, median_val, q3 = q
            except Exception:
                q1, median_val, q3 = (
                    sorted_vals[0],
                    sorted_vals[len(sorted_vals) // 2],
                    sorted_vals[-1],
                )
            iqr = q3 - q1
            lower = max(sorted_vals[0], q1 - 1.5 * iqr)
            upper = min(sorted_vals[-1], q3 + 1.5 * iqr)
            box_data.append(
                [round(lower, 4), round(q1, 4), round(median_val, 4), round(q3, 4), round(upper, 4)]
            )

        return {
            "chart_type": "boxplot",
            "title": "分数离散度分析",
            "categories": [g["name"] for g in groups],
            "box_data": box_data,
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ==================== 热力图数据 ====================

    @staticmethod
    def generate_heatmap(
        x_labels: list[str],
        y_labels: list[str],
        values: list[list[float]],
    ) -> dict[str, Any]:
        """生成相关性热力图

        Args:
            x_labels: 横轴标签
            y_labels: 纵轴标签
            values: 二维数组 values[i][j] 表示 (y[i], x[j]) 的值
        """
        heatmap_data = []
        for i, _y in enumerate(y_labels):
            for j, _x in enumerate(x_labels):
                if i < len(values) and j < len(values[i]):
                    heatmap_data.append([j, i, round(values[i][j], 4)])

        return {
            "chart_type": "heatmap",
            "title": "评估器相关性矩阵",
            "x_labels": x_labels,
            "y_labels": y_labels,
            "data": heatmap_data,
            "min_value": min((v[2] for v in heatmap_data), default=0.0),
            "max_value": max((v[2] for v in heatmap_data), default=1.0),
            "generated_at": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def heatmap_from_evaluations(
        evaluations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """从评估结果生成评估器相关性热力图（皮尔逊相关系数）"""
        # 按评估器聚合分数
        by_type: dict[str, list[float]] = defaultdict(list)
        for e in evaluations:
            etype = e.get("evaluator_type", "unknown")
            by_type[etype].append(float(e.get("score", 0)))

        types = sorted(by_type.keys())
        n = len(types)
        if n == 0:
            return VisualizationService.generate_heatmap([], [], [])

        # 截断到相同长度以便计算相关系数
        min_len = min(len(v) for v in by_type.values())
        if min_len < 2:
            return VisualizationService.generate_heatmap(
                types, types, [[1.0] * n for _ in range(n)]
            )

        matrix = [[0.0] * n for _ in range(n)]
        for i, ti in enumerate(types):
            for j, tj in enumerate(types):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    matrix[i][j] = round(
                        VisualizationService._pearson(by_type[ti][:min_len], by_type[tj][:min_len]),
                        4,
                    )
        return VisualizationService.generate_heatmap(types, types, matrix)

    # ==================== 综合仪表盘 ====================

    @staticmethod
    def generate_dashboard(
        evaluations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """生成综合仪表盘数据

        一次性输出多个图表数据，前端可单次请求完整展示
        """
        all_scores = [float(e.get("score", 0)) for e in evaluations]
        by_evaluator: dict[str, list[float]] = defaultdict(list)
        for e in evaluations:
            by_evaluator[e.get("evaluator_type", "unknown")].append(float(e.get("score", 0)))

        return {
            "kpi_cards": VisualizationService._build_kpi_cards(all_scores, by_evaluator),
            "radar_chart": VisualizationService.radar_from_evaluator_results(evaluations),
            "trend_chart": VisualizationService.trend_from_evaluations(evaluations, bucket="day"),
            "distribution_chart": VisualizationService.generate_distribution_chart(all_scores),
            "boxplot": VisualizationService.generate_boxplot(
                [{"name": k, "values": v} for k, v in by_evaluator.items()]
            ),
            "heatmap": VisualizationService.heatmap_from_evaluations(evaluations),
            "generated_at": datetime.utcnow().isoformat(),
            "total_evaluations": len(evaluations),
        }

    @staticmethod
    def _build_kpi_cards(
        all_scores: list[float],
        by_evaluator: dict[str, list[float]],
    ) -> list[dict[str, Any]]:
        """生成 KPI 卡片数据"""
        if not all_scores:
            return [
                {"label": "总评估数", "value": 0, "unit": ""},
                {"label": "平均分", "value": 0.0, "unit": ""},
                {"label": "通过率", "value": "0%", "unit": ""},
            ]
        pass_rate = sum(1 for s in all_scores if s >= 0.8) / len(all_scores)
        return [
            {"label": "总评估数", "value": len(all_scores), "unit": ""},
            {"label": "平均分", "value": round(mean(all_scores), 4), "unit": ""},
            {"label": "通过率", "value": f"{pass_rate:.1%}", "unit": ""},
            {"label": "评估器数", "value": len(by_evaluator), "unit": ""},
        ]

    # ==================== 工具方法 ====================

    @staticmethod
    def _bucket_timestamp(ts: Any, bucket: str) -> str:
        """将时间戳分桶"""
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return ts
        elif isinstance(ts, (int, float)):
            dt = datetime.utcfromtimestamp(ts)
        elif isinstance(ts, datetime):
            dt = ts
        else:
            return str(ts)

        if bucket == "minute":
            return dt.strftime("%Y-%m-%d %H:%M")
        if bucket == "hour":
            return dt.strftime("%Y-%m-%d %H:00")
        return dt.strftime("%Y-%m-%d")

    @staticmethod
    def _pearson(xs: list[float], ys: list[float]) -> float:
        """皮尔逊相关系数"""
        n = min(len(xs), len(ys))
        if n < 2:
            return 0.0
        xs = xs[:n]
        ys = ys[:n]
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=False))
        den_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        den_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
        if den_x == 0 or den_y == 0:
            return 0.0
        return max(-1.0, min(1.0, num / (den_x * den_y)))


__all__ = ["VisualizationService"]
