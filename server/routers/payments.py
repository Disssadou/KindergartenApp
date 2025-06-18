from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import (
    Session,
    selectinload,
)
from sqlalchemy import Tuple, text
from typing import List, Annotated, Optional, Dict
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar
import logging


from database import (
    database,
    models,
    schemas,
)
from server.utils import security
from server.utils.encryption import (
    decrypt_data,
)


get_db = database.get_db
get_current_active_user = security.get_current_active_user
require_admin_role = security.require_admin_role


logger = logging.getLogger("KindergartenApp.routers.payments")


router = APIRouter()


# --- Массовый расчет и сохранение ежемесячных начислений ---
@router.post(
    "/charge-monthly",
    response_model=List[schemas.MonthlyChargeRead],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_admin_role)],
)
async def calculate_and_save_monthly_charges(
    payload: schemas.MonthlyChargeCalculationPayload,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """
    Рассчитывает и сохраняет/обновляет ежемесячные начисления за посещение
    для всех детей в указанной группе за указанный месяц/год.
    Учитывает посещаемость, праздники, выходные, индивидуальные ставки.
    """
    group_id = payload.group_id
    year = payload.year
    month = payload.month
    default_day_cost = Decimal(str(payload.default_day_cost)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    individual_rates_map: Dict[int, Decimal] = {
        rate.child_id: Decimal(str(rate.day_cost)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        for rate in payload.individual_rates
    }

    logger.info(
        f"Admin {current_user.username} initiating monthly charge calculation for group {group_id}, {month}/{year}. "
        f"Default day cost: {default_day_cost}, Individual rates count: {len(individual_rates_map)}"
    )

    # --- 1. Получение данных для расчета ---
    children_in_group = (
        db.query(models.Child)
        .filter(models.Child.group_id == group_id)
        .order_by(models.Child.id)
        .all()
    )

    if not children_in_group:
        logger.warning(
            f"No children found in group {group_id} for monthly charge calculation."
        )
        return []

    children_ids = [child.id for child in children_in_group]

    try:
        start_of_month = date(year, month, 1)
        days_in_month = calendar.monthrange(year, month)[1]
        end_of_month = date(year, month, days_in_month)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid year or month."
        )

    holidays_db = (
        db.query(models.Holiday.date)
        .filter(
            models.Holiday.date >= start_of_month, models.Holiday.date <= end_of_month
        )
        .all()
    )
    holiday_dates_set = {h_date for (h_date,) in holidays_db}

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

    result_monthly_charges: List[models.MonthlyCharge] = []

    try:
        for child in children_in_group:
            child_id = child.id
            # Получаем ФИО ребенка для деталей расчета (дешифруем)
            decrypted_child_name = (
                decrypt_data(child.full_name) if child.full_name else "Имя неизвестно"
            )

            child_day_cost = individual_rates_map.get(child_id, default_day_cost)
            payable_days_count = 0
            attended_days_details = []

            for day_num in range(1, days_in_month + 1):
                current_day_date = date(year, month, day_num)
                day_status = ""

                if current_day_date.weekday() >= 5:  # Сб, Вс
                    day_status = "Выходной"

                elif current_day_date in holiday_dates_set:
                    day_status = "Праздник"

                if not day_status:
                    attendance_record = attendance_map.get((child_id, current_day_date))
                    is_payable_day = False
                    if attendance_record:
                        if attendance_record.present:
                            is_payable_day = True
                            day_status = "Присутствовал (+)"
                        else:
                            day_status = f"Отсутствовал ({attendance_record.absence_type or 'не указано'})"
                            if attendance_record.absence_type not in [
                                models.AbsenceType.SICK_LEAVE,
                                models.AbsenceType.VACATION,
                            ]:
                                is_payable_day = True  #
                    else:
                        is_payable_day = True
                        day_status = "Отсутствовал (нет отметки)"

                    if is_payable_day:
                        payable_days_count += 1

                attended_days_details.append(f"{current_day_date.day}: {day_status}")

            amount_to_charge = (
                Decimal(str(payable_days_count)) * child_day_cost
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            calculation_details_str = (
                f"Ребенок: {decrypted_child_name}. "
                f"Оплачиваемых дней: {payable_days_count}. "
                f"Ставка за день: {child_day_cost:.2f} руб. "
                f"Итого к оплате: {amount_to_charge:.2f} руб. "
                f"Детали по дням: [{'; '.join(attended_days_details)}]"
            )

            logger.debug(
                f"Child {child_id} ({decrypted_child_name}): Payable days = {payable_days_count}, "
                f"Day cost = {child_day_cost}, Amount to charge = {amount_to_charge}"
            )

            # Ищем существующую запись MonthlyCharge или создаем новую
            db_monthly_charge = (
                db.query(models.MonthlyCharge)
                .filter(
                    models.MonthlyCharge.child_id == child_id,
                    models.MonthlyCharge.year == year,
                    models.MonthlyCharge.month == month,
                )
                .first()
            )

            if db_monthly_charge:
                db_monthly_charge.amount_due = amount_to_charge
                db_monthly_charge.calculation_details = calculation_details_str
                db_monthly_charge.calculated_at = datetime.now(timezone.utc)
                logger.info(
                    f"Updating MonthlyCharge for child {child_id} for {month}/{year}."
                )
            else:
                db_monthly_charge = models.MonthlyCharge(
                    child_id=child_id,
                    year=year,
                    month=month,
                    amount_due=amount_to_charge,
                    calculation_details=calculation_details_str,
                )
                db.add(db_monthly_charge)
                logger.info(
                    f"Creating new MonthlyCharge for child {child_id} for {month}/{year}."
                )

            result_monthly_charges.append(db_monthly_charge)

        db.commit()
        for charge in result_monthly_charges:
            db.refresh(charge)
            if charge.child:
                db.refresh(charge.child)

        logger.info(
            f"Monthly charges calculation and saving complete for group {group_id}, {month}/{year}. "
            f"Processed {len(result_monthly_charges)} children."
        )

        return [
            schemas.MonthlyChargeRead.model_validate(charge)
            for charge in result_monthly_charges
        ]

    except Exception as e:
        db.rollback()
        logger.error(
            f"Error during monthly charge calculation for group {group_id}, {month}/{year}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process monthly charges: {e}",
        )


# --- Получение истории начислений для ребенка ---
@router.get(
    "/children/{child_id}/monthly-charges",
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


# --- Получение начислений по группе за месяц/год ---
@router.get(
    "/groups/{group_id}/monthly-charges",
    response_model=List[schemas.MonthlyChargeRead],
    dependencies=[Depends(require_admin_role)],
)
async def get_monthly_charges_for_group(
    group_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
    year: int = Query(..., description="Год начислений"),
    month: int = Query(..., ge=1, le=12, description="Месяц начислений"),
):
    """
    Возвращает все ежемесячные начисления для детей указанной группы за заданный год и месяц.
    Доступно только администраторам.
    """
    logger.info(
        f"Admin '{current_user.username}' requesting monthly charges for group {group_id}, {month}/{year}."
    )

    children_ids_in_group = (
        db.query(models.Child.id).filter(models.Child.group_id == group_id).all()
    )
    children_ids = [cid[0] for cid in children_ids_in_group]

    if not children_ids:
        return []

    charges = (
        db.query(models.MonthlyCharge)
        .filter(
            models.MonthlyCharge.child_id.in_(children_ids),
            models.MonthlyCharge.year == year,
            models.MonthlyCharge.month == month,
        )
        .options(selectinload(models.MonthlyCharge.child))
        .order_by(models.MonthlyCharge.child_id)
        .all()
    )

    response_charges = []
    for charge in charges:
        child_simple = None
        if charge.child:
            decrypted_child_name = decrypt_data(charge.child.full_name)
            child_simple = schemas.ChildSimple(
                id=charge.child.id, full_name=decrypted_child_name
            )

        charge_read = schemas.MonthlyChargeRead.model_validate(charge)
        charge_read.child = child_simple
        response_charges.append(charge_read)

    return response_charges
