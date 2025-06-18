import logging
from typing import Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import delete
from datetime import (
    date,
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path

from database import models
from database.database import (
    SessionLocal,
)
from database.models import (
    Post,
    Notification,
    Media,
    MealMenu,
    Attendance,
)

logger_tasks = logging.getLogger("KindergartenApp.tasks")


# --- Логика очистки старых записей меню ---
def cleanup_old_meal_menus_logic(db: Session, days_to_keep: int = 30):
    """
    Удаляет старые записи меню из таблицы meal_menus.
    Эта функция содержит только логику и принимает сессию db.
    """
    if days_to_keep <= 0:
        logger_tasks.warning(
            "Cleanup for MealMenus skipped: days_to_keep must be positive."
        )
        return 0

    deleted_count = 0
    current_date = date.today()
    cutoff_date = current_date - timedelta(days=days_to_keep)

    logger_tasks.info(
        f"Cleanup: Deleting MealMenu entries with date < {cutoff_date}..."
    )

    try:
        stmt = delete(MealMenu).where(MealMenu.date < cutoff_date)
        result = db.execute(stmt)

        deleted_count = result.rowcount
        logger_tasks.info(
            f"Cleanup: Marked {deleted_count} old MealMenu entries for deletion."
        )
    except Exception as e:
        logger_tasks.error(f"Error during MealMenu cleanup logic: {e}", exc_info=True)

        raise

    return deleted_count


# --- Обертка для APScheduler для очистки меню ---
def scheduled_cleanup_meal_menus_job(
    days_to_keep: int,
):
    logger_tasks.info(
        f"APScheduler: Starting scheduled_cleanup_meal_menus_job (days_to_keep={days_to_keep})..."
    )
    db: Session = SessionLocal()
    deleted_count = 0
    try:
        deleted_count = cleanup_old_meal_menus_logic(db=db, days_to_keep=days_to_keep)
        if deleted_count > 0:
            db.commit()
            logger_tasks.info(
                f"APScheduler: Meal menu cleanup - {deleted_count} entries committed for deletion."
            )
        else:
            logger_tasks.info("APScheduler: Meal menu cleanup - No entries to delete.")
    except Exception as e:
        logger_tasks.error(
            f"APScheduler: Error in scheduled_cleanup_meal_menus_job: {e}",
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()
        logger_tasks.info(
            f"APScheduler: Database session closed for meal menu cleanup job. Total deleted: {deleted_count}"
        )


# --- Логика очистки старых постов и уведомлений ---
def cleanup_old_posts_and_notifications_logic(
    db: Session,
    days_to_keep_posts: int = 180,
    days_to_keep_notifications: int = 90,
    upload_dir_posts_abs_path: Optional[Path] = None,
):
    if upload_dir_posts_abs_path is None and days_to_keep_posts > 0:
        logger_tasks.error(
            "Cleanup for posts skipped: 'upload_dir_posts_abs_path' not provided."
        )
        days_to_keep_posts = 0

    if days_to_keep_posts <= 0 and days_to_keep_notifications <= 0:
        logger_tasks.info(
            "Cleanup: No posts/notifications to clean based on 'days_to_keep' settings."
        )
        return 0, 0

    deleted_posts_count = 0
    deleted_notifications_count = 0
    current_utc_time = datetime.now(timezone.utc)

    # Удаление старых постов и их медиа
    if days_to_keep_posts > 0 and upload_dir_posts_abs_path is not None:
        cutoff_date_posts = current_utc_time - timedelta(days=days_to_keep_posts)
        logger_tasks.info(
            f"Cleanup: Deleting Posts created before {cutoff_date_posts}..."
        )
        posts_to_delete = (
            db.query(models.Post)
            .options(selectinload(models.Post.media_files))
            .filter(models.Post.created_at < cutoff_date_posts)
            .all()
        )

        if not posts_to_delete:
            logger_tasks.info("Cleanup: No old posts found to delete.")
        else:
            for post in posts_to_delete:
                logger_tasks.debug(
                    f"Cleanup: Preparing to delete post ID {post.id} (created: {post.created_at})."
                )
                if post.media_files:
                    for media_record in post.media_files:

                        paths_to_delete = []
                        if media_record.file_path:
                            paths_to_delete.append(
                                upload_dir_posts_abs_path / media_record.file_path
                            )
                        if media_record.thumbnail_path:
                            paths_to_delete.append(
                                upload_dir_posts_abs_path / media_record.thumbnail_path
                            )
                        for file_on_disk in paths_to_delete:
                            try:
                                if file_on_disk.exists():
                                    if file_on_disk.is_file():
                                        file_on_disk.unlink()
                                        logger_tasks.info(
                                            f"Task: Deleted file: {file_on_disk}"
                                        )
                                    else:
                                        logger_tasks.warning(
                                            f"Task: Path {file_on_disk} is not a file."
                                        )
                            except Exception as e_file:
                                logger_tasks.error(
                                    f"Task: Error deleting file {file_on_disk}: {e_file}"
                                )
                db.delete(post)
                deleted_posts_count += 1
            logger_tasks.info(
                f"Cleanup: Marked {deleted_posts_count} old Posts for deletion."
            )

    # Удаление старых уведомлений
    if days_to_keep_notifications > 0:
        cutoff_date_notifications = current_utc_time - timedelta(
            days=days_to_keep_notifications
        )
        logger_tasks.info(
            f"Cleanup: Deleting Notifications created before {cutoff_date_notifications}..."
        )
        stmt_notifications = delete(models.Notification).where(
            models.Notification.created_at < cutoff_date_notifications
        )
        result_notifications = db.execute(stmt_notifications)
        deleted_notifications_count = result_notifications.rowcount
        logger_tasks.info(
            f"Cleanup: Marked {deleted_notifications_count} old Notifications for deletion."
        )

    return deleted_posts_count, deleted_notifications_count


# --- Обертка для APScheduler для постов и уведомлений ---
def scheduled_cleanup_job(
    days_posts: int,
    days_notifs: int,
    upload_path_str: str,
):
    logger_tasks.info(
        "APScheduler: Starting scheduled_cleanup_job (posts/notifications)..."
    )
    db: Session = SessionLocal()
    upload_path = Path(upload_path_str) if upload_path_str else None
    total_posts_deleted = 0
    total_notifs_deleted = 0
    try:
        posts_del, notifs_del = cleanup_old_posts_and_notifications_logic(
            db=db,
            days_to_keep_posts=days_posts,
            days_to_keep_notifications=days_notifs,
            upload_dir_posts_abs_path=upload_path,
        )
        total_posts_deleted += posts_del
        total_notifs_deleted += notifs_del

        if total_posts_deleted > 0 or total_notifs_deleted > 0:
            db.commit()
            logger_tasks.info(
                "APScheduler: Post/Notification cleanup - DB changes committed."
            )
        else:
            logger_tasks.info(
                "APScheduler: Post/Notification cleanup - No DB changes to commit."
            )

        logger_tasks.info(
            f"APScheduler: Cleanup job (posts/notifications) finished. Deleted posts: {total_posts_deleted}, Deleted notifications: {total_notifs_deleted}"
        )
    except Exception as e:
        logger_tasks.error(
            f"APScheduler: Error in scheduled_cleanup_job (posts/notifications): {e}",
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()
        logger_tasks.info(
            "APScheduler: Database session closed for posts/notifications cleanup job."
        )


# --- Логика очистки старых записей посещаемости ---
def cleanup_old_attendance_records_logic(db: Session, days_to_keep: int = 180):
    """
    Удаляет старые записи посещаемости из таблицы attendances.
    Эта функция содержит только логику и принимает сессию db.
    """
    if days_to_keep <= 0:
        logger_tasks.warning(
            "Cleanup for Attendance skipped: days_to_keep must be positive."
        )
        return 0

    deleted_count = 0
    current_date = date.today()
    cutoff_date = current_date - timedelta(days=days_to_keep)

    logger_tasks.info(
        f"Cleanup: Deleting Attendance entries with date < {cutoff_date}..."
    )

    try:

        stmt = delete(Attendance).where(Attendance.date < cutoff_date)
        result = db.execute(stmt)
        deleted_count = result.rowcount
        logger_tasks.info(
            f"Cleanup: Marked {deleted_count} old Attendance entries for deletion."
        )
    except Exception as e:
        logger_tasks.error(f"Error during Attendance cleanup logic: {e}", exc_info=True)
        raise

    return deleted_count


# --- Обертка для APScheduler для очистки посещаемости ---
def scheduled_cleanup_attendance_job(days_to_keep: int):
    logger_tasks.info(
        f"APScheduler: Starting scheduled_cleanup_attendance_job (days_to_keep={days_to_keep})..."
    )
    db: Session = SessionLocal()
    deleted_count = 0
    try:
        deleted_count = cleanup_old_attendance_records_logic(
            db=db, days_to_keep=days_to_keep
        )
        if deleted_count > 0:
            db.commit()
            logger_tasks.info(
                f"APScheduler: Attendance cleanup - {deleted_count} entries committed for deletion."
            )
        else:
            logger_tasks.info("APScheduler: Attendance cleanup - No entries to delete.")
    except Exception as e:
        logger_tasks.error(
            f"APScheduler: Error in scheduled_cleanup_attendance_job: {e}",
            exc_info=True,
        )
        db.rollback()
    finally:
        db.close()
        logger_tasks.info(
            f"APScheduler: Database session closed for attendance cleanup job. Total deleted: {deleted_count}"
        )
