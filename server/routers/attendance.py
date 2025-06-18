from fastapi import APIRouter, Depends, HTTPException, status, Query, Body, logger
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, delete  # Добавили or_
from typing import List, Annotated, Optional, Dict
from datetime import date
import logging


from database import database, models, schemas
from server.utils import security
from database.schemas import BulkAttendanceItem
from server.utils.encryption import decrypt_data

# Получаем нужные зависимости
get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role
require_teacher_or_admin_role = security.require_teacher_or_admin_role

logger = logging.getLogger("KindergartenApp.routers.attendance")

router = APIRouter()


# --- Получение записей посещаемости (GET /) ---
@router.get("/", response_model=List[schemas.AttendanceRead])
async def read_attendance_records(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    attendance_date: date = Query(..., description="Дата посещаемости (YYYY-MM-DD)"),
    group_id: Optional[int] = Query(None, description="Фильтр по ID группы", ge=1),
    child_id: Optional[int] = Query(None, description="Фильтр по ID ребенка", ge=1),
):

    logger.debug(f"User {current_user.username} requests attendance...")

    stmt = (
        select(models.Attendance)
        .options(selectinload(models.Attendance.child).selectinload(models.Child.group))
        .where(models.Attendance.date == attendance_date)
    )

    if child_id is not None:

        stmt = stmt.where(models.Attendance.child_id == child_id)
    elif group_id is not None:

        stmt = stmt.where(
            select(models.Child.id)
            .where(models.Child.id == models.Attendance.child_id)
            .where(models.Child.group_id == group_id)
            .exists()
        )

    if current_user.role == models.UserRole.TEACHER:

        teacher_group_ids_result = db.execute(
            select(models.Group.id).where(models.Group.teacher_id == current_user.id)
        )
        teacher_group_ids = teacher_group_ids_result.scalars().all()

        if not teacher_group_ids:
            security.logger.debug(
                f"Teacher {current_user.username} has no assigned groups."
            )
            return []

        if group_id is not None and group_id not in teacher_group_ids:
            security.logger.warning(
                f"Teacher {current_user.username} requested group {group_id}, but it's not assigned to them."
            )

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view attendance for this group",
            )

        if child_id is None:

            stmt = stmt.where(
                select(models.Child.id)
                .where(models.Child.id == models.Attendance.child_id)
                .where(models.Child.group_id.in_(teacher_group_ids))
                .exists()
            )

    elif current_user.role == models.UserRole.PARENT:

        parent_child_ids_result = db.execute(
            select(models.ChildParent.child_id).where(
                models.ChildParent.parent_id == current_user.id
            )
        )
        parent_child_ids = parent_child_ids_result.scalars().all()

        if not parent_child_ids:
            security.logger.debug(
                f"Parent {current_user.username} has no associated children."
            )
            return []

        if child_id is not None and child_id not in parent_child_ids:
            security.logger.warning(
                f"Parent {current_user.username} requested child {child_id}, but it's not theirs."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view attendance for this child",
            )

        if child_id is None:
            stmt = stmt.where(models.Attendance.child_id.in_(parent_child_ids))

    try:
        stmt = stmt.order_by(models.Attendance.id)
        result = db.execute(stmt)
        attendance_records_db = result.scalars().unique().all()

        # --- ДЕШИФРОВКА И ФОРМИРОВАНИЕ ОТВЕТА ---
        response_data: List[schemas.AttendanceRead] = []
        for record_db in attendance_records_db:
            child_simple_dto = None
            if record_db.child:
                decrypted_child_name = decrypt_data(record_db.child.full_name)
                if decrypted_child_name == "[Ошибка дешифровки]":
                    decrypted_child_name = (
                        f"Ребенок ID {record_db.child.id} (ошибка имени)"
                    )

                child_simple_dto = schemas.ChildSimple(
                    id=record_db.child.id,
                    full_name=decrypted_child_name,
                    last_charge_amount=None,
                    last_charge_year=None,
                    last_charge_month=None,
                )

            attendance_read_dto = schemas.AttendanceRead(
                id=record_db.id,
                child_id=record_db.child_id,
                date=record_db.date,
                present=record_db.present,
                absence_reason=record_db.absence_reason,
                absence_type=record_db.absence_type,
                created_by=record_db.created_by,
                created_at=record_db.created_at,
                child=child_simple_dto,
            )
            response_data.append(attendance_read_dto)

        return response_data
    except Exception as e:

        logger.error(f"Database error reading attendance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attendance records due to database error.",
        )


# --- Вспомогательная функция для определения типа отсутствия ---
def determine_absence_type(reason: Optional[str]) -> Optional[models.AbsenceType]:
    """Определяет тип отсутствия по тексту причины."""
    if not reason:
        return None
    reason_lower = reason.lower()

    if any(keyword in reason_lower for keyword in ["бол", "забол", "sick"]):
        return models.AbsenceType.SICK_LEAVE
    if any(keyword in reason_lower for keyword in ["отпуск", "отдых", "vacation"]):
        return models.AbsenceType.VACATION

    if reason_lower in [at.value for at in models.AbsenceType]:
        try:
            return models.AbsenceType(reason_lower)
        except ValueError:
            return models.AbsenceType.OTHER

    return models.AbsenceType.OTHER


# --- Создание новой записи посещаемости (только Админ) ---
@router.post(
    "/",
    response_model=schemas.AttendanceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def create_attendance_record(
    attendance_in: schemas.AttendanceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Создает новую запись о посещаемости. Доступно только администраторам и воспитателям (только для детей из своей группы).
    """

    child = (
        db.query(models.Child).filter(models.Child.id == attendance_in.child_id).first()
    )
    if not child:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Child with id {attendance_in.child_id} not found.",
        )

    if current_user.role == models.UserRole.TEACHER:

        teacher_group_ids_result = db.execute(
            select(models.Group.id).where(models.Group.teacher_id == current_user.id)
        )
        teacher_group_ids = teacher_group_ids_result.scalars().all()
        if child.group_id not in teacher_group_ids:
            logger.warning(
                f"Teacher {current_user.username} attempt to create attendance for child {child.id} not in their groups."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create attendance for this child",
            )

    existing_record = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.date == attendance_in.date,
            models.Attendance.child_id == attendance_in.child_id,
        )
        .first()
    )
    if existing_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance record already exists for child {attendance_in.child_id} on date {attendance_in.date}.",
        )

    is_present = attendance_in.present
    absence_reason = attendance_in.absence_reason if not is_present else None

    absence_type = None
    if not is_present:
        if attendance_in.absence_type:
            absence_type = attendance_in.absence_type
        else:
            absence_type = determine_absence_type(absence_reason)

    db_attendance = models.Attendance(
        child_id=attendance_in.child_id,
        date=attendance_in.date,
        present=is_present,
        absence_reason=absence_reason,
        absence_type=absence_type,
        created_by=current_user.id,
    )

    try:
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)

        db.refresh(db_attendance, ["child"])
        logger.info(
            f"User {current_user.username} created attendance record id={db_attendance.id}..."
        )
        return db_attendance
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating attendance record: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create attendance record due to database error.",
        )


# --- Обновление существующей записи посещаемости (только Админ) ---
@router.put(
    "/{attendance_id}",
    response_model=schemas.AttendanceRead,
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def update_attendance_record(
    attendance_id: int,
    attendance_in: schemas.AttendanceUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Обновляет существующую запись посещаемости (статус или причину).
    Доступно только администраторам и воспитателям (только для записи ребенка из своей группы).
    """

    db_attendance = (
        db.query(models.Attendance)
        .options(selectinload(models.Attendance.child))
        .filter(models.Attendance.id == attendance_id)
        .first()
    )

    if db_attendance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found"
        )

    if current_user.role == models.UserRole.TEACHER:

        if not db_attendance.child:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Child associated with this attendance record not found",
            )
        teacher_group_ids_result = db.execute(
            select(models.Group.id).where(models.Group.teacher_id == current_user.id)
        )
        teacher_group_ids = teacher_group_ids_result.scalars().all()
        if db_attendance.child.group_id not in teacher_group_ids:
            logger.warning(
                f"Teacher {current_user.username} attempt to update attendance for child ..."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update attendance for this child",
            )

    update_data = attendance_in.model_dump(exclude_unset=True)
    if not update_data:
        return db_attendance

    updated_fields = []
    new_present = update_data.get("present", db_attendance.present)
    new_reason = update_data.get("absence_reason", db_attendance.absence_reason)
    new_type = update_data.get("absence_type", db_attendance.absence_type)

    if db_attendance.present != new_present:
        db_attendance.present = new_present
        updated_fields.append("present")

    current_reason = None
    current_type = None
    if not db_attendance.present:
        if "absence_type" in update_data:
            current_type = new_type
            if db_attendance.absence_type != current_type:
                db_attendance.absence_type = current_type
                updated_fields.append("absence_type")

        elif "absence_reason" in update_data:
            current_type = determine_absence_type(new_reason)
            if db_attendance.absence_type != current_type:
                db_attendance.absence_type = current_type
                updated_fields.append("absence_type")
        else:
            current_type = db_attendance.absence_type

        if "absence_reason" in update_data:
            current_reason = new_reason
            if db_attendance.absence_reason != current_reason:
                db_attendance.absence_reason = current_reason
                updated_fields.append("absence_reason")
        else:
            current_reason = db_attendance.absence_reason

    if db_attendance.present:
        if db_attendance.absence_reason is not None:
            db_attendance.absence_reason = None
            updated_fields.append("absence_reason (cleared)")
        if db_attendance.absence_type is not None:
            db_attendance.absence_type = None
            updated_fields.append("absence_type (cleared)")

    try:
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)

        db.refresh(db_attendance, ["child"])
        logger.info(
            f"User {current_user.username} updated attendance record id={attendance_id}..."
        )
        return db_attendance
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error updating attendance record id={attendance_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update attendance record due to database error.",
        )


# --- Удаление записи посещаемости (только Админ) ---
@router.delete(
    "/{attendance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
)
async def delete_attendance_record(
    attendance_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Удаляет запись посещаемости по ID.
    Требует прав администратора.
    """
    try:

        stmt = delete(models.Attendance).where(models.Attendance.id == attendance_id)
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found",
            )
        else:

            logger.info(
                f"Admin '{current_user.username}' deleted attendance record with id {attendance_id}."
            )
            # Статус 204 будет возвращен автоматически, т.к. функция ничего не возвращает
    except HTTPException:
        db.rollback()  # Откатываем, если была ошибка 404 (хотя commit уже мог быть)
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error deleting attendance record id {attendance_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attendance record due to database error.",
        )


# --- Массовая отметка посещаемости ---
@router.post(
    "/bulk",
    response_model=List[schemas.AttendanceRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def create_or_update_bulk_attendance(
    bulk_data: schemas.BulkAttendanceCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Создает или обновляет записи посещаемости для ВСЕХ детей указанной группы
    на указанную дату на основе переданного списка.
    Если ребенок из группы отсутствует в списке `attendance_list`, он будет
    отмечен как ОТСУТСТВУЮЩИЙ (present=False).
    Доступно администраторам и воспитателям (для своих групп).
    """
    group_id = bulk_data.group_id
    attendance_date = bulk_data.date
    attendance_map: Dict[int, BulkAttendanceItem] = {
        item.child_id: item for item in bulk_data.attendance_list
    }

    logger.info(
        f"User {current_user.username} submitting bulk attendance for group {group_id} on {attendance_date}. Provided for {len(attendance_map)} children."
    )

    # --- Проверка прав доступа и существования группы ---
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with id {group_id} not found.",
        )

    if current_user.role == models.UserRole.TEACHER:

        teacher_group_ids_result = db.execute(
            select(models.Group.id).where(models.Group.teacher_id == current_user.id)
        )
        teacher_group_ids = teacher_group_ids_result.scalars().all()
        if group_id not in teacher_group_ids:
            logger.warning(
                f"Teacher {current_user.username} attempt to bulk update attendance for group {group_id} not assigned to them."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to manage attendance for this group",
            )

    # --- Получаем ВСЕХ детей в этой группе ---
    children_in_group = (
        db.query(models.Child).filter(models.Child.group_id == group_id).all()
    )
    if not children_in_group:
        logger.warning(
            f"No children found in group {group_id}. Skipping bulk attendance."
        )
        return []

    # --- Получаем СУЩЕСТВУЮЩИЕ записи посещаемости на эту дату для этой группы ---
    existing_records_map: Dict[int, models.Attendance] = {
        rec.child_id: rec
        for rec in db.query(models.Attendance)
        .filter(
            models.Attendance.date == attendance_date,
            models.Attendance.child_id.in_([child.id for child in children_in_group]),
        )
        .all()
    }
    logger.debug(
        f"Found {len(existing_records_map)} existing records for group {group_id} on {attendance_date}."
    )

    processed_records: List[models.Attendance] = []

    # --- Обрабатываем КАЖДОГО ребенка из группы ---
    try:
        for child_from_group in children_in_group:
            current_child_id = child_from_group.id

            child_attendance_data_from_request: Optional[schemas.BulkAttendanceItem] = (
                attendance_map.get(current_child_id)
            )

            is_present_final: bool
            absence_reason_final: Optional[str] = None
            absence_type_final: Optional[models.AbsenceType] = None

            if child_attendance_data_from_request:

                is_present_final = child_attendance_data_from_request.present
                if not is_present_final:
                    absence_reason_final = (
                        child_attendance_data_from_request.absence_reason
                    )

                    if child_attendance_data_from_request.absence_type is not None:

                        absence_type_final = (
                            child_attendance_data_from_request.absence_type
                        )
                    elif absence_reason_final:

                        absence_type_final = determine_absence_type(
                            absence_reason_final
                        )
                    else:

                        absence_type_final = models.AbsenceType.OTHER
            else:

                is_present_final = False
                absence_reason_final = "Не отмечен (авто)"
                absence_type_final = models.AbsenceType.OTHER

            db_attendance = existing_records_map.get(current_child_id)

            if db_attendance:
                changed = False
                if db_attendance.present != is_present_final:
                    db_attendance.present = is_present_final
                    changed = True

                if not is_present_final:
                    if db_attendance.absence_reason != absence_reason_final:
                        db_attendance.absence_reason = absence_reason_final
                        changed = True

                    if db_attendance.absence_type != absence_type_final:
                        db_attendance.absence_type = absence_type_final
                        changed = True
                elif is_present_final:
                    if db_attendance.absence_reason is not None:
                        db_attendance.absence_reason = None
                        changed = True
                    if db_attendance.absence_type is not None:
                        db_attendance.absence_type = None
                        changed = True

                if changed:
                    db_attendance.created_by = current_user.id
                    db.add(db_attendance)
                processed_records.append(db_attendance)
            else:
                db_attendance = models.Attendance(
                    child_id=current_child_id,
                    date=attendance_date,
                    present=is_present_final,
                    absence_reason=absence_reason_final,
                    absence_type=absence_type_final,
                    created_by=current_user.id,
                )
                db.add(db_attendance)
                processed_records.append(db_attendance)

        # --- Коммитим все изменения разом ---
        if processed_records:
            db.commit()
            logger.info(
                f"Bulk attendance processed for group {group_id} on {attendance_date}. Processed {len(processed_records)} records for DB."
            )

            refreshed_records = []
            for record_to_refresh in processed_records:
                try:
                    db.refresh(record_to_refresh)
                    if hasattr(record_to_refresh, "child"):
                        db.refresh(record_to_refresh, ["child"])
                    refreshed_records.append(record_to_refresh)
                except Exception as refresh_exc:
                    logger.error(
                        f"Failed to refresh attendance record id={record_to_refresh.id if hasattr(record_to_refresh, 'id') else 'N/A'}: {refresh_exc}"
                    )
                    refreshed_records.append(record_to_refresh)
            return refreshed_records
        else:
            logger.info(
                f"No records were processed or changed for group {group_id} on {attendance_date}."
            )
            return []

    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error during bulk attendance processing for group {group_id} on {attendance_date}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk attendance due to database error.",
        )
