"""
认证路由模块
包含登录、刷新令牌、获取当前用户信息等端点
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from src.api.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    HAS_AUTH,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_token,
    fake_users_db,
    get_current_user,
)
from src.api.common import error_response, success_response

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


# =====================================================================
# Pydantic Schema - 输入验证
# =====================================================================


class LoginRequest(BaseModel):
    """登录请求Schema - FastAPI自动验证返回422"""

    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class RefreshRequest(BaseModel):
    """刷新令牌请求Schema"""

    refresh_token: str = Field(..., min_length=1, description="刷新令牌")


# =====================================================================
# 路由端点
# =====================================================================


@router.post("/login")
async def login_endpoint(request: LoginRequest, response: Response):
    """用户登录 - 使用Pydantic Schema自动验证"""
    username = request.username.strip()
    password = request.password.strip()

    if not HAS_AUTH:
        return success_response(
            {
                "access_token": "demo-token",
                "refresh_token": "demo-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    user = authenticate_user(fake_users_db, username, password)
    if not user:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Invalid username or password")

    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": "super_admin" if user["username"] == "admin" else "user",
        },
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(data={"sub": user["username"]})

    return success_response(
        {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@router.post("/refresh")
async def refresh_endpoint(request: RefreshRequest, response: Response):
    """刷新令牌 - 使用Pydantic Schema自动验证"""
    refresh_token = request.refresh_token

    if not HAS_AUTH:
        # Demo模式下也需校验token格式，防止任意字符串绕过
        if not refresh_token.startswith("demo-"):
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return error_response(401, "Invalid refresh_token")
        return success_response(
            {
                "access_token": "demo-token",
                "refresh_token": "demo-refresh-token",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    payload = decode_token(refresh_token)
    if not payload:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "Invalid refresh_token")

    username = payload.get("sub")
    if not username or username not in fake_users_db:
        response.status_code = status.HTTP_401_UNAUTHORIZED
        return error_response(401, "User not found")

    access_token = create_access_token(
        data={"sub": username, "role": "super_admin" if username == "admin" else "user"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    new_refresh_token = create_refresh_token(data={"sub": username})

    return success_response(
        {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )


@router.get("/me")
async def get_current_user_endpoint(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return success_response(
        {
            "username": current_user.get("username"),
            "full_name": current_user.get("full_name"),
            "email": current_user.get("email"),
            "roles": ["admin"] if current_user.get("username") == "admin" else ["user"],
        }
    )
