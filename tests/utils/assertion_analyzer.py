#!/usr/bin/env python3
"""断言强度分析工具 - 自动分析测试文件的断言质量"""

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class AssertionStats:
    file_path: str
    total_assertions: int
    strong_count: int
    medium_count: int
    weak_count: int
    strong_ratio: float


class AssertionPatterns:
    """断言模式配置"""
    STRONG = [
        r'assert.*==.*pytest\.approx',
        r'assert.*evaluate_semantic_similarity',
        r'assert.*==.*\d+\.\d+',
        r'assert.*==.*1\.0',
        r'assert.*==.*0\.0',
        r'assert.*==.*"success"',
        r'assert.*==.*"error"',
        r'assert.*==.*"open"',
        r'assert.*==.*"closed"',
        r'assert_called_with',
        r'assert.*in.*call_args',
        r'assert.*"[^"]+" in ',
        r'assert.*\.stats\.\w+ == \d+',
        r'assert.*evaluation_status\.value ==',
        r'assert.*evaluation_status.*==.*EvaluatorStatus',
        r'assert.*confidence.*==.*\d+\.\d+',
        r'assert.*==.*len\(',
        r'assert.*==.*"low"',
        r'assert.*==.*"high"',
        r'assert.*==.*"medium"',
        r'assert.*==.*"positive"',
        r'assert.*==.*"negative"',
        r'assert.*==.*"neutral"',
        r'assert.*==.*"true"',
        r'assert.*==.*"false"',
        r'assert.*==.*True',
        r'assert.*==.*False',
        r'assert.*==.*None',
        r'assert.*<=.*score.*<=',
        r'assert.*score.*>=.*0\.',
        r'assert.*score.*<=.*1\.0',
        r'assert.*<=.*<=.*1\.0',
        r'assert.*>=.*>=.*0\.0',
        r'assert.*confidence.*>=.*0\.',
        r'assert.*confidence.*<=.*1\.0',
        r'assert.*len\(.*\).*==',
        r'assert.*len\(.*\).*>=',
        r'assert.*len\(.*\).*<=',
        r'assert.*hasattr',
        r'assert.*in.*result\.(text|error|label|data)',
        r'assert.*"[^"]+" in result\.',
    ]

    MEDIUM = [
        r'assert.*confidence.*is not None',
        r'assert.*data.*is not None',
    ]

    WEAK = [
        r'assert result\.is_valid',
        r'assert.*is_valid is True',
        r'assert.*is_valid is False',
        r'assert.*score is not None',
        r'assert_called_once',
        r'assert_called',
        r'assert_not_called',
        r'assert result\.is_valid is True',
        r'assert result\.is_valid is False',
        r'assert.*is not None',
    ]


def analyze_file(file_path: str, patterns: AssertionPatterns = None) -> AssertionStats:
    """分析单个测试文件"""
    if patterns is None:
        patterns = AssertionPatterns()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            content = f.read()

    strong = sum(len(re.findall(p, content)) for p in patterns.STRONG)
    medium = sum(len(re.findall(p, content)) for p in patterns.MEDIUM)
    weak = sum(len(re.findall(p, content)) for p in patterns.WEAK)

    total = strong + medium + weak
    ratio = strong / total if total > 0 else 0.0

    return AssertionStats(
        file_path=file_path,
        total_assertions=total,
        strong_count=strong,
        medium_count=medium,
        weak_count=weak,
        strong_ratio=ratio
    )


def analyze_directory(directory: str) -> List[AssertionStats]:
    """分析目录下所有测试文件"""
    results = []
    for root, _, files in os.walk(directory):
        if '__pycache__' in root:
            continue
        for file in files:
            if file.endswith('_test.py') or file.startswith('test_'):
                stats = analyze_file(os.path.join(root, file))
                results.append(stats)
    return results


def generate_report(stats_list: List[AssertionStats], verbose: bool = False) -> Dict:
    """生成结构化报告"""
    total_files = len(stats_list)
    avg_ratio = sum(s.strong_ratio for s in stats_list) / total_files if total_files > 0 else 0

    weak_files = [s for s in stats_list if s.strong_ratio == 0]
    medium_files = [s for s in stats_list if 0 < s.strong_ratio < 0.5]
    strong_files = [s for s in stats_list if s.strong_ratio >= 0.5]

    report = {
        'total_files': total_files,
        'avg_strong_ratio': avg_ratio,
        'rating_distribution': {
            'A': len(strong_files),
            'C': len(medium_files),
            'D': len(weak_files),
        },
        'needs_fix': [
            {'file': s.file_path, 'ratio': s.strong_ratio}
            for s in sorted(stats_list, key=lambda x: x.strong_ratio)
            if s.strong_ratio < 0.5
        ],
        'all_passed': len(weak_files) == 0 and len(medium_files) == 0,
    }

    return report


def print_report(report: Dict):
    """打印报告"""
    lines = [
        "=" * 60,
        "ASSERTION STRENGTH ANALYSIS REPORT",
        "=" * 60,
        f"Total Files: {report['total_files']}",
        f"Average Strong Ratio: {report['avg_strong_ratio']:.1%}",
        "",
        "Rating Distribution:",
        f"  A - Excellent (>=50%): {report['rating_distribution']['A']}",
        f"  C - Poor (<50%): {report['rating_distribution']['C']}",
        f"  D - Invalid (=0%): {report['rating_distribution']['D']}",
    ]

    if report['needs_fix']:
        lines.append("")
        lines.append("Files Needing Fix (<50% strong assertions):")
        lines.append("-" * 60)
        for item in report['needs_fix']:
            rating = "D" if item['ratio'] == 0 else "C"
            lines.append(f"  [{rating}] {item['file']}: {item['ratio']:.1%}")

    lines.append("")
    lines.append("RESULT: PASS" if report['all_passed'] else "RESULT: FAIL")

    print("\n".join(lines))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Analyze assertion strength in test files",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("directory", nargs="?", default="tests", help="Directory to analyze")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    stats = analyze_directory(args.directory)
    report = generate_report(stats, args.verbose)
    print_report(report)

    sys.exit(0 if report['all_passed'] else 1)