import logging
from typing import List, Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, selectinload

from database import database, models, schemas
from database.models import NotificationAudience
from server.utils import security

logger = logging.getLogger("KindergartenApp.routers.notifications")
router = APIRouter()
get_db = database.get_db

# --- Эндпоинты для Уведомлений/Событий ---


@router.post(
    "/",
    response_model=schemas.NotificationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(security.require_admin_role)],
)
async def create_notification(
    notification_in: schemas.NotificationCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Создает новое общее уведомление или событие.
    """
    logger.info(
        f"User '{current_user.username}' attempting to create a notification/event."
    )

    if notification_in.is_event and not notification_in.event_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="event_date is required if is_event is true.",
        )
    if not notification_in.is_event and notification_in.event_date is not None:

        logger.warning(
            "event_date provided but is_event is false. event_date will be ignored or cleared."
        )

    db_notification = models.Notification(
        **notification_in.model_dump(),
        author_id=current_user.id,
    )

    try:
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)

        logger.info(
            f"Notification/Event id={db_notification.id} titled '{db_notification.title}' created by '{current_user.username}'."
        )
        return db_notification
    except Exception as e:
        db.rollback()
        logger.error(f"Database error creating notification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create notification/event due to a database error.",
        )


@router.get("/", response_model=List[schemas.NotificationRead])
async def read_notifications(
    db: Annotated[Session, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    audience: Optional[NotificationAudience] = Query(
        None, description="Filter by target audience"
    ),
    is_event: Optional[bool] = Query(
        None,
        description="Filter by event type (true for events, false for notifications, null for all)",
    ),
):
    """
    Получает список общих уведомлений и событий.
    Доступно всем аутентифицированным пользователям.
    """
    query = db.query(models.Notification)

    if audience is not None:
        query = query.filter(models.Notification.audience == audience.value)

    if is_event is not None:
        query = query.filter(models.Notification.is_event == is_event)

    notifications = (
        query.order_by(models.Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return notifications


@router.get("/{notification_id}", response_model=schemas.NotificationRead)
async def read_notification(
    notification_id: int, db: Annotated[Session, Depends(get_db)]
):
    """
    Получает одно уведомление/событие по ID.
    """
    db_notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id)
        .first()
    )

    if db_notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification/Event not found"
        )
    return db_notification


@router.put(
    "/{notification_id}",
    response_model=schemas.NotificationRead,
    dependencies=[Depends(security.require_admin_role)],
)
async def update_notification(
    notification_id: int,
    notification_in: schemas.NotificationUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Обновляет существующее уведомление/событие.
    """
    db_notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id)
        .first()
    )
    if db_notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification/Event not found"
        )

    update_data = notification_in.model_dump(exclude_unset=True)
    if not update_data:
        return db_notification

    # Обработка логики is_event и event_date при обновлении
    final_is_event = update_data.get("is_event", db_notification.is_event)
    final_event_date = update_data.get("event_date", db_notification.event_date)

    if "is_event" in update_data or "event_date" in update_data:
        if final_is_event and final_event_date is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="event_date is required if is_event is true.",
            )
        if not final_is_event and final_event_date is not None:
            # Если is_event становится False, event_date должен быть очищен
            logger.info("is_event is False, clearing event_date during update.")
            update_data["event_date"] = None

            if "event_date" not in update_data:
                setattr(db_notification, "event_date", None)

    for key, value in update_data.items():
        setattr(db_notification, key, value)

    try:
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)

        logger.info(
            f"Notification/Event id={db_notification.id} updated by user '{current_user.username}'."
        )
        return db_notification
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error updating notification {notification_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification/event due to a database error.",
        )


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(security.require_admin_role)],
)
async def delete_notification(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(security.get_current_active_user)],
):
    """
    Удаляет уведомление/событие.
    """
    db_notification = (
        db.query(models.Notification)
        .filter(models.Notification.id == notification_id)
        .first()
    )
    if db_notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification/Event not found"
        )

    title_for_log = db_notification.title
    try:
        db.delete(db_notification)
        db.commit()
        logger.info(
            f"Notification/Event id={notification_id} (title: '{title_for_log}') deleted by user '{current_user.username}'."
        )
    except Exception as e:
        db.rollback()
        logger.error(
            f"Database error deleting notification {notification_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification/event due to a database error.",
        )
