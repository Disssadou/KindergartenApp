import logging
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


try:
    from utils.api_client import (
        ApiClient,
        ApiConnectionError,
        ApiTimeoutError,
        ApiClientError,
        ApiHttpError,
    )
except ImportError as e:
    print(f"ERROR in login_dialog.py: Cannot import from utils.api_client: {e}")

    class ApiClient:
        pass

    class ApiConnectionError(Exception):
        pass

    class ApiTimeoutError(Exception):
        pass

    class ApiClientError(Exception):
        pass

    class ApiHttpError(Exception):
        pass


logger = logging.getLogger("KindergartenApp")


class LoginDialog(QDialog):
    def __init__(self, api_client: ApiClient, parent: Optional[QWidget] = None):
        """
        Диалог входа в систему.

        Args:
            api_client: Экземпляр API клиента для выполнения запроса логина.
            parent: Родительский виджет (обычно None или главное окно).
        """
        super().__init__(parent)
        if not isinstance(api_client, ApiClient):

            QMessageBox.critical(
                self, "Ошибка конфигурации", "Не удалось инициализировать API клиент."
            )

            self.api_client = None
        else:
            self.api_client = api_client

        self.setWindowTitle("Вход в систему")
        self.setMinimumWidth(350)

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.setModal(True)

        self.initUI()
        logger.debug("LoginDialog initialized.")

    def initUI(self):
        """Создает элементы интерфейса диалога."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Поля ввода
        self.username_label = QLabel("Имя пользователя:")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите имя пользователя (admin)")

        self.password_label = QLabel("Пароль:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Введите пароль (password)")

        layout.addWidget(self.username_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_input)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal,
            self,
        )

        button_box.accepted.connect(self.handle_login)

        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)
        self.setLayout(layout)

        self.username_input.setFocus()

        self.password_input.returnPressed.connect(self.handle_login)

    def handle_login(self):
        """Обработчик нажатия кнопки 'OK' или Enter в поле пароля."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(
                self, "Ошибка ввода", "Пожалуйста, введите имя пользователя и пароль."
            )
            return

        if self.api_client is None:
            QMessageBox.critical(self, "Ошибка", "API клиент не инициализирован.")
            return

        logger.info(f"Login attempt for user: {username}")

        self.setEnabled(False)

        try:

            if self.api_client.login(username, password):
                logger.info(
                    f"Authentication successful for {username} (handled by ApiClient)."
                )
                self.accept()
            else:
                # Ошибка (401 Invalid credentials) или ошибка получения user_info
                logger.warning(
                    f"Authentication failed for {username} (ApiClient.login returned False)."
                )
                QMessageBox.warning(
                    self,
                    "Ошибка входа",
                    "Неверное имя пользователя или пароль, или не удалось получить данные пользователя.",
                )
                self.password_input.clear()
                self.password_input.setFocus()

        # Обрабатываем специфичные ошибки API клиента
        except ApiConnectionError as e:
            logger.error(f"Login failed: {e}")
            QMessageBox.critical(
                self,
                "Ошибка сети",
                f"{e.message}\nПроверьте запуск сервера и сетевое соединение.",
            )
        except ApiTimeoutError as e:
            logger.error(f"Login failed: {e}")
            QMessageBox.warning(
                self,
                "Таймаут",
                f"{e.message}\nСервер не ответил вовремя. Попробуйте позже.",
            )
        except ApiHttpError as e:
            logger.error(f"Login failed: {e}")
            QMessageBox.critical(
                self,
                f"Ошибка сервера ({e.status_code})",
                f"Сервер вернул ошибку:\n{e.message}",
            )
        except ApiClientError as e:
            logger.exception(f"API Client Error during login: {e}")
            QMessageBox.critical(
                self,
                "Ошибка API",
                f"Произошла ошибка при обращении к API:\n{e.message}",
            )
        except Exception as e:
            logger.exception("An unexpected error occurred during login handling.")
            QMessageBox.critical(
                self, "Неизвестная ошибка", f"Произошла непредвиденная ошибка:\n{e}"
            )
        finally:

            if not self.result() == QDialog.DialogCode.Accepted:
                self.setEnabled(True)
