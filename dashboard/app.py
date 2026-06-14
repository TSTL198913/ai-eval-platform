"""
AI 评测平台仪表盘 v1.0

Web 控制台，提供：
- 实时监控
- 评测管理
- 模型对比
- 报告生成
"""

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)


# API 端点
@app.route("/")
def dashboard():
    """仪表盘主页"""
    return render_template("dashboard.html")


@app.route("/api/overview")
def api_overview():
    """概览数据"""
    return jsonify({
        "total_evaluations": 12543,
        "active_models": 15,
        "success_rate": 98.5,
        "avg_latency_ms": 245.3,
        "daily_growth": 12.3,
        "monthly_cost": 8560.00,
    })


@app.route("/api/models")
def api_models():
    """模型列表"""
    return jsonify([
        {
            "id": "gpt-4",
            "name": "GPT-4",
            "provider": "OpenAI",
            "status": "active",
            "evaluations": 5234,
            "avg_accuracy": 0.92,
            "avg_latency_ms": 245,
        },
        {
            "id": "claude-3",
            "name": "Claude 3",
            "provider": "Anthropic",
            "status": "active",
            "evaluations": 3456,
            "avg_accuracy": 0.89,
            "avg_latency_ms": 198,
        },
        {
            "id": "gemini-pro",
            "name": "Gemini Pro",
            "provider": "Google",
            "status": "active",
            "evaluations": 2345,
            "avg_accuracy": 0.87,
            "avg_latency_ms": 156,
        },
    ])


@app.route("/api/datasets")
def api_datasets():
    """数据集列表"""
    return jsonify([
        {"id": "mmlu", "name": "MMLU", "category": "通用", "questions": 14000},
        {"id": "humaneval", "name": "HumanEval", "category": "代码", "questions": 164},
        {"id": "gsm8k", "name": "GSM8K", "category": "数学", "questions": 8500},
    ])


@app.route("/api/evaluations")
def api_evaluations():
    """评测历史"""
    return jsonify([
        {
            "id": "eval-001",
            "model": "gpt-4",
            "dataset": "mmlu",
            "timestamp": "2024-01-15T10:30:00Z",
            "status": "completed",
            "accuracy": 0.92,
            "latency_ms": 245,
        },
        {
            "id": "eval-002",
            "model": "claude-3",
            "dataset": "mmlu",
            "timestamp": "2024-01-15T10:35:00Z",
            "status": "completed",
            "accuracy": 0.89,
            "latency_ms": 198,
        },
    ])


@app.route("/api/compare", methods=["POST"])
def api_compare():
    """模型对比"""
    data = request.json
    models = data.get("models", [])
    dataset = data.get("dataset", "mmlu")

    # 模拟对比结果
    results = []
    for model in models:
        results.append({
            "model": model,
            "dataset": dataset,
            "accuracy": 0.85 + random.random() * 0.10,
            "latency_ms": 150 + random.random() * 100,
            "cost": 0.01 + random.random() * 0.05,
        })

    return jsonify({
        "report_id": f"compare-{int(time.time())}",
        "results": results,
        "timestamp": time.time(),
    })


@app.route("/api/health")
def api_health():
    """系统健康状态"""
    return jsonify({
        "status": "healthy",
        "components": {
            "api": {"status": "healthy", "latency_ms": 12},
            "database": {"status": "healthy", "connections": 45},
            "redis": {"status": "healthy", "memory_usage": "45%"},
            "queue": {"status": "healthy", "pending_tasks": 23},
        },
        "uptime_seconds": 86400,
    })


@app.route("/api/metrics")
def api_metrics():
    """性能指标"""
    return jsonify({
        "requests_per_minute": 125,
        "p50_latency_ms": 120,
        "p95_latency_ms": 245,
        "p99_latency_ms": 380,
        "error_rate": 0.02,
        "cache_hit_rate": 0.85,
    })


if __name__ == "__main__":
    import random
    import time

    app.run(debug=True, port=5000)
