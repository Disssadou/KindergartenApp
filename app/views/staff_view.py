import logging
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QAbstractItemView,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QLabel,
    QComboBox,
    QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from typing import Optional, Dict, List

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


try:
    from database.schemas import UserRole
except ImportError:
    print(
        "ERROR in staff_view.py: Could not import UserRole from schemas! Using fallback."
    )

    class UserRole:
        ADMIN = "admin"
        TEACHER = "teacher"
        PARENT = "parent"


from app.dialogs.user_dialog import UserDialog


logger = logging.getLogger("KindergartenApp")


class StaffView(QWidget):
    status_changed = pyqtSignal(str)

    # Словарь для отображения ролей в QComboBox
    ROLE_FILTER_MAP = {
        "Все роли": None,
        "Администраторы": UserRole.ADMIN,
        "Воспитатели": UserRole.TEACHER,
        "Родители": UserRole.PARENT,
    }

    ROLE_DISPLAY_MAP = {v.value: k for k, v in ROLE_FILTER_MAP.items() if v is not None}

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.users_data = []

        self.initUI()
        self.load_users()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Верхняя панель ---
        top_bar_layout = QHBoxLayout()
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фильтр по роли:"))
        self.role_filter_combo = QComboBox()

        self.role_filter_combo.addItems(self.ROLE_FILTER_MAP.keys())
        self.role_filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.role_filter_combo)
        filter_layout.addStretch()

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.clicked.connect(self.load_users)
        self.add_button = QPushButton("Добавить")
        self.add_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_button.clicked.connect(self.add_user)
        self.edit_button = QPushButton("Редактировать")
        self.edit_button.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_button.clicked.connect(self.edit_user)
        self.edit_button.setEnabled(False)
        self.delete_button = QPushButton("Удалить")
        self.delete_button.setIcon(QIcon.fromTheme("list-remove"))
        self.delete_button.clicked.connect(self.delete_user)
        self.delete_button.setEnabled(False)

        top_bar_layout.addLayout(filter_layout)
        top_bar_layout.addWidget(self.refresh_button)
        top_bar_layout.addWidget(self.add_button)
        top_bar_layout.addWidget(self.edit_button)
        top_bar_layout.addWidget(self.delete_button)
        main_layout.addLayout(top_bar_layout)

        # --- Таблица ---
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(
            ["ID", "Логин", "ФИО", "Email", "Телефон", "Роль"]
        )

        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )  # ID
        self.table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )  # Username
        self.table_widget.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )  # Full Name
        self.table_widget.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Interactive
        )  # Email
        self.table_widget.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.Interactive
        )  # Phone
        self.table_widget.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )  # Role
        self.table_widget.setSortingEnabled(True)
        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)

        main_layout.addWidget(self.table_widget)
        self.setLayout(main_layout)

    def on_filter_changed(self):
        self.load_users()

    def load_users(self):
        selected_role_text = self.role_filter_combo.currentText()

        role_enum = self.ROLE_FILTER_MAP.get(selected_role_text)

        role_value = role_enum.value if role_enum else None

        self.status_changed.emit(
            f"Загрузка пользователей (Роль: {selected_role_text})..."
        )
        self.table_widget.setRowCount(0)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        try:

            self.users_data = self.api_client.get_users(role=role_value, limit=200)
            self.populate_table()
            self.status_changed.emit(f"Загружено {len(self.users_data)} пользователей.")
            logger.info(
                f"Successfully loaded {len(self.users_data)} users (filter: {role_value})."
            )
        except ApiHttpError as e:
            if e.status_code == 403:
                logger.warning("Access denied to load users list (403 Forbidden).")
                self.users_data = []
                self.populate_table()
                self.status_changed.emit("Доступ к списку запрещен.")
                QMessageBox.warning(
                    self,
                    "Доступ запрещен",
                    "Недостаточно прав для просмотра списка пользователей.",
                )
            else:
                logger.exception("Failed to load users from API.")
                QMessageBox.critical(
                    self, "Ошибка загрузки", f"Не удалось загрузить список:\n{e}"
                )
                self.status_changed.emit("Ошибка загрузки пользователей.")
        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load users from API.")
            QMessageBox.critical(
                self, "Ошибка загрузки", f"Не удалось загрузить список:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки пользователей.")

    def populate_table(self):
        self.table_widget.setRowCount(len(self.users_data))
        self.table_widget.setSortingEnabled(False)
        for row, user in enumerate(self.users_data):
            user_id = user.get("id")
            role_value = user.get("role")

            role_display = self.ROLE_DISPLAY_MAP.get(role_value, role_value)

            id_item = QTableWidgetItem(str(user_id))
            id_item.setData(Qt.ItemDataRole.UserRole, user_id)
            username_item = QTableWidgetItem(user.get("username", ""))
            fullname_item = QTableWidgetItem(user.get("full_name", ""))
            email_item = QTableWidgetItem(user.get("email", ""))
            phone_item = QTableWidgetItem(user.get("phone", ""))
            role_item = QTableWidgetItem(role_display)

            self.table_widget.setItem(row, 0, id_item)
            self.table_widget.setItem(row, 1, username_item)
            self.table_widget.setItem(row, 2, fullname_item)
            self.table_widget.setItem(row, 3, email_item)
            self.table_widget.setItem(row, 4, phone_item)
            self.table_widget.setItem(row, 5, role_item)
        self.table_widget.setSortingEnabled(True)

    def on_selection_changed(self):
        is_selected = bool(self.table_widget.selectionModel().selectedRows())

        self.edit_button.setEnabled(is_selected)
        self.delete_button.setEnabled(is_selected)

    def get_selected_user_id(self) -> Optional[int]:
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            return selected_items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def get_user_data_by_id(self, user_id: int) -> Optional[Dict]:
        for user in self.users_data:
            if user.get("id") == user_id:
                return user
        return None

    def add_user(self):
        dialog = UserDialog(api_client=self.api_client, parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("User added dialog accepted. Refreshing list.")
            self.load_users()
            self.status_changed.emit("Пользователь успешно добавлен.")
        else:
            logger.debug("User add dialog cancelled.")

    def edit_user(self):
        selected_id = self.get_selected_user_id()
        if selected_id is None:
            return
        self.status_changed.emit(f"Загрузка данных пользователя ID {selected_id}...")
        try:
            user_data = self.api_client.get_user(selected_id)
            self.status_changed.emit(f"Данные пользователя ID {selected_id} загружены.")
        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to load user data for editing id={selected_id}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить данные:\n{e}")
            self.status_changed.emit("Ошибка загрузки данных пользователя.")
            return
        if not user_data:
            logger.error(
                f"Could not find user data for selected id {selected_id} after API call"
            )
            QMessageBox.warning(
                self, "Ошибка", "Не найдены данные для выбранного пользователя."
            )
            return

        dialog = UserDialog(
            api_client=self.api_client, user_data=user_data, parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info(f"User {selected_id} edit dialog accepted. Refreshing list.")
            self.load_users()
            self.status_changed.emit(f"Пользователь ID {selected_id} успешно обновлен.")
        else:
            logger.debug(f"User {selected_id} edit dialog cancelled.")

    def delete_user(self):
        selected_id = self.get_selected_user_id()
        if selected_id is None:
            return
        user_data = self.get_user_data_by_id(selected_id)
        user_display = (
            user_data.get("username", f"ID {selected_id}")
            if user_data
            else f"ID {selected_id}"
        )

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить пользователя '{user_display}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.status_changed.emit(f"Удаление пользователя '{user_display}'...")
            try:
                success = self.api_client.delete_user(selected_id)
                if success:
                    logger.info(
                        f"User {selected_id} ('{user_display}') deleted successfully."
                    )
                    QMessageBox.information(
                        self,
                        "Удалено",
                        f"Пользователь '{user_display}' успешно удален.",
                    )
                    self.load_users()
                    self.status_changed.emit(f"Пользователь '{user_display}' удален.")
                else:
                    QMessageBox.warning(
                        self,
                        "Ошибка удаления",
                        f"Не удалось удалить пользователя '{user_display}'.",
                    )
                    self.status_changed.emit(
                        f"Ошибка удаления пользователя '{user_display}'."
                    )
            except (ApiClientError, Exception) as e:
                logger.exception(
                    f"Failed to delete user {selected_id} ('{user_display}')."
                )
                QMessageBox.critical(
                    self,
                    "Ошибка удаления",
                    f"Не удалось удалить '{user_display}':\n{e}",
                )
                self.status_changed.emit(
                    f"Ошибка удаления пользователя '{user_display}'."
                )
