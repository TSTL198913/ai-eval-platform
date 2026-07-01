"""
统一配置管理（兼容性文件）

使用 pydantic-settings 管理所有配置，支持：
1. 环境变量自动注入
2. 类型验证
3. 默认值设置
4. .env 文件加载

注意：此文件为兼容性文件，实际配置定义在 src/config/__init__.py 中
"""

from src.config import Settings, settings, get_settings

__all__ = ["Settings", "settings", "get_settings"]