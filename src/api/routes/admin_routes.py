"""
用户管理 API

提供用户、角色、权限的管理接口。
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.auth import get_password_hash, verify_password
from src.api.dependencies import get_current_user, require_admin
from src.infra.security import ROLE_PERMISSIONS, Permission, Role

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Pydantic 模型
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, description="密码")
    full_name: str | None = Field(None, description="全名")
    email: str | None = Field(None, description="邮箱")
    role: str = Field(default="user", description="角色")


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, description="全名")
    email: str | None = Field(None, description="邮箱")
    role: str | None = Field(None, description="角色")
    disabled: bool | None = Field(None, description="是否禁用")


class UserResponse(BaseModel):
    username: str
    full_name: str | None
    email: str | None
    role: str
    disabled: bool
    created_at: datetime | None = None


class RoleResponse(BaseModel):
    name: str
    value: str
    permissions: list[str]
    level: int


class PermissionResponse(BaseModel):
    name: str
    value: str
    category: str


# 模拟用户数据库（实际应使用真实数据库）
_users_db: dict[str, dict[str, Any]] = {
    "admin": {
        "username": "admin",
        "full_name": "Admin User",
        "email": "admin@example.com",
        "hashed_password": get_password_hash("admin123"),
        "role": "admin",
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
    },
    "user": {
        "username": "user",
        "full_name": "Regular User",
        "email": "user@example.com",
        "hashed_password": get_password_hash("user123"),
        "role": "user",
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
    },
}


@router.get("/users", response_model=list[UserResponse])
@require_admin
async def list_users(current_user: dict = Depends(get_current_user)) -> list[UserResponse]:
    """
    获取用户列表

    需要管理员权限。
    """
    users = []
    for username, user_data in _users_db.items():
        users.append(
            UserResponse(
                username=username,
                full_name=user_data.get("full_name"),
                email=user_data.get("email"),
                role=user_data.get("role", "user"),
                disabled=user_data.get("disabled", False),
                created_at=user_data.get("created_at"),
            )
        )
    return users


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@require_admin
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """
    创建用户

    需要管理员权限。
    """
    # 检查用户名是否已存在
    if user_data.username in _users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"用户名 '{user_data.username}' 已存在",
        )

    # 验证角色是否有效
    try:
        Role(user_data.role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色: {user_data.role}",
        )

    # 创建用户
    new_user = {
        "username": user_data.username,
        "full_name": user_data.full_name,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "role": user_data.role,
        "disabled": False,
        "created_at": datetime.now(timezone.utc),
    }

    _users_db[user_data.username] = new_user

    return UserResponse(
        username=user_data.username,
        full_name=user_data.full_name,
        email=user_data.email,
        role=user_data.role,
        disabled=False,
        created_at=new_user["created_at"],
    )


@router.get("/users/{username}", response_model=UserResponse)
@require_admin
async def get_user(
    username: str,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """
    获取用户详情

    需要管理员权限。
    """
    if username not in _users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 '{username}' 不存在",
        )

    user_data = _users_db[username]
    return UserResponse(
        username=username,
        full_name=user_data.get("full_name"),
        email=user_data.get("email"),
        role=user_data.get("role", "user"),
        disabled=user_data.get("disabled", False),
        created_at=user_data.get("created_at"),
    )


@router.put("/users/{username}", response_model=UserResponse)
@require_admin
async def update_user(
    username: str,
    user_data: UserUpdate,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """
    更新用户

    需要管理员权限。
    """
    if username not in _users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 '{username}' 不存在",
        )

    existing_user = _users_db[username]

    # 更新字段
    if user_data.full_name is not None:
        existing_user["full_name"] = user_data.full_name
    if user_data.email is not None:
        existing_user["email"] = user_data.email
    if user_data.role is not None:
        try:
            Role(user_data.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的角色: {user_data.role}",
            )
        existing_user["role"] = user_data.role
    if user_data.disabled is not None:
        existing_user["disabled"] = user_data.disabled

    _users_db[username] = existing_user

    return UserResponse(
        username=username,
        full_name=existing_user.get("full_name"),
        email=existing_user.get("email"),
        role=existing_user.get("role", "user"),
        disabled=existing_user.get("disabled", False),
        created_at=existing_user.get("created_at"),
    )


@router.delete("/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
@require_admin
async def delete_user(
    username: str,
    current_user: dict = Depends(get_current_user),
) -> None:
    """
    删除用户

    需要管理员权限。

    注意：不能删除自己。
    """
    if username not in _users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 '{username}' 不存在",
        )

    # 不能删除自己
    if username == current_user.get("username"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己的账户",
        )

    del _users_db[username]


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(current_user: dict = Depends(get_current_user)) -> list[RoleResponse]:
    """
    获取角色列表

    所有登录用户可查看。
    """
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

    roles = []
    for role in Role:
        permissions = [p.value for p in ROLE_PERMISSIONS.get(role, [])]
        roles.append(
            RoleResponse(
                name=role.name,
                value=role.value,
                permissions=permissions,
                level=role_levels.get(role, 0),
            )
        )
    return roles


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    current_user: dict = Depends(get_current_user),
) -> list[PermissionResponse]:
    """
    获取权限列表

    所有登录用户可查看。
    """
    # 权限分类
    permission_categories = {
        "基础权限": [Permission.EVALUATE, Permission.VIEW_REPORT, Permission.COMPARE],
        "标注权限": [Permission.ANNOTATE, Permission.REVIEW_ANNOTATION],
        "A/B测试权限": [Permission.CREATE_AB_TEST, Permission.MANAGE_AB_TEST],
        "Benchmark权限": [Permission.RUN_BENCHMARK, Permission.VIEW_BENCHMARK],
        "校准权限": [Permission.MANAGE_GOLDEN_DATASET, Permission.CORRECT_SAMPLE],
        "管理权限": [
            Permission.MANAGE_MODELS,
            Permission.MANAGE_MODEL_VERSIONS,
            Permission.MANAGE_EVALUATORS,
            Permission.MANAGE_EVALUATOR_VERSIONS,
        ],
        "安全权限": [
            Permission.RUN_SECURITY_TEST,
            Permission.VIEW_SECURITY_REPORT,
            Permission.MANAGE_SECURITY_RULES,
        ],
        "质量权限": [Permission.RUN_QUALITY_GATE, Permission.MANAGE_QUALITY_CONFIG],
        "成本权限": [Permission.VIEW_COST_REPORT, Permission.MANAGE_BUDGET],
        "元评估权限": [Permission.VIEW_META_CONFLICTS, Permission.RESOLVE_META_CONFLICT],
        "变异测试权限": [Permission.RUN_MUTATION_TEST, Permission.VIEW_MUTATION_REPORT],
        "系统权限": [Permission.ADMIN, Permission.SUPER_ADMIN],
    }

    permissions = []
    for category, perms in permission_categories.items():
        for perm in perms:
            permissions.append(
                PermissionResponse(
                    name=perm.name,
                    value=perm.value,
                    category=category,
                )
            )

    return permissions


@router.get("/my-permissions", response_model=list[str])
async def get_my_permissions(current_user: dict = Depends(get_current_user)) -> list[str]:
    """
    获取当前用户的权限列表

    所有登录用户可查看自己的权限。
    """
    user_role_str = current_user.get("role", "user")

    try:
        user_role = Role(user_role_str)
    except ValueError:
        return []

    permissions = ROLE_PERMISSIONS.get(user_role, [])
    return [p.value for p in permissions]


@router.post("/users/{username}/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    username: str,
    old_password: str,
    new_password: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """
    修改密码

    用户只能修改自己的密码，管理员可以修改任何人的密码。
    """
    # 检查权限：只能修改自己的密码，或者是管理员
    current_username = current_user.get("username")
    current_role = current_user.get("role", "user")

    if username != current_username and current_role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只能修改自己的密码",
        )

    if username not in _users_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"用户 '{username}' 不存在",
        )

    user_data = _users_db[username]

    # 验证旧密码（管理员修改他人密码时不需要验证旧密码）
    if username == current_username:
        if not verify_password(old_password, user_data["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="旧密码不正确",
            )

    # 更新密码
    user_data["hashed_password"] = get_password_hash(new_password)
    _users_db[username] = user_data

    return {"message": "密码已更新"}
