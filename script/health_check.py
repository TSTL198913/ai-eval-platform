# scripts/health_check.py
from src.services.evaluator_svc import run_evaluation_service

def regression_test():
    test_cases = [
        {"id": "REG_001", "type": "finance", "payload": {"text": "投资分析", "metadata": {"rate": 0.05}}},
        {"id": "REG_002", "type": "error_test", "payload": {"text": "非法类型"}}
    ]
    for case in test_cases:
        res = run_evaluation_service(case)
        print(f"Case {case['id']} | Status: {res['status']}")

if __name__ == "__main__":
    regression_test()