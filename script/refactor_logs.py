import os


def refactor_logs(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                with open(path, encoding="utf-8") as f:
                    content = f.read()

                # 简单的批量替换逻辑
                new_content = content.replace("print(", "logger.info(")

                if content != new_content:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print(f"Refactored: {path}")


# 执行替换（请确保在执行前已提交 git）
refactor_logs("src")
