"""测试DeepSeek API Key是否有效"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx


def main():
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY 未设置")
        return 1

    print(f"API Key: {api_key[:8]}...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": "Hello, what is 1+1?"}
        ],
        "temperature": 0.1,
    }

    try:
        print("\n正在测试 DeepSeek API...")
        with httpx.Client(timeout=30) as client:
            response = client.post("https://api.deepseek.com/v1/chat/completions", headers=headers, json=payload)
            print(f"HTTP状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                print(f"响应内容: {content[:100]}")
                print("\n✅ API Key 有效")
                return 0
            else:
                print(f"错误响应: {response.text[:200]}")
                if response.status_code == 401:
                    print("\n❌ API Key 无效或已过期")
                elif response.status_code == 402:
                    print("\n❌ API Key 额度不足")
                else:
                    print(f"\n❌ API 请求失败: HTTP {response.status_code}")
                return 1

    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
