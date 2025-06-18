from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Annotated


from database import database, models, schemas
from server.utils import security


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role


router = APIRouter()

# --- Создание группы (только админ) ---
@router.post(
    "/",
    response_model=schemas.GroupRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_role)] 
)
async def create_group(
    group_data: schemas.GroupCreate,
    db: Annotated[Session, Depends(get_db)],
    
):
    """Создает новую группу."""
    if group_data.teacher_id:
        teacher = db.query(models.User).filter(
            models.User.id == group_data.teacher_id,
            models.User.role == models.UserRole.TEACHER
        ).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Teacher with id {group_data.teacher_id} not found or is not a teacher."
            )
    
    existing_group = db.query(models.Group).filter(models.Group.name == group_data.name).first()
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Group with name '{group_data.name}' already exists."
        )

    db_group = models.Group(**group_data.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# --- Получение списка групп (все аутентифицированные) ---
@router.get("/", response_model=List[schemas.GroupRead])
async def read_groups(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)], 
    skip: int = 0,
    limit: int = 100
):
    """Возвращает список групп."""
    groups = db.query(models.Group).order_by(models.Group.name).offset(skip).limit(limit).all()
    return groups

# --- Получение одной группы по ID (все аутентифицированные) ---
@router.get("/{group_id}", response_model=schemas.GroupRead)
async def read_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)], 
):
    """Возвращает информацию о конкретной группе по ее ID."""
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if db_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return db_group

# --- Обновление группы (только админ) ---
@router.put(
    "/{group_id}",
    response_model=schemas.GroupRead,
    dependencies=[Depends(require_admin_role)] 
)
async def update_group(
    group_id: int,
    group_data: schemas.GroupUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    """Обновляет информацию о группе."""
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if db_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    update_data = group_data.dict(exclude_unset=True)

    
    if 'name' in update_data and update_data['name'] != db_group.name:
        existing_group = db.query(models.Group).filter(models.Group.name == update_data['name']).first()
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Group with name '{update_data['name']}' already exists."
            )

    
    if 'teacher_id' in update_data:
        teacher_id = update_data['teacher_id']
        if teacher_id is not None: 
             teacher = db.query(models.User).filter(
                models.User.id == teacher_id,
                models.User.role == models.UserRole.TEACHER
            ).first()
             if not teacher:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Teacher with id {teacher_id} not found or is not a teacher."
                )
        

    for key, value in update_data.items():
        setattr(db_group, key, value)

    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

# --- Удаление группы (только админ) ---
@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)] 
)
async def delete_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Удаляет группу."""
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if db_group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    

    db.delete(db_group)
    db.commit()
    