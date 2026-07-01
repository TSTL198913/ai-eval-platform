#!/usr/bin/env python3
"""
评估器批量重构工具 - 清理过时设计模式

功能：
1. 将 `DomainResponse(is_valid=True/False, ...)` 替换为工厂方法
2. 将 `DomainResponse(evaluation_status=EvaluatorStatus.ERROR, error="...")` 替换为 `create_error_response`
3. 将成功响应替换为 `create_success_response`
"""

import os
import re

EVALUATORS_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "domain", "evaluators")


def refactor_file(filepath: str):
    """重构单个评估器文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    changes_made = 0

    content, count = refactor_is_valid_false(content)
    changes_made += count

    content, count = refactor_is_valid_true(content)
    changes_made += count

    content, count = refactor_error_response(content)
    changes_made += count

    content, count = refactor_success_response(content)
    changes_made += count

    if changes_made > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"OK {os.path.basename(filepath)}: {changes_made} changes")
    else:
        print(f"  {os.path.basename(filepath)}: 无需修改")

    return changes_made


def refactor_is_valid_false(content: str) -> tuple[str, int]:
    """替换 DomainResponse(is_valid=False, error="...")"""
    pattern = r'DomainResponse\(is_valid=False,\s*error="([^"]+)"\)'
    replacement = r'self.create_error_response(error_message="\1")'
    content, count = re.subn(pattern, replacement, content)
    return content, count


def refactor_is_valid_true(content: str) -> tuple[str, int]:
    """替换 DomainResponse(is_valid=True, ...)"""
    pattern = r'DomainResponse\(is_valid=True,\s*text="([^"]+)",\s*score=([\d.]+),\s*data=(\{[^}]+\})'
    replacement = r'self.create_success_response(text="\1", score=\2, data=\3)'
    content, count = re.subn(pattern, replacement, content)
    return content, count


def refactor_error_response(content: str) -> tuple[str, int]:
    """替换 DomainResponse(evaluation_status=EvaluatorStatus.ERROR, error="...")"""
    pattern = r'DomainResponse\(evaluation_status=EvaluatorStatus\.ERROR,\s*error="([^"]+)"\)'
    replacement = r'self.create_error_response(error_message="\1")'
    content, count = re.subn(pattern, replacement, content)
    return content, count


def refactor_success_response(content: str) -> tuple[str, int]:
    """替换简单的成功响应"""
    pattern = r'DomainResponse\(is_valid=True,\s*text="([^"]+)",\s*score=([\d.]+)\)'
    replacement = r'self.create_success_response(text="\1", score=\2)'
    content, count = re.subn(pattern, replacement, content)
    return content, count


def main():
    print("=" * 60)
    print("评估器批量重构工具")
    print("=" * 60)
    print()

    total_changes = 0
    files_modified = 0

    for filename in os.listdir(EVALUATORS_DIR):
        if filename.endswith(".py") and filename != "__init__.py":
            filepath = os.path.join(EVALUATORS_DIR, filename)
            changes = refactor_file(filepath)
            if changes > 0:
                files_modified += 1
            total_changes += changes

    print()
    print("=" * 60)
    print(f"重构完成！共修改 {files_modified} 个文件，{total_changes} 处修改")
    print("=" * 60)


if __name__ == "__main__":
    main()