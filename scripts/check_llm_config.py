"""检查LLM客户端配置"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["TESTING"] = "1"

from src.domain.models.llm_factory import validate_config, create_llm_client, load_config


def main():
    print("=== 配置验证 ===")
    result = validate_config()
    print("有效:", result["valid"])
    print("提供者:", result["provider"])
    print("模型:", result["model"])
    print("警告:", result["warnings"])
    print("错误:", result["errors"])

    print()
    print("=== 加载配置 ===")
    config = load_config()
    api_key = config.api_key.get_secret_value() if config.api_key else "None"
    print("API Key:", api_key[:8] + "..." if api_key else "None")
    print("模型:", config.model_name)
    print("Base URL:", config.base_url)

    print()
    print("=== 创建客户端 ===")
    client = create_llm_client()
    client_type = type(client).__name__
    print("客户端类型:", client_type)
    is_local = "LocalScoringClient" in client_type
    print("是否是本地评分客户端:", is_local)

    if is_local:
        print()
        print("警告：系统使用了本地评分客户端，未配置真实LLM")
        print("请检查 API Key 是否正确设置")
    else:
        print()
        print("成功：系统使用了真实LLM客户端")

    return 0


if __name__ == "__main__":
    sys.exit(main())
