from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import (
    select,
    and_,
    delete,
    or_,
)
from typing import List, Annotated, Optional
from datetime import date, datetime, timezone
import logging


from database import database, models, schemas
from server.utils import security
from server.utils.encryption import (
    encrypt_data,
    decrypt_data,
)


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role
require_teacher_or_admin_role = security.require_teacher_or_admin_role

logger = logging.getLogger("KindergartenApp.routers.children")

router = APIRouter()


def _convert_child_model_to_read_schema(db_child: models.Child) -> schemas.ChildRead:
    if db_child is None:
        return None

    decrypted_full_name = decrypt_data(db_child.full_name)

    decrypted_birth_date_str = decrypt_data(db_child.birth_date)
    birth_date_obj = None
    if decrypted_birth_date_str and decrypted_birth_date_str != "[Ошибка дешифровки]":
        try:
            birth_date_obj = date.fromisoformat(decrypted_birth_date_str)
        except ValueError:
            logger.error(
                f"Could not convert decrypted birth_date string '{decrypted_birth_date_str}' to date for child {db_child.id}"
            )

    decrypted_address = decrypt_data(db_child.address)
    decrypted_medical_info = decrypt_data(db_child.medical_info)

    group_simple = None
    if db_child.group:
        group_simple = schemas.GroupSimple.model_validate(db_child.group)

    return schemas.ChildRead(
        id=db_child.id,
        full_name=decrypted_full_name,
        birth_date=birth_date_obj,
        address=decrypted_address,
        medical_info=decrypted_medical_info,
        group_id=db_child.group_id,
        created_at=db_child.created_at,
        group=group_simple,
    )


# --- Создание ребенка (Админ или Учитель) ---
@router.post(
    "/",
    response_model=schemas.ChildRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def create_child(
    child_in: schemas.ChildCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.info(
        f"User '{current_user.username}' attempting to create child: {child_in.full_name}"
    )
    if child_in.group_id:
        group = (
            db.query(models.Group).filter(models.Group.id == child_in.group_id).first()
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group with id {child_in.group_id} not found.",
            )
        if (
            current_user.role == models.UserRole.TEACHER
            and group.teacher_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to add child to this group",
            )

    encrypted_full_name = encrypt_data(child_in.full_name)
    birth_date_iso_str = child_in.birth_date.isoformat()
    encrypted_birth_date_str = encrypt_data(birth_date_iso_str)
    encrypted_address = encrypt_data(child_in.address) if child_in.address else None
    encrypted_medical_info = (
        encrypt_data(child_in.medical_info) if child_in.medical_info else None
    )

    db_child = models.Child(
        full_name=encrypted_full_name,
        birth_date=encrypted_birth_date_str,
        address=encrypted_address,
        medical_info=encrypted_medical_info,
        group_id=child_in.group_id,
    )

    try:
        db.add(db_child)
        db.commit()
        db.refresh(db_child)
        logger.info(
            f"User '{current_user.username}' created child (ID: {db_child.id}, Encrypted Name: {db_child.full_name[:20]}...)."
        )
        if db_child.group_id:
            db.refresh(db_child, ["group"])

        return _convert_child_model_to_read_schema(db_child)
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error creating child (encrypted name: {encrypted_full_name[:20]}...): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create child.",
        )


# --- Получение списка детей (Админ или Учитель) ---
@router.get(
    "/",
    response_model=List[schemas.ChildRead],
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def read_children(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    group_id: Optional[int] = Query(None, description="Фильтр по ID группы"),
    search: Optional[str] = Query(
        None,
        description="Поиск по ФИО (частичное совпадение, работает по НЕЗАШИФРОВАННЫМ данным, если реализовано)",
        min_length=2,
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
):
    logger.debug(
        f"User '{current_user.username}' reading children list with filters: group_id={group_id}, search='{search}'"
    )
    query = db.query(models.Child).options(selectinload(models.Child.group))

    if current_user.role == models.UserRole.TEACHER:
        teacher_group_ids = [group.id for group in current_user.groups_led]
        if not teacher_group_ids:
            return []
        if group_id is not None and group_id not in teacher_group_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view children of this group",
            )
        if group_id is None:
            query = query.filter(models.Child.group_id.in_(teacher_group_ids))

    if group_id is not None:
        query = query.filter(models.Child.group_id == group_id)

    db_children = query.order_by(models.Child.id).offset(skip).limit(limit).all()

    # --- ДЕШИФРОВКА СПИСКА ПЕРЕД ВОЗВРАТОМ ---
    response_children = []
    for db_child in db_children:
        child_read = _convert_child_model_to_read_schema(db_child)
        if search:
            if (
                child_read
                and child_read.full_name
                and search.lower() in child_read.full_name.lower()
            ):
                response_children.append(child_read)
        else:
            if child_read:
                response_children.append(child_read)

    logger.info(
        f"Returning {len(response_children)} children for user '{current_user.username}'."
    )
    return response_children


# --- Получение одного ребенка по ID (Админ, Учитель, Родитель этого ребенка) ---
@router.get("/{child_id}", response_model=schemas.ChildRead)
async def read_child(
    child_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.debug(
        f"User '{current_user.username}' attempting to read child ID: {child_id}"
    )
    db_child = (
        db.query(models.Child)
        .options(selectinload(models.Child.group))
        .filter(models.Child.id == child_id)
        .first()
    )

    if db_child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
        )

    can_view = False
    if current_user.role == models.UserRole.ADMIN:
        can_view = True
    elif current_user.role == models.UserRole.TEACHER:
        teacher_group_ids = [group.id for group in current_user.groups_led]
        if db_child.group_id in teacher_group_ids:
            can_view = True
    elif current_user.role == models.UserRole.PARENT:
        is_parent = (
            db.query(models.ChildParent)
            .filter(
                models.ChildParent.child_id == child_id,
                models.ChildParent.parent_id == current_user.id,
            )
            .first()
        )
        if is_parent:
            can_view = True

    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this child's information",
        )

    # --- ДЕШИФРОВКА ПЕРЕД ВОЗВРАТОМ ---
    logger.info(f"Child ID {child_id} data retrieved, preparing for response.")
    return _convert_child_model_to_read_schema(db_child)


# --- Обновление ребенка (Админ или Учитель) ---
@router.put("/{child_id}", response_model=schemas.ChildRead)
async def update_child(
    child_id: int,
    child_in: schemas.ChildUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    logger.info(
        f"User '{current_user.username}' attempting to update child ID: {child_id} with data: {child_in.model_dump(exclude_unset=True)}"
    )
    db_child = db.query(models.Child).filter(models.Child.id == child_id).first()

    if db_child is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
        )

    can_edit = False
    if current_user.role == models.UserRole.ADMIN:
        can_edit = True
    elif current_user.role == models.UserRole.TEACHER:
        teacher_group_ids = [group.id for group in current_user.groups_led]
        if db_child.group_id in teacher_group_ids:
            can_edit = True
    if not can_edit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this child",
        )

    update_data = child_in.model_dump(exclude_unset=True)

    # --- ШИФРОВАНИЕ ОБНОВЛЯЕМЫХ ДАННЫХ ---
    if "full_name" in update_data and update_data["full_name"] is not None:
        update_data["full_name"] = encrypt_data(update_data["full_name"])

    if "birth_date" in update_data and update_data["birth_date"] is not None:
        birth_date_obj: date = update_data["birth_date"]
        update_data["birth_date"] = encrypt_data(birth_date_obj.isoformat())

    if "address" in update_data and update_data["address"] is not None:
        update_data["address"] = encrypt_data(update_data["address"])
    elif "address" in update_data and update_data["address"] is None:
        update_data["address"] = None

    if "medical_info" in update_data and update_data["medical_info"] is not None:
        update_data["medical_info"] = encrypt_data(update_data["medical_info"])
    elif "medical_info" in update_data and update_data["medical_info"] is None:
        update_data["medical_info"] = None

    if "group_id" in update_data:
        new_group_id = update_data["group_id"]
        if new_group_id is not None:
            group = (
                db.query(models.Group).filter(models.Group.id == new_group_id).first()
            )
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Group with id {new_group_id} not found.",
                )
            if (
                current_user.role == models.UserRole.TEACHER
                and group.teacher_id != current_user.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to assign child to this group",
                )

    for key, value in update_data.items():
        setattr(db_child, key, value)

    try:
        db.add(db_child)
        db.commit()
        db.refresh(db_child)
        if db_child.group_id:
            db.refresh(db_child, ["group"])
        logger.info(f"User '{current_user.username}' updated child (ID: {child_id}).")

        # --- ДЕШИФРОВКА ПЕРЕД ВОЗВРАТОМ ---
        return _convert_child_model_to_read_schema(db_child)
    except Exception as e:
        db.rollback()
        logger.error(f"Database error updating child id {child_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update child.",
        )


def _convert_child_parent_model_to_read_schema(
    db_link: models.ChildParent,
) -> schemas.ChildParentRead:

    decrypted_parent_full_name = decrypt_data(db_link.parent.full_name)
    parent_simple = schemas.UserSimple(
        id=db_link.parent.id,
        username=db_link.parent.username,
        full_name=decrypted_parent_full_name,
    )

    decrypted_child_full_name = decrypt_data(db_link.child.full_name)
    child_simple = schemas.ChildSimple(
        id=db_link.child.id,
        full_name=decrypted_child_full_name,
    )

    return schemas.ChildParentRead(
        child_id=db_link.child_id,
        parent_id=db_link.parent_id,
        relation_type=db_link.relation_type,
        child=child_simple,
        parent=parent_simple,
    )


@router.post(
    "/{child_id}/parents",
    response_model=schemas.ChildParentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_role)],
)
async def link_parent_to_child(
    child_id: int,
    link_data: schemas.ChildParentLink,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):

    db_child = db.query(models.Child).filter(models.Child.id == child_id).first()
    if not db_child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
        )
    db_parent = (
        db.query(models.User).filter(models.User.id == link_data.parent_id).first()
    )
    if not db_parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent user with id {link_data.parent_id} not found",
        )
    if db_parent.role != models.UserRole.PARENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {link_data.parent_id} is not a parent.",
        )
    existing_link = (
        db.query(models.ChildParent)
        .filter(
            models.ChildParent.child_id == child_id,
            models.ChildParent.parent_id == link_data.parent_id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This parent is already linked to this child.",
        )

    db_link = models.ChildParent(
        child_id=child_id,
        parent_id=link_data.parent_id,
        relation_type=link_data.relation_type,
    )
    try:
        db.add(db_link)
        db.commit()
        db.refresh(db_link)
        db.refresh(db_link, ["child", "parent"])
        logger.info(
            f"Successfully linked parent {link_data.parent_id} to child {child_id}."
        )

        return _convert_child_parent_model_to_read_schema(db_link)
    except Exception as e:

        db.rollback()
        logger.error(
            f"Database error linking parent {link_data.parent_id} to child {child_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error creating link.",
        )


@router.get(
    "/{child_id}/parents",
    response_model=List[schemas.ChildParentRead],
)
async def get_child_parents_link(
    child_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):

    db_child = db.query(models.Child).filter(models.Child.id == child_id).first()
    if not db_child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
        )

    can_view = False
    if current_user.role in [models.UserRole.ADMIN, models.UserRole.TEACHER]:
        can_view = True
    elif current_user.role == models.UserRole.PARENT:
        is_parent = (
            db.query(models.ChildParent.parent_id)
            .filter(
                models.ChildParent.child_id == child_id,
                models.ChildParent.parent_id == current_user.id,
            )
            .first()
        )
        if is_parent:
            can_view = True
    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view parents for this child",
        )

    links = (
        db.query(models.ChildParent)
        .options(
            selectinload(models.ChildParent.parent),
            selectinload(models.ChildParent.child),
        )
        .filter(models.ChildParent.child_id == child_id)
        .all()
    )

    return [_convert_child_parent_model_to_read_schema(link) for link in links]


# --- Получение истории начислений для ребенка ---
@router.get(
    "/{child_id}/monthly-charges",
    response_model=List[schemas.MonthlyChargeRead],
)
async def get_monthly_charges_for_child(
    child_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    year: Optional[int] = Query(None, description="Фильтр по году"),
):
    """
    Возвращает историю ежемесячных начислений для указанного ребенка.
    Доступно админу или родителю этого ребенка.
    """
    child = db.query(models.Child).filter(models.Child.id == child_id).first()
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Child not found"
        )

    can_view = False
    if current_user.role == models.UserRole.ADMIN:
        can_view = True
    elif current_user.role == models.UserRole.PARENT:
        is_parent = (
            db.query(models.ChildParent)
            .filter(
                models.ChildParent.child_id == child_id,
                models.ChildParent.parent_id == current_user.id,
            )
            .first()
        )
        if is_parent:
            can_view = True

    if not can_view:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view these charges",
        )

    query = db.query(models.MonthlyCharge).filter(
        models.MonthlyCharge.child_id == child_id
    )
    if year:
        query = query.filter(models.MonthlyCharge.year == year)

    charges = query.order_by(
        models.MonthlyCharge.year.desc(), models.MonthlyCharge.month.desc()
    ).all()

    return [schemas.MonthlyChargeRead.model_validate(charge) for charge in charges]
