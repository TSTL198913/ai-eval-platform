"""
评测报告生成功能

支持:
- HTML报告生成
- PDF报告生成
- Markdown报告生成
- 可视化图表
- 多维度分析
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class ReportFormat(Enum):
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


class ReportTheme(Enum):
    LIGHT = "light"
    DARK = "dark"


class EvaluationReport:
    """评测报告"""

    def __init__(self, title: str = "AI评测报告"):
        self.title = title
        self.generated_at = datetime.now().isoformat()
        self.summary: Dict = {}
        self.detailed_results: List[Dict] = []
        self.metrics: Dict = {}
        self.charts: List[Dict] = []

    def add_summary(self, key: str, value):
        self.summary[key] = value

    def add_result(self, result: Dict):
        self.detailed_results.append(result)

    def add_metric(self, name: str, value, unit: str = ""):
        self.metrics[name] = {"value": value, "unit": unit}

    def add_chart(self, chart_type: str, title: str, data: Dict):
        self.charts.append({
            "type": chart_type,
            "title": title,
            "data": data,
        })

    def generate_html(self, theme: ReportTheme = ReportTheme.LIGHT) -> str:
        """生成HTML报告"""
        theme_class = "theme-light" if theme == ReportTheme.LIGHT else "theme-dark"
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif; line-height: 1.6; }}
        .theme-light {{ background: #f8f9fa; color: #333; }}
        .theme-dark {{ background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ text-align: center; padding: 30px 0; border-bottom: 2px solid #007bff; }}
        .header h1 {{ font-size: 2.5em; color: #007bff; }}
        .header p {{ color: #666; margin-top: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
        .summary-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .theme-dark .summary-card {{ background: #16213e; }}
        .summary-card h3 {{ color: #007bff; margin-bottom: 10px; }}
        .summary-card .value {{ font-size: 2em; font-weight: bold; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #007bff; margin-bottom: 20px; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        .theme-dark th, .theme-dark td {{ border-color: #333; }}
        th {{ background: #007bff; color: white; }}
        .status-pass {{ color: #28a745; }}
        .status-fail {{ color: #dc3545; }}
        .chart-container {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 20px 0; }}
        .theme-dark .chart-container {{ background: #16213e; }}
        .bar-chart {{ display: flex; align-items: flex-end; height: 200px; gap: 10px; }}
        .bar {{ flex: 1; background: #007bff; border-radius: 4px 4px 0 0; position: relative; }}
        .bar-label {{ position: absolute; bottom: -25px; width: 100%; text-align: center; font-size: 0.8em; }}
        .bar-value {{ position: absolute; top: -30px; width: 100%; text-align: center; font-weight: bold; }}
        .footer {{ text-align: center; padding: 20px; border-top: 2px solid #007bff; margin-top: 30px; color: #666; }}
    </style>
</head>
<body class="{theme_class}">
    <div class="container">
        <div class="header">
            <h1>{self.title}</h1>
            <p>生成时间: {self.generated_at}</p>
        </div>
"""

        html += "<div class='section'><h2>评测概览</h2><div class='summary'>"
        for key, value in self.summary.items():
            html += f"""
            <div class='summary-card'>
                <h3>{key}</h3>
                <div class='value'>{value}</div>
            </div>
            """
        html += "</div></div>"

        html += "<div class='section'><h2>详细结果</h2><table><thead><tr><th>ID</th><th>类型</th><th>状态</th><th>分数</th><th>耗时(ms)</th></tr></thead><tbody>"
        for result in self.detailed_results:
            status = "pass" if result.get("score", 0) >= 0.7 else "fail"
            html += f"""
            <tr>
                <td>{result.get('id', '')}</td>
                <td>{result.get('type', '')}</td>
                <td class='status-{status}'>{result.get('status', '')}</td>
                <td>{result.get('score', 0):.2f}</td>
                <td>{result.get('latency_ms', 0)}</td>
            </tr>
            """
        html += "</tbody></table></div>"

        html += "<div class='section'><h2>评测指标</h2><div class='chart-container'>"
        html += "<div class='bar-chart'>"
        for name, metric in self.metrics.items():
            value = metric["value"]
            unit = metric.get("unit", "")
            height = min(value * 10, 180)
            html += f"""
            <div class='bar' style='height: {height}px;'>
                <div class='bar-value'>{value}{unit}</div>
                <div class='bar-label'>{name}</div>
            </div>
            """
        html += "</div></div></div>"

        html += "<div class='footer'>AI评测平台生成</div></div></body></html>"
        return html

    def generate_markdown(self) -> str:
        """生成Markdown报告"""
        md = f"# {self.title}\n\n"
        md += f"**生成时间**: {self.generated_at}\n\n"

        md += "## 评测概览\n\n"
        md += "| 指标 | 值 |\n|------|------|\n"
        for key, value in self.summary.items():
            md += f"| {key} | {value} |\n"
        md += "\n"

        md += "## 详细结果\n\n"
        md += "| ID | 类型 | 状态 | 分数 | 耗时(ms) |\n|------|------|------|------|------|\n"
        for result in self.detailed_results:
            md += f"| {result.get('id', '')} | {result.get('type', '')} | {result.get('status', '')} | {result.get('score', 0):.2f} | {result.get('latency_ms', 0)} |\n"
        md += "\n"

        md += "## 评测指标\n\n"
        for name, metric in self.metrics.items():
            md += f"- **{name}**: {metric['value']}{metric.get('unit', '')}\n"
        md += "\n"

        return md

    def generate_json(self) -> str:
        """生成JSON报告"""
        data = {
            "title": self.title,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "detailed_results": self.detailed_results,
            "metrics": self.metrics,
            "charts": self.charts,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def save(self, file_path: str, format: ReportFormat = ReportFormat.HTML):
        """保存报告到文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        if format == ReportFormat.HTML:
            content = self.generate_html()
        elif format == ReportFormat.MARKDOWN:
            content = self.generate_markdown()
        elif format == ReportFormat.JSON:
            content = self.generate_json()
        else:
            content = self.generate_html()

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)


class ReportGenerator:
    """报告生成器"""

    @classmethod
    def generate(cls, results: List[Dict], format: ReportFormat = ReportFormat.HTML) -> str:
        """从评测结果生成报告"""
        report = EvaluationReport(title="AI Evaluation Report")

        total = len(results)
        passed = sum(1 for r in results if r.get("score", 0) >= 0.7)
        failed = total - passed
        avg_score = sum(r.get("score", 0) for r in results) / max(total, 1)
        avg_latency = sum(r.get("latency_ms", 0) for r in results) / max(total, 1)

        report.add_summary("总测试数", total)
        report.add_summary("通过数", passed)
        report.add_summary("失败数", failed)
        report.add_summary("通过率", f"{(passed/total)*100:.1f}%" if total > 0 else "N/A")
        report.add_summary("平均分数", f"{avg_score:.2f}")
        report.add_summary("平均耗时", f"{avg_latency:.2f}ms")

        for result in results:
            report.add_result({
                "id": result.get("id", ""),
                "type": result.get("type", ""),
                "status": "passed" if result.get("score", 0) >= 0.7 else "failed",
                "score": result.get("score", 0),
                "latency_ms": result.get("latency_ms", 0),
            })

        report.add_metric("准确率", passed / max(total, 1) * 100, "%")
        report.add_metric("平均分数", avg_score * 100, "%")

        return report.generate_html() if format == ReportFormat.HTML else \
               report.generate_markdown() if format == ReportFormat.MARKDOWN else \
               report.generate_json()

    @classmethod
    def generate_and_save(cls, results: List[Dict], file_path: str, format: ReportFormat = ReportFormat.HTML):
        """生成并保存报告"""
        report = EvaluationReport(title="AI Evaluation Report")

        total = len(results)
        passed = sum(1 for r in results if r.get("score", 0) >= 0.7)
        avg_score = sum(r.get("score", 0) for r in results) / max(total, 1)

        report.add_summary("总测试数", total)
        report.add_summary("通过数", passed)
        report.add_summary("通过率", f"{(passed/total)*100:.1f}%" if total > 0 else "N/A")
        report.add_summary("平均分数", f"{avg_score:.2f}")

        for result in results:
            report.add_result(result)

        report.save(file_path, format)


def _get_score_from_record(record: Dict) -> float:
    """从记录中获取分数，处理response_data嵌套情况"""
    score = record.get("score")
    if score is not None:
        return score
    response_data = record.get("response_data", {})
    if isinstance(response_data, dict):
        return response_data.get("score", 0.0)
    try:
        import json
        response_data = json.loads(response_data)
        return response_data.get("score", 0.0)
    except:
        return 0.0


def generate_report_from_records(records: List[Dict], output_path: str = "reports/") -> str:
    """从数据库记录生成报告"""
    os.makedirs(output_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    report = EvaluationReport(title="AI Evaluation Report")

    total = len(records)
    passed = sum(1 for r in records if _get_score_from_record(r) >= 0.7)
    avg_score = sum(_get_score_from_record(r) for r in records) / max(total, 1)

    report.add_summary("评测总数", total)
    report.add_summary("通过数", passed)
    report.add_summary("通过率", f"{(passed/total)*100:.1f}%" if total > 0 else "N/A")
    report.add_summary("平均分数", f"{avg_score:.2f}")

    for record in records:
        report.add_result({
            "id": record.get("case_id", record.get("id", "")),
            "type": record.get("evaluator_type", record.get("type", "")),
            "status": record.get("status", ""),
            "score": _get_score_from_record(record),
            "latency_ms": record.get("latency_ms", 0),
        })

    html_path = os.path.join(output_path, f"report_{timestamp}.html")
    report.save(html_path, ReportFormat.HTML)

    md_path = os.path.join(output_path, f"report_{timestamp}.md")
    report.save(md_path, ReportFormat.MARKDOWN)

    return html_path
