"""
📄 src/infra/analytics/report_generator.py
增强型报告生成器 - 2026 工业级实现

支持格式：
- HTML 报告（自包含 ECharts CDN，可邮件分发）
- JSON 数据（前端自定义渲染）
- Markdown 报告（PR/Issue 评论友好）

报告内容：
- KPI 卡片
- 多维度雷达图
- 历史趋势图
- 分数分布直方图
- 评估器相关性热力图
- 详细任务列表
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# 嵌入式 ECharts CDN（生产环境推荐替换为内部 CDN）
ECHARTS_CDN = "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"


class ReportGenerator:
    """报告生成器

    所有方法均无副作用（除显式调用 write_*），便于测试。
    """

    def __init__(self, title: str = "AI 评测报告"):
        self.title = title

    # ==================== HTML 报告 ====================

    def generate_html_report(
        self,
        evaluations: list[dict[str, Any]],
        dashboard_data: dict[str, Any] | None = None,
    ) -> str:
        """生成自包含 HTML 报告

        Args:
            evaluations: 评估结果列表
            dashboard_data: 仪表盘数据（可由 VisualizationService.generate_dashboard 提供）

        Returns:
            str: 完整 HTML 字符串
        """
        if dashboard_data is None:
            from src.infra.analytics.visualization_service import VisualizationService

            dashboard_data = VisualizationService.generate_dashboard(evaluations)

        dashboard_json = json.dumps(dashboard_data, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{self.title}</title>
<script src="{ECHARTS_CDN}"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; padding: 24px; background: #f5f7fa; color: #2c3e50; }}
  h1 {{ text-align: center; color: #1a202c; }}
  .meta {{ text-align: center; color: #718096; font-size: 14px; margin-bottom: 24px; }}
  .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .kpi-card {{ flex: 1; min-width: 180px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .kpi-label {{ font-size: 12px; color: #718096; text-transform: uppercase; letter-spacing: 0.5px; }}
  .kpi-value {{ font-size: 28px; font-weight: 600; color: #2d3748; margin-top: 8px; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }}
  .chart-card {{ background: white; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); min-height: 360px; }}
  .chart-title {{ font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #4a5568; }}
  .chart {{ width: 100%; height: 320px; }}
  .full-width {{ grid-column: 1 / -1; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #edf2f7; font-size: 13px; }}
  th {{ background: #edf2f7; font-weight: 600; color: #2d3748; }}
  .footer {{ text-align: center; color: #a0aec0; font-size: 12px; margin-top: 32px; }}
</style>
</head>
<body>
<h1>{self.title}</h1>
<div class="meta">生成时间: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC | 总评估数: {len(evaluations)}</div>

<div class="kpi-row" id="kpi-row"></div>

<div class="chart-row">
  <div class="chart-card">
    <div class="chart-title">多维度评估雷达图</div>
    <div id="radar-chart" class="chart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">分数分布</div>
    <div id="distribution-chart" class="chart"></div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-card full-width">
    <div class="chart-title">历史趋势</div>
    <div id="trend-chart" class="chart" style="height: 360px;"></div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-card">
    <div class="chart-title">评估器相关性</div>
    <div id="heatmap-chart" class="chart"></div>
  </div>
  <div class="chart-card">
    <div class="chart-title">分数离散度</div>
    <div id="boxplot-chart" class="chart"></div>
  </div>
</div>

<div class="chart-row">
  <div class="chart-card full-width">
    <div class="chart-title">评估明细</div>
    <table>
      <thead>
        <tr><th>评估器</th><th>分数</th><th>状态</th><th>延迟(ms)</th><th>时间</th></tr>
      </thead>
      <tbody id="eval-table"></tbody>
    </table>
  </div>
</div>

<div class="footer">AI Eval Platform · 2026 工业级评测报告</div>

<script>
  const data = {dashboard_json};

  // KPI 渲染
  const kpiRow = document.getElementById('kpi-row');
  (data.kpi_cards || []).forEach(c => {{
    const card = document.createElement('div');
    card.className = 'kpi-card';
    card.innerHTML = `<div class="kpi-label">${{c.label}}</div><div class="kpi-value">${{c.value}}</div>`;
    kpiRow.appendChild(card);
  }});

  // 通用图表渲染函数
  function renderChart(id, option) {{
    const el = document.getElementById(id);
    if (!el) return;
    const chart = echarts.init(el);
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
  }}

  // 雷达图
  if (data.radar_chart) {{
    renderChart('radar-chart', {{
      tooltip: {{}},
      legend: {{ data: data.radar_chart.legend || [] }},
      radar: {{ indicator: data.radar_chart.indicator || [] }},
      series: [{{
        type: 'radar',
        data: (data.radar_chart.series || []).map(s => ({{
          name: s.name, value: s.value,
          areaStyle: {{ opacity: 0.2 }}
        }}))
      }}]
    }});
  }}

  // 趋势图
  if (data.trend_chart) {{
    renderChart('trend-chart', {{
      tooltip: {{ trigger: 'axis' }},
      legend: {{ data: (data.trend_chart.series || []).map(s => s.name) }},
      xAxis: data.trend_chart.x_axis,
      yAxis: data.trend_chart.y_axis,
      series: data.trend_chart.series
    }});
  }}

  // 分布图
  if (data.distribution_chart) {{
    renderChart('distribution-chart', {{
      tooltip: {{ trigger: 'axis' }},
      xAxis: {{ type: 'category', data: data.distribution_chart.bins || [] }},
      yAxis: {{ type: 'value' }},
      series: [{{
        name: '样本数', type: 'bar',
        data: data.distribution_chart.counts || [],
        itemStyle: {{ color: '#4299e1' }}
      }}]
    }});
  }}

  // 箱线图
  if (data.boxplot) {{
    renderChart('boxplot-chart', {{
      tooltip: {{}},
      xAxis: {{ type: 'category', data: data.boxplot.categories || [] }},
      yAxis: {{ type: 'value', min: 0, max: 1 }},
      series: [{{
        name: 'boxplot', type: 'boxplot',
        data: data.boxplot.box_data || []
      }}]
    }});
  }}

  // 热力图
  if (data.heatmap) {{
    renderChart('heatmap-chart', {{
      tooltip: {{}},
      xAxis: {{ type: 'category', data: data.heatmap.x_labels || [], splitArea: {{ show: true }} }},
      yAxis: {{ type: 'category', data: data.heatmap.y_labels || [], splitArea: {{ show: true }} }},
      visualMap: {{ min: data.heatmap.min_value, max: data.heatmap.max_value, calculable: true, orient: 'horizontal', left: 'center', bottom: '0%' }},
      series: [{{
        name: '相关性', type: 'heatmap',
        data: data.heatmap.data || [],
        label: {{ show: true }},
        emphasis: {{ itemStyle: {{ shadowBlur: 10, shadowColor: 'rgba(0, 0, 0, 0.5)' }} }}
      }}]
    }});
  }}

  // 表格
  const tbody = document.getElementById('eval-table');
  (data._table || []).slice(0, 50).forEach(row => {{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${{row.evaluator_type || '-'}}</td><td>${{(row.score || 0).toFixed(4)}}</td><td>${{row.status || '-'}}</td><td>${{row.latency_ms || 0}}</td><td>${{row.created_at || '-'}}</td>`;
    tbody.appendChild(tr);
  }});
</script>
</body>
</html>
"""

    def write_html_report(
        self,
        evaluations: list[dict[str, Any]],
        output_path: str | Path,
        dashboard_data: dict[str, Any] | None = None,
    ) -> Path:
        """生成 HTML 报告并写入文件"""
        html = self.generate_html_report(evaluations, dashboard_data)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"HTML 报告已生成: {output_path}")
        return output_path

    # ==================== JSON 数据 ====================

    def generate_json_data(
        self,
        evaluations: list[dict[str, Any]],
        dashboard_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成 JSON 报告数据（前端直接渲染）"""
        if dashboard_data is None:
            from src.infra.analytics.visualization_service import VisualizationService

            dashboard_data = VisualizationService.generate_dashboard(evaluations)

        return {
            "title": self.title,
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_evaluations": len(evaluations),
            },
            "dashboard": dashboard_data,
            "evaluations": evaluations[:500],  # 限制最大明细数
        }

    def write_json_report(
        self,
        evaluations: list[dict[str, Any]],
        output_path: str | Path,
    ) -> Path:
        """生成 JSON 报告并写入文件"""
        data = self.generate_json_data(evaluations)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"JSON 报告已生成: {output_path}")
        return output_path

    # ==================== Markdown 报告 ====================

    def generate_markdown_report(
        self,
        evaluations: list[dict[str, Any]],
        dashboard_data: dict[str, Any] | None = None,
    ) -> str:
        """生成 Markdown 报告（适合 PR/Issue 评论）"""
        if dashboard_data is None:
            from src.infra.analytics.visualization_service import VisualizationService

            dashboard_data = VisualizationService.generate_dashboard(evaluations)

        kpi = dashboard_data.get("kpi_cards", [])
        kpi_lines = "\n".join(f"- **{c['label']}**: {c['value']}{c.get('unit', '')}" for c in kpi)
        box = dashboard_data.get("boxplot", {})
        box_stats = box.get("box_data", [])

        lines = [
            f"# {self.title}",
            "",
            f"> 生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC | 总评估数: {len(evaluations)}",
            "",
            "## KPI 概览",
            "",
            kpi_lines or "- 无数据",
            "",
            "## 分布统计",
            "",
        ]

        dist = dashboard_data.get("distribution_chart", {})
        stats = dist.get("stats", {})
        if stats:
            lines.append(f"- 样本数: {stats.get('count', 0)}")
            lines.append(f"- 均值: {stats.get('mean', 0):.4f}")
            lines.append(f"- 中位数: {stats.get('median', 0):.4f}")
            lines.append(f"- 标准差: {stats.get('stdev', 0):.4f}")
            lines.append(f"- 最小值: {stats.get('min', 0):.4f}")
            lines.append(f"- 最大值: {stats.get('max', 0):.4f}")
        else:
            lines.append("- 无分布数据")
        lines.append("")

        # 评估器维度
        radar = dashboard_data.get("radar_chart", {})
        series = radar.get("series", [])
        if series:
            lines.append("## 评估器平均分")
            lines.append("")
            lines.append("| 评估器 | 平均分 |")
            lines.append("| --- | --- |")
            for s in series[0].get("value", []):
                idx = series[0]["value"].index(s)
                dim = radar.get("indicator", [{}])[idx].get("name", f"维度{idx}")
                lines.append(f"| {dim} | {s:.4f} |")
            lines.append("")

        # 离散度
        if box.get("categories"):
            lines.append("## 分数离散度")
            lines.append("")
            lines.append("| 评估器 | 最小 | Q1 | 中位数 | Q3 | 最大 |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            for cat, bd in zip(box["categories"], box_stats, strict=False):
                lines.append(
                    f"| {cat} | {bd[0]:.4f} | {bd[1]:.4f} | {bd[2]:.4f} | {bd[3]:.4f} | {bd[4]:.4f} |"
                )
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append("*由 AI Eval Platform 自动生成 · 2026 工业级*")
        return "\n".join(lines)

    def write_markdown_report(
        self,
        evaluations: list[dict[str, Any]],
        output_path: str | Path,
    ) -> Path:
        """生成 Markdown 报告并写入文件"""
        md = self.generate_markdown_report(evaluations)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md, encoding="utf-8")
        logger.info(f"Markdown 报告已生成: {output_path}")
        return output_path


__all__ = ["ReportGenerator", "ECHARTS_CDN"]
