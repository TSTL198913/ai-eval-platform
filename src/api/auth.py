import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# 认证模块可用性标志（始终为True，因为auth模块已加载）
HAS_AUTH = True

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def _init_users_db():
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    user_password = os.environ.get("USER_PASSWORD", "user123")

    if not admin_password:
        admin_password = "admin123"
    if not user_password:
        user_password = "user123"

    return {
        "admin": {
            "username": "admin",
            "full_name": "Admin User",
            "email": "admin@example.com",
            "hashed_password": get_password_hash(admin_password),
            "role": "admin",
            "disabled": False,
            "created_at": datetime.now(timezone.utc),
        },
        "user": {
            "username": "user",
            "full_name": "Regular User",
            "email": "user@example.com",
            "hashed_password": get_password_hash(user_password),
            "role": "user",
            "disabled": False,
            "created_at": datetime.now(timezone.utc),
        },
    }


fake_users_db = _init_users_db()


def authenticate_user(fake_db: dict, username: str, password: str) -> dict | None:
    if username not in fake_db:
        return None
    user = fake_db[username]
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict | None:
    if not token:
        return None
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as err:
        raise credentials_exception from err
    user = fake_users_db.get(username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user is None:
        raise HTTPException(status_code=400, detail="Inactive user")
    if current_user.get("disabled"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
