"""
AI Eval Platform Mock API Server
用于E2E测试，模拟后端API响应
"""

import random
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AI Eval Platform Mock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str


# 修复：修改评估请求模型以匹配前端发送的数据格式
class EvaluationPayload(BaseModel):
    user_input: Optional[str] = ""
    tests: Optional[list[str]] = None
    text: Optional[str] = None
    context: Optional[str] = None
    expected_output: Optional[str] = None


class EvaluationRequest(BaseModel):
    id: Optional[str] = None
    type: Optional[str] = "security"
    payload: EvaluationPayload = EvaluationPayload()


# Mock data
MOCK_USERS = {
    "admin": {"password": "admin", "token": "mock-jwt-token-12345"},
    "user": {"password": "user123", "token": "mock-jwt-token-67890"},
}

MOCK_EVALUATORS = [
    {"name": "security", "description": "安全检测评估器", "version": "1.0.0", "status": "active"},
    {"name": "quality", "description": "质量评估器", "version": "1.0.0", "status": "active"},
    {"name": "toxicity", "description": "毒性检测评估器", "version": "1.0.0", "status": "active"},
    {"name": "factuality", "description": "事实性评估器", "version": "1.0.0", "status": "active"},
]

MOCK_MODELS = [
    {"name": "gpt-4", "provider": "openai", "status": "active", "cost_per_1k_tokens": 0.03},
    {"name": "claude-3", "provider": "anthropic", "status": "active", "cost_per_1k_tokens": 0.015},
    {"name": "qwen-2.5", "provider": "aliyun", "status": "active", "cost_per_1k_tokens": 0.001},
]

MOCK_RECORDS = [
    {
        "id": "rec_001",
        "case_id": "case_001",
        "model_name": "gpt-4",
        "evaluator": "security",
        "status": "completed",
        "score": 0.95,
        "created_at": "2024-01-15T10:30:00",
    },
    {
        "id": "rec_002",
        "case_id": "case_002",
        "model_name": "claude-3",
        "evaluator": "quality",
        "status": "completed",
        "score": 0.88,
        "created_at": "2024-01-15T11:00:00",
    },
    {
        "id": "rec_003",
        "case_id": "case_003",
        "model_name": "qwen-2.5",
        "evaluator": "toxicity",
        "status": "failed",
        "score": 0.45,
        "created_at": "2024-01-15T12:30:00",
    },
]


# Routes
@app.get("/")
async def root():
    return {"message": "AI Eval Platform API", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Auth routes
@app.post("/api/v1/auth/login")
async def login(request: LoginRequest):
    user = MOCK_USERS.get(request.username)
    if not user or user["password"] != request.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "code": 0,
        "message": "Login successful",
        "data": {
            "token": user["token"],
            "user": {
                "username": request.username,
                "role": "admin" if request.username == "admin" else "user",
            },
        },
    }


@app.get("/api/v1/auth/me")
async def get_current_user():
    return {"code": 0, "data": {"username": "admin", "role": "admin"}}


# Dashboard routes
@app.get("/api/v1/dashboard/stats")
async def get_dashboard_stats():
    return {
        "code": 0,
        "data": {
            "total_records": len(MOCK_RECORDS),
            "avg_score": sum(r["score"] for r in MOCK_RECORDS) / len(MOCK_RECORDS),
            "total_cost_usd": 125.50,
            "avg_latency_ms": 350,
            "evaluator_types": ["security", "quality", "toxicity", "factuality"],
            "status_distribution": {"completed": 2, "failed": 1, "running": 0},
        },
    }


# Evaluators routes
@app.get("/api/v1/evaluators")
async def list_evaluators():
    return {"code": 0, "data": MOCK_EVALUATORS}


@app.get("/api/v1/evaluators/{name}")
async def get_evaluator(name: str):
    evaluator = next((e for e in MOCK_EVALUATORS if e["name"] == name), None)
    if not evaluator:
        raise HTTPException(status_code=404, detail="Evaluator not found")
    return {"code": 0, "data": evaluator}


# Models routes
@app.get("/api/v1/models")
async def list_models():
    return {"code": 0, "data": MOCK_MODELS}


# Records routes
@app.get("/api/v1/records")
async def list_records(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量，最大100"),
    evaluator: Optional[str] = None,
    model: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = Query(None, ge=1, le=1000, description="记录数量限制（兼容性）"),
):
    filtered = MOCK_RECORDS.copy()
    if evaluator:
        filtered = [r for r in filtered if r["evaluator"] == evaluator]
    if model:
        filtered = [r for r in filtered if r["model_name"] == model]
    if status:
        filtered = [r for r in filtered if r["status"] == status]

    # 处理limit参数（兼容性）
    if limit:
        filtered = filtered[:limit]

    return {
        "code": 0,
        "data": {"records": filtered, "total": len(filtered), "page": page, "page_size": page_size},
    }


# Evaluation routes
@app.post("/api/v1/evaluate")
async def evaluate(request: EvaluationRequest):
    # Simulate evaluation
    score = random.uniform(0.6, 1.0)
    is_valid = True

    # Get user input from payload
    user_input = request.payload.user_input or ""

    # Simple injection detection
    if any(keyword in user_input.lower() for keyword in ["ignore", "bypass", "admin", "api key"]):
        score = random.uniform(0.1, 0.4)
        is_valid = False

    # Get tests from payload
    tests = request.payload.tests or ["injection"]
    security_tests = {}

    for test in tests:
        detected = False
        test_score = score

        if test == "injection" and any(k in user_input.lower() for k in ["ignore", "bypass"]):
            detected = True
        elif test == "jailbreak" and any(k in user_input.lower() for k in ["you are no longer"]):
            detected = True
        elif test == "data_leakage" and any(
            k in user_input.lower() for k in ["api key", "password", "secret"]
        ):
            detected = True
        elif test == "tool_abuse" and any(
            k in user_input.lower() for k in ["run command", "rm -rf"]
        ):
            detected = True

        security_tests[test] = {
            "detected": detected,
            "score": round(test_score, 2),
            "reason": f"{test} test result" if detected else None,
        }

    return {
        "code": 0,
        "message": "Evaluation completed",
        "data": {
            "case_id": request.id or f"eval_{int(datetime.now().timestamp())}",
            "score": round(score, 2),
            "is_valid": is_valid,
            "security_tests": security_tests,
            "details": {
                "evaluator": request.type or "security",
                "latency_ms": random.randint(100, 500),
                "cost_usd": round(random.uniform(0.001, 0.01), 4),
            },
        },
    }


# Cost routes
@app.get("/api/v1/cost")
async def get_cost():
    """成本分析路由 - 别名"""
    return await get_cost_analysis()


@app.get("/api/v1/cost/analysis")
async def get_cost_analysis(
    start_date: Optional[str] = None, end_date: Optional[str] = None, granularity: str = "day"
):
    return {
        "code": 0,
        "data": {
            "total_cost_usd": 125.50,
            "cost_by_model": {"gpt-4": 85.20, "claude-3": 35.10, "qwen-2.5": 5.20},
            "cost_by_evaluator": {
                "security": 45.30,
                "quality": 38.70,
                "toxicity": 28.40,
                "factuality": 13.10,
            },
            "daily_costs": [
                {"date": "2024-01-15", "cost": 55.30},
                {"date": "2024-01-14", "cost": 42.80},
                {"date": "2024-01-13", "cost": 27.40},
            ],
        },
    }


# Reports routes
@app.get("/api/v1/reports")
async def list_reports():
    return {
        "code": 0,
        "data": [
            {
                "id": "rpt_001",
                "filename": "security_report_2024-01-15.pdf",
                "created_at": "2024-01-15T14:00:00",
                "size_kb": 256,
            },
            {
                "id": "rpt_002",
                "filename": "quality_report_2024-01-14.pdf",
                "created_at": "2024-01-14T14:00:00",
                "size_kb": 189,
            },
        ],
    }


@app.post("/api/v1/reports/generate")
async def generate_report(report_type: str = "summary"):
    return {
        "code": 0,
        "message": "Report generation started",
        "data": {"report_id": f"rpt_{int(datetime.now().timestamp())}", "status": "pending"},
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
