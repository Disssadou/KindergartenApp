from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session, selectinload
from typing import List, Annotated, Optional
import logging

from database import database, models, schemas
from server.utils import security
from server.utils.encryption import encrypt_data, decrypt_data


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role
get_password_hash = security.get_password_hash

logger = logging.getLogger("KindergartenApp.routers.users")

router = APIRouter()


# --- Создание пользователя (только админ) ---
@router.post(
    "/",
    response_model=schemas.UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_role)],
)
async def create_user(
    user_in: schemas.UserCreate,
    db: Annotated[Session, Depends(get_db)],
):
    logger.info(f"Attempting to create user: {user_in.username}")
    # Проверка на уникальность username
    db_user_by_username = (
        db.query(models.User).filter(models.User.username == user_in.username).first()
    )
    if db_user_by_username:
        logger.warning(f"Username '{user_in.username}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пользователь с именем '{user_in.username}' уже существует.",
        )

    # === ШИФРОВАНИЕ И ПРОВЕРКА EMAIL ===
    encrypted_email = encrypt_data(user_in.email)
    db_user_by_email = (
        db.query(models.User).filter(models.User.email == encrypted_email).first()
    )
    if db_user_by_email:
        logger.warning(f"Email (encrypted) for '{user_in.email}' already exists.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Пользователь с email '{user_in.email}' уже существует.",
        )

    hashed_password = get_password_hash(user_in.password)

    # === ШИФРОВАНИЕ ПДн ПЕРЕД СОЗДАНИЕМ ОБЪЕКТА ===
    db_user = models.User(
        username=user_in.username,
        email=encrypted_email,
        full_name=encrypt_data(user_in.full_name),
        phone=(encrypt_data(user_in.phone) if user_in.phone else None),
        password_hash=hashed_password,
        role=user_in.role.value,
        fcm_token=None,
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(
            f"Admin created user '{db_user.username}' (ID: {db_user.id}, role: {db_user.role})."
        )

        # === ДЕШИФРОВКА ПЕРЕД ВОЗВРАТОМ В UserRead ===

        return schemas.UserRead(
            id=db_user.id,
            username=db_user.username,
            email=decrypt_data(db_user.email),
            full_name=decrypt_data(db_user.full_name),
            phone=decrypt_data(db_user.phone) if db_user.phone else None,
            role=db_user.role,
            created_at=db_user.created_at,
            last_login=db_user.last_login,
            fcm_token=db_user.fcm_token,
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error creating user '{user_in.username}': {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user due to database error.",
        )


# --- Получение списка пользователей (только админ) ---
@router.get(
    "/",
    response_model=List[schemas.UserRead],
    dependencies=[Depends(require_admin_role)],
)
async def read_users(
    db: Annotated[Session, Depends(get_db)],
    role: Optional[schemas.UserRole] = Query(
        None, description="Фильтр по роли (admin, teacher, parent)"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    logger.debug(f"Reading users with role: {role}, skip: {skip}, limit: {limit}")
    query = db.query(models.User)
    if role:
        query = query.filter(models.User.role == role.value)

    db_users = query.order_by(models.User.id).offset(skip).limit(limit).all()

    # === ДЕШИФРОВКА ДЛЯ КАЖДОГО ПОЛЬЗОВАТЕЛЯ В СПИСКЕ ===
    users_response = []
    for db_user in db_users:
        users_response.append(
            schemas.UserRead(
                id=db_user.id,
                username=db_user.username,
                email=decrypt_data(db_user.email),
                full_name=decrypt_data(db_user.full_name),
                phone=decrypt_data(db_user.phone) if db_user.phone else None,
                role=db_user.role,
                created_at=db_user.created_at,
                last_login=db_user.last_login,
                fcm_token=db_user.fcm_token,
            )
        )
    return users_response


# --- Получение конкретного пользователя (админ или сам пользователь) ---
@router.get("/{user_id}", response_model=schemas.UserRead)
async def read_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user_dependency: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.debug(f"User {current_user_dependency.username} reading user ID: {user_id}")
    db_user: Optional[models.User] = None
    if current_user_dependency.role == models.UserRole.ADMIN:
        db_user = db.query(models.User).filter(models.User.id == user_id).first()
    elif current_user_dependency.id == user_id:
        db_user = current_user_dependency
    else:
        logger.warning(
            f"User {current_user_dependency.username} forbidden to access user ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's information.",
        )

    if db_user is None:
        logger.info(f"User ID: {user_id} not found.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # === ДЕШИФРОВКА ПЕРЕД ВОЗВРАТОМ ===
    return schemas.UserRead(
        id=db_user.id,
        username=db_user.username,
        email=decrypt_data(db_user.email),
        full_name=decrypt_data(db_user.full_name),
        phone=decrypt_data(db_user.phone) if db_user.phone else None,
        role=db_user.role,
        created_at=db_user.created_at,
        last_login=db_user.last_login,
        fcm_token=db_user.fcm_token,
    )


# --- Обновление пользователя (админ или сам пользователь) ---
@router.put("/{user_id}", response_model=schemas.UserRead)
async def update_user(
    user_id: int,
    user_in: schemas.UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user_dependency: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.info(
        f"User {current_user_dependency.username} attempting to update user ID: {user_id} with data: {user_in.model_dump(exclude_unset=True)}"
    )
    user_to_update = db.query(models.User).filter(models.User.id == user_id).first()

    if user_to_update is None:
        logger.info(f"User ID: {user_id} not found for update.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if (
        current_user_dependency.role != models.UserRole.ADMIN
        and current_user_dependency.id != user_id
    ):
        logger.warning(
            f"User {current_user_dependency.username} forbidden to update user ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user.",
        )

    update_data = user_in.model_dump(exclude_unset=True)

    # === ШИФРОВАНИЕ И ПРОВЕРКА EMAIL ПРИ ОБНОВЛЕНИИ ===
    if "email" in update_data:
        new_email_plain = update_data["email"]
        encrypted_new_email = encrypt_data(new_email_plain)
        if encrypted_new_email != user_to_update.email:
            existing_user_by_email = (
                db.query(models.User)
                .filter(models.User.email == encrypted_new_email)
                .first()
            )
            if existing_user_by_email and existing_user_by_email.id != user_id:
                logger.warning(
                    f"New email (encrypted) for '{new_email_plain}' already exists for another user."
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Пользователь с email '{new_email_plain}' уже существует.",
                )
            update_data["email"] = encrypted_new_email
        else:

            del update_data["email"]

    # === ШИФРОВАНИЕ ДРУГИХ ПОЛЕЙ ПРИ ОБНОВЛЕНИИ ===
    if "full_name" in update_data:
        update_data["full_name"] = encrypt_data(update_data["full_name"])

    if "phone" in update_data:
        update_data["phone"] = (
            encrypt_data(update_data["phone"]) if update_data["phone"] else None
        )

    for key, value in update_data.items():
        setattr(user_to_update, key, value)

    try:
        db.add(user_to_update)
        db.commit()
        db.refresh(user_to_update)
        logger.info(
            f"User '{user_to_update.username}' (ID: {user_id}) updated by {current_user_dependency.username}."
        )

        # === ДЕШИФРОВКА ПЕРЕД ВОЗВРАТОМ ===
        return schemas.UserRead(
            id=user_to_update.id,
            username=user_to_update.username,
            email=decrypt_data(user_to_update.email),
            full_name=decrypt_data(user_to_update.full_name),
            phone=decrypt_data(user_to_update.phone) if user_to_update.phone else None,
            role=user_to_update.role,
            created_at=user_to_update.created_at,
            last_login=user_to_update.last_login,
            fcm_token=user_to_update.fcm_token,
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating user id {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user due to database error.",
        )


# --- Удаление пользователя (только админ) ---
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
)
async def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user_dependency: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.info(
        f"Admin {current_user_dependency.username} attempting to delete user ID: {user_id}"
    )
    if current_user_dependency.id == user_id:
        logger.warning(
            f"Admin {current_user_dependency.username} attempted to delete self."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator cannot delete themselves.",
        )

    user_to_delete = db.query(models.User).filter(models.User.id == user_id).first()

    if user_to_delete is None:
        logger.info(f"User ID: {user_id} not found for deletion.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    username_deleted = user_to_delete.username
    try:
        db.delete(user_to_delete)
        db.commit()
        logger.info(
            f"User '{username_deleted}' (ID: {user_id}) deleted by admin {current_user_dependency.username}."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Database error deleting user id {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user due to database error.",
        )


# --- Получение списка детей родителя (Сам родитель или Админ) ---
@router.get(
    "/{user_id}/children",
    response_model=List[schemas.ChildParentRead],
)
async def read_user_children_link(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user_dependency: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.debug(
        f"User {current_user_dependency.username} requesting children for user ID: {user_id}"
    )

    if not (
        current_user_dependency.role == models.UserRole.ADMIN
        or current_user_dependency.id == user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view children for this user",
        )

    target_user_db = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
        )

    if target_user_db.role != models.UserRole.PARENT:

        logger.warning(
            f"User ID: {user_id} is not a parent (role: {target_user_db.role}). Returning empty list."
        )

        return []

    # Загружаем связи ребенок-родитель, предзагружая объекты ребенка и родителя
    links = (
        db.query(models.ChildParent)
        .options(
            selectinload(models.ChildParent.child).selectinload(models.Child.group),
            selectinload(models.ChildParent.parent),
        )
        .filter(models.ChildParent.parent_id == user_id)
        .all()
    )

    response_links = []
    for link in links:
        if not link.parent or not link.child:
            logger.warning(
                f"Skipping ChildParent link due to missing parent or child object for parent_id={link.parent_id}, child_id={link.child_id}"
            )
            continue

        # --- Формируем Parent (UserSimple) ---
        decrypted_parent_full_name = decrypt_data(link.parent.full_name)
        parent_simple = schemas.UserSimple(
            id=link.parent.id,
            username=link.parent.username,
            full_name=decrypted_parent_full_name,
        )

        # --- Формируем Child (ChildSimple с информацией о последнем начислении) ---
        decrypted_child_full_name = decrypt_data(link.child.full_name)

        # Ищем последнее начисление для этого ребенка
        last_charge_db = (
            db.query(models.MonthlyCharge)
            .filter(models.MonthlyCharge.child_id == link.child.id)
            .order_by(desc(models.MonthlyCharge.year), desc(models.MonthlyCharge.month))
            .first()
        )

        last_charge_amount = None
        last_charge_year = None
        last_charge_month = None

        if last_charge_db:
            last_charge_amount = float(last_charge_db.amount_due)
            last_charge_year = last_charge_db.year
            last_charge_month = last_charge_db.month

        child_simple = schemas.ChildSimple(
            id=link.child.id,
            full_name=decrypted_child_full_name,
            last_charge_amount=last_charge_amount,
            last_charge_year=last_charge_year,
            last_charge_month=last_charge_month,
        )

        response_links.append(
            schemas.ChildParentRead(
                child_id=link.child_id,
                parent_id=link.parent_id,
                relation_type=link.relation_type,
                child=child_simple,
                parent=parent_simple,
            )
        )

    logger.info(
        f"Returning {len(response_links)} children links for user ID: {user_id}"
    )
    return response_links
