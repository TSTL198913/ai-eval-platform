"""
API 权限依赖模块

提供 RBAC 权限验证装饰器和依赖注入。
"""

from collections.abc import Callable
from functools import wraps

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.api.auth import decode_token
from src.infra.security import ROLE_PERMISSIONS, Permission, Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict | None:
    """
    获取当前用户

    从 JWT token 中解析用户信息。

    Args:
        token: OAuth2 token

    Returns:
        用户信息字典，包含 username, role 等

    Raises:
        HTTPException: 未提供认证令牌或令牌无效
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def get_optional_user(token: str = Depends(oauth2_scheme)) -> dict | None:
    """
    获取可选用户（不强制要求认证）

    Args:
        token: OAuth2 token

    Returns:
        用户信息字典或 None
    """
    if not token:
        return None

    payload = decode_token(token)
    return payload


def require_permissions(*permissions: Permission) -> Callable:
    """
    权限验证装饰器

    验证当前用户是否具有所需权限。

    使用示例:
        @router.get("/admin/users")
        @require_permissions(Permission.MANAGE_MODELS)
        async def list_users(current_user: dict = Depends(get_current_user)):
            ...

    Args:
        permissions: 所需权限列表

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            user_role_str = current_user.get("role", "user")

            try:
                user_role = Role(user_role_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无效的角色: {user_role_str}",
                )

            # 获取用户角色的权限列表
            user_permissions = ROLE_PERMISSIONS.get(user_role, [])

            # 检查用户是否有所有要求的权限
            for permission in permissions:
                if permission not in user_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"权限不足，需要权限: {permission.value}",
                    )

            # 将 current_user 传递给被装饰的函数
            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def require_roles(*roles: Role) -> Callable:
    """
    角色验证装饰器

    验证当前用户是否具有所需角色。

    使用示例:
        @router.post("/admin/config")
        @require_roles(Role.ADMIN, Role.SUPER_ADMIN)
        async def update_config(current_user: dict = Depends(get_current_user)):
            ...

    Args:
        roles: 所需角色列表

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user: dict = Depends(get_current_user), **kwargs):
            user_role_str = current_user.get("role", "user")

            try:
                user_role = Role(user_role_str)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"无效的角色: {user_role_str}",
                )

            if user_role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"角色不足，需要角色: {[r.value for r in roles]}",
                )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def require_admin(func: Callable) -> Callable:
    """
    需要管理员权限

    快捷装饰器，验证用户是否为管理员或超级管理员。

    使用示例:
        @router.get("/admin/settings")
        @require_admin
        async def get_settings(current_user: dict = Depends(get_current_user)):
            ...
    """
    return require_roles(Role.ADMIN, Role.SUPER_ADMIN)(func)


def require_super_admin(func: Callable) -> Callable:
    """
    需要超级管理员权限

    快捷装饰器，验证用户是否为超级管理员。

    使用示例:
        @router.delete("/admin/system")
        @require_super_admin
        async def delete_system(current_user: dict = Depends(get_current_user)):
            ...
    """
    return require_roles(Role.SUPER_ADMIN)(func)


def check_permission(user: dict, permission: Permission) -> bool:
    """
    检查用户是否有指定权限（不抛异常）

    Args:
        user: 用户信息字典
        permission: 要检查的权限

    Returns:
        是否有权限
    """
    user_role_str = user.get("role", "user")

    try:
        user_role = Role(user_role_str)
    except ValueError:
        return False

    user_permissions = ROLE_PERMISSIONS.get(user_role, [])
    return permission in user_permissions


def check_role(user: dict, role: Role) -> bool:
    """
    检查用户是否为指定角色（不抛异常）

    Args:
        user: 用户信息字典
        role: 要检查的角色

    Returns:
        是否为该角色
    """
    user_role_str = user.get("role", "user")

    try:
        user_role = Role(user_role_str)
    except ValueError:
        return False

    return user_role == role


class PermissionDependency:
    """
    权限依赖类

    用于 FastAPI 依赖注入。

    使用示例:
        @router.get("/protected")
        async def protected_route(
            user: dict = Depends(PermissionDependency(Permission.EVALUATE))
        ):
            ...
    """

    def __init__(self, permission: Permission):
        self.permission = permission

    async def __call__(self, current_user: dict = Depends(get_current_user)) -> dict:
        user_role_str = current_user.get("role", "user")

        try:
            user_role = Role(user_role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无效的角色: {user_role_str}",
            )

        user_permissions = ROLE_PERMISSIONS.get(user_role, [])

        if self.permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要权限: {self.permission.value}",
            )

        return current_user


class RoleDependency:
    """
    角色依赖类

    用于 FastAPI 依赖注入。

    使用示例:
        @router.get("/admin")
        async def admin_route(
            user: dict = Depends(RoleDependency(Role.ADMIN))
        ):
            ...
    """

    def __init__(self, *roles: Role):
        self.roles = roles

    async def __call__(self, current_user: dict = Depends(get_current_user)) -> dict:
        user_role_str = current_user.get("role", "user")

        try:
            user_role = Role(user_role_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无效的角色: {user_role_str}",
            )

        if user_role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"角色不足，需要角色: {[r.value for r in self.roles]}",
            )

        return current_user
