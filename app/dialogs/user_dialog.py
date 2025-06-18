import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QComboBox,
)
from PyQt6.QtCore import Qt
from typing import Optional, Dict


from utils.api_client import ApiClient, ApiClientError, ApiHttpError

try:

    from database.schemas import UserRole
except ImportError:
    print(
        "ERROR in user_dialog.py: Could not import UserRole from schemas! Using fallback strings."
    )

    class UserRole:
        ADMIN = "admin"
        TEACHER = "teacher"
        PARENT = "parent"

        @property
        def value(self):
            return self


logger = logging.getLogger("KindergartenApp")


class UserDialog(QDialog):

    ROLE_MAP = {
        "Администратор": UserRole.ADMIN,
        "Воспитатель": UserRole.TEACHER,
        "Родитель": UserRole.PARENT,
    }

    def __init__(
        self, api_client: ApiClient, user_data: Optional[Dict] = None, parent=None
    ):
        """
        Диалог для добавления или редактирования пользователя.

        Args:
            api_client: Экземпляр API клиента.
            user_data: Словарь с данными пользователя для редактирования (None для добавления).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self.api_client = api_client
        self.user_data = user_data

        self.is_edit_mode = self.user_data is not None

        self.setWindowTitle(
            "Редактирование пользователя"
            if self.is_edit_mode
            else "Добавление пользователя"
        )
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.initUI()

        # Если режим редактирования, заполняем поля
        if self.is_edit_mode:
            self.populate_fields()

        logger.debug(
            f"UserDialog initialized in {'edit' if self.is_edit_mode else 'add'} mode."
        )

    def initUI(self):
        """Создает элементы интерфейса диалога."""
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)  # Метки справа
        # --- Поля ввода ---
        self.username_input = QLineEdit()
        self.username_input.setMaxLength(50)
        # Имя пользователя нельзя редактировать после создания
        self.username_input.setReadOnly(self.is_edit_mode)
        self.username_input.setToolTip(
            "Имя пользователя (логин). Нельзя изменить после создания."
            if self.is_edit_mode
            else "Имя пользователя (логин)."
        )
        form_layout.addRow("Имя пользователя (*):", self.username_input)

        self.fullname_input = QLineEdit()
        self.fullname_input.setMaxLength(100)
        form_layout.addRow("Полное имя (*):", self.fullname_input)

        self.email_input = QLineEdit()
        self.email_input.setMaxLength(100)
        form_layout.addRow("Email (*):", self.email_input)

        self.phone_input = QLineEdit()
        self.phone_input.setMaxLength(20)
        self.phone_input.setPlaceholderText("Необязательно")
        form_layout.addRow("Телефон:", self.phone_input)

        # --- Поля пароля (только для добавления) ---
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Минимум 6 символов")

        self.password_confirm_input = QLineEdit()
        self.password_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_confirm_input.setPlaceholderText("Повторите пароль")

        if not self.is_edit_mode:
            form_layout.addRow("Пароль (*):", self.password_input)
            form_layout.addRow("Подтвердите пароль (*):", self.password_confirm_input)

        # --- Выбор роли ---
        self.role_combo = QComboBox()
        for display_name in self.ROLE_MAP.keys():
            self.role_combo.addItem(display_name)

        self.role_combo.setEnabled(not self.is_edit_mode)
        self.role_combo.setToolTip(
            "Роль задается при создании и не меняется здесь."
            if self.is_edit_mode
            else "Выберите роль пользователя."
        )
        form_layout.addRow("Роль (*):", self.role_combo)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()
        # --- Кнопки OK/Cancel ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def populate_fields(self):
        """Заполняет поля данными существующего пользователя (для режима редактирования)."""
        if not self.user_data:
            return

        self.username_input.setText(self.user_data.get("username", ""))
        self.fullname_input.setText(self.user_data.get("full_name", ""))
        self.email_input.setText(self.user_data.get("email", ""))
        self.phone_input.setText(self.user_data.get("phone", ""))

        # Устанавливаем выбранную роль в комбобоксе
        current_role_value = self.user_data.get("role")
        found_role = False
        for display_name, role_enum in self.ROLE_MAP.items():
            if role_enum.value == current_role_value:
                self.role_combo.setCurrentText(display_name)
                found_role = True
                break
        if not found_role:
            logger.warning(
                f"Could not find display name for role '{current_role_value}' in ROLE_MAP."
            )

    def accept_data(self):
        """Проверяет введенные данные и отправляет запрос на сервер."""

        username = self.username_input.text().strip()
        full_name = self.fullname_input.text().strip()
        email = self.email_input.text().strip()
        phone = self.phone_input.text().strip() or None
        if not username or not full_name or not email:
            QMessageBox.warning(
                self,
                "Ошибка ввода",
                "Имя пользователя, Полное имя и Email обязательны для заполнения.",
            )
            return

        if "@" not in email or "." not in email.split("@")[-1]:
            QMessageBox.warning(self, "Ошибка ввода", "Введите корректный Email адрес.")
            return

        # Собираем данные для API
        data_to_send = {
            "username": username,
            "full_name": full_name,
            "email": email,
            "phone": phone,
        }

        # Добавляем пароль и роль только при создании
        if not self.is_edit_mode:
            password = self.password_input.text()
            password_confirm = self.password_confirm_input.text()

            if len(password) < 6:
                QMessageBox.warning(
                    self, "Ошибка ввода", "Пароль должен быть не менее 6 символов."
                )
                return
            if password != password_confirm:
                QMessageBox.warning(self, "Ошибка ввода", "Пароли не совпадают.")
                return

            # Получаем выбранную роль из комбобокса
            selected_role_text = self.role_combo.currentText()
            role_enum = self.ROLE_MAP.get(selected_role_text)
            if (
                role_enum is None
            ):  # Должно быть выбрано что-то кроме "Все роли" (если бы оно там было)
                QMessageBox.warning(
                    self, "Ошибка ввода", "Выберите корректную роль пользователя."
                )
                return

            data_to_send["password"] = password
            data_to_send["role"] = role_enum.value
        # --- Отправка запроса на сервер ---
        self.setEnabled(False)
        try:
            if self.is_edit_mode:
                user_id = self.user_data.get("id")
                if not user_id:
                    raise ValueError("User ID missing for editing.")

                update_payload = {
                    k: v
                    for k, v in data_to_send.items()
                    if k in ["full_name", "email", "phone"]
                }
                logger.debug(f"Updating user {user_id} with data: {update_payload}")
                updated_user = self.api_client.update_user(user_id, update_payload)
                logger.info(f"User {user_id} updated successfully.")
            else:

                logger.debug(
                    f"Creating new user with data: { {k:v for k,v in data_to_send.items() if k != 'password'} }"
                )
                created_user = self.api_client.create_user(data_to_send)
                logger.info(
                    f"User '{created_user.get('username')}' created successfully with ID {created_user.get('id')}."
                )

            self.accept()

        except ApiHttpError as e:
            logger.error(f"API HTTP Error during user save: {e}")

            QMessageBox.warning(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось сохранить пользователя:\n{e.message}",
            )
            self.setEnabled(True)
        except (ApiClientError, Exception) as e:
            logger.exception("Error saving user.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить пользователя:\n{e}"
            )
            self.setEnabled(True)
