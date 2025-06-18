print("--- Loading server/routers/menus.py ---")
try:
    from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
    from sqlalchemy.orm import Session
    from sqlalchemy import delete

    from typing import List, Annotated, Optional
    from datetime import date
    import logging

    print("FastAPI, SQLAlchemy, Typing imports successful.")
    imports_ok = True
except ImportError as e:
    print(f"!!! FAILED TO IMPORT base modules in menus.py: {e}")
    imports_ok = False
    raise e from e
except Exception as e:
    print(f"!!! UNEXPECTED ERROR during base imports in menus.py: {e}")
    imports_ok = False
    raise e from e

try:

    from database import database, models, schemas

    from server.utils import security

    print("Project imports successful.")
    project_imports_ok = True
except ImportError as e:
    print(f"!!! FAILED TO IMPORT project modules in menus.py: {e}")
    project_imports_ok = False
    raise e from e
except Exception as e:
    print(f"!!! UNEXPECTED ERROR during project imports in menus.py: {e}")
    project_imports_ok = False
    raise e from e


logger = logging.getLogger("KindergartenApp.routers.menus")


router = APIRouter()

# --- Вспомогательные зависимости ---
if imports_ok and project_imports_ok:
    try:
        get_db = database.get_db
        get_current_active_user = security.get_current_active_user
        require_admin_role = security.require_admin_role
        print("Dependencies assigned successfully.")
        dependencies_ok = True
    except AttributeError as e:
        print(f"!!! AttributeError assigning dependencies in menus.py: {e}")
        dependencies_ok = False
        raise AttributeError(f"Failed to assign dependencies: {e}") from e
    except Exception as e:
        print(f"!!! UNEXPECTED ERROR assigning dependencies in menus.py: {e}")
        dependencies_ok = False
        raise e from e
else:
    raise ImportError("Could not complete necessary imports for menus router.")


# --- Эндпоинт POST /  ---
@router.post(
    "/",
    response_model=schemas.MealMenuRead,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Menu entry updated successfully",
            "model": schemas.MealMenuRead,
        },
        201: {
            "description": "Menu entry created successfully",
            "model": schemas.MealMenuRead,
        },
        204: {"description": "Menu entry deleted successfully (empty description)"},
        400: {"description": "Bad Request"},
        403: {"description": "Forbidden"},
        404: {"description": "Not Found"},
    },
    dependencies=[Depends(require_admin_role)],
)
async def create_or_update_meal_menu(
    menu_data: schemas.MealMenuCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_active_user)],
):
    """Создает или обновляет запись меню. Если описание пустое, удаляет запись."""
    logger.debug(
        f"POST /api/menus called with data: date={menu_data.date}, type={menu_data.meal_type}, desc_len={len(menu_data.description or '')}"
    )
    db_menu = (
        db.query(models.MealMenu)
        .filter(
            models.MealMenu.date == menu_data.date,
            models.MealMenu.meal_type == menu_data.meal_type.value,
        )
        .with_for_update()
        .first()
    )

    if not menu_data.description or menu_data.description.strip() == "":
        if db_menu:
            logger.info(
                f"Deleting existing meal menu entry id={db_menu.id} due to empty description."
            )
            db.delete(db_menu)
            db.commit()
            response.status_code = status.HTTP_204_NO_CONTENT
            return response
        else:
            logger.info(
                f"No meal menu entry found for {menu_data.date} ({menu_data.meal_type.value}) to delete."
            )
            response.status_code = status.HTTP_204_NO_CONTENT
            return response

    action = ""
    if db_menu:
        db_menu.description = menu_data.description
        db_menu.created_by = current_user.id
        response.status_code = status.HTTP_200_OK
        action = "updated"
    else:
        db_menu = models.MealMenu(
            date=menu_data.date,
            meal_type=menu_data.meal_type.value,
            description=menu_data.description,
            created_by=current_user.id,
        )
        response.status_code = status.HTTP_201_CREATED
        action = "created"
    try:
        db.add(db_menu)
        db.commit()
        db.refresh(db_menu)
        logger.info(
            f"Meal menu entry for {menu_data.date} ({menu_data.meal_type.value}) {action} successfully by user {current_user.username}. ID: {db_menu.id}"
        )
        return db_menu
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error during meal menu upsert (action: {action}): {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save meal menu entry due to database error.",
        )


# --- Эндпоинт GET / ---
@router.get("/", response_model=List[schemas.MealMenuRead])
async def read_meal_menus(
    db: Annotated[Session, Depends(get_db)],
    start_date: date = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Конечная дата (YYYY-MM-DD)"),
):
    """
    Возвращает список записей меню за указанный диапазон дат (включительно).
    """
    logger.debug(
        f"GET /api/menus called with start_date={start_date}, end_date={end_date}"
    )
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date cannot be after end date.",
        )

    try:
        menus = (
            db.query(models.MealMenu)
            .filter(
                models.MealMenu.date >= start_date, models.MealMenu.date <= end_date
            )
            .order_by(models.MealMenu.date, models.MealMenu.meal_type)
            .all()
        )
        return menus
    except Exception as e:
        logger.error(f"Database error reading meal menus: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve meal menus due to database error.",
        )


print(f"--- Finished loading server/routers/menus.py ---")


# --- DELETE /{menu_id}  ---
@router.delete(
    "/{menu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_role)],
)
async def delete_meal_menu(
    menu_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Удаляет запись меню по ее ID. Доступно только администраторам."""
    try:

        stmt = delete(models.MealMenu).where(models.MealMenu.id == menu_id)
        result = db.execute(stmt)
        db.commit()

        if result.rowcount == 0:
            logger.warning(
                f"Attempted to delete non-existent meal menu entry with id {menu_id}."
            )

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meal menu entry not found",
            )
        else:
            logger.info(f"Meal menu entry with id {menu_id} deleted successfully.")

    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error deleting meal menu entry id {menu_id}: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete meal menu entry due to database error.",
        )
