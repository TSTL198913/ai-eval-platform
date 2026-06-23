"""
🧪 tests/unit/test_visualization_service.py
可视化数据服务单元测试
"""
from datetime import datetime

from src.infra.analytics.visualization_service import VisualizationService


class TestRadarChartPositiveCases:
    """正向测试 - 雷达图"""

    def test_generate_radar_chart_basic(self):
        """基础雷达图生成"""
        data = VisualizationService.generate_radar_chart(
            dimensions=["准确性", "安全性", "流畅性"],
            series=[{"name": "模型A", "values": [0.9, 0.85, 0.92]}],
        )
        assert data["chart_type"] == "radar"
        assert len(data["indicator"]) == 3
        assert data["series"][0]["value"] == [0.9, 0.85, 0.92]

    def test_radar_from_evaluator_results(self):
        """从评估结果生成雷达图"""
        results = [
            {"evaluator_type": "ragas", "score": 0.9},
            {"evaluator_type": "ragas", "score": 0.8},
            {"evaluator_type": "deepeval", "score": 0.7},
            {"evaluator_type": "deepeval", "score": 0.85},
        ]
        data = VisualizationService.radar_from_evaluator_results(results)
        assert data["chart_type"] == "radar"
        # RAGAS 平均分 0.85，DeepEval 平均分 0.775
        assert len(data["series"]) == 1
        values = data["series"][0]["value"]
        # 验证至少有一个维度
        assert len(values) >= 1
        # 验证所有值在 0-1 区间
        for v in values:
            assert 0.0 <= v <= 1.0


class TestRadarChartNegativeCases:
    """负向测试 - 雷达图"""

    def test_empty_results_returns_empty(self):
        """空结果返回空数据"""
        data = VisualizationService.radar_from_evaluator_results([])
        assert data["series"] == []


class TestTrendChartPositiveCases:
    """正向测试 - 趋势图"""

    def test_generate_trend_chart(self):
        """基础趋势图"""
        data = VisualizationService.generate_trend_chart(
            series=[
                {
                    "name": "A",
                    "points": [("2024-01-01", 0.8), ("2024-01-02", 0.85)],
                }
            ]
        )
        assert data["chart_type"] == "line"
        assert "2024-01-01" in data["x_axis"]["data"]

    def test_trend_from_evaluations(self):
        """从评估结果生成趋势"""
        now = datetime.utcnow()
        evals = [
            {"evaluator_type": "ragas", "score": 0.9, "created_at": now.isoformat()},
            {"evaluator_type": "deepeval", "score": 0.8, "created_at": now.isoformat()},
        ]
        data = VisualizationService.trend_from_evaluations(evals, bucket="day")
        assert data["chart_type"] == "line"
        assert len(data["series"]) == 2


class TestDistributionChartPositiveCases:
    """正向测试 - 分布图"""

    def test_basic_distribution(self):
        """基础分布"""
        scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        data = VisualizationService.generate_distribution_chart(scores, bin_count=5)
        assert data["chart_type"] == "histogram"
        assert sum(data["counts"]) == 9
        assert data["stats"]["count"] == 9
        assert 0.4 < data["stats"]["mean"] < 0.6

    def test_distribution_with_uniform_scores(self):
        """全相同分数"""
        scores = [0.5] * 10
        data = VisualizationService.generate_distribution_chart(scores, bin_count=10)
        assert sum(data["counts"]) == 10
        assert data["stats"]["stdev"] == 0.0

    def test_distribution_with_extreme_values(self):
        """极值测试"""
        scores = [0.0, 1.0]
        data = VisualizationService.generate_distribution_chart(scores)
        assert data["stats"]["min"] == 0.0
        assert data["stats"]["max"] == 1.0


class TestDistributionChartNegativeCases:
    """负向测试 - 分布图"""

    def test_empty_scores(self):
        """空分数"""
        data = VisualizationService.generate_distribution_chart([])
        assert data["counts"] == []


class TestBoxplotPositiveCases:
    """正向测试 - 箱线图"""

    def test_basic_boxplot(self):
        """基础箱线图"""
        groups = [
            {"name": "A", "values": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]},
            {"name": "B", "values": [0.5, 0.5, 0.5, 0.5, 0.5]},
        ]
        data = VisualizationService.generate_boxplot(groups)
        assert data["chart_type"] == "boxplot"
        # A 组：min=0.1, q1≈0.3, median=0.5, q3≈0.7, max=0.9
        assert data["box_data"][0][0] == 0.1
        assert abs(data["box_data"][0][2] - 0.5) < 0.01  # median

    def test_uniform_group(self):
        """全相同值"""
        groups = [{"name": "X", "values": [0.5, 0.5, 0.5]}]
        data = VisualizationService.generate_boxplot(groups)
        assert data["box_data"][0] == [0.5, 0.5, 0.5, 0.5, 0.5]


class TestBoxplotNegativeCases:
    """负向测试 - 箱线图"""

    def test_empty_group(self):
        """空组"""
        groups = [{"name": "A", "values": []}]
        data = VisualizationService.generate_boxplot(groups)
        assert data["box_data"][0] == [0, 0, 0, 0, 0]


class TestHeatmapPositiveCases:
    """正向测试 - 热力图"""

    def test_basic_heatmap(self):
        """基础热力图"""
        data = VisualizationService.generate_heatmap(
            x_labels=["A", "B"],
            y_labels=["A", "B"],
            values=[[1.0, 0.5], [0.5, 1.0]],
        )
        assert data["chart_type"] == "heatmap"
        assert len(data["data"]) == 4

    def test_heatmap_from_evaluations(self):
        """从评估结果生成热力图"""
        evals = [
            {"evaluator_type": "ragas", "score": 0.9},
            {"evaluator_type": "ragas", "score": 0.8},
            {"evaluator_type": "deepeval", "score": 0.7},
            {"evaluator_type": "deepeval", "score": 0.85},
        ]
        data = VisualizationService.heatmap_from_evaluations(evals)
        assert data["chart_type"] == "heatmap"


class TestHeatmapNegativeCases:
    """负向测试 - 热力图"""

    def test_empty_evaluations(self):
        """空评估列表"""
        data = VisualizationService.heatmap_from_evaluations([])
        assert data["x_labels"] == []


class TestDashboardPositiveCases:
    """正向测试 - 仪表盘"""

    def test_dashboard_complete(self):
        """完整仪表盘"""
        evals = [
            {"evaluator_type": "ragas", "score": 0.9, "created_at": datetime.utcnow().isoformat()},
            {
                "evaluator_type": "deepeval",
                "score": 0.8,
                "created_at": datetime.utcnow().isoformat(),
            },
        ]
        data = VisualizationService.generate_dashboard(evals)
        assert "kpi_cards" in data
        assert "radar_chart" in data
        assert "trend_chart" in data
        assert "distribution_chart" in data
        assert "boxplot" in data
        assert "heatmap" in data
        assert data["total_evaluations"] == 2


class TestDashboardNegativeCases:
    """负向测试 - 仪表盘"""

    def test_empty_dashboard(self):
        """空仪表盘"""
        data = VisualizationService.generate_dashboard([])
        assert data["total_evaluations"] == 0
        # 应有 0 个评估
        assert data["kpi_cards"][0]["value"] == 0


class TestPearsonCorrelation:
    """皮尔逊相关系数测试"""

    def test_perfect_positive_correlation(self):
        """完全正相关"""
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]
        corr = VisualizationService._pearson(xs, ys)
        assert abs(corr - 1.0) < 0.001

    def test_perfect_negative_correlation(self):
        """完全负相关"""
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [5.0, 4.0, 3.0, 2.0, 1.0]
        corr = VisualizationService._pearson(xs, ys)
        assert abs(corr - (-1.0)) < 0.001

    def test_zero_correlation(self):
        """零相关"""
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [3.0, 3.0, 3.0, 3.0, 3.0]  # 常数，无相关性
        corr = VisualizationService._pearson(xs, ys)
        assert corr == 0.0

    def test_too_short_returns_zero(self):
        """长度不足返回 0"""
        assert VisualizationService._pearson([1.0], [2.0]) == 0.0
