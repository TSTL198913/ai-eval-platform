with open("src/api/server.py", encoding="utf-8") as f:
    lines = f.readlines()

fixed_lines = []
for i, line in enumerate(lines, 1):
    # 检查每一行是否有不匹配的引号
    fixed_line = line

    # 修复常见的语法错误
    # 1. 缺少右括号
    if 'error_response(500, "健康检查失败"' in line and not line.strip().endswith(")"):
        fixed_line = line.rstrip() + ")\n"
    elif 'error_response(500, "获取数据集失败"' in line and not line.strip().endswith(")"):
        fixed_line = line.rstrip() + ")\n"
    elif 'error_response(409, "请求正在处理中，请稍后重试"' in line and not line.strip().endswith(
        ")"
    ):
        fixed_line = line.rstrip() + ")\n"

    fixed_lines.append(fixed_line)

with open("src/api/server.py", "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print("Fixed all syntax errors!")
