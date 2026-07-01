#!/usr/bin/env python3
"""统计置信度分析工具"""

import argparse
import sys
from typing import List, Dict
from scipy import stats


def analyze_confidence(scores: List[float], alpha: float = 0.05) -> Dict:
    """分析评分的统计置信度"""
    n = len(scores)
    mean = sum(scores) / n
    std_dev = stats.tstd(scores)
    std_error = stats.sem(scores)

    margin = std_error * stats.t.ppf((1 + (1 - alpha)) / 2, n - 1)
    ci_lower, ci_upper = mean - margin, mean + margin

    cv = std_dev / mean if mean > 0 else float('inf')

    norm_stat, norm_p = None, None
    if n >= 20:
        norm_stat, norm_p = stats.normaltest(scores)

    return {
        'sample_size': n,
        'mean': mean,
        'std_dev': std_dev,
        'std_error': std_error,
        'cv': cv,
        'ci_95_lower': ci_lower,
        'ci_95_upper': ci_upper,
        'is_normal': norm_p > alpha if norm_p is not None else None,
        'normality_p_value': norm_p,
    }


def generate_report(scores: List[float], threshold: float = 0.8) -> Dict:
    """生成结构化报告"""
    stats = analyze_confidence(scores)

    checks = [
        ('score_consistency', stats['std_dev'] < 0.05, f"std_dev={stats['std_dev']:.4f}"),
        ('cv', stats['cv'] < 0.1, f"cv={stats['cv']:.4f}"),
        ('ci_lower', stats['ci_95_lower'] > threshold, f"ci_lower={stats['ci_95_lower']:.4f}"),
    ]

    if stats['normality_p_value'] is not None:
        checks.append(('normality', stats['is_normal'], f"p_value={stats['normality_p_value']:.4f}"))

    all_passed = all(passed for _, passed, _ in checks)

    report = {
        'statistics': stats,
        'threshold': threshold,
        'checks': [{'name': name, 'passed': passed, 'detail': detail} for name, passed, detail in checks],
        'all_passed': all_passed,
    }

    return report


def print_report(report: Dict):
    """打印报告"""
    stats = report['statistics']
    lines = [
        "=" * 60,
        "STATISTICAL CONFIDENCE ANALYSIS REPORT",
        "=" * 60,
        f"Sample Size: {stats['sample_size']}",
        f"Mean: {stats['mean']:.4f}",
        f"Std Dev: {stats['std_dev']:.4f}",
        f"CV: {stats['cv']:.4f}",
        f"95% CI: [{stats['ci_95_lower']:.4f}, {stats['ci_95_upper']:.4f}]",
    ]

    if stats['normality_p_value'] is not None:
        lines.append(f"Normality: {'PASS' if stats['is_normal'] else 'FAIL'} (p={stats['normality_p_value']:.4f})")
    else:
        lines.append("Normality: SKIP (n<20)")

    lines.append("")
    lines.append("GATE CHECKS:")
    for check in report['checks']:
        status = "[PASS]" if check['passed'] else "[FAIL]"
        lines.append(f"  {status} {check['name']}: {check['detail']}")

    lines.append("")
    lines.append("RESULT: PASS" if report['all_passed'] else "RESULT: FAIL")

    print("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze statistical confidence of evaluator scores",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--scores", type=str, required=True, help="Comma-separated score list")
    parser.add_argument("--threshold", type=float, default=0.8, help="Passing threshold")
    args = parser.parse_args()

    scores = [float(s.strip()) for s in args.scores.split(",")]
    report = generate_report(scores, args.threshold)
    print_report(report)

    sys.exit(0 if report['all_passed'] else 1)