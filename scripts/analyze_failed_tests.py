import subprocess
import re
from collections import Counter
import json

result = subprocess.run(
    ["python", "-m", "pytest", "tests/integration", "--tb=no", "-q", "--no-header"],
    capture_output=True,
    text=True,
    cwd="d:/workspace/ai-eval-platform-refactor",
    timeout=600
)

failed_lines = []
for line in result.stdout.split('\n'):
    if 'FAILED' in line:
        failed_lines.append(line)

pattern = re.compile(r'tests/integration/([^/]+)/([^:]+)::')
counter = Counter()

for line in failed_lines:
    match = pattern.search(line)
    if match:
        module = match.group(1)
        file = match.group(2)
        key = f"{module}/{file}"
        counter[key] += 1

total_failed = len(failed_lines)
total_collected = 1175

print(f"=== 集成测试 FAILED 模块统计 ===")
print(f"总 FAILED: {total_failed}/{total_collected}")
print(f"总通过: {total_collected - total_failed}")
print(f"通过率: {(total_collected - total_failed)/total_collected*100:.1f}%")
print()
print("=== Top 10 失败模块 ===")
for idx, (key, count) in enumerate(counter.most_common(10), 1):
    module = key.split('/')[0]
    file = key.split('/')[1]
    total_in_module = sum(1 for k in counter if k.startswith(module))
    print(f"{idx}. {module}/{file}.py: {count} 失败")

print()
print("=== 按目录聚合 ===")
dir_counter = Counter()
for key, count in counter.items():
    dir_name = key.split('/')[0]
    dir_counter[dir_name] += count

for idx, (dir_name, count) in enumerate(dir_counter.most_common(), 1):
    print(f"{idx}. {dir_name}/: {count} 失败")

summary = {
    "total_failed": total_failed,
    "total_collected": total_collected,
    "pass_rate": (total_collected - total_failed) / total_collected * 100,
    "top_modules": [
        {"module": key, "failures": count}
        for key, count in counter.most_common(10)
    ],
    "dir_summary": [
        {"directory": dir_name, "failures": count}
        for dir_name, count in dir_counter.most_common()
    ]
}

with open("d:/workspace/ai-eval-platform-refactor/data/failed_modules_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print(f"\n结果已保存到 data/failed_modules_summary.json")
