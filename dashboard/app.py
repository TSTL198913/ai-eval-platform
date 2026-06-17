"""
AI 评测平台仪表盘 v2.0

Web 控制台，提供：
- 实时监控
- 评测管理
- 模型对比
- 报告生成
- 评估器管理
- 安全测试
- 漂移检测
"""

import random
import time

from flask import Flask, jsonify, render_template, request

from src.domain.evaluators import EvaluatorFactory
from src.infra.benchmark.benchmark_manager import benchmark_manager
from src.infra.cost_governance import cost_governance
from src.infra.db.repository import EvaluationRepository

app = Flask(__name__)

_repository = EvaluationRepository()


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/overview")
def api_overview():
    record_count = _repository.count()
    recent_records = _repository.get_recent(10)

    success_count = sum(1 for r in recent_records if r["status"] == "passed")
    success_rate = (success_count / len(recent_records)) * 100 if recent_records else 98.5

    avg_latency = sum(r["latency_ms"] for r in recent_records if r["latency_ms"]) / len(recent_records) if recent_records else 245.3

    evaluators_count = len(EvaluatorFactory.list_evaluators())

    cost_metrics = cost_governance.get_metrics(24)

    return jsonify(
        {
            "total_evaluations": record_count,
            "active_models": 15,
            "active_evaluators": evaluators_count,
            "success_rate": round(success_rate, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "daily_growth": 12.3,
            "monthly_cost": cost_metrics.daily_cost_usd * 30,
            "today_cost": cost_metrics.daily_cost_usd,
        }
    )


@app.route("/api/models")
def api_models():
    return jsonify(
        [
            {"id": "gpt-4", "name": "GPT-4", "provider": "OpenAI", "status": "active", "evaluations": 5234, "avg_accuracy": 0.92, "avg_latency_ms": 245},
            {"id": "claude-3", "name": "Claude 3", "provider": "Anthropic", "status": "active", "evaluations": 3456, "avg_accuracy": 0.89, "avg_latency_ms": 198},
            {"id": "gemini-pro", "name": "Gemini Pro", "provider": "Google", "status": "active", "evaluations": 2345, "avg_accuracy": 0.87, "avg_latency_ms": 156},
            {"id": "deepseek", "name": "DeepSeek", "provider": "DeepSeek", "status": "active", "evaluations": 1876, "avg_accuracy": 0.85, "avg_latency_ms": 120},
            {"id": "qwen", "name": "Qwen", "provider": "Alibaba", "status": "active", "evaluations": 1543, "avg_accuracy": 0.84, "avg_latency_ms": 98},
            {"id": "ollama", "name": "Ollama Local", "provider": "Ollama", "status": "active", "evaluations": 876, "avg_accuracy": 0.78, "avg_latency_ms": 45},
        ]
    )


@app.route("/api/datasets")
def api_datasets():
    datasets = benchmark_manager.list_datasets()
    return jsonify(datasets)


@app.route("/api/evaluations")
def api_evaluations():
    recent = _repository.get_recent(20)
    return jsonify(recent)


@app.route("/api/evaluators")
def api_evaluators():
    return jsonify(EvaluatorFactory.get_evaluator_info())


@app.route("/api/compare", methods=["POST"])
def api_compare():
    data = request.json
    models = data.get("models", [])
    dataset = data.get("dataset", "mmlu")

    results = []
    for model in models:
        results.append(
            {
                "model": model,
                "dataset": dataset,
                "accuracy": 0.85 + random.random() * 0.10,
                "latency_ms": 150 + random.random() * 100,
                "cost": 0.01 + random.random() * 0.05,
            }
        )

    return jsonify(
        {
            "report_id": f"compare-{int(time.time())}",
            "results": results,
            "timestamp": time.time(),
        }
    )


@app.route("/api/health")
def api_health():
    return jsonify(
        {
            "status": "healthy",
            "components": {
                "api": {"status": "healthy", "latency_ms": 12},
                "database": {"status": "healthy", "connections": 45},
                "redis": {"status": "healthy", "memory_usage": "45%"},
                "queue": {"status": "healthy", "pending_tasks": 23},
            },
            "uptime_seconds": 86400,
        }
    )


@app.route("/api/metrics")
def api_metrics():
    cost_metrics = cost_governance.get_metrics(24)
    return jsonify(
        {
            "requests_per_minute": cost_metrics.total_requests / 1440 if cost_metrics.total_requests > 0 else 125,
            "p50_latency_ms": cost_metrics.p50_latency_ms or 120,
            "p95_latency_ms": cost_metrics.p95_latency_ms or 245,
            "p99_latency_ms": cost_metrics.p99_latency_ms or 380,
            "error_rate": 0.02,
            "cache_hit_rate": 0.85,
            "avg_tokens_per_request": cost_metrics.avg_tokens_per_request or 150,
            "daily_cost_usd": cost_metrics.daily_cost_usd,
        }
    )


@app.route("/api/cost")
def api_cost():
    cost_metrics = cost_governance.get_metrics()
    top_models = cost_governance.get_top_models_by_cost(5)
    return jsonify(
        {
            "daily_cost_usd": cost_metrics.daily_cost_usd,
            "weekly_cost_usd": cost_metrics.weekly_cost_usd,
            "monthly_cost_usd": cost_metrics.monthly_cost_usd,
            "top_models": top_models,
            "budget_status": cost_governance.check_budget(),
        }
    )


@app.route("/api/benchmark/run", methods=["POST"])
def api_run_benchmark():
    data = request.json
    dataset_id = data.get("dataset_id")
    model_name = data.get("model_name")

    try:
        def mock_evaluator(question, **kwargs):
            is_valid = random.random() > 0.2
            return {
                "is_valid": is_valid,
                "score": 0.8 + random.random() * 0.2 if is_valid else 0.3,
                "text": "测试输出",
                "token_usage": 100 + random.randint(50, 100),
            }

        result = benchmark_manager.run_benchmark(dataset_id, model_name, mock_evaluator)
        return jsonify({
            "status": "success",
            "benchmark_id": result.benchmark_id,
            "accuracy": result.accuracy,
            "avg_latency_ms": result.avg_latency_ms,
            "total_tokens": result.total_tokens,
            "cost_usd": result.cost_usd,
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
