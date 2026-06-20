"""
AI全链路监控指标清单

定义系统中所有关键指标及其采集方式
"""

# ============================================================================
# 一、API层指标 (API Layer)
# ============================================================================

API_METRICS = {
    # 请求量指标
    "api_requests_total": {
        "type": "Counter",
        "description": "API请求总数",
        "labels": ["method", "endpoint", "status_code"],
        "query": "sum(rate(api_requests_total[5m])) by (endpoint)",
    },
    "api_request_duration_seconds": {
        "type": "Histogram",
        "description": "API请求延迟分布",
        "labels": ["method", "endpoint"],
        "buckets": [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
        "query": "histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le, endpoint))",
    },
    # HTTP状态码分布
    "api_http_status_codes": {
        "type": "Counter",
        "description": "HTTP状态码分布",
        "labels": ["status_code", "endpoint"],
        "query": "sum(rate(api_http_status_codes[5m])) by (status_code)",
    },
}

# ============================================================================
# 二、评估器层指标 (Evaluator Layer)
# ============================================================================

EVALUATOR_METRICS = {
    # 评估请求量
    "evaluator_calls_total": {
        "type": "Counter",
        "description": "评估器调用次数",
        "labels": ["evaluator_type", "status"],
        "query": "sum(rate(evaluator_calls_total[5m])) by (evaluator_type)",
    },
    # 评估延迟
    "evaluator_latency_seconds": {
        "type": "Histogram",
        "description": "评估器执行延迟",
        "labels": ["evaluator_type"],
        "buckets": [0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        "query": "histogram_quantile(0.99, sum(rate(evaluator_latency_seconds_bucket[5m])) by (le, evaluator_type))",
    },
    # 评估分数分布
    "evaluator_score_distribution": {
        "type": "Histogram",
        "description": "评估分数分布",
        "labels": ["evaluator_type", "score_bucket"],
        "buckets": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "query": "sum(rate(evaluator_score_distribution_bucket[5m])) by (le, evaluator_type)",
    },
    # 评估通过率
    "evaluator_pass_rate": {
        "type": "Gauge",
        "description": "评估通过率",
        "labels": ["evaluator_type"],
        "query": 'sum(evaluator_calls_total{status="pass"}) / sum(evaluator_calls_total) by (evaluator_type)',
    },
    # 评估失败原因分布
    "evaluator_failure_reasons": {
        "type": "Counter",
        "description": "评估失败原因分布",
        "labels": ["evaluator_type", "error_type"],
        "query": "sum(rate(evaluator_failure_reasons[5m])) by (evaluator_type, error_type)",
    },
}

# ============================================================================
# 三、LLM层指标 (LLM Layer)
# ============================================================================

LLM_METRICS = {
    # Token消耗
    "llm_tokens_total": {
        "type": "Counter",
        "description": "LLM Token消耗总数",
        "labels": ["provider", "model", "token_type"],  # token_type: prompt/completion
        "query": "sum(rate(llm_tokens_total[5m])) by (provider, model)",
    },
    # Token成本
    "llm_cost_usd": {
        "type": "Counter",
        "description": "LLM调用成本（美元）",
        "labels": ["provider", "model"],
        "query": "sum(rate(llm_cost_usd[5m])) by (provider, model)",
    },
    # LLM延迟
    "llm_latency_seconds": {
        "type": "Histogram",
        "description": "LLM API调用延迟",
        "labels": ["provider", "model"],
        "buckets": [0.5, 1.0, 2.0, 5.0, 10.0, 20.0],
        "query": "histogram_quantile(0.95, sum(rate(llm_latency_seconds_bucket[5m])) by (le, provider, model))",
    },
    # LLM错误率
    "llm_errors_total": {
        "type": "Counter",
        "description": "LLM调用错误总数",
        "labels": ["provider", "model", "error_type"],
        "query": "sum(rate(llm_errors_total[5m])) by (provider, model, error_type)",
    },
    # LLM调用成功率
    "llm_success_rate": {
        "type": "Gauge",
        "description": "LLM调用成功率",
        "labels": ["provider", "model"],
        "query": "1 - (sum(rate(llm_errors_total[5m])) by (provider, model) / sum(rate(llm_calls_total[5m])) by (provider, model))",
    },
    # 模型选择分布（智能路由）
    "llm_model_selection": {
        "type": "Counter",
        "description": "模型选择分布",
        "labels": [
            "provider",
            "model",
            "selection_reason",
        ],  # selection_reason: cost/quality/fallback
        "query": "sum(rate(llm_model_selection[5m])) by (model, selection_reason)",
    },
}

# ============================================================================
# 四、业务层指标 (Business Layer)
# ============================================================================

BUSINESS_METRICS = {
    # 每日评估量
    "daily_evaluations": {
        "type": "Counter",
        "description": "每日评估总数",
        "labels": ["date", "evaluator_type"],
        "query": "sum(increase(evaluator_calls_total[1d])) by (date, evaluator_type)",
    },
    # 每日活跃用户
    "daily_active_users": {
        "type": "Counter",
        "description": "每日活跃用户数",
        "labels": ["date"],
        "query": 'count(count(evaluation_requests{user_id!=""}) by (user_id, date))',
    },
    # 评估场景分布
    "evaluation_scenario_distribution": {
        "type": "Counter",
        "description": "评估场景分布",
        "labels": ["scenario"],  # scenario: code_review/security/finance/planning
        "query": "sum(rate(evaluator_calls_total[5m])) by (scenario)",
    },
    # 高价值评估（分数>=0.8且置信度>=0.9）
    "high_value_evaluations": {
        "type": "Counter",
        "description": "高价值评估次数",
        "labels": ["evaluator_type"],
        "query": "sum(rate(high_value_evaluations[5m])) by (evaluator_type)",
    },
    # 黄金数据集使用次数
    "golden_dataset_usage": {
        "type": "Counter",
        "description": "黄金数据集使用次数",
        "labels": ["dataset_id", "purpose"],  # purpose: calibration/few_shot/validation
        "query": "sum(rate(golden_dataset_usage[5m])) by (dataset_id, purpose)",
    },
    # 校准偏差
    "calibration_deviation": {
        "type": "Gauge",
        "description": "评估器校准偏差",
        "labels": ["evaluator_type"],
        "query": "abs(calibration_score - baseline_score) / baseline_score",
    },
}

# ============================================================================
# 五、模型性能指标 (Model Performance)
# ============================================================================

MODEL_PERFORMANCE_METRICS = {
    # 模型平均分数
    "model_avg_score": {
        "type": "Gauge",
        "description": "模型平均评估分数",
        "labels": ["provider", "model", "evaluator_type"],
        "query": "avg(evaluation_score) by (provider, model, evaluator_type)",
    },
    # 模型通过率
    "model_pass_rate": {
        "type": "Gauge",
        "description": "模型通过率",
        "labels": ["provider", "model", "evaluator_type", "threshold"],
        "query": "sum(evaluation_score >= threshold) / count(evaluation_score) by (provider, model, evaluator_type, threshold)",
    },
    # 模型延迟vs质量Pareto前沿
    "model_pareto_frontier": {
        "type": "Gauge",
        "description": "模型Pareto前沿状态",
        "labels": ["provider", "model"],
        "query": "evaluation_latency vs evaluation_score",  # 需要2D图表
    },
    # 模型性价比指数 (Quality/Cost)
    "model_cost_efficiency": {
        "type": "Gauge",
        "description": "模型性价比指数",
        "labels": ["provider", "model"],
        "query": "avg(evaluation_score) / avg(llm_cost_per_request) by (provider, model)",
    },
    # 模型稳定性 (分数标准差)
    "model_score_stability": {
        "type": "Gauge",
        "description": "模型分数稳定性（标准差越小越稳定）",
        "labels": ["provider", "model", "evaluator_type"],
        "query": "stddev(evaluation_score) by (provider, model, evaluator_type)",
    },
    # 模型排名变化
    "model_ranking_change": {
        "type": "Gauge",
        "description": "模型排名变化",
        "labels": ["provider", "model", "period"],  # period: daily/weekly/monthly
        "query": "rank(evaluation_score) - rank(previous_evaluation_score)",
    },
}

# ============================================================================
# 六、成本治理指标 (Cost Governance)
# ============================================================================

COST_METRICS = {
    # 日成本
    "daily_cost_usd": {
        "type": "Counter",
        "description": "日累计成本（美元）",
        "query": "sum(increase(llm_cost_usd[1d]))",
    },
    # 周成本
    "weekly_cost_usd": {
        "type": "Counter",
        "description": "周累计成本（美元）",
        "query": "sum(increase(llm_cost_usd[7d]))",
    },
    # 月成本
    "monthly_cost_usd": {
        "type": "Counter",
        "description": "月累计成本（美元）",
        "query": "sum(increase(llm_cost_usd[30d]))",
    },
    # 单位评估成本
    "cost_per_evaluation": {
        "type": "Gauge",
        "description": "单个评估的平均成本",
        "query": "sum(llm_cost_usd) / sum(evaluator_calls_total)",
    },
    # 成本预算使用率
    "cost_budget_usage": {
        "type": "Gauge",
        "description": "成本预算使用率",
        "labels": ["budget_type"],  # budget_type: daily/monthly
        "query": "sum(llm_cost_usd) / budget_limit",
    },
    # Token使用效率 (有效Token/总Token)
    "token_usage_efficiency": {
        "type": "Gauge",
        "description": "Token使用效率",
        "query": '(sum(llm_tokens_total{token_type="completion"}) / sum(llm_tokens_total)) * 100',
    },
}

# ============================================================================
# 七、系统健康指标 (System Health)
# ============================================================================

SYSTEM_HEALTH_METRICS = {
    # API可用性
    "api_availability": {
        "type": "Gauge",
        "description": "API可用性（百分比）",
        "query": '(sum(evaluator_calls_total{status!="error"}) / sum(evaluator_calls_total)) * 100',
    },
    # 错误率
    "error_rate": {
        "type": "Gauge",
        "description": "错误率（百分比）",
        "query": "(sum(rate(evaluator_failure_reasons[5m])) / sum(rate(evaluator_calls_total[5m]))) * 100",
    },
    # P99延迟
    "p99_latency": {
        "type": "Gauge",
        "description": "P99延迟（秒）",
        "query": "histogram_quantile(0.99, sum(rate(evaluator_latency_seconds_bucket[5m])) by (le))",
    },
    # 队列堆积
    "queue_depth": {
        "type": "Gauge",
        "description": "任务队列堆积深度",
        "labels": ["queue_name"],
        "query": "task_queue_size",
    },
    # 数据库连接池使用率
    "db_connection_pool_usage": {
        "type": "Gauge",
        "description": "数据库连接池使用率",
        "query": '(db_connections{status="active"} / db_connections{status="total"}) * 100',
    },
    # 内存使用
    "memory_usage_bytes": {
        "type": "Gauge",
        "description": "内存使用量",
        "query": "process_resident_memory_bytes",
    },
}

# ============================================================================
# 八、完整指标清单汇总
# ============================================================================

ALL_METRICS = {
    "api": API_METRICS,
    "evaluator": EVALUATOR_METRICS,
    "llm": LLM_METRICS,
    "business": BUSINESS_METRICS,
    "model_performance": MODEL_PERFORMANCE_METRICS,
    "cost": COST_METRICS,
    "system_health": SYSTEM_HEALTH_METRICS,
}

# 指标分类索引
METRIC_INDEX = {}
for category, metrics in ALL_METRICS.items():
    for metric_name, metric_info in metrics.items():
        METRIC_INDEX[metric_name] = {"category": category, **metric_info}


def get_metrics_by_category(category: str) -> dict:
    """获取指定分类的所有指标"""
    return ALL_METRICS.get(category, {})


def get_all_metric_names() -> list:
    """获取所有指标名称"""
    return list(METRIC_INDEX.keys())


def get_metric_info(metric_name: str) -> dict:
    """获取指标详细信息"""
    return METRIC_INDEX.get(metric_name, {})
