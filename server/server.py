from datetime import datetime, timedelta
from typing import Optional
import uvicorn
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import threading
import logging
import os
from sqlalchemy import text
from database import database
from pathlib import Path
from dotenv import load_dotenv


load_dotenv()

log_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)
logger = logging.getLogger("KindergartenApp")
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)

from server.routers import (
    auth,
    groups,
    menus,
    users,
    children,
    attendance,
    holidays,
    reports,
    payments,
    posts,
    notifications,
)
from server.utils import security


try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    from server.tasks import (
        scheduled_cleanup_job as scheduled_cleanup_posts_notifs_job,
        scheduled_cleanup_meal_menus_job,
        scheduled_cleanup_attendance_job,
    )

    SCHEDULER_ENABLED = True
    logger.info(
        "APScheduler and tasks (cleanup_posts_notifs, cleanup_meal_menus, cleanup_attendance) imported successfully."  # Обновил лог
    )
except ImportError as e_aps:
    logger.warning(
        f"APScheduler or required tasks not found. Scheduled tasks will be disabled. Error: {e_aps}"
    )
    SCHEDULER_ENABLED = False
    BackgroundScheduler = None
    CronTrigger = None

    scheduled_cleanup_posts_notifs_job = None
    scheduled_cleanup_meal_menus_job = None
    scheduled_cleanup_attendance_job = None

HOST = os.getenv("SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("SERVER_PORT", 8000))
CURRENT_FILE_PATH = Path(__file__).resolve()
SERVER_DIR = CURRENT_FILE_PATH.parent
BASE_DIR = SERVER_DIR.parent
UPLOADS_PATH_ROOT = BASE_DIR / "uploads"
UPLOAD_DIR_POSTS_ABS_FOR_TASK = str(UPLOADS_PATH_ROOT / "post_media")
app = FastAPI(
    title="Kindergarten API",
    description="API для информационной системы дошкольного учреждения",
    version="1.0.1",
    swagger_ui_parameters={
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
    },
)
try:
    UPLOADS_PATH_ROOT.mkdir(parents=True, exist_ok=True)
    (UPLOADS_PATH_ROOT / "post_media").mkdir(parents=True, exist_ok=True)
    logger.info(f"Uploads directory ensured at: {UPLOADS_PATH_ROOT}")
except Exception as e_mkdir:
    logger.error(
        f"Could not create uploads directory at {UPLOADS_PATH_ROOT}: {e_mkdir}"
    )
if UPLOADS_PATH_ROOT.is_dir():
    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_PATH_ROOT)), name="uploads")
    logger.info(f"Mounted static files from {UPLOADS_PATH_ROOT} to /uploads")
else:
    logger.error(
        f"Cannot mount static files: Directory {UPLOADS_PATH_ROOT} does not exist or is not a directory."
    )
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = None


@app.on_event("startup")
async def startup_event_app():
    global scheduler

    logger.info("Running startup DB check...")
    db = None
    try:
        db = database.SessionLocal()
        db.execute(text("SELECT 1")).scalar_one_or_none()
        logger.info("Startup DB check successful.")
    except Exception as e:
        logger.error(f"!!! Startup DB check FAILED: {e}", exc_info=True)
    finally:
        if db:
            db.close()

    if SCHEDULER_ENABLED:
        if BackgroundScheduler is not None and CronTrigger is not None:
            logger.info("APScheduler components available. Initializing scheduler.")

            if scheduler is None:
                scheduler = BackgroundScheduler(
                    timezone=str(os.getenv("TZ", "Europe/Moscow"))
                )

            jobs_added_count = 0

            if scheduled_cleanup_posts_notifs_job:
                days_posts = int(os.getenv("DAYS_TO_KEEP_POSTS", "180"))
                days_notifs = int(os.getenv("DAYS_TO_KEEP_NOTIFICATIONS", "90"))
                trigger_posts_notifs = CronTrigger(
                    hour=int(os.getenv("CLEANUP_HOUR_POSTS_NOTIFS", "3")),
                    minute=int(os.getenv("CLEANUP_MINUTE_POSTS_NOTIFS", "15")),
                )
                scheduler.add_job(
                    scheduled_cleanup_posts_notifs_job,
                    trigger=trigger_posts_notifs,
                    id="cleanup_posts_notifications_job",
                    name="Clean old posts and notifications",
                    replace_existing=True,
                    args=[
                        days_posts,
                        days_notifs,
                        UPLOAD_DIR_POSTS_ABS_FOR_TASK,
                    ],
                )
                logger.info(
                    f"Scheduled: Posts (>{days_posts}d) & Notifications (>{days_notifs}d) cleanup with trigger: {str(trigger_posts_notifs)}"
                )
                jobs_added_count += 1

            if scheduled_cleanup_meal_menus_job:
                days_menu = int(os.getenv("DAYS_TO_KEEP_MENUS", "30"))
                trigger_menus = CronTrigger(
                    hour=int(os.getenv("CLEANUP_HOUR_MENUS", "3")),
                    minute=int(os.getenv("CLEANUP_MINUTE_MENUS", "0")),
                )
                scheduler.add_job(
                    scheduled_cleanup_meal_menus_job,
                    trigger=trigger_menus,
                    id="cleanup_meal_menus_job",
                    name="Clean old meal menus",
                    replace_existing=True,
                    args=[days_menu],
                )
                logger.info(
                    f"Scheduled: Meal Menus (>{days_menu}d) cleanup with trigger: {str(trigger_menus)}"
                )
                jobs_added_count += 1

            # --- Очистка старых записей посещаемости ---
            if scheduled_cleanup_attendance_job:
                days_attendance = int(os.getenv("DAYS_TO_KEEP_ATTENDANCE", "180"))
                trigger_attendance = CronTrigger(
                    day="1",
                    hour=int(os.getenv("CLEANUP_HOUR_ATTENDANCE", "4")),
                    minute=int(os.getenv("CLEANUP_MINUTE_ATTENDANCE", "30")),
                )
                scheduler.add_job(
                    scheduled_cleanup_attendance_job,
                    trigger=trigger_attendance,
                    id="cleanup_attendance_job",
                    name="Clean old attendance records",
                    replace_existing=True,
                    args=[days_attendance],
                )
                logger.info(
                    f"Scheduled: Attendance records (>{days_attendance}d) cleanup with trigger: {str(trigger_attendance)}"
                )
                jobs_added_count += 1

            if jobs_added_count > 0 and scheduler is not None and not scheduler.running:
                try:
                    scheduler.start()
                    logger.info(
                        f"APScheduler started successfully with {jobs_added_count} job(s)."
                    )
                except Exception as e_aps_start:
                    logger.error(
                        f"Failed to start APScheduler: {e_aps_start}", exc_info=True
                    )
            elif scheduler is not None and scheduler.running:
                logger.info(
                    f"APScheduler already running. Total jobs configured: {len(scheduler.get_jobs())}"
                )
            elif scheduler is not None:
                logger.info(
                    "APScheduler initialized, but no jobs were added/scheduled."
                )
        else:
            logger.error(
                "APScheduler enabled, but required components (BackgroundScheduler/CronTrigger or task functions) are None. Cannot start scheduler."
            )
    else:
        logger.info("APScheduler is disabled.")


@app.on_event("shutdown")
async def shutdown_event_app():
    global scheduler
    if scheduler and hasattr(scheduler, "running") and scheduler.running:
        logger.info("Shutting down APScheduler...")
        scheduler.shutdown(wait=False)
        logger.info("APScheduler shutdown initiated.")
    else:
        logger.info("APScheduler not running or not initialized at shutdown.")


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(
    groups.router,
    prefix="/api/groups",
    tags=["Groups"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(
    menus.router,
    prefix="/api/menus",
    tags=["Meal Menus"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(children.router, prefix="/api/children", tags=["Children"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(
    reports.router,
    prefix="/api/reports",
    tags=["Reports"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(
    holidays.router,
    prefix="/api/holidays",
    tags=["Holidays"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(
    payments.router,
    prefix="/api/payments",
    tags=["Payments"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(
    posts.router,
    prefix="/api/posts",
    tags=["Posts"],
    dependencies=[Depends(security.get_current_active_user)],
)
app.include_router(
    notifications.router,
    prefix="/api/notifications",
    tags=["Notifications & Events"],
    dependencies=[Depends(security.get_current_active_user)],
)


@app.get("/api", tags=["Root"])
async def read_api_root():
    return {"message": "Welcome to Kindergarten API"}


@app.get("/api/health", tags=["Health Check"])
async def health_check():
    return {
        "status": "OK",
        "version": app.version if hasattr(app, "version") else "N/A",
    }


server_instance: Optional[uvicorn.Server] = None
should_exit = threading.Event()


def get_server_url():
    return f"http://{HOST}:{PORT}"


def start_server():
    global server_instance, should_exit
    config = uvicorn.Config(
        "server.server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        loop="asyncio",
        http="h11",
    )
    server_instance = uvicorn.Server(config)
    logger.info(f"Starting Uvicorn server on http://{HOST}:{PORT}...")
    should_exit.clear()
    try:
        server_instance.run()
        logger.info("Uvicorn server has stopped.")
    except Exception as e:
        logger.exception("Uvicorn server run failed!")


def stop_server():
    global server_instance, should_exit
    if server_instance and not should_exit.is_set():
        logger.info("Signaling Uvicorn server to stop...")
        should_exit.set()

        server_instance.should_exit = True
        logger.info("Stop signal sent to Uvicorn.")
        return True
    elif not server_instance:
        logger.warning("Stop server called, but server instance is not running.")
        return False
    else:
        logger.info("Server is already stopping or has stopped.")
        return True


if __name__ == "__main__":
    logger.info(f"Starting server directly via uvicorn.run on http://{HOST}:{PORT}...")
    uvicorn.run(
        "server.server:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="debug",
        loop="asyncio",
        http="h11",
    )
