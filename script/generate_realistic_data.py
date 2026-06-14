import datetime
import json
import os
import random
import uuid


def generate_realistic_payload(case_type):
    """模拟不同类型的评测负载"""
    templates = {
        "finance": "分析以下财务报表数据: " + "资产负债表数据... " * 20,
        "code_review": "def calculate(a, b): return a + b # 这是一个简单的加法函数",
        "general": "解释一下量子力学在生活中的应用。",
    }
    return {
        "text": templates.get(case_type, "默认输入"),
        "timestamp": datetime.datetime.now().isoformat(),
        "model_params": {"temperature": random.uniform(0.1, 0.9)},
    }


def generate_bulk_cases(count=50):
    case_types = ["finance", "code_review", "general"]
    cases = []
    for _ in range(count):
        case_type = random.choice(case_types)
        cases.append(
            {
                "id": f"prod_case_{uuid.uuid4().hex[:6]}",
                "type": case_type,
                "payload": generate_realistic_payload(case_type),
            }
        )
    return cases


def main():
    # 1. 确定项目根目录 (相对于脚本所在位置向上追溯)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)  # 假设脚本在 scripts/ 下
    output_dir = os.path.join(project_root, "tests")

    # 2. 自动创建 tests 目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 3. 生成数据
    data = generate_bulk_cases(50)

    # 4. 写入 JSON
    output_path = os.path.join(output_dir, "prod_simulated_cases.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"成功生成评测数据: {output_path}")


if __name__ == "__main__":
    main()
