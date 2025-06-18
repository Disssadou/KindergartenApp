from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Annotated, Optional


from database import database, models, schemas
from server.utils import security
from server.utils.encryption import decrypt_data


from server.utils.security import (
    get_current_active_user,
    verify_password,
    create_access_token,
)

get_db = database.get_db
router = APIRouter()


# --- Эндпоинт для получения токена ---
@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
):
    """Аутентифицирует пользователя и возвращает JWT токен."""
    user = (
        db.query(models.User).filter(models.User.username == form_data.username).first()
    )
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_data = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
    }
    access_token = create_access_token(data=access_token_data)

    return {"access_token": access_token, "token_type": "bearer"}


# --- Эндпоинт для получения информации о себе ---
@router.get("/me", response_model=schemas.UserRead)
async def read_users_me(
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    decrypted_email = decrypt_data(current_user.email)
    decrypted_full_name = decrypt_data(current_user.full_name)
    decrypted_phone = decrypt_data(current_user.phone) if current_user.phone else None
    """Возвращает информацию о текущем аутентифицированном пользователе."""
    return schemas.UserRead(
        id=current_user.id,
        username=current_user.username,
        email=decrypted_email,
        full_name=decrypted_full_name,
        phone=decrypted_phone,
        role=current_user.role,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        fcm_token=current_user.fcm_token,
    )
