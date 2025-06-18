import sys
import os
import threading
import time
import logging
from dotenv import load_dotenv

# --- Настройка путей ---

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- Импорты компонентов ---

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog
    from app.main_window import MainWindow
    from app.dialogs.login_dialog import LoginDialog
    from server.server import (
        start_server,
        stop_server,
        get_server_url,
    )
    from utils.logger import setup_logger
    from utils.api_client import (
        ApiClient,
        ApiConnectionError,
        ApiTimeoutError,
        ApiHttpError,
        ApiClientError,
    )
except ImportError as e:

    print(f"КРИТИЧЕСКАЯ ОШИБКА ИМПОРТА в main.py: {e}")
    print(
        "Пожалуйста, убедитесь, что все зависимости установлены (pip install -r requirements.txt)"
    )
    print(
        "и вы запускаете скрипт из корневой папки проекта с активированным виртуальным окружением."
    )

    try:
        from PyQt6.QtWidgets import (
            QApplication,
            QMessageBox,
        )

        app_temp = QApplication.instance()
        if not app_temp:
            app_temp = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Ошибка Запуска",
            f"Не удалось импортировать необходимые модули:\n{e}\n\nПроверьте консоль для деталей.",
        )
    except Exception:
        pass
    sys.exit(1)


logger = setup_logger()

# --- Основная логика запуска ---
if __name__ == "__main__":
    load_dotenv()
    logger.info("========================================")
    logger.info("Запуск приложения ИСУПДУ...")
    logger.info(f"Корень проекта: {project_root}")
    logger.info(f"Исполняемый файл Python: {sys.executable}")
    logger.info(f"Версия Python: {sys.version}")
    logger.info(f"Пути поиска модулей (sys.path): {sys.path}")

    app = QApplication(sys.argv)
    QApplication.setOrganizationName("Детский сад")
    QApplication.setApplicationName("KindergartenApp")

    # --- Запуск FastAPI сервера ---
    server_thread = None
    server_running_assumed = False
    server_url = "http://127.0.0.1:8000"

    try:
        try:
            server_url = get_server_url()
            logger.info(f"Целевой URL сервера: {server_url}")
        except Exception as e_url:
            logger.warning(
                f"Не удалось определить URL сервера до старта: {e_url}. Используется URL по умолчанию: {server_url}"
            )

        logger.info("Попытка запуска сервера FastAPI в отдельном потоке...")
        server_thread = threading.Thread(
            target=start_server, name="FastAPIServerThread", daemon=True
        )
        server_thread.start()

        startup_wait_time = 7.0
        logger.info(f"Ожидание инициализации сервера ({startup_wait_time} секунд)...")
        time.sleep(startup_wait_time)

        if server_thread.is_alive():
            logger.info(
                "Поток сервера активен. Предполагается, что сервер запущен или запускается."
            )
            server_running_assumed = True
        else:
            logger.error(
                "КРИТИЧЕСКАЯ ОШИБКА: Поток сервера неожиданно завершился во время старта!"
            )
            raise RuntimeError("Поток сервера не смог запуститься корректно.")

    except Exception as e_server_start:
        logger.exception(
            "КРИТИЧЕСКАЯ ОШИБКА: Не удалось запустить поток сервера FastAPI!"
        )
        QMessageBox.critical(
            None,
            "Ошибка Запуска Сервера",
            f"Не удалось запустить внутренний сервер:\n{e_server_start}",
        )
        sys.exit(1)

    api_client = None
    main_window = None
    login_success = False

    # --- Аутентификация и Запуск Главного Окна ---
    api_client = None
    main_window = None
    login_success = False

    if server_running_assumed:
        try:
            api_client = ApiClient(base_url=server_url)
            login_dialog_main = LoginDialog(api_client=api_client)

            logger.info("Отображение диалога входа из main.py...")
            if login_dialog_main.exec() == QDialog.DialogCode.Accepted:

                if api_client.get_current_user_details():
                    logger.info(
                        f"Успешный вход для пользователя: {api_client.get_current_user_details().get('username')}"
                    )
                    login_success = True
                    main_window = MainWindow(api_client=api_client)
                    main_window.show()
                else:
                    logger.error(
                        "Успешный exec() LoginDialog, но нет данных пользователя в ApiClient."
                    )
                    QMessageBox.critical(
                        None,
                        "Ошибка входа",
                        "Не удалось получить данные пользователя после входа.",
                    )
                    login_success = False
            else:
                logger.info(
                    "Диалог входа (из main.py) отклонен или отменен пользователем."
                )
                login_success = False

        except ApiConnectionError as e_conn:
            logger.error(f"Ошибка сети при попытке входа: {e_conn.message}")
            QMessageBox.critical(
                None,
                "Ошибка Сети",
                f"Не удалось подключиться к серверу для входа:\n{e_conn.message}\n\nУбедитесь, что сервер запущен и доступен.",
            )
            login_success = False
        except ApiTimeoutError as e_timeout:
            logger.error(f"Таймаут при попытке входа: {e_timeout.message}")
            QMessageBox.warning(
                None,
                "Таймаут",
                f"Сервер не ответил вовремя при попытке входа:\n{e_timeout.message}\n\nПопробуйте позже.",
            )
            login_success = False
        except ApiHttpError as e_http:
            logger.error(f"HTTP ошибка при попытке входа: {e_http.message}")
            QMessageBox.critical(
                None,
                f"Ошибка Сервера ({e_http.status_code})",
                f"Сервер вернул ошибку при попытке входа:\n{e_http.message}",
            )
            login_success = False
        except ApiClientError as e_client:
            logger.exception(f"Ошибка API клиента при входе: {e_client.message}")
            QMessageBox.critical(
                None,
                "Ошибка API",
                f"Произошла ошибка при обращении к API:\n{e_client.message}",
            )
            login_success = False
        except Exception as e_main:
            logger.exception(
                f"Непредвиденная ошибка на этапе входа/создания главного окна: {e_main}"
            )
            QMessageBox.critical(
                None,
                "Критическая Ошибка",
                f"Произошла непредвиденная ошибка:\n{e_main}",
            )
            login_success = False
    else:

        pass

    # --- Запуск главного цикла Qt или выход из приложения ---
    exit_code = 0
    if login_success and main_window:
        logger.info("Вход в главный цикл событий приложения Qt...")
        exit_code = app.exec()
        logger.info(f"Главный цикл событий Qt завершен с кодом: {exit_code}.")

    else:
        logger.info(
            "Приложение завершается до входа в главный цикл (логин не удался или отменен)."
        )

        if server_running_assumed and server_thread and server_thread.is_alive():
            logger.info("Остановка сервера после неудачного/отмененного входа...")
            if stop_server():
                logger.info("Команда остановки сервера отправлена.")
            else:
                logger.warning(
                    "Не удалось отправить команду остановки сервера (возможно, он уже остановлен)."
                )

            if server_thread:
                server_thread.join(timeout=3)
                if server_thread.is_alive():
                    logger.warning(
                        "Поток сервера FastAPI не завершился корректно после команды остановки."
                    )
        exit_code = 1 if not server_running_assumed else 0

    logger.info("Приложение ИСУПДУ завершено.")
    sys.exit(exit_code)
