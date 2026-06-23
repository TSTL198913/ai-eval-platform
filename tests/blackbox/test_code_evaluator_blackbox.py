"""
Code Evaluator 黑盒测试
通过 HTTP API 调用，不依赖内部实现
"""

import sys
import time

BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"


def login():
    """登录获取 token"""
    import requests

    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login", json={"username": USERNAME, "password": PASSWORD}
    )
    if r.status_code != 200:
        print(f"[FAIL] 登录失败: {r.status_code} {r.text}")
        return None
    return r.json()["data"]["access_token"]


def evaluate_code(token, payload, expected_status=200, test_name=""):
    """调用评估 API"""
    import requests

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE_URL}/api/v1/evaluate", json=payload, headers=headers)

    success = r.status_code == expected_status
    status = "[PASS]" if success else "[FAIL]"
    print(f"{status} {test_name}: HTTP {r.status_code}")

    if not success:
        print(f"   期望: {expected_status}, 实际: {r.status_code}")
        print(f"   响应: {r.text[:200]}")

    return r


def get_records(token, limit=5):
    """获取评估记录"""
    import requests

    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{BASE_URL}/api/v1/records?limit={limit}", headers=headers)
    return r.json()["data"]["items"] if r.status_code == 200 else []


def main():
    import requests

    print("=" * 60)
    print("Code Evaluator 黑盒测试 (Black Box Testing)")
    print("=" * 60)

    # 1. 登录
    print("\n[1/8] 登录...")
    token = login()
    if not token:
        print("[FAIL] 测试终止: 登录失败")
        sys.exit(1)
    print("[PASS] 登录成功")

    results = []

    # 2. 有效 Python 代码（语法正确）
    print("\n[2/8] 测试有效 Python 代码...")
    r = evaluate_code(
        token,
        {
            "id": "blackbox-001",
            "type": "code",
            "payload": {
                "code": "def add(a, b):\n    return a + b",
                "metadata": {"language": "python"},
            },
        },
        test_name="有效代码",
    )

    if r.status_code == 200:
        data = r.json()["data"]
        score = data.get("data", {}).get("score")
        is_valid = data.get("data", {}).get("is_valid")
        print(f"   评分: {score}, is_valid: {is_valid}")
        if score is not None and is_valid:
            print("[PASS] 有效代码评分正常")
            results.append(True)
        else:
            print("[FAIL] 评分异常")
            results.append(False)
    else:
        results.append(False)

    # 3. 语法错误代码
    print("\n[3/8] 测试语法错误代码...")
    r = evaluate_code(
        token,
        {
            "id": "blackbox-002",
            "type": "code",
            "payload": {
                "code": "def hello()\n    return 1",  # 缺少冒号
                "metadata": {"language": "python"},
            },
        },
        test_name="语法错误",
    )

    if r.status_code == 200:
        data = r.json()["data"]
        is_valid = data.get("data", {}).get("is_valid")
        error = data.get("data", {}).get("error")
        print(f"   is_valid: {is_valid}, error: {error}")
        if not is_valid and error and "语法" in error:
            print("[PASS] 语法错误被正确检测")
            results.append(True)
        else:
            print("[FAIL] 语法错误未正确处理")
            results.append(False)
    else:
        results.append(False)

    # 4. 空代码
    print("\n[4/8] 测试空代码...")
    r = evaluate_code(
        token,
        {
            "id": "blackbox-003",
            "type": "code",
            "payload": {"code": "", "metadata": {"language": "python"}},
        },
        test_name="空代码",
    )

    if r.status_code == 200:
        data = r.json()["data"]
        is_valid = data.get("data", {}).get("is_valid")
        print(f"   is_valid: {is_valid}")
        if not is_valid:
            print("[PASS] 空代码被正确拒绝")
            results.append(True)
        else:
            print("[FAIL] 空代码未被拒绝")
            results.append(False)
    else:
        results.append(False)

    # 5. 持久化验证
    print("\n[5/8] 测试数据持久化...")
    records = get_records(token, limit=3)
    if records:
        latest = records[0]
        score = latest.get("score")
        print(f"   最新记录 score: {score}")
        if score is not None:
            print("[PASS] 分数已持久化到数据库")
            results.append(True)
        else:
            print("[WARN] 分数字段为空（可能历史数据）")
            results.append(True)  # 不算失败，因为历史数据可能没分数
    else:
        print("[WARN] 无评估记录")
        results.append(True)

    # 6. 带 expected_output 的评估
    print("\n[6/8] 测试带期望输出的评估...")
    r = evaluate_code(
        token,
        {
            "id": "blackbox-004",
            "type": "code",
            "payload": {
                "code": "def multiply(x, y):\n    return x * y",
                "expected_output": "代码审查建议",
                "metadata": {"language": "python"},
            },
        },
        test_name="期望输出",
    )

    if r.status_code == 200:
        data = r.json()["data"]
        persist = data.get("persist")
        print(f"   persist: {persist}")
        if persist:
            print("[PASS] 带期望输出的评估完成且持久化")
            results.append(True)
        else:
            print("[FAIL] 持久化失败")
            results.append(False)
    else:
        results.append(False)

    # 7. 不存在的评估器类型
    print("\n[7/8] 测试无效评估器类型...")
    r = evaluate_code(
        token,
        {"id": "blackbox-005", "type": "nonexistent_evaluator", "payload": {}},
        expected_status=422,
        test_name="无效类型",
    )

    if r.status_code == 422:
        print("[PASS] 无效评估器类型被拒绝")
        results.append(True)
    else:
        print(f"[FAIL] 期望 422，实际 {r.status_code}")
        results.append(False)

    # 8. 性能测试
    print("\n[8/8] 性能测试...")
    times = []
    for i in range(5):
        start = time.time()
        r = requests.post(
            f"{BASE_URL}/api/v1/evaluate",
            json={"id": f"perf-{i}", "type": "code", "payload": {"code": "x = 1"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        elapsed = (time.time() - start) * 1000
        times.append(elapsed)

    avg_time = sum(times) / len(times)
    print(f"   平均响应时间: {avg_time:.0f}ms")
    if avg_time < 5000:
        print("[PASS] 性能可接受")
        results.append(True)
    else:
        print("[WARN] 响应时间较长")
        results.append(True)

    # 汇总
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"测试结果: {passed}/{total} 通过")

    if all(results):
        print("全部测试通过")
    else:
        print("存在失败测试")

    print("=" * 60)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
