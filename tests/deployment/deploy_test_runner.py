#!/usr/bin/env python3
"""
部署测试运行器 - 直接测试服务器API，绕过pytest复杂fixture
"""

import os
import sys

try:
    import requests
except ImportError:
    print("请先安装requests: pip install requests")
    sys.exit(1)

API_BASE_URL = os.environ.get("API_BASE_URL", "http://192.168.30.134:8000")

TEST_RESULTS = []


def log_result(test_name, passed, message=""):
    status = "PASS" if passed else "FAIL"
    TEST_RESULTS.append((test_name, passed))
    print(f"[{status}] {test_name}")
    if message:
        print(f"      {message}")


def test_health():
    """测试健康检查端点"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and data["data"].get("status") == "healthy":
                log_result("健康检查端点", True)
                return True
            else:
                log_result("健康检查端点", False, f"响应内容错误: {data}")
        else:
            log_result("健康检查端点", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("健康检查端点", False, f"连接失败: {e}")
    return False


def test_root():
    """测试根路径端点"""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and data["data"].get("name") == "AI Eval Platform":
                log_result("根路径端点", True)
                return True
            else:
                log_result("根路径端点", False, f"响应内容错误: {data}")
        else:
            log_result("根路径端点", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("根路径端点", False, f"连接失败: {e}")
    return False


def test_admin_login():
    """测试管理员登录"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "access_token" in data["data"]:
                log_result("管理员登录", True)
                return data["data"]["access_token"]
            else:
                log_result("管理员登录", False, f"响应内容错误: {data}")
        else:
            log_result(
                "管理员登录", False, f"状态码: {response.status_code}, 响应: {response.text}"
            )
    except Exception as e:
        log_result("管理员登录", False, f"连接失败: {e}")
    return None


def test_user_login():
    """测试普通用户登录"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json={"username": "user", "password": "user123"},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "access_token" in data["data"]:
                log_result("普通用户登录", True)
                return True
            else:
                log_result("普通用户登录", False, f"响应内容错误: {data}")
        else:
            log_result("普通用户登录", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("普通用户登录", False, f"连接失败: {e}")
    return False


def test_wrong_password_login():
    """测试错误密码登录"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/v1/auth/login",
            json={"username": "admin", "password": "wrongpassword"},
            timeout=10,
        )
        if response.status_code == 401:
            log_result("错误密码登录", True)
            return True
        else:
            log_result("错误密码登录", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("错误密码登录", False, f"连接失败: {e}")
    return False


def test_list_evaluators():
    """测试列出评估器"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/evaluators", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and isinstance(data["data"], list) and len(data["data"]) > 0:
                names = [e["name"] for e in data["data"]]
                required = ["general", "code", "semantic", "risk"]
                missing = [r for r in required if r not in names]
                if not missing:
                    log_result("列出评估器", True)
                    return True
                else:
                    log_result("列出评估器", False, f"缺少评估器: {missing}")
            else:
                log_result("列出评估器", False, f"响应内容错误: {data}")
        else:
            log_result("列出评估器", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("列出评估器", False, f"连接失败: {e}")
    return False


def test_evaluate(token):
    """测试提交评测请求"""
    if not token:
        log_result("提交评测请求", False, "无认证token")
        return False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_BASE_URL}/api/v1/evaluate",
            headers=headers,
            json={
                "id": "deploy_test_case_001",
                "type": "general",
                "payload": {
                    "user_input": "What is AI?",
                    "expected_output": "AI stands for Artificial Intelligence",
                },
            },
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "record_id" in data["data"]:
                log_result("提交评测请求", True)
                return True
            else:
                log_result("提交评测请求", False, f"响应内容错误: {data}")
        else:
            log_result(
                "提交评测请求", False, f"状态码: {response.status_code}, 响应: {response.text}"
            )
    except Exception as e:
        log_result("提交评测请求", False, f"连接失败: {e}")
    return False


def test_get_me(token):
    """测试获取当前用户信息"""
    if not token:
        log_result("获取当前用户信息", False, "无认证token")
        return False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE_URL}/api/v1/auth/me", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and data["data"].get("username") == "admin":
                log_result("获取当前用户信息", True)
                return True
            else:
                log_result("获取当前用户信息", False, f"响应内容错误: {data}")
        else:
            log_result("获取当前用户信息", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("获取当前用户信息", False, f"连接失败: {e}")
    return False


def test_list_records(token):
    """测试查询评测记录列表"""
    if not token:
        log_result("查询评测记录列表", False, "无认证token")
        return False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_BASE_URL}/api/v1/records", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "items" in data["data"]:
                log_result("查询评测记录列表", True)
                return True
            else:
                log_result("查询评测记录列表", False, f"响应内容错误: {data}")
        else:
            log_result("查询评测记录列表", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("查询评测记录列表", False, f"连接失败: {e}")
    return False


def test_detailed_health():
    """测试详细健康检查"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/health", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0 and "components" in data["data"]:
                log_result("详细健康检查", True)
                components = data["data"]["components"]
                for comp in ["database", "redis", "rabbitmq"]:
                    if comp in components:
                        status = components[comp].get("status")
                        print(f"        {comp}: {status}")
                    else:
                        print(f"        {comp}: 未检查")
                return True
            else:
                log_result("详细健康检查", False, f"响应内容错误: {data}")
        else:
            log_result("详细健康检查", False, f"状态码: {response.status_code}")
    except Exception as e:
        log_result("详细健康检查", False, f"连接失败: {e}")
    return False


def main():
    print("=" * 60)
    print("AI-Eval-Pro 部署测试")
    print(f"目标服务器: {API_BASE_URL}")
    print("=" * 60)
    print()

    test_health()
    test_root()
    test_detailed_health()

    token = test_admin_login()
    test_user_login()
    test_wrong_password_login()

    test_list_evaluators()

    if token:
        test_get_me(token)
        test_list_records(token)
        test_evaluate(token)

    print()
    print("=" * 60)
    passed = sum(1 for _, p in TEST_RESULTS if p)
    total = len(TEST_RESULTS)
    print(f"测试结果: {passed}/{total} 通过")
    if passed == total:
        print("所有测试通过！")
    else:
        print("部分测试失败，请检查服务器状态")
        print("失败测试:")
        for name, p in TEST_RESULTS:
            if not p:
                print(f"  - {name}")
    print("=" * 60)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
