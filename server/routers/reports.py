from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func, extract
from typing import List, Annotated, Optional, Dict, Any, Tuple
from datetime import date, timedelta
import calendar
import logging
from fastapi.responses import StreamingResponse
import io
import os


from database import database, models, schemas
from server.utils import security
from server.utils.encryption import decrypt_data


try:
    from utils.report_generator import (
        generate_attendance_excel_from_template,
        OPENPYXL_AVAILABLE,
    )
except ImportError as e_gen:
    print(f"ERROR importing report_generator: {e_gen}")
    OPENPYXL_AVAILABLE = False

    def generate_attendance_excel_from_template(*args, **kwargs):
        raise ImportError("report_generator module or its dependencies not found")


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_teacher_or_admin_role = security.require_teacher_or_admin_role

logger = logging.getLogger("KindergartenApp.routers.reports")
router = APIRouter()

# --- Определение пути к файлу шаблона ---
try:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    TEMPLATE_FILENAME = "template_attendance_report.xlsx"
    ATTENDANCE_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, TEMPLATE_FILENAME)

    if not os.path.exists(ATTENDANCE_TEMPLATE_PATH):
        logger.error(f"CRITICAL: Template file not found at {ATTENDANCE_TEMPLATE_PATH}")
        ATTENDANCE_TEMPLATE_PATH = None
except Exception as e_path:
    logger.error(f"CRITICAL: Error defining template path: {e_path}")
    ATTENDANCE_TEMPLATE_PATH = None


# --- Эндпоинт для получения данных отчета посещаемости (GET) ---
@router.get(
    "/attendance/data",
    response_model=schemas.AttendanceReportData,
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def get_attendance_report_data_endpoint(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    group_id: int = Query(..., ge=1, description="ID группы"),
    year: int = Query(..., ge=2020, le=date.today().year + 5, description="Год отчета"),
    month: int = Query(..., ge=1, le=12, description="Месяц отчета (1-12)"),
) -> schemas.AttendanceReportData:
    """Собирает и обрабатывает данные для формирования табеля посещаемости."""
    logger.info(
        f"User {current_user.username} requesting attendance report data for group {group_id}, {month}/{year}."
    )

    # --- 1. Получение данных группы и проверка прав ---
    group = (
        db.query(models.Group)
        .options(selectinload(models.Group.teacher))
        .filter(models.Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found."
        )
    if (
        current_user.role == models.UserRole.TEACHER
        and group.teacher_id != current_user.id
    ):
        logger.warning(
            f"Teacher {current_user.username} tried to access report for group {group_id} not assigned to them."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this group.",
        )
    teacher_name_decrypted = None
    if group.teacher and group.teacher.full_name:
        teacher_name_decrypted = decrypt_data(group.teacher.full_name)

    if teacher_name_decrypted == "[Ошибка дешифровки]":
        teacher_name_decrypted = "Ошибка имени учителя"

    # --- 2. Получение списка детей группы ---
    children_list = (
        db.query(models.Child)
        .filter(models.Child.group_id == group_id)
        .order_by(models.Child.full_name)
        .all()
    )
    logger.debug(
        f"For report: Found {len(children_list)} children in group {group_id}: {[c.full_name for c in children_list]}"
    )

    # Определяем количество дней в месяце
    try:
        days_in_month = calendar.monthrange(year, month)[1]
    except calendar.IllegalMonthError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid month provided."
        )

    # Если детей нет, возвращаем базовую структуру
    if not children_list:
        logger.warning(
            f"No children found in group {group_id} for report. Returning empty data."
        )
        empty_daily_totals = {str(d): 0 for d in range(1, 32)}
        total_work_days_in_month_empty = 0
        empty_holiday_dates_set = set()
        try:
            start_of_month_empty = date(year, month, 1)
            end_of_month_empty = date(year, month, days_in_month)
            holidays_db_empty = (
                db.query(models.Holiday)
                .filter(
                    models.Holiday.date >= start_of_month_empty,
                    models.Holiday.date <= end_of_month_empty,
                )
                .all()
            )
            empty_holiday_dates_set = {h.date for h in holidays_db_empty}
            for day_num_calc in range(1, days_in_month + 1):
                current_date_calc = date(year, month, day_num_calc)
                if (
                    current_date_calc.weekday() < 5
                    and current_date_calc not in empty_holiday_dates_set
                ):
                    total_work_days_in_month_empty += 1
        except Exception as e_calc_empty:
            logger.error(
                f"Error calculating workdays/holidays for empty report: {e_calc_empty}"
            )

        return schemas.AttendanceReportData(
            year=year,
            month=month,
            days_in_month=days_in_month,
            group_id=group_id,
            group_name=group.name,
            group_description=group.description,
            teacher_name=teacher_name_decrypted,
            children_data=[],
            holiday_dates=sorted(list(empty_holiday_dates_set)),
            daily_totals=empty_daily_totals,
            total_work_days=total_work_days_in_month_empty,
        )
    children_ids = [child.id for child in children_list]

    # --- 3. Получение данных посещаемости за месяц ---
    start_of_month = date(year, month, 1)
    end_of_month = date(year, month, days_in_month)
    attendance_records_db = (
        db.query(models.Attendance)
        .filter(
            models.Attendance.child_id.in_(children_ids),
            models.Attendance.date >= start_of_month,
            models.Attendance.date <= end_of_month,
        )
        .all()
    )
    attendance_map: Dict[Tuple[int, date], models.Attendance] = {
        (rec.child_id, rec.date): rec for rec in attendance_records_db
    }
    logger.debug(
        f"For report: Attendance map created with {len(attendance_map)} entries."
    )

    # --- 4. Получение праздников за месяц ---
    holidays_db = (
        db.query(models.Holiday)
        .filter(
            models.Holiday.date >= start_of_month, models.Holiday.date <= end_of_month
        )
        .all()
    )
    holiday_dates_set = {h.date for h in holidays_db}

    report_children_data: List[schemas.AttendanceReportChildData] = []

    daily_totals: Dict[str, int] = {str(day): 0 for day in range(1, 32)}
    logger.debug(f"Initialized daily_totals with keys: {list(daily_totals.keys())}")

    total_work_days_in_month = 0
    for day_num_calc in range(1, days_in_month + 1):
        try:
            current_date_calc = date(year, month, day_num_calc)
            if (
                current_date_calc.weekday() < 5
                and current_date_calc not in holiday_dates_set
            ):
                total_work_days_in_month += 1
        except ValueError:
            continue

    for child in children_list:
        decrypted_child_name = decrypt_data(child.full_name)
        if decrypted_child_name == "[Ошибка дешифровки]":
            decrypted_child_name = f"Ребенок ID {child.id} (ошибка имени)"

        child_report_data = schemas.AttendanceReportChildData(
            child_id=child.id, child_name=decrypted_child_name
        )
        summary = schemas.AttendanceReportChildSummary()

        current_child_days_data: Dict[str, schemas.AttendanceReportDayRecord] = {}

        for day_num in range(1, 32):
            mark = "х"
            is_holiday = False
            is_weekend = False
            day_str = str(day_num)

            if day_num <= days_in_month:
                current_date = date(year, month, day_num)
                weekday = current_date.weekday()
                is_holiday = current_date in holiday_dates_set
                is_weekend = weekday >= 5

                if is_holiday or is_weekend:
                    mark = ""
                else:
                    attendance_record = attendance_map.get((child.id, current_date))
                    if attendance_record:
                        if attendance_record.present:
                            mark = "+"
                            summary.present_days += 1

                            daily_totals[day_str] = daily_totals.get(day_str, 0) + 1
                        else:
                            absence_type_to_use = attendance_record.absence_type
                            if (
                                not absence_type_to_use
                                and attendance_record.absence_reason
                            ):
                                absence_type_to_use = security.determine_absence_type(
                                    attendance_record.absence_reason
                                )

                            if absence_type_to_use == models.AbsenceType.SICK_LEAVE:
                                mark = "б"
                                summary.absent_sick_days += 1
                            elif absence_type_to_use == models.AbsenceType.VACATION:
                                mark = "о"
                                summary.absent_vacation_days += 1
                            else:
                                mark = "н"
                                summary.absent_other_days += 1
                    else:
                        mark = "н"
                        summary.absent_other_days += 1

            current_child_days_data[day_str] = schemas.AttendanceReportDayRecord(
                mark=mark, is_weekend=is_weekend, is_holiday=is_holiday
            )

        child_report_data.days = current_child_days_data
        summary.payable_days = summary.present_days + summary.absent_other_days
        child_report_data.summary = summary
        logger.debug(
            f"Prepared child_report_data for {child.full_name}: Days count = {len(child_report_data.days)}, Present = {summary.present_days}"
        )
        report_children_data.append(child_report_data)

    logger.debug(f"Final daily_totals BEFORE creating response object: {daily_totals}")
    logger.debug(f"Final children_data count: {len(report_children_data)}")
    if report_children_data:
        logger.debug(
            f"First child data in final response: {report_children_data[0].model_dump_json(indent=2)}"
        )

    return schemas.AttendanceReportData(
        year=year,
        month=month,
        days_in_month=days_in_month,
        group_id=group_id,
        group_name=group.name,
        group_description=group.description,
        teacher_name=teacher_name_decrypted,
        holiday_dates=sorted(list(holiday_dates_set)),
        children_data=report_children_data,
        daily_totals=daily_totals,
        total_work_days=total_work_days_in_month,
    )


# --- Эндпоинт для генерации и скачивания Excel отчета ---
@router.post(
    "/attendance",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            },
            "description": "XLSX report.",
        },
        403: {"description": "Forbidden"},
        404: {"description": "Group not found"},
        500: {"description": "Server error generating report"},
        501: {"description": "Excel library not available"},
    },
    dependencies=[Depends(require_teacher_or_admin_role)],
)
async def download_attendance_report(
    report_params: schemas.AttendanceReportParams,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """Формирует и возвращает табель посещаемости в формате XLSX."""
    if not OPENPYXL_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Excel generation library (openpyxl) is not installed on the server.",
        )
    if ATTENDANCE_TEMPLATE_PATH is None or not os.path.exists(ATTENDANCE_TEMPLATE_PATH):
        logger.error(
            f"Attendance report template not found at {ATTENDANCE_TEMPLATE_PATH}"
        )
        raise HTTPException(
            status_code=500, detail="Report template file is missing on the server."
        )

    logger.info(
        f"User {current_user.username} requested Excel attendance report for group {report_params.group_id}, {report_params.month}/{report_params.year}."
    )
    try:
        # 1. Получаем данные для отчета
        report_data_pydantic = await get_attendance_report_data_endpoint(
            db=db,
            current_user=current_user,
            group_id=report_params.group_id,
            year=report_params.year,
            month=report_params.month,
        )
        report_data_dict = report_data_pydantic.model_dump()

        # 2. Создаем поток в памяти
        excel_stream = io.BytesIO()

        # 3. Генерируем Excel
        generate_attendance_excel_from_template(
            report_data=report_data_dict,
            staff_rates=report_params.staff_rates or {},
            default_rate=report_params.default_rate,
            template_path=ATTENDANCE_TEMPLATE_PATH,
            output_stream=excel_stream,
        )
        excel_stream.seek(0)

        # 4. Формируем имя файла и заголовки
        group_name_safe = (
            report_data_dict.get("group_name", "group")
            .replace('"', "'")
            .replace(" ", "_")
        )
        file_name = f"Табель_{group_name_safe}_{report_params.year}_{report_params.month:02d}.xlsx"
        from urllib.parse import quote

        encoded_filename = quote(file_name)
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

        return StreamingResponse(
            content=excel_stream,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": content_disposition},
        )
    except HTTPException as he:  # Перехватываем HTTP ошибки из get_data
        raise he
    except ImportError as e_imp:  # Ошибка импорта openpyxl
        logger.error(f"Import error during report generation: {e_imp}")
        raise HTTPException(
            status_code=501,
            detail=f"Report generation failed due to missing library: {e_imp}",
        )
    except Exception as e_gen:
        logger.exception(
            f"Failed to generate or stream attendance report for group {report_params.group_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {e_gen}",
        )
