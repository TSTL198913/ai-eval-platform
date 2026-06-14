import logging
import os
import subprocess
import sys
import time

os.environ["PYTHONIOENCODING"] = "utf-8"

# 如果是在 Windows 下，确保终端环境也被设置为 UTF-8
if sys.platform == "win32":
    import subprocess

    # 这会告诉子进程（即你的 Celery Worker）使用 UTF-8
    os.environ["PYTHONUTF8"] = "1"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    # 关键点：显式添加 encoding='utf-8'
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("../watcher.log", encoding="utf-8"),
    ],
)

# 配置日志：生产环境必须具备时间戳和层级记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("../watcher.log")],
)


def start_worker():
    venv_python = sys.executable
    cmd = [
        venv_python,
        "-m",
        "celery",
        "-A",
        "src.tasks",
        "workers",
        "--loglevel=info",
        "-P",
        "solo",
    ]

    logging.info(f"启动 Worker, 命令: {' '.join(cmd)}")
    try:
        return subprocess.Popen(cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    except Exception as e:
        logging.error(f"Worker 启动失败: {e}")
        return None


def main():
    logging.info("监控进程启动，进入守护模式...")
    process = start_worker()
    print("celery pid:", process.pid)

    while True:
        if process is None or process.poll() is not None:
            logging.warning("检测到 Worker 异常或已退出，5秒后重启...")
            time.sleep(5)
            process = start_worker()
        time.sleep(5)


if __name__ == "__main__":
    main()
