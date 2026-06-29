"""
评测报告生成框架

支持：
1. 人类可读的评测报告
2. 评分维度具体证据
3. 弱点自动归类和改进建议
4. 报告导出（JSON/Markdown/PDF）
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import markdown2


class ReportFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"


class WeaknessCategory(str, Enum):
    RELEVANCE = "relevance"
    COMPLETENESS = "completeness"
    CORRECTNESS = "correctness"
    CLARITY = "clarity"
    SAFETY = "safety"
    CONSISTENCY = "consistency"
    EFFICIENCY = "efficiency"


class ImprovementSuggestion:
    def __init__(
        self,
        category: WeaknessCategory,
        severity: str,
        description: str,
        suggestion: str,
        evidence: str,
    ):
        self.category = category
        self.severity = severity
        self.description = description
        self.suggestion = suggestion
        self.evidence = evidence

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "severity": self.severity,
            "description": self.description,
            "suggestion": self.suggestion,
            "evidence": self.evidence,
        }


class DimensionScore:
    def __init__(
        self,
        name: str,
        score: float,
        weight: float,
        evidence: str,
        is_passing: bool,
    ):
        self.name = name
        self.score = score
        self.weight = weight
        self.evidence = evidence
        self.is_passing = is_passing

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "evidence": self.evidence,
            "is_passing": self.is_passing,
        }


class EvaluationResult:
    def __init__(
        self,
        evaluator_name: str,
        user_input: str,
        actual_output: str,
        expected_output: str | None,
        overall_score: float,
        is_valid: bool,
        dimension_scores: list[DimensionScore],
        evidence: dict[str, str],
        metadata: dict[str, Any] | None = None,
    ):
        self.evaluator_name = evaluator_name
        self.user_input = user_input
        self.actual_output = actual_output
        self.expected_output = expected_output
        self.overall_score = overall_score
        self.is_valid = is_valid
        self.dimension_scores = dimension_scores
        self.evidence = evidence
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluator_name": self.evaluator_name,
            "user_input": self.user_input,
            "actual_output": self.actual_output,
            "expected_output": self.expected_output,
            "overall_score": round(self.overall_score, 2),
            "is_valid": self.is_valid,
            "dimension_scores": [ds.to_dict() for ds in self.dimension_scores],
            "evidence": self.evidence,
            "metadata": self.metadata,
        }


class ReportGenerator:
    SCORE_LEVELS = {
        (0.9, 1.0): {"label": "优秀", "color": "#22c55e", "emoji": "🌟"},
        (0.7, 0.9): {"label": "良好", "color": "#3b82f6", "emoji": "👍"},
        (0.5, 0.7): {"label": "一般", "color": "#f59e0b", "emoji": "⚠️"},
        (0.0, 0.5): {"label": "较差", "color": "#ef4444", "emoji": "❌"},
    }

    WEAKNESS_RULES = {
        WeaknessCategory.RELEVANCE: {
            "threshold": 0.7,
            "severity_map": {
                (0.0, 0.3): "严重",
                (0.3, 0.5): "中等",
                (0.5, 0.7): "轻微",
            },
            "suggestions": {
                "严重": "回答与问题完全不相关，请重新理解用户意图。",
                "中等": "回答部分偏离主题，建议聚焦问题核心。",
                "轻微": "回答基本相关，但可进一步优化相关性。",
            },
        },
        WeaknessCategory.COMPLETENESS: {
            "threshold": 0.7,
            "severity_map": {
                (0.0, 0.3): "严重",
                (0.3, 0.5): "中等",
                (0.5, 0.7): "轻微",
            },
            "suggestions": {
                "严重": "回答缺少关键信息，建议补充完整内容。",
                "中等": "回答不够全面，建议增加更多细节。",
                "轻微": "回答基本完整，可适当补充扩展。",
            },
        },
        WeaknessCategory.CORRECTNESS: {
            "threshold": 0.7,
            "severity_map": {
                (0.0, 0.3): "严重",
                (0.3, 0.5): "中等",
                (0.5, 0.7): "轻微",
            },
            "suggestions": {
                "严重": "回答存在明显错误，建议重新核实信息。",
                "中等": "回答部分不准确，建议修正错误内容。",
                "轻微": "回答基本正确，存在少量偏差。",
            },
        },
        WeaknessCategory.CLARITY: {
            "threshold": 0.7,
            "severity_map": {
                (0.0, 0.3): "严重",
                (0.3, 0.5): "中等",
                (0.5, 0.7): "轻微",
            },
            "suggestions": {
                "严重": "表达不够清晰，建议重新组织语言结构。",
                "中等": "逻辑不够连贯，建议使用更清晰的表达方式。",
                "轻微": "表达基本清晰，可进一步优化。",
            },
        },
        WeaknessCategory.SAFETY: {
            "threshold": 0.9,
            "severity_map": {
                (0.0, 0.5): "严重",
                (0.5, 0.9): "中等",
            },
            "suggestions": {
                "严重": "检测到有害内容，必须立即修正。",
                "中等": "存在潜在安全风险，建议审查内容。",
            },
        },
    }

    def __init__(self, report_dir: str = "reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def get_score_level(self, score: float) -> dict[str, str]:
        for (low, high), level in self.SCORE_LEVELS.items():
            if low <= score < high:
                return level
        return self.SCORE_LEVELS[(0.0, 0.5)]

    def analyze_weaknesses(self, result: EvaluationResult) -> list[ImprovementSuggestion]:
        weaknesses = []

        for ds in result.dimension_scores:
            category = self._get_category_from_dimension(ds.name)
            if category not in self.WEAKNESS_RULES:
                continue

            rule = self.WEAKNESS_RULES[category]
            if ds.score >= rule["threshold"]:
                continue

            severity = "轻微"
            for (low, high), sev in rule["severity_map"].items():
                if low <= ds.score < high:
                    severity = sev
                    break

            suggestion = rule["suggestions"].get(severity, "建议优化该维度。")

            weaknesses.append(
                ImprovementSuggestion(
                    category=category,
                    severity=severity,
                    description=f"{ds.name}评分较低",
                    suggestion=suggestion,
                    evidence=ds.evidence,
                )
            )

        return sorted(weaknesses, key=lambda w: w.severity, reverse=True)

    def _get_category_from_dimension(self, dimension_name: str) -> WeaknessCategory | None:
        mapping = {
            "correctness": WeaknessCategory.CORRECTNESS,
            "relevance": WeaknessCategory.RELEVANCE,
            "completeness": WeaknessCategory.COMPLETENESS,
            "clarity": WeaknessCategory.CLARITY,
            "safety": WeaknessCategory.SAFETY,
        }
        return mapping.get(dimension_name.lower())

    def generate_markdown_report(self, result: EvaluationResult) -> str:
        score_level = self.get_score_level(result.overall_score)
        weaknesses = self.analyze_weaknesses(result)

        report = f"""# AI评测报告

## 基本信息

| 项目 | 内容 |
|------|------|
| 评测时间 | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |
| 评测器 | {result.evaluator_name} |
| 总体评分 | {round(result.overall_score, 2)} ({score_level["emoji"]} {score_level["label"]}) |
| 评测结果 | {"✅ 通过" if result.is_valid else "❌ 未通过"} |

---

## 用户输入

```text
{result.user_input}
```

---

## 模型输出

```text
{result.actual_output}
```

---

## 期望输出

```text
{result.expected_output or "无"}
```

---

## 评分详情

| 维度 | 评分 | 权重 | 评估结果 | 证据 |
|------|------|------|----------|------|
"""

        for ds in result.dimension_scores:
            level = self.get_score_level(ds.score)
            report += f"| {ds.name} | {round(ds.score, 2)} {level['emoji']} | {ds.weight} | {'✅ 通过' if ds.is_passing else '❌ 未通过'} | {ds.evidence} |\n"

        report += """
---

## 弱点分析

"""

        if weaknesses:
            for w in weaknesses:
                report += f"### {w.category.value} - {w.severity}\n\n"
                report += f"- **描述**: {w.description}\n"
                report += f"- **证据**: {w.evidence}\n"
                report += f"- **建议**: {w.suggestion}\n\n"
        else:
            report += "暂无明显弱点，模型表现良好。\n\n"

        report += """---

## 改进建议

"""

        for w in weaknesses:
            if w.severity in ["严重", "中等"]:
                report += f"- [{w.category.value}] {w.suggestion}\n"

        if not any(w.severity in ["严重", "中等"] for w in weaknesses):
            report += "当前评估未发现需要重点改进的问题。\n"

        report += """

---

## 元数据

```json
"""
        report += json.dumps(result.metadata, indent=2, ensure_ascii=False)
        report += """
```
"""

        return report

    def generate_json_report(self, result: EvaluationResult) -> str:
        weaknesses = self.analyze_weaknesses(result)
        score_level = self.get_score_level(result.overall_score)

        report_data = {
            "report_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "basic_info": {
                "evaluator_name": result.evaluator_name,
                "overall_score": round(result.overall_score, 2),
                "score_level": score_level["label"],
                "is_valid": result.is_valid,
            },
            "inputs": {
                "user_input": result.user_input,
                "actual_output": result.actual_output,
                "expected_output": result.expected_output,
            },
            "dimension_scores": [ds.to_dict() for ds in result.dimension_scores],
            "evidence": result.evidence,
            "weaknesses": [w.to_dict() for w in weaknesses],
            "improvement_suggestions": [
                {
                    "category": w.category.value,
                    "severity": w.severity,
                    "suggestion": w.suggestion,
                }
                for w in weaknesses
                if w.severity in ["严重", "中等"]
            ],
            "metadata": result.metadata,
        }

        return json.dumps(report_data, indent=2, ensure_ascii=False)

    def generate_html_report(self, result: EvaluationResult) -> str:
        markdown_report = self.generate_markdown_report(result)
        html_content = markdown2.markdown(markdown_report, extras=["tables", "fenced-code-blocks"])

        score_level = self.get_score_level(result.overall_score)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI评测报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; max-width: 900px; margin: 0 auto; background: #f8fafc; }}
        .report-container {{ background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 40px; }}
        h1 {{ color: #1e293b; border-bottom: 2px solid {score_level["color"]}; padding-bottom: 10px; margin-bottom: 20px; }}
        h2 {{ color: #334155; margin: 24px 0 12px; font-size: 1.2em; }}
        h3 {{ color: #475569; margin: 16px 0 8px; font-size: 1.1em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; font-weight: 600; color: #475569; }}
        code {{ background: #f8fafc; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }}
        pre {{ background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }}
        .score-badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: 600; color: white; }}
        .badge-excellent {{ background: #22c55e; }}
        .badge-good {{ background: #3b82f6; }}
        .badge-average {{ background: #f59e0b; }}
        .badge-poor {{ background: #ef4444; }}
        .weakness-severe {{ border-left: 4px solid #ef4444; padding-left: 12px; margin: 8px 0; }}
        .weakness-medium {{ border-left: 4px solid #f59e0b; padding-left: 12px; margin: 8px 0; }}
        .weakness-mild {{ border-left: 4px solid #3b82f6; padding-left: 12px; margin: 8px 0; }}
        .pass {{ color: #22c55e; font-weight: 600; }}
        .fail {{ color: #ef4444; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="report-container">
        {html_content}
    </div>
</body>
</html>
"""

        return html

    def generate_report(
        self, result: EvaluationResult, format_type: ReportFormat = ReportFormat.MARKDOWN
    ) -> str:
        if format_type == ReportFormat.JSON:
            return self.generate_json_report(result)
        elif format_type == ReportFormat.HTML:
            return self.generate_html_report(result)
        else:
            return self.generate_markdown_report(result)

    def save_report(
        self,
        result: EvaluationResult,
        format_type: ReportFormat = ReportFormat.MARKDOWN,
        filename: str | None = None,
    ) -> str:
        report_content = self.generate_report(result, format_type)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = format_type.value
            filename = f"evaluation_report_{timestamp}.{ext}"

        file_path = self.report_dir / filename
        file_path.write_text(report_content, encoding="utf-8")

        return str(file_path)


class BatchReportGenerator:
    def __init__(self, report_dir: str = "reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.single_generator = ReportGenerator(report_dir)

    def generate_batch_report(self, results: list[EvaluationResult]) -> dict[str, Any]:
        total = len(results)
        passed = sum(1 for r in results if r.is_valid)
        avg_score = sum(r.overall_score for r in results) / total if total > 0 else 0

        score_distribution = {
            "excellent": sum(1 for r in results if r.overall_score >= 0.9),
            "good": sum(1 for r in results if 0.7 <= r.overall_score < 0.9),
            "average": sum(1 for r in results if 0.5 <= r.overall_score < 0.7),
            "poor": sum(1 for r in results if r.overall_score < 0.5),
        }

        all_weaknesses = []
        for result in results:
            weaknesses = self.single_generator.analyze_weaknesses(result)
            all_weaknesses.extend(weaknesses)

        category_counts = {}
        for w in all_weaknesses:
            category_counts[w.category.value] = category_counts.get(w.category.value, 0) + 1

        return {
            "report_version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_tests": total,
                "passed_tests": passed,
                "failed_tests": total - passed,
                "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
                "average_score": round(avg_score, 2),
            },
            "score_distribution": score_distribution,
            "weakness_summary": category_counts,
            "detailed_results": [result.to_dict() for result in results],
        }

    def save_batch_report(
        self, results: list[EvaluationResult], filename: str | None = None
    ) -> str:
        report_data = self.generate_batch_report(results)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_evaluation_report_{timestamp}.json"

        file_path = self.report_dir / filename
        file_path.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return str(file_path)


report_generator = ReportGenerator()
batch_report_generator = BatchReportGenerator()
