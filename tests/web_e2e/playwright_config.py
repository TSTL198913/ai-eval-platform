# =====================================================================
# Playwright 配置文件
# AI Evaluation Platform - E2E 测试配置
# =====================================================================

import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent

# Playwright 配置
PLAYWRIGHT_CONFIG = {
    "headless": True,
    "viewport": {"width": 1280, "height": 720},
    "timeout": 30000,
    "screenshot": "only-on-failure",
    "video": "retain-on-failure",
    "trace": "on-first-retry",
}

# 测试环境配置
TEST_ENV = {
    "base_url": os.getenv("E2E_BASE_URL", "http://localhost:5174"),
    "api_url": os.getenv("E2E_API_URL", "http://localhost:8000"),
    "demo_username": "admin",
    "demo_password": "admin123",
    "slow_mo": 100,  # 慢动作模式，便于调试
}

# 浏览器配置
BROWSERS = ["chromium", "firefox", "webkit"]

# 截图和视频配置
SCREENSHOTS_DIR = ROOT_DIR / "tests" / "web_e2e" / "screenshots"
VIDEOS_DIR = ROOT_DIR / "tests" / "web_e2e" / "videos"
TRACES_DIR = ROOT_DIR / "tests" / "web_e2e" / "traces"

# 确保目录存在
for directory in [SCREENSHOTS_DIR, VIDEOS_DIR, TRACES_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# 等待条件配置
WAIT_CONFIGS = {
    "load": 30000,
    "domcontentloaded": 10000,
    "networkidle": 30000,
    "commit": 5000,
}

# 重试配置
RETRY_CONFIGS = {
    "max_retries": 2,
    "retry_delay": 1000,
}
