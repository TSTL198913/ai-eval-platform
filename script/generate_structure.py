import os


def get_project_structure(root_dir, output_file="structure.txt"):
    # 1. 定义需要排除的文件夹名称集合（使用 set 提高查找效率）
    skip_dirs = {
        ".idea",
        ".venv",
        "__pycache__",
        ".git",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
    }

    structure_lines = []

    # 2. 使用 os.walk 遍历目录树
    for root, dirs, files in os.walk(root_dir):
        # 计算当前目录的相对层级，用于生成树状缩进
        level = root.replace(root_dir, "").count(os.sep)
        indent = "│   " * (level - 1) + "├── " if level > 0 else ""
        structure_lines.append(f"{indent}{os.path.basename(root)}/")

        # 3. 【核心操作】就地修改 dirs 列表，实现“剪枝”
        # 注意：必须使用 dirs[:] = ... 而不是 dirs = ...，否则无法阻止递归进入
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        # 4. 处理当前目录下的文件
        sub_indent = "│   " * level + "├── "
        for file in files:
            structure_lines.append(f"{sub_indent}{file}")

    # 5. 将结果写入文本文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(structure_lines))

    print(f"✅ 目录结构已成功导出到: {output_file}")


# 运行脚本（'.' 代表当前项目根目录）
if __name__ == "__main__":
    get_project_structure("..")
