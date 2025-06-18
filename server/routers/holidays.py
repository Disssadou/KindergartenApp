from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from typing import List, Annotated, Optional
from datetime import date
import logging

from database import database, models, schemas
from server.utils import security


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role


logger = logging.getLogger("KindergartenApp.routers.holidays")

router = APIRouter()


# --- Получение списка праздников/выходных в диапазоне дат ---
@router.get("/", response_model=List[schemas.HolidayRead])
async def read_holidays(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    start_date: date = Query(..., description="Начальная дата диапазона (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Конечная дата диапазона (YYYY-MM-DD)"),
):
    """
    Возвращает список праздничных/выходных дней в указанном диапазоне дат.
    Доступно всем аутентифицированным пользователям.
    """
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date.",
        )
    logger.debug(
        f"User {current_user.username} requests holidays from {start_date} to {end_date}"
    )
    try:
        stmt = (
            select(models.Holiday)
            .where(models.Holiday.date >= start_date, models.Holiday.date <= end_date)
            .order_by(models.Holiday.date)
        )
        holidays = db.execute(stmt).scalars().all()
        return holidays
    except Exception as e:
        logger.error(f"Database error reading holidays: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve holidays due to database error.",
        )


# --- Добавление праздничного/выходного дня (только Админ) ---
@router.post(
    "/",
    response_model=schemas.HolidayRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin_role)],
)
async def add_holiday(
    holiday_in: schemas.HolidayCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Добавляет новый праздничный/выходной день.
    Требует прав администратора.
    """
    logger.info(
        f"Admin {current_user.username} attempting to add holiday on {holiday_in.date} with name '{holiday_in.name}'"
    )

    existing = (
        db.query(models.Holiday).filter(models.Holiday.date == holiday_in.date).first()
    )
    if existing:
        logger.warning(
            f"Holiday on date {holiday_in.date} already exists (id: {existing.id})."
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A holiday or non-working day already exists for date {holiday_in.date}.",
        )

    db_holiday = models.Holiday(**holiday_in.dict())

    try:
        db.add(db_holiday)
        db.commit()
        db.refresh(db_holiday)
        logger.info(
            f"Holiday added successfully for date {db_holiday.date} (id: {db_holiday.id})."
        )
        return db_holiday
    except Exception as e:
        db.rollback()

        if (
            "unique constraint" in str(e).lower()
            and "holidays_date_key" in str(e).lower()
        ):
            logger.warning(
                f"Failed to add holiday on {holiday_in.date} due to existing entry (constraint violation)."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A holiday already exists for date {holiday_in.date}.",
            )
        else:
            logger.error(
                f"Database error adding holiday for date {holiday_in.date}: {e}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add holiday due to database error.",
            )


# --- Удаление праздничного/выходного дня по дате (только Админ) ---


@router.delete(
    "/by_date",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
)
async def delete_holiday_by_date(
    holiday_del: schemas.HolidayDelete,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Удаляет праздничный/выходной день по указанной дате.
    Требует прав администратора.
    """
    target_date = holiday_del.date
    logger.info(
        f"Admin {current_user.username} attempting to delete holiday on {target_date}"
    )
    try:
        stmt = delete(models.Holiday).where(models.Holiday.date == target_date)
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            logger.warning(
                f"Attempted to delete non-existent holiday for date {target_date}."
            )

            pass
        else:
            logger.info(f"Holiday for date {target_date} deleted successfully.")

    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error deleting holiday for date {target_date}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete holiday due to database error.",
        )
