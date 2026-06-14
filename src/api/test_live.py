import json

import requests

BASE_URL = "http://127.0.0.1:8000/api/v1/evaluate"


def test_feature(name, data):
    print(f"\n>>> 正在测试功能: {name}")
    try:
        response = requests.post(BASE_URL, json=data)
        print(f"结果: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"连接失败，请确保服务已启动: {e}")


# 实测 1: 契约拦截 (你将看到CONTRACT_ERROR)
test_feature("契约拦截", {"wrong": "data"})

# 实测 2: 领域路由 (你将看到评估结果)
test_feature("业务路由", {
    "id": "LIVE_001",
    "type": "finance",
    "payload": {"case_id": "c1", "user_input": "我想了解定投建议", "metadata": {"rate": 0.05}}
})
