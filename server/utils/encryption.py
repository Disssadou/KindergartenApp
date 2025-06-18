import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import logging

logger = logging.getLogger("KindergartenApp.Encryption")


def _get_fernet_instance() -> Fernet:
    """
    Загружает ключ и возвращает инициализированный экземпляр Fernet.
    Вызывает исключение, если ключ не найден или невалиден.
    """

    if not os.getenv("APP_ENCRYPTION_KEY"):
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        dotenv_path = os.path.join(project_root, ".env")
        if os.path.exists(dotenv_path):
            logger.info(
                f"Attempting to load .env from {dotenv_path} in _get_fernet_instance"
            )
            loaded_count = load_dotenv(dotenv_path, verbose=True, override=True)
            logger.info(
                f"load_dotenv result (variables loaded/overridden): {loaded_count}"
            )

    encryption_key_str = os.getenv("APP_ENCRYPTION_KEY")
    logger.info(
        f"Value of APP_ENCRYPTION_KEY after trying to load .env: '{encryption_key_str}'"
    )

    if not encryption_key_str:
        logger.critical(
            "CRITICAL: APP_ENCRYPTION_KEY is not set in environment variables!"
        )
        raise ValueError("APP_ENCRYPTION_KEY environment variable is not set!")

    try:
        encryption_key_bytes = encryption_key_str.encode()
        return Fernet(encryption_key_bytes)
    except Exception as e:
        logger.critical(
            f"CRITICAL: Invalid APP_ENCRYPTION_KEY. Fernet initialization failed: {e}",
            exc_info=True,
        )
        raise ValueError(f"Invalid APP_ENCRYPTION_KEY: {e}")


_fernet = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = _get_fernet_instance()
    return _fernet


def encrypt_data(data: str | None) -> str | None:
    """Шифрует строку. Возвращает зашифрованную строку или None, если на входе None."""
    if data is None:
        return None
    if not isinstance(data, str):
        logger.warning(
            f"encrypt_data: input is not a string, but {type(data)}. Returning as is."
        )
        return str(data)
    try:
        fernet = get_fernet()
        return fernet.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Error encrypting data: {e}", exc_info=True)
        raise


def decrypt_data(encrypted_data: str | None) -> str | None:
    """Дешифрует строку. Возвращает дешифрованную строку или None, если на входе None."""
    if encrypted_data is None:
        return None
    if not isinstance(encrypted_data, str):
        logger.warning(
            f"decrypt_data: input is not a string, but {type(encrypted_data)}. Returning as is."
        )
        return str(encrypted_data)
    try:
        fernet = get_fernet()
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.error(
            f"Error decrypting data (possibly malformed or wrong key): {e}",
            exc_info=False,
        )
        return "[Ошибка дешифровки]"
