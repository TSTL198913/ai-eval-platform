"""
安全中间件 - 在API Gateway层进行安全检测
毫秒级响应，只拦截高风险请求
"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
import time
import re

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+all\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"ignore\s+previous\s+instructions?", re.IGNORECASE),
    re.compile(r"ignore\s+all\s+previous\s+commands?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(developer|hacker|admin)\s+mode", re.IGNORECASE),
    re.compile(r"show\s+me\s+your\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+your\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+your\s+programming", re.IGNORECASE),
    re.compile(r"overwrite\s+your\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+no\s+longer\s+an\s+ai", re.IGNORECASE),
    re.compile(r"bypass\s+security", re.IGNORECASE),
    re.compile(r"execute\s+command", re.IGNORECASE),
    re.compile(r"run\s+shell", re.IGNORECASE),
    re.compile(r"rm\s+-rf", re.IGNORECASE),
    re.compile(r"format\s+disk", re.IGNORECASE),
    re.compile(r"system\s*:\s*override", re.IGNORECASE),
    re.compile(r"override\s+security\s+settings", re.IGNORECASE),
]

DATA_LEAK_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
    re.compile(r"AKIA[A-Z0-9]{16}", re.IGNORECASE),
    re.compile(r"AIza[0-9A-Za-z_-]{30,45}", re.IGNORECASE),  # GCP API keys vary in length
    re.compile(r"mongodb\+srv://", re.IGNORECASE),
    re.compile(r"postgres://.*:.*@", re.IGNORECASE),
    re.compile(r"mysql://.*:.*@", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*['\"]?[^'\"]{8,}", re.IGNORECASE),
    re.compile(r"secret\s*[:=]\s*['\"]?[^'\"]{16,}", re.IGNORECASE),
]

# 安全响应头
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        body = {}
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.json()
        except:
            pass

        user_input = ""
        if isinstance(body, dict):
            user_input = str(body.get("user_input", "")) + str(body.get("payload", "")) + str(body.get("input", ""))

        if isinstance(body, list):
            user_input = str(body)

        user_input += str(request.query_params)

        risk_level, risk_details = self.detect_risk(user_input)
        response_time = (time.time() - start_time) * 1000

        if risk_level == "high":
            response = JSONResponse(
                status_code=403,
                content={
                    "code": 403,
                    "message": "Security Blocked: High risk detected",
                    "data": {
                        "risk_level": risk_level,
                        "risk_details": risk_details,
                        "response_time_ms": round(response_time, 2)
                    }
                }
            )
            # 添加安全头
            for header_name, header_value in SECURITY_HEADERS.items():
                response.headers[header_name] = header_value
            return response

        response = await call_next(request)

        # 添加安全头到所有响应
        if isinstance(response, Response):
            for header_name, header_value in SECURITY_HEADERS.items():
                response.headers[header_name] = header_value

        return response

    def detect_risk(self, text: str) -> tuple[str, list]:
        risk_details = []

        for pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                risk_details.append(f"Injection: {pattern.pattern[:30]}...")

        for pattern in DATA_LEAK_PATTERNS:
            if pattern.search(text):
                risk_details.append(f"Data leak: {pattern.pattern[:30]}...")

        if len(risk_details) >= 1:
            return "high", risk_details
        else:
            return "low", risk_details
