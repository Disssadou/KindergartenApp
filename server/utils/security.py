from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Annotated
import os
import sys
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import JWTError, jwt
from pydantic import (
    ValidationError,
    BaseModel,
    Field,
)

from fastapi import Depends, HTTPException, status

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import logging


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from database import (
    database,
    models,
    schemas,
)

logger = logging.getLogger("KindergartenApp")


load_dotenv()

# --- Настройки JWT ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

if not SECRET_KEY:
    logger.critical("CRITICAL ERROR: SECRET_KEY environment variable not set!")
    raise ValueError(
        "SECRET_KEY environment variable is not set! Please set it in .env"
    )

# --- Настройки хеширования паролей ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет, соответствует ли введенный пароль хешу."""
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:

        logger.error(f"Error verifying password: {e}", exc_info=False)
        return False


def get_password_hash(password: str) -> str:
    """Генерирует хеш пароля."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создает JWT токен доступа."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# Схема для валидации данных из токена
class TokenPayload(BaseModel):
    sub: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[schemas.UserRole] = None
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None


def decode_access_token(token: str) -> Optional[TokenPayload]:
    """
    Декодирует JWT токен доступа и валидирует его с помощью Pydantic.
    Возвращает объект TokenPayload в случае успеха, иначе None.
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_sub": True,
            },
        )
        token_data = TokenPayload(**payload)

        return token_data
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        return None
    except ValidationError as e:
        logger.warning(f"JWT payload validation error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error decoding token: {e}", exc_info=True)
        return None


# --- Зависимости FastAPI ---


bearer_scheme = HTTPBearer(auto_error=False)

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
forbidden_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Operation not permitted",
)


async def get_validated_token_data(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> TokenPayload:
    """
    Зависимость FastAPI: Проверяет заголовок Authorization, декодирует токен
    и возвращает валидированные данные токена (TokenPayload).
    Вызывает HTTPException при ошибках.
    """
    if auth is None or auth.scheme.lower() != "bearer":
        logger.debug(
            "Bearer token not found or invalid scheme in Authorization header."
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(auth.credentials)
    if token_data is None:
        logger.debug("Token decoding or validation failed.")

        raise credentials_exception

    logger.debug(f"Token validated successfully for user_id: {token_data.user_id}")
    return token_data


async def get_current_active_user(
    token_data: Annotated[TokenPayload, Depends(get_validated_token_data)],
    db: Annotated[Session, Depends(database.get_db)],
) -> models.User:
    """
    Зависимость FastAPI: Получает пользователя из БД на основе валидных данных токена
    и проверяет его активность (если необходимо).
    """
    if token_data.user_id is None:

        logger.warning("user_id is missing in token payload.")
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == token_data.user_id).first()
    if user is None:

        logger.warning(f"User with id {token_data.user_id} from token not found in DB.")
        raise credentials_exception

    logger.debug(f"Authenticated user retrieved: {user.username} (id: {user.id})")
    return user


# --- Зависимости для проверки ролей ---


async def require_admin_role(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """Зависимость FastAPI: Проверяет, имеет ли пользователь роль ADMIN."""
    if current_user.role != models.UserRole.ADMIN:
        logger.warning(
            f"Access denied for user {current_user.username} (role: {current_user.role}). Admin role required."
        )
        raise forbidden_exception


async def require_teacher_or_admin_role(
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """Зависимость FastAPI: Проверяет, имеет ли пользователь роль TEACHER или ADMIN."""
    allowed_roles = [models.UserRole.TEACHER, models.UserRole.ADMIN]
    if current_user.role not in allowed_roles:
        logger.warning(
            f"Access denied for user {current_user.username} (role: {current_user.role}). Teacher or Admin role required."
        )
        raise forbidden_exception
