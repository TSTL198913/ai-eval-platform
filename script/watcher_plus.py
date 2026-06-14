import os
import sys
import time
import subprocess
import importlib.util
from typing import Optional, List
from loguru import logger

# =====================================================================
# 1. 全局环境屏障 (Environment Guard)
# =====================================================================
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    os.environ["PYTHONUTF8"] = "1"

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE_PATH = os.path.join(LOG_DIR, "watcher.log")
CELERY_LOG_PATH = os.path.join(LOG_DIR, "celery_worker.log")

# =====================================================================
# 2. 工业级日志底座 (Loguru Infrastructure)
# =====================================================================
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>({extra[component]})</cyan> <level>{message}</level>",
    level="INFO",
)
logger.add(
    LOG_FILE_PATH,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | ({extra[component]}) {message}",
    level="INFO",
    encoding="utf-8",
    rotation="10 MB",
    retention="7 days",
    enqueue=True,
)

watcher_logger = logger.bind(component="Watcher")


# =====================================================================
# 3. 核心守护进程架构 (Process Guardian)
# =====================================================================
class CeleryWorkerGuardian:
    """Celery 计算节点工程级生命周期守护者"""

    def __init__(self, target_app: str = "src.workers.celery_app"):
        self.target_app = target_app
        self.process: Optional[subprocess.Popen] = None
        self.child_env = self._prepare_environment()
        self._worker_log_file = None

    def _prepare_environment(self) -> dict:
        env = os.environ.copy()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.path.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = PROJECT_ROOT
        return env

    def verify_environment(self) -> bool:
        """【熔断防御机制（Circuit Breaker）】"""
        watcher_logger.info("🧪 启动拉起前全链路路径自测 (Self-Test)...")
        if PROJECT_ROOT not in sys.path:
            sys.path.insert(0, PROJECT_ROOT)

        try:
            spec = importlib.util.find_spec(self.target_app)
            if spec is None:
                raise ModuleNotFoundError(
                    f"无法在当前命名空间定位模块: {self.target_app}"
                )
            watcher_logger.info(
                "✅ 路径自测成功！'src' 命名空间已成功激活，PYTHONPATH 有效。"
            )
            return True
        except Exception as e:
            watcher_logger.critical("❌ 核心路径自测未通过！")
            watcher_logger.error(f"   原因: {e}")
            return False

    def build_boot_cmd(self) -> List[str]:
        safe_root = PROJECT_ROOT.replace("\\", "/")
        # cpu_cores = os.cpu_count()
        inline_script = (
            "import sys; "
            f"sys.path.insert(0, {repr(safe_root)}); "
            f"from {self.target_app} import celery_app; "
            # 🎯 架构师硬化防线：将所有参数锁死在各自的独立位置，参数与值之间绝不用空格，统一用等号 = 连接
            f"celery_app.start(['worker', '--loglevel=warning', '--pool=solo'])"
        )
        return [sys.executable, "-c", inline_script]

    def start(self):
        cmd = self.build_boot_cmd()
        watcher_logger.info("正在拉起后台 Celery 计算节点...")

        try:
            self._worker_log_file = open(CELERY_LOG_PATH, "a", encoding="utf-8")
            self.process = subprocess.Popen(
                cmd,
                cwd=PROJECT_ROOT,
                env=self.child_env,
                stdout=self._worker_log_file,
                stderr=subprocess.STDOUT,
            )
            watcher_logger.info(
                f"🚀 成功捕获子进程 [Celery Worker], 分配 PID: {self.process.pid}"
            )
            watcher_logger.info(
                f"📊 计算节点吞吐日志已重定向输出至: logs/celery_worker.log"
            )
        except Exception as e:
            watcher_logger.error(f"❌ Worker 进程拉起遭遇底层物理异常: {e}")
            self.process = None
            if self._worker_log_file:
                self._worker_log_file.close()

    def is_alive(self) -> bool:
        if self.process is None:
            return False
        return self.process.poll() is None

    def heal_if_needed(self):
        """自动愈合机制（Self-Healing Loop）"""
        if not self.is_alive():
            exit_code = "未拉起" if self.process is None else self.process.poll()
            watcher_logger.warning(
                f"🚨 检测到后台计算节点异常退出 [退出码: {exit_code}]！"
            )

            if self._worker_log_file:
                self._worker_log_file.close()

            watcher_logger.info("🔄 触发愈合机制，5秒后尝试重新激活节点...")
            time.sleep(5)
            self.start()

    def shutdown(self):
        watcher_logger.info("🛑 收到终止信号，正在安全清理并关闭子进程...")
        if self.process and self.is_alive():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                watcher_logger.warning(
                    "⚠️ 子进程拒绝优雅退出，执行强制杀灭 (SIGKILL)..."
                )
                self.process.kill()

        if self._worker_log_file:
            self._worker_log_file.close()
        watcher_logger.info("👋 守护进程已安全优雅退出。")


def main():
    print("=" * 70)
    watcher_logger.info("🛡️  全时段进程守护架构（Process Guardian）已激活...")
    print("=" * 70)

    guardian = CeleryWorkerGuardian(target_app="src.workers.celery_app")

    if not guardian.verify_environment():
        watcher_logger.critical(
            "🚨 基础依赖或路径自测失败，监控进程主动启动熔断防御，拒绝拉起。"
        )
        sys.exit(1)

    guardian.start()

    while True:
        try:
            guardian.heal_if_needed()
            time.sleep(5)
        except KeyboardInterrupt:
            guardian.shutdown()
            break


if __name__ == "__main__":
    main()
