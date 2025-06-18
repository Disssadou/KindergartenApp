import sys
import threading
import logging
from datetime import date, datetime
import time
from typing import Dict, Optional
import subprocess
import os


from PyQt6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
    QApplication,
    QToolBar,
    QStatusBar,
    QStyle,
    QDialog,
    QFileDialog,
)
from PyQt6.QtCore import (
    Qt,
    QSize,
    pyqtSignal,
    QSettings,
    QTimer,
    QStandardPaths,
)
from PyQt6.QtGui import QAction, QIcon


try:
    from server.server import (
        stop_server,
    )
except ImportError:
    print("Warning: Could not import stop_server. Server stop on close might fail.")

    def stop_server():
        print("stop_server function not available.")
        return False


from utils.api_client import ApiClient

# --- Импорты представлений (View) ---
from app.views.groups_view import GroupsView
from app.views.menu_view import MenuView
from app.views.staff_view import StaffView
from app.views.children_view import ChildrenView
from app.views.attendance_view import AttendanceView
from app.views.reports_view import ReportsView
from app.views.payments_view import PaymentsView
from app.views.dashboard_view import DashboardView

# --- Импорты диалогов ---
from app.dialogs.login_dialog import LoginDialog
from app.dialogs.settings_dialog import SettingsDialog


logger = logging.getLogger("KindergartenApp")


# --- Класс Главного Окна ---
class MainWindow(QMainWindow):
    status_update_signal = pyqtSignal(str)

    def __init__(self, api_client: ApiClient):
        super().__init__()
        self.api_client = api_client
        self.setWindowTitle(
            "Информационная Система Учета Посещаемости Дошкольного Учреждения (ИСУПДУ)"
        )
        self.setMinimumSize(1100, 750)

        self.settings = QSettings()

        self.current_user_info: Optional[Dict] = (
            self.api_client.get_current_user_details()
        )

        if not self.current_user_info:

            logger.critical(
                "MainWindow создан, но отсутствует информация о пользователе в ApiClient!"
            )
            QMessageBox.critical(
                self,
                "Критическая ошибка",
                "Не удалось получить данные пользователя после входа. Приложение будет закрыто.",
            )

            QTimer.singleShot(0, self.close)
            return

        # --- Создаем экземпляры представлений (View) ---

        try:
            self.groups_view = GroupsView(api_client=self.api_client, parent=self)
        except Exception as e:
            logger.exception("Failed to initialize GroupsView")
            QMessageBox.critical(
                self, "Ошибка инициализации", f"Не удалось загрузить модуль Групп:\n{e}"
            )
            self.groups_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Групп"
            )

        try:
            self.menu_view = MenuView(api_client=self.api_client, parent=self)
        except Exception as e:
            logger.exception("Failed to initialize MenuView")
            QMessageBox.critical(
                self, "Ошибка инициализации", f"Не удалось загрузить модуль Меню:\n{e}"
            )
            self.menu_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Меню"
            )

        try:
            self.dashboard_view = DashboardView(api_client=self.api_client, parent=self)
        except Exception as e:
            logger.exception("Failed to initialize DashboardView")
            self.dashboard_view = self._create_error_placeholder_widget(
                "Ошибка модуля Панели управления"
            )

        try:
            self.children_view = ChildrenView(api_client=self.api_client, parent=self)
        except Exception as e:
            logger.exception("Failed to initialize ChildrenView")
            QMessageBox.critical(
                self, "Ошибка инициализации", f"Не удалось загрузить модуль Детей:\n{e}"
            )
            self.children_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Детей"
            )

        try:
            self.attendance_view = AttendanceView(
                api_client=self.api_client, parent=self
            )
        except Exception as e:
            logger.exception("Failed to initialize AttendanceView")
            QMessageBox.critical(
                self,
                "Ошибка инициализации",
                f"Не удалось загрузить модуль Посещаемости:\n{e}",
            )
            self.attendance_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Посещаемости"
            )

        try:

            self.payments_view = PaymentsView(
                api_client=self.api_client, settings=self.settings, parent=self
            )
        except Exception as e:
            logger.exception("Failed to initialize PaymentsView")
            QMessageBox.critical(
                self, "Ошибка инициализации", f"Не удалось загрузить модуль Оплат:\n{e}"
            )
            self.payments_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Оплат"
            )

        try:

            self.reports_view = ReportsView(
                api_client=self.api_client, settings=self.settings, parent=self
            )
        except Exception as e:
            logger.exception("Failed to initialize ReportsView")
            QMessageBox.critical(
                self,
                "Ошибка инициализации",
                f"Не удалось загрузить модуль Отчетов:\n{e}",
            )
            self.reports_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Отчетов"
            )

        try:
            self.staff_view = StaffView(api_client=self.api_client, parent=self)
        except Exception as e:
            logger.exception("Failed to initialize StaffView")
            QMessageBox.critical(
                self,
                "Ошибка инициализации",
                f"Не удалось загрузить модуль Персонала:\n{e}",
            )
            self.staff_view = self._create_error_placeholder_widget(
                "Ошибка загрузки модуля Персонала"
            )

        self.initUI_structure()

        self.connect_view_signals()
        self.update_window_title_with_user()
        self.configure_ui_for_user_role()
        self.load_initial_settings()

        logger.info("Main window initialized.")
        self.status_update_signal.emit("Приложение готово. Требуется вход.")

    def _create_error_placeholder_widget(self, message: str) -> QWidget:
        """Создает виджет-заглушку для отображения ошибки загрузки модуля."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(message))
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return widget

    def initUI_structure(self):
        """Инициализирует основные компоненты интерфейса окна."""
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tabs.addTab(self.dashboard_view, "📊 Панель управления")
        self.tabs.addTab(self.groups_view, "👥 Группы")
        self.tabs.addTab(self.children_view, "👶 Дети")
        self.tabs.addTab(self.staff_view, "👩‍🏫 Пользователи")
        self.tabs.addTab(self.attendance_view, "📅 Посещаемость")
        self.tabs.addTab(self.payments_view, "💳 Оплаты")
        self.tabs.addTab(self.menu_view, "🍲 Питание")
        self.tabs.addTab(self.reports_view, "📄 Отчеты")

        self.create_actions()
        self.create_toolbars()
        self.create_menus()
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_update_signal.connect(self.status_bar.showMessage)

    def connect_view_signals(self):
        """Подключает сигналы status_changed от всех View к слоту обновления StatusBar."""
        views_with_status_signal = [
            self.groups_view,
            self.menu_view,
            self.staff_view,
            self.children_view,
            self.attendance_view,
            self.reports_view,
            self.payments_view,
            self.dashboard_view,
        ]
        for view_instance in views_with_status_signal:
            if hasattr(view_instance, "status_changed") and hasattr(
                view_instance.status_changed, "connect"
            ):
                view_instance.status_changed.connect(self.update_status_bar_slot)
            else:
                logger.debug(
                    f"View {type(view_instance).__name__} does not have 'status_changed' signal."
                )

    def update_status_bar_slot(self, message: str, timeout: int = 5000):
        """Слот для обновления статус-бара с таймаутом."""
        self.status_bar.showMessage(message, timeout)

    def create_actions(self):
        style = self.style()

        self.settings_action = QAction(
            QIcon.fromTheme(
                "preferences-system",
                style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            ),
            "&Настройки...",
            self,
        )
        self.settings_action.setStatusTip("Открыть настройки приложения")
        self.settings_action.triggered.connect(self.open_settings_dialog)

        self.backup_action = QAction(
            QIcon.fromTheme(
                "document-save-as",
                style.standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon),
            ),
            "Резервное копирование БД...",
            self,
        )
        self.backup_action.setStatusTip(
            "Создать резервную копию базы данных PostgreSQL"
        )
        self.backup_action.triggered.connect(self.backup_database)
        self.backup_action.setEnabled(True)

        self.exit_action = QAction(
            QIcon.fromTheme(
                "application-exit",
                style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton),
            ),
            "&Выход",
            self,
        )
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.setStatusTip("Выйти из приложения (Ctrl+Q)")
        self.exit_action.triggered.connect(self.close)

        self.about_action = QAction("О программе", self)
        self.about_action.triggered.connect(self.show_about_dialog)

    def create_toolbars(self):
        toolbar = QToolBar("Основные действия")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        toolbar.addAction(self.settings_action)
        toolbar.addAction(self.backup_action)
        toolbar.addSeparator()
        toolbar.addAction(self.exit_action)

    def create_menus(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Файл")
        file_menu.addAction(self.settings_action)
        file_menu.addAction(self.backup_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        help_menu = menu_bar.addMenu("&Справка")
        help_menu.addAction(self.about_action)

    def update_window_title_with_user(self):
        if self.current_user_info:
            username = self.current_user_info.get("username", "N/A")
            self.setWindowTitle(f"ИСУПДУ - [{username}]")

    def configure_ui_for_user_role(self):

        pass

    def open_settings_dialog(self):

        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Настройки приложения были изменены и сохранены.")
            self.update_status_bar_slot("Настройки сохранены.", 3000)
            self.apply_settings_changes()
        else:
            self.update_status_bar_slot("Изменение настроек отменено.", 3000)

    def apply_settings_changes(self):
        """Применяет изменения настроек, которые влияют на UI или поведение."""

        if hasattr(self.reports_view, "update_default_paths_from_settings"):
            self.reports_view.update_default_paths_from_settings()

        logger.info("Relevant settings changes applied to UI components.")

    def load_initial_settings(self):
        """Загружает и применяет настройки при запуске, которые влияют на MainWindow."""

        logger.info("Initial application settings loaded for MainWindow.")
        self.apply_settings_changes()

    def show_about_dialog(self):
        about_text = (
            f"{self.windowTitle()}\n\n"
            "Версия 0.2 (Alpha)\n\n"
            "Разработчик: Попов А.И.\n"
            f"Год создания: {datetime.now().year}"
        )
        QMessageBox.about(self, "О программе", about_text)

    def backup_database(self):
        logger.info("Initiating database backup process...")
        self.status_update_signal.emit("Запуск процесса резервного копирования...")

        from app.dialogs.settings_dialog import DEFAULT_BACKUPS_PATH_KEY

        default_backup_dir = self.settings.value(
            DEFAULT_BACKUPS_PATH_KEY,
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            ),
        )
        default_backup_dir_str = str(default_backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"kindergarten_db_backup_{timestamp}.sql"

        suggested_path = os.path.join(default_backup_dir_str, default_filename)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить резервную копию базы данных",
            suggested_path,
            "SQL Files (*.sql);;All Files (*)",
        )

        if not file_path:
            logger.info("Database backup cancelled by user.")
            self.status_update_signal.emit("Резервное копирование отменено.")
            return

        # --- Формирование и выполнение команды pg_dump ---

        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.error("DATABASE_URL not found in environment for backup.")
            QMessageBox.critical(
                self,
                "Ошибка конфигурации",
                "URL базы данных не найден. Невозможно создать резервную копию.",
            )
            self.status_update_signal.emit("Ошибка конфигурации для бэкапа.")
            return

        try:
            from sqlalchemy.engine.url import make_url

            url_obj = make_url(db_url)

            db_user = url_obj.username
            db_password = url_obj.password
            db_host = url_obj.host
            db_port = str(url_obj.port) if url_obj.port else "5432"
            db_name = url_obj.database

            if not all([db_user, db_host, db_name]):
                raise ValueError(
                    "Неполные данные для подключения к БД из DATABASE_URL."
                )

        except Exception as e:
            logger.error(f"Error parsing DATABASE_URL for backup: {e}")
            QMessageBox.critical(
                self,
                "Ошибка конфигурации",
                f"Не удалось разобрать URL базы данных: {e}",
            )
            self.status_update_signal.emit("Ошибка парсинга URL БД для бэкапа.")
            return

        pg_dump_cmd = [
            "pg_dump",
            "-U",
            db_user,
            "-h",
            db_host,
            "-p",
            db_port,
            "-d",
            db_name,
            "-f",
            file_path,
            "--no-password",
        ]
        logger.debug(
            f"pg_dump command (password omitted for log): {' '.join(pg_dump_cmd[:-3])} -f {file_path}"
        )

        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
        else:

            logger.warning(
                "DB password not found in DATABASE_URL. pg_dump might fail or ask for password if .pgpass is not configured."
            )

        self.status_update_signal.emit(f"Создание резервной копии в {file_path}...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:

            process = subprocess.Popen(
                pg_dump_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout, stderr = process.communicate(timeout=300)

            if process.returncode == 0:
                logger.info(f"Database backup successful: {file_path}")
                QMessageBox.information(
                    self,
                    "Успех",
                    f"Резервная копия базы данных успешно создана:\n{file_path}",
                )
                self.status_update_signal.emit(
                    "Резервное копирование успешно завершено."
                )
            else:
                error_message = stderr.decode(errors="replace").strip()
                logger.error(
                    f"pg_dump failed (code {process.returncode}): {error_message}"
                )
                QMessageBox.critical(
                    self,
                    "Ошибка резервного копирования",
                    f"Не удалось создать резервную копию:\n{error_message}",
                )
                self.status_update_signal.emit(
                    f"Ошибка резервного копирования: {error_message[:50]}..."
                )

        except FileNotFoundError:
            logger.error(
                "pg_dump command not found. Is PostgreSQL client installed and in PATH?"
            )
            QMessageBox.critical(
                self,
                "Ошибка",
                "Команда pg_dump не найдена. Убедитесь, что клиентские утилиты PostgreSQL установлены и доступны в системном PATH.",
            )
            self.status_update_signal.emit("pg_dump не найден.")
        except subprocess.TimeoutExpired:
            logger.error("pg_dump process timed out.")
            process.kill()
            stdout, stderr = process.communicate()
            QMessageBox.warning(
                self,
                "Таймаут",
                "Процесс резервного копирования занял слишком много времени и был прерван.",
            )
            self.status_update_signal.emit("Таймаут резервного копирования.")
        except Exception as e:
            logger.exception("An unexpected error occurred during database backup.")
            QMessageBox.critical(
                self,
                "Неизвестная ошибка",
                f"Произошла непредвиденная ошибка при резервном копировании:\n{e}",
            )
            self.status_update_signal.emit(
                f"Неизвестная ошибка бэкапа: {str(e)[:50]}..."
            )
        finally:
            QApplication.restoreOverrideCursor()
            if "PGPASSWORD" in env:
                del env["PGPASSWORD"]
            if "db_password" in locals() and db_password:
                del db_password

            self.status_update_signal.emit("Операция резервного копирования завершена.")

    def closeEvent(self, event):
        logger.debug("Close event received for main window.")
        reply = QMessageBox.question(
            self,
            "Подтверждение выхода",
            "Вы уверены, что хотите выйти?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("User confirmed exit. Accepting close event.")

            event.accept()
        else:
            logger.info("User cancelled exit. Ignoring close event.")
            event.ignore()


if __name__ == "__main__":
    print("INFO: Running main_window.py directly for UI testing.")
    print("INFO: Using Mock API client. No real server or database interaction.")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    )
    logger_test = logging.getLogger("KindergartenApp.Test")

    app_test = QApplication(sys.argv)

    QApplication.setOrganizationName("MyTestCompany")
    QApplication.setApplicationName("MyTestAppForMainWindow")

    class MockApiClient:
        def __init__(self, base_url="http://mockserver"):
            self.base_url = base_url
            self._token = None

        def set_token(self, token):
            self._token = token

        def login(self, username, password):
            logger_test.debug(f"Mock login: {username}")
            return {"access_token": "mock_token", "token_type": "bearer"}, None

        def get_current_user(self):
            logger_test.debug("Mock get_current_user")
            return {
                "id": 1,
                "username": "testuser",
                "full_name": "Тестовый Пользователь",
                "role": "admin",
            }, None

        def get_groups(self, limit=100):
            logger_test.debug("Mock get_groups")
            return [], None

        def get_users(self, role=None, skip=0, limit=100):
            logger_test.debug("Mock get_users")
            return [], None

        def get_children(self, group_id=None, search=None, skip=0, limit=100):
            logger_test.debug("Mock get_children")
            return [], None

        def get_meal_menus_for_date_range(self, start_date, end_date):
            logger_test.debug("Mock get_meal_menus")
            return {}, None

        def get_attendance(self_or_other, date, group_id=None, child_id=None):
            logger_test.debug("Mock get_attendance")
            return [], None

        def get_holidays(self_or_other, start_date, end_date):
            logger_test.debug("Mock get_holidays")
            return [], None

        def get_attendance_report_data(self_or_other, group_id, year, month):
            logger_test.debug("Mock get_attendance_report_data")
            return {
                "year": year,
                "month": month,
                "days_in_month": 30,
                "group_id": group_id,
                "group_name": "Mock Group",
                "children_data": [],
                "holiday_dates": [],
                "daily_totals": {},
                "teacher_name": "Mock Teacher",
                "total_work_days": 20,
            }, None

        def download_attendance_report(self, params):
            logger_test.debug("Mock download_attendance_report")
            return b"mock excel data", None

        def get_child_transactions(self, child_id, limit=100):
            logger_test.debug(f"Mock get_child_transactions for {child_id}")
            return [], None

    mock_api = MockApiClient()

    try:
        main_window_test = MainWindow(api_client=mock_api)

    except Exception as e:
        logger_test.exception("Failed to create or show main window in test mode.")
        QMessageBox.critical(
            None, "Ошибка запуска UI", f"Не удалось создать главное окно:\n{e}"
        )
        sys.exit(1)

    sys.exit(app_test.exec())
