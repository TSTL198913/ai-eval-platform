import os


def print_structure(root_path, indent=0):
    for item in os.listdir(root_path):
        if item in [".venv", ".git", "__pycache__", ".idea"]:  # 过滤不必要目录
            continue
        path = os.path.join(root_path, item)
        print("  " * indent + f"|-- {item}")
        if os.path.isdir(path):
            print_structure(path, indent + 1)


print_structure("..")
