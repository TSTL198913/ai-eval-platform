import re

with open("src/api/server.py", encoding="utf-8") as f:
    content = f.read()

# 找到所有error_response调用缺少右括号的情况
# 模式: error_response(XXX, "中文文本"后面直接换行
pattern = r'(error_response\([^)]+"[^"]*)(\n)'
replacement = r"\1)\2"
content = re.sub(pattern, replacement, content)

with open("src/api/server.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed!")
