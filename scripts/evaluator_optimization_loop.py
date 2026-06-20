"""
评估器持续优化闭环机制

功能：
1. 定期评估所有评估器代码质量
2. 跟踪评估历史，识别改进趋势
3. 自动生成修复优先级列表
4. 验证修复效果
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 设置环境变量
os.environ.setdefault("LLM_PROVIDER", "deepseek")

from src.domain.evaluators.llm_as_judge import LLMAJudgeEvaluator
from src.domain.models.llm_factory import create_llm_client
from src.schemas.evaluation import EvaluationSchema


class EvaluatorOptimizationLoop:
    """评估器优化闭环管理器"""

    def __init__(self, history_dir: str = "data/evaluator_history"):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "evaluation_history.json"
        self.history = self._load_history()

    def _load_history(self) -> list:
        """加载评估历史"""
        if self.history_file.exists():
            with open(self.history_file, encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_history(self):
        """保存评估历史"""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def evaluate_evaluator(self, evaluator_name: str, code_path: str) -> dict:
        """评估单个评估器"""
        if not os.path.exists(code_path):
            return {
                "evaluator_name": evaluator_name,
                "code_path": code_path,
                "is_valid": False,
                "error": "文件不存在",
            }

        # 读取代码
        with open(code_path, encoding="utf-8") as f:
            code = f.read()

        # 创建LLM客户端
        client = create_llm_client(provider="deepseek")
        evaluator = LLMAJudgeEvaluator(client=client)

        # 构建评估请求
        request = EvaluationSchema(
            id=f"eval_{evaluator_name}",
            type="llm_as_judge",
            payload={
                "user_input": f"""请对以下评估器代码进行质量评审（满分100分）：

评估器名称：{evaluator_name}
文件路径：{code_path}

代码内容：
```python
{code[:5000]}  # 限制长度避免解析失败
```

请从以下维度评估：
1. 代码质量（可读性、结构清晰度）
2. 错误处理（异常处理是否完善）
3. 测试覆盖（是否易于测试）
4. 安全性（是否有潜在安全风险）
5. 文档完整性（是否有足够的注释和文档）
""",
                "actual_output": code[:5000],
                "dimensions": [
                    "code_quality",
                    "error_handling",
                    "testability",
                    "security",
                    "documentation",
                ],
                "criteria": "请严格按照代码质量标准评分，每个维度0-100分",
            },
        )

        result = evaluator.evaluate(request)

        return {
            "evaluator_name": evaluator_name,
            "code_path": code_path,
            "is_valid": result.is_valid,
            "total_score": result.data.get("total_score", 0) if result.data else 0,
            "confidence": result.data.get("confidence", 0) if result.data else 0,
            "scores": result.data.get("llm_judge_scores", {}) if result.data else {},
            "error": result.error if not result.is_valid else None,
        }

    def run_evaluation_cycle(self, evaluators: list) -> dict:
        """执行一轮评估"""
        timestamp = datetime.now().isoformat()
        results = []

        print("=" * 70)
        print(f"评估器质量评审 - {timestamp}")
        print("=" * 70)

        for evaluator_name, code_path in evaluators:
            print(f"\n[评估中] {evaluator_name}...")

            try:
                result = self.evaluate_evaluator(evaluator_name, code_path)
                results.append(result)

                if result["is_valid"]:
                    # 修正总分（如果是累加值，计算平均值）
                    total = result["total_score"]
                    if total > 100:
                        scores = result.get("scores", {})
                        if scores:
                            valid_scores = [
                                s.get("score", 0) for s in scores.values() if isinstance(s, dict)
                            ]
                            if valid_scores:
                                total = sum(valid_scores) / len(valid_scores)
                                result["total_score"] = round(total, 1)

                    print(f"  [PASS] 总分: {result['total_score']}/100")
                    print(f"  [PASS] 置信度: {result['confidence']:.2f}")
                else:
                    print(f"  [FAIL] 评估失败: {result['error']}")

            except Exception as e:
                print(f"  [FAIL] 异常: {str(e)}")
                results.append(
                    {
                        "evaluator_name": evaluator_name,
                        "code_path": code_path,
                        "is_valid": False,
                        "error": str(e),
                    }
                )

        # 记录评估历史
        evaluation_record = {
            "timestamp": timestamp,
            "results": results,
            "summary": self._generate_summary(results),
        }
        self.history.append(evaluation_record)
        self._save_history()

        return evaluation_record

    def _generate_summary(self, results: list) -> dict:
        """生成评估汇总"""
        valid_results = [r for r in results if r.get("is_valid")]

        if not valid_results:
            return {
                "evaluated_count": 0,
                "total_count": len(results),
                "average_score": 0,
                "average_confidence": 0,
                "needs_improvement": [],
                "high_quality": [],
            }

        # 计算平均分数（排除异常值）
        normal_scores = [r["total_score"] for r in valid_results if r["total_score"] <= 100]
        avg_score = sum(normal_scores) / len(normal_scores) if normal_scores else 0
        avg_confidence = sum(r["confidence"] for r in valid_results) / len(valid_results)

        # 分类评估器
        needs_improvement = sorted(
            [r for r in valid_results if r["total_score"] < 80], key=lambda x: x["total_score"]
        )
        high_quality = sorted(
            [r for r in valid_results if r["total_score"] >= 85],
            key=lambda x: x["total_score"],
            reverse=True,
        )

        return {
            "evaluated_count": len(valid_results),
            "total_count": len(results),
            "average_score": round(avg_score, 1),
            "average_confidence": round(avg_confidence, 2),
            "needs_improvement": needs_improvement,
            "high_quality": high_quality,
        }

    def get_improvement_trend(self, evaluator_name: str) -> dict:
        """获取评估器改进趋势"""
        trend = []
        for record in self.history:
            for result in record["results"]:
                if result["evaluator_name"] == evaluator_name:
                    trend.append(
                        {
                            "timestamp": record["timestamp"],
                            "total_score": result["total_score"],
                            "confidence": result["confidence"],
                        }
                    )

        if len(trend) < 2:
            return {"trend": trend, "improvement": None}

        # 计算改进幅度
        first_score = trend[0]["total_score"]
        last_score = trend[-1]["total_score"]
        improvement = last_score - first_score

        return {"trend": trend, "improvement": round(improvement, 1), "improved": improvement > 0}

    def generate_fix_priorities(self) -> list:
        """生成修复优先级列表"""
        if not self.history:
            return []

        latest_record = self.history[-1]
        needs_improvement = latest_record["summary"]["needs_improvement"]

        priorities = []
        for result in needs_improvement:
            # 计算优先级分数（分数越低，优先级越高）
            priority_score = 100 - result["total_score"]

            # 安全性问题优先级更高
            scores = result.get("scores", {})
            security_score = (
                scores.get("security", {}).get("score", 100)
                if isinstance(scores.get("security"), dict)
                else 100
            )
            if security_score < 70:
                priority_score += 30  # 安全问题加权

            priorities.append(
                {
                    "evaluator_name": result["evaluator_name"],
                    "current_score": result["total_score"],
                    "security_score": security_score,
                    "priority": (
                        "P0" if priority_score >= 50 else "P1" if priority_score >= 30 else "P2"
                    ),
                    "priority_score": round(priority_score, 1),
                    "recommendation": self._generate_recommendation(result),
                }
            )

        return sorted(priorities, key=lambda x: x["priority_score"], reverse=True)

    def _generate_recommendation(self, result: dict) -> str:
        """生成修复建议"""
        scores = result.get("scores", {})
        recommendations = []

        for dim, score_data in scores.items():
            if isinstance(score_data, dict):
                score = score_data.get("score", 100)
                if score < 70:
                    recommendations.append(f"{dim}({score}分): 需改进")

        if not recommendations:
            return "整体质量良好，建议持续优化"

        return "; ".join(recommendations)


def main():
    """主函数"""
    # 检查API Key
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        print("错误: 请设置DEEPSEEK_API_KEY环境变量")
        sys.exit(1)

    # 创建优化闭环管理器
    loop = EvaluatorOptimizationLoop()

    # 定义评估器列表
    evaluators = [
        ("SecurityEvaluator", "src/domain/evaluators/security.py"),
        ("CodeEvaluator", "src/domain/evaluators/code.py"),
        ("FinanceEvaluator", "src/domain/evaluators/finance.py"),
        ("LLMAJudgeEvaluator", "src/domain/evaluators/llm_as_judge.py"),
        ("PlanningEvaluator", "src/domain/evaluators/planning_evaluator.py"),
        ("RobustnessEvaluator", "src/domain/evaluators/robustness_evaluator.py"),
        ("FactualityEvaluator", "src/domain/evaluators/factuality_evaluator.py"),
        ("FunctionCallEvaluator", "src/domain/evaluators/function_call_evaluator.py"),
        ("MultiAgentEvaluator", "src/domain/evaluators/multi_agent_evaluator.py"),
        ("RuntimeAgentEvaluator", "src/domain/evaluators/runtime_agent_evaluator.py"),
    ]

    # 执行评估
    record = loop.run_evaluation_cycle(evaluators)

    # 打印汇总
    print("\n" + "=" * 70)
    print("评估汇总")
    print("=" * 70)
    summary = record["summary"]
    print(f"评估数量: {summary['evaluated_count']}/{summary['total_count']}")
    print(f"平均分数: {summary['average_score']}/100")
    print(f"平均置信度: {summary['average_confidence']}")

    # 打印修复优先级
    print("\n" + "=" * 70)
    print("修复优先级")
    print("=" * 70)
    priorities = loop.generate_fix_priorities()
    for p in priorities:
        print(f"[{p['priority']}] {p['evaluator_name']}: {p['current_score']}/100")
        print(f"  - 安全性: {p['security_score']}/100")
        print(f"  - 建议: {p['recommendation']}")

    # 打印改进趋势（如果有历史数据）
    if len(loop.history) > 1:
        print("\n" + "=" * 70)
        print("改进趋势")
        print("=" * 70)
        for evaluator_name, _ in evaluators[:3]:  # 只显示前3个
            trend_data = loop.get_improvement_trend(evaluator_name)
            if trend_data["improvement"]:
                print(f"{evaluator_name}: 改进 {trend_data['improvement']}分")

    # 保存详细报告
    report_file = loop.history_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存到: {report_file}")


if __name__ == "__main__":
    main()
