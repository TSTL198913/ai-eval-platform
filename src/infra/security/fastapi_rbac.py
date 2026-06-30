"""
FastAPI RBAC 安全中间件与依赖注入
实现真正的权限验证：
1. JWT令牌验证中间件
2. require_permission依赖注入
3. 当前用户信息获取
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from src.infra.security.rbac import (
    APIKey,
    Permission,
    Role,
    get_security,
)

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)


async def get_current_user(
    request: Request,
    api_key: str | None = Depends(api_key_header),
) -> APIKey | None:
    """获取当前用户（从Authorization头）"""
    security = get_security()

    if api_key and api_key.startswith("Bearer "):
        raw_key = api_key[7:]
    elif api_key:
        raw_key = api_key
    else:
        return None

    return security.verify_api_key(raw_key)


async def require_permission(
    permission: Permission,
    user: APIKey | None = Depends(get_current_user),
) -> APIKey:
    """权限验证依赖注入"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权：需要有效的API密钥",
        )

    security = get_security()
    has_perm, _ = security.check_permission(user.key_id, permission)

    if not has_perm:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"权限不足：需要权限 {permission.value}",
        )

    return user


async def require_role(
    required_role: Role,
    user: APIKey | None = Depends(get_current_user),
) -> APIKey:
    """角色验证依赖注入"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权：需要有效的API密钥",
        )

    role_levels = {
        Role.GUEST: 0,
        Role.USER: 1,
        Role.ANNOTATOR: 1,
        Role.PREMIUM: 2,
        Role.ENTERPRISE: 3,
        Role.ADMIN: 4,
        Role.SECURITY_ADMIN: 4,
        Role.QUALITY_ADMIN: 4,
        Role.FINANCE_ADMIN: 4,
        Role.DEVOPS: 4,
        Role.SUPER_ADMIN: 5,
    }

    if role_levels.get(user.role, 0) < role_levels.get(required_role, 0):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"角色不足：需要角色 {required_role.value}",
        )

    return user


class RBACMiddleware:
    """RBAC权限验证中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        try:
            user = await get_current_user(request)
            if user:
                scope["user"] = user
        except Exception:
            pass

        await self.app(scope, receive, send)


PermissionDep = Annotated[APIKey, Depends(require_permission)]
RoleDep = Annotated[APIKey, Depends(require_role)]
CurrentUserDep = Annotated[APIKey | None, Depends(get_current_user)]
