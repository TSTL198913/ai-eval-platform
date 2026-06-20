from prometheus_client import Counter, Gauge, Histogram

FEATURE_CREEP_RISK = Gauge(
    "eval_platform_feature_creep_risk",
    "功能蔓延风险评分",
    ["module"],
)

TECH_DEBT_RISK = Gauge(
    "eval_platform_tech_debt_risk",
    "技术债务风险评分",
    ["module"],
)

COUPLING_RISK = Gauge(
    "eval_platform_coupling_risk",
    "模块耦合风险评分",
    ["module"],
)

TEST_COVERAGE_RISK = Gauge(
    "eval_platform_test_coverage_risk",
    "测试覆盖风险评分",
    ["module"],
)

DRIFT_RISK = Gauge(
    "eval_platform_drift_risk",
    "行为漂移风险评分",
    ["evaluator_type"],
)

RISK_EVENTS = Counter(
    "eval_platform_risk_events_total",
    "风险事件总数",
    ["risk_type", "risk_level"],
)

RISK_EVALUATION_DURATION = Histogram(
    "eval_platform_risk_evaluation_duration_seconds",
    "风险评估耗时",
    ["risk_type"],
)


def record_risk_metrics(risk_results: dict):
    details = risk_results.get("details") or {}
    for risk_type, data in details.items():
        risk_score = data.get("risk_score", 0)
        module = data.get("metrics", {}).get("module", "unknown")

        if risk_type == "feature_creep":
            FEATURE_CREEP_RISK.labels(module=module).set(risk_score)
        elif risk_type == "tech_debt":
            TECH_DEBT_RISK.labels(module=module).set(risk_score)
        elif risk_type == "coupling":
            COUPLING_RISK.labels(module=module).set(risk_score)
        elif risk_type == "test_coverage":
            TEST_COVERAGE_RISK.labels(module=module).set(risk_score)
        elif risk_type == "drift":
            DRIFT_RISK.labels(evaluator_type=module).set(risk_score)

        risk_level = data.get("risk_level", "low")
        RISK_EVENTS.labels(risk_type=risk_type, risk_level=risk_level).inc()


def check_risk_thresholds() -> list[dict]:
    warnings = []

    feature_creep = FEATURE_CREEP_RISK.collect()
    for metric in feature_creep:
        for sample in metric.samples:
            if sample.value >= 0.7:
                warnings.append(
                    {
                        "type": "feature_creep",
                        "module": sample.labels.get("module"),
                        "value": sample.value,
                        "message": "功能蔓延风险超过阈值",
                    }
                )

    tech_debt = TECH_DEBT_RISK.collect()
    for metric in tech_debt:
        for sample in metric.samples:
            if sample.value >= 0.6:
                warnings.append(
                    {
                        "type": "tech_debt",
                        "module": sample.labels.get("module"),
                        "value": sample.value,
                        "message": "技术债务风险超过阈值",
                    }
                )

    coupling = COUPLING_RISK.collect()
    for metric in coupling:
        for sample in metric.samples:
            if sample.value >= 0.5:
                warnings.append(
                    {
                        "type": "coupling",
                        "module": sample.labels.get("module"),
                        "value": sample.value,
                        "message": "模块耦合风险超过阈值",
                    }
                )

    return warnings
