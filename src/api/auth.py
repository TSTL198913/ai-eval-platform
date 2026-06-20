from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import secrets
import os

from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

SECRET_KEY = os.environ.get(
    "JWT_SECRET_KEY",
    secrets.token_urlsafe(32)
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", 7))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _hash_password(password: str) -> str:
    salt = os.environ.get("PASSWORD_SALT", "")
    if not salt:
        import uuid
        salt = uuid.uuid4().hex
        os.environ["PASSWORD_SALT"] = salt
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return secrets.compare_digest(_hash_password(plain_password), hashed_password)


def get_password_hash(password: str) -> str:
    return _hash_password(password)


def _init_users_db():
    return {
        "admin": {
            "username": "admin",
            "full_name": "Admin User",
            "email": "admin@example.com",
            "hashed_password": _hash_password(os.environ.get("ADMIN_PASSWORD", "admin")),
            "disabled": False,
        },
        "user": {
            "username": "user",
            "full_name": "Regular User",
            "email": "user@example.com",
            "hashed_password": _hash_password(os.environ.get("USER_PASSWORD", "user123")),
            "disabled": False,
        },
    }


fake_users_db = _init_users_db()


def authenticate_user(fake_db: dict, username: str, password: str) -> Optional[dict]:
    if username not in fake_db:
        return None
    user = fake_db[username]
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
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


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(token: str = Depends(oauth2_scheme)) -> Optional[dict]:
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
    except JWTError:
        raise credentials_exception
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
