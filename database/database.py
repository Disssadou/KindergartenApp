from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging  # Добавим для логгирования URL

logger = logging.getLogger(
    "KindergartenApp"
)  # Предполагаем, что логгер настроен где-то (например, в main.py или utils.logger)

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    logger.critical(
        "CRITICAL ERROR: DATABASE_URL environment variable not found in .env!"
    )
    raise ValueError("DATABASE_URL environment variable is not set!")

# Логируем часть URL для проверки (без пароля)
try:
    db_user_host_db = SQLALCHEMY_DATABASE_URL.split("@")[-1]
    logger.info(f"Database URL loaded, connecting to: ...@{db_user_host_db}")
except Exception:
    logger.info(
        f"Database URL loaded: {SQLALCHEMY_DATABASE_URL[:20]}..."
    )  # Показываем только начало

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    # --- Добавляем параметры пула ---
    pool_size=10,  # Увеличиваем размер пула (например, до 10)
    max_overflow=5 # Дополнительные временные соединения сверх пула
    # -------------------------------
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency that provides a SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
