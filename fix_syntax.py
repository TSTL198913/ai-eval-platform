# -*- coding: utf-8 -*-
import re

with open('src/api/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复所有错误的引号 - 使用正则表达式查找并修复
# 查找 "后面跟着中文且以)"结尾的模式
content = re.sub(r'"([^"]+)）\)', r'"\1）', content)  # 中文括号
content = re.sub(r'"([^"]+)\)"', r'"\1"', content)  # 英文括号但错误的引号

with open('src/api/server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed!")
