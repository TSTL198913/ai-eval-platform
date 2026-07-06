#!/usr/bin/env python3
"""断言强度分析工具 - 自动分析测试文件的断言质量"""

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass
class AssertionStats:
    file_path: str
    total_assertions: int
    strong_count: int
    pseudo_strong_count: int
    medium_count: int
    weak_count: int
    strong_ratio: float
    mock_tautology_count: int


class AssertionPatterns:
    """断言模式配置"""
    STRONG = [
        r'assert.*==.*pytest\.approx\(\s*(\d+\.\d+)',
        r'assert.*evaluate_semantic_similarity',
        r'assert.*result\.score\s*==\s*(\d+\.\d+)',
        r'assert.*result\.score\s*==\s*1\.0',
        r'assert.*result\.score\s*==\s*0\.0',
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
        r'assert.*confidence.*==.*(\d+\.\d+)',
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

    MOCK_RETURN_VALUE = [
        r'mock_client\.chat\.return_value\s*=\s*["\'](\d+\.\d+)["\']',
        r'mock_client\.return_value\s*=\s*["\'](\d+\.\d+)["\']',
        r'mock_client\.chat\.return_value\s*=\s*(\d+\.\d+)',
        r'mock_client\.return_value\s*=\s*(\d+\.\d+)',
    ]


def extract_mock_values(content: str) -> List[str]:
    """提取Mock返回值中的数字"""
    values = []
    for pattern in AssertionPatterns.MOCK_RETURN_VALUE:
        matches = re.findall(pattern, content)
        values.extend(matches)
    return values


def detect_mock_tautology(content: str) -> Tuple[int, List[Tuple[str, str]]]:
    """检测Mock同义反复：assert期望值与mock返回值相同"""
    mock_values = extract_mock_values(content)
    
    tautology_count = 0
    tautology_pairs = []
    
    for mock_val in mock_values:
        for pattern in AssertionPatterns.STRONG:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                if match == mock_val:
                    tautology_count += 1
                    tautology_pairs.append((mock_val, pattern))
    
    return tautology_count, tautology_pairs


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

    strong = 0
    pseudo_strong = 0
    medium = 0
    weak = 0

    for p in patterns.STRONG:
        matches = re.findall(p, content)
        strong += len(matches)

    for p in patterns.MEDIUM:
        medium += len(re.findall(p, content))

    for p in patterns.WEAK:
        weak += len(re.findall(p, content))

    mock_tautology_count, _ = detect_mock_tautology(content)
    
    pseudo_strong = mock_tautology_count
    strong -= pseudo_strong

    total = strong + pseudo_strong + medium + weak
    ratio = strong / total if total > 0 else 0.0

    return AssertionStats(
        file_path=file_path,
        total_assertions=total,
        strong_count=strong,
        pseudo_strong_count=pseudo_strong,
        medium_count=medium,
        weak_count=weak,
        strong_ratio=ratio,
        mock_tautology_count=mock_tautology_count
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
    avg_tautology = sum(s.mock_tautology_count for s in stats_list) / total_files if total_files > 0 else 0

    weak_files = [s for s in stats_list if s.strong_ratio == 0]
    medium_files = [s for s in stats_list if 0 < s.strong_ratio < 0.5]
    strong_files = [s for s in stats_list if s.strong_ratio >= 0.5]
    
    high_tautology_files = [s for s in stats_list if s.mock_tautology_count > 3]

    report = {
        'total_files': total_files,
        'avg_strong_ratio': avg_ratio,
        'avg_mock_tautology': avg_tautology,
        'rating_distribution': {
            'A': len(strong_files),
            'C': len(medium_files),
            'D': len(weak_files),
        },
        'needs_fix': [
            {'file': s.file_path, 'ratio': s.strong_ratio, 'tautology': s.mock_tautology_count}
            for s in sorted(stats_list, key=lambda x: x.strong_ratio)
            if s.strong_ratio < 0.5
        ],
        'high_tautology': [
            {'file': s.file_path, 'tautology': s.mock_tautology_count, 'ratio': s.strong_ratio}
            for s in sorted(high_tautology_files, key=lambda x: -x.mock_tautology_count)
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
        f"Average Mock Tautology: {report['avg_mock_tautology']:.1f}",
        "",
        "Rating Distribution:",
        f"  A - Excellent (>=50%): {report['rating_distribution']['A']}",
        f"  C - Poor (<50%): {report['rating_distribution']['C']}",
        f"  D - Invalid (=0%): {report['rating_distribution']['D']}",
    ]

    if report['high_tautology']:
        lines.append("")
        lines.append("Files with High Mock Tautology (>3 instances):")
        lines.append("-" * 60)
        for item in report['high_tautology']:
            lines.append(f"  [TAUTOLOGY x{item['tautology']}] {item['file']}")

    if report['needs_fix']:
        lines.append("")
        lines.append("Files Needing Fix (<50% strong assertions):")
        lines.append("-" * 60)
        for item in report['needs_fix']:
            rating = "D" if item['ratio'] == 0 else "C"
            lines.append(f"  [{rating}] {item['file']}: {item['ratio']:.1%} (tautology: {item['tautology']})")

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