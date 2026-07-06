"""
批量更新评估器测试文件中的断言策略

将硬编码的分数断言替换为approx_score()和assert_response_valid()调用
排除边界值0.0和1.0的精确断言
"""

import os
import re
import sys

TEST_DIR = os.path.join(os.path.dirname(__file__), "../tests/unit/evaluator")


def should_update_score(value: str) -> bool:
    """判断分数值是否需要用approx替换（排除0.0和1.0边界值）"""
    try:
        float_val = float(value)
        return float_val not in (0.0, 1.0)
    except ValueError:
        return False


def update_file(filepath: str) -> int:
    """更新单个测试文件中的断言"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes_count = 0
    
    # 模式1: assert result.score == X (带换行)
    pattern1 = r'assert\s+result\.score\s*==\s*(\d+\.\d+)(.*?)\n'
    
    def replace_func1(match):
        nonlocal changes_count
        score_val = match.group(1)
        rest = match.group(2)
        if should_update_score(score_val):
            changes_count += 1
            return f'assert result.score == approx_score({score_val}){rest}\n'
        return match.group(0)
    
    content = re.sub(pattern1, replace_func1, content, flags=re.DOTALL)
    
    # 模式2: assert result.score == X (行内)
    pattern2 = r'assert\s+result\.score\s*==\s*(\d+\.\d+)(?!\s*\()'
    
    def replace_func2(match):
        nonlocal changes_count
        score_val = match.group(1)
        if should_update_score(score_val):
            changes_count += 1
            return f'assert result.score == approx_score({score_val})'
        return match.group(0)
    
    content = re.sub(pattern2, replace_func2, content)
    
    # 添加import语句（如果文件中已有approx_score则跳过）
    if changes_count > 0 and 'approx_score' not in content:
        # 在from src.schemas.evaluation导入后添加
        import_section = re.search(
            r'(from\s+src\.schemas\.evaluation\s+import\s+.*?)\n',
            content,
            re.DOTALL
        )
        if import_section:
            insertion_point = import_section.end()
            import_line = '\nfrom tests.utils.test_helpers import approx_score\n'
            content = content[:insertion_point] + import_line + content[insertion_point:]
        else:
            # 如果找不到特定导入，在所有import语句之后添加
            last_import = re.search(r'(^import\s+\w+|^from\s+\w+.*import.*)\n', content, re.MULTILINE)
            if last_import:
                insertion_point = last_import.end()
                import_line = '\nfrom tests.utils.test_helpers import approx_score\n'
                content = content[:insertion_point] + import_line + content[insertion_point:]
            else:
                # 在sys.path.insert之后添加
                sys_path_insert = re.search(r'(sys\.path\.insert\(0.*?\))\n', content)
                if sys_path_insert:
                    insertion_point = sys_path_insert.end()
                    import_line = '\nfrom tests.utils.test_helpers import approx_score\n'
                    content = content[:insertion_point] + import_line + content[insertion_point:]
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return changes_count


def main():
    print("=== 批量更新断言策略 ===")
    print(f"扫描目录: {TEST_DIR}")
    
    total_changes = 0
    updated_files = []
    
    for filename in sorted(os.listdir(TEST_DIR)):
        if filename.startswith('test_') and filename.endswith('.py'):
            filepath = os.path.join(TEST_DIR, filename)
            changes = update_file(filepath)
            if changes > 0:
                total_changes += changes
                updated_files.append((filename, changes))
                print(f"  {filename}: {changes}个断言已更新")
    
    print(f"\n=== 更新完成 ===")
    print(f"共更新 {len(updated_files)} 个文件，{total_changes} 个断言")
    print(f"\n更新的文件:")
    for filename, changes in updated_files:
        print(f"  - {filename}: {changes}个断言")


if __name__ == "__main__":
    main()
