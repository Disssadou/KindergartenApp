import logging
from typing import Dict, Optional
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
    QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon


from utils.api_client import ApiClient, ApiClientError, ApiHttpError
from app.dialogs.group_dialog import GroupDialog

logger = logging.getLogger("KindergartenApp")


class GroupsView(QWidget):

    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.groups_data = []

        self.initUI()
        self.load_groups()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Верхняя панель с кнопками ---
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.refresh_button = QPushButton(QIcon(), "Обновить")
        self.refresh_button.setToolTip("Обновить список групп")
        self.refresh_button.clicked.connect(self.load_groups)

        self.add_button = QPushButton(QIcon(), "Добавить группу")
        self.add_button.setToolTip("Создать новую группу")
        self.add_button.clicked.connect(self.add_group)

        self.edit_button = QPushButton(QIcon(), "Редактировать")
        self.edit_button.setToolTip("Изменить выбранную группу")
        self.edit_button.clicked.connect(self.edit_group)
        self.edit_button.setEnabled(False)

        self.delete_button = QPushButton(QIcon(), "Удалить")
        self.delete_button.setToolTip("Удалить выбранную группу")
        self.delete_button.clicked.connect(self.delete_group)
        self.delete_button.setEnabled(False)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        main_layout.addLayout(button_layout)

        # --- Таблица для отображения групп ---
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(
            6
        )  # ID, Name, Desc, Teacher ID, Capacity, Ages
        self.table_widget.setHorizontalHeaderLabels(
            ["ID", "Название", "Описание", "ID Учителя", "Мест", "Возраст"]
        )

        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table_widget.horizontalHeader().setStretchLastSection(True)

        self.table_widget.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )  # ID
        self.table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Interactive
        )  # Name
        self.table_widget.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.ResizeToContents
        )  # Teacher ID
        self.table_widget.horizontalHeader().setSectionResizeMode(
            4, QHeaderView.ResizeMode.ResizeToContents
        )  # Capacity
        self.table_widget.horizontalHeader().setSectionResizeMode(
            5, QHeaderView.ResizeMode.ResizeToContents
        )  # Ages
        self.table_widget.setSortingEnabled(True)

        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)

        main_layout.addWidget(self.table_widget)
        self.setLayout(main_layout)

    def load_groups(self):
        """Загружает список групп из API и заполняет таблицу."""
        self.status_changed.emit("Загрузка списка групп...")
        self.table_widget.setRowCount(0)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        try:
            self.groups_data = self.api_client.get_groups(limit=1000)
            self.populate_table()
            self.status_changed.emit(f"Загружено {len(self.groups_data)} групп.")
            logger.info(f"Successfully loaded {len(self.groups_data)} groups.")
        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load groups from API.")
            QMessageBox.critical(
                self, "Ошибка загрузки", f"Не удалось загрузить список групп:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки групп.")

    def populate_table(self):
        """Заполняет таблицу данными из self.groups_data."""
        self.table_widget.setRowCount(len(self.groups_data))
        self.table_widget.setSortingEnabled(False)
        for row, group in enumerate(self.groups_data):
            id_item = QTableWidgetItem(str(group.get("id", "")))

            id_item.setData(Qt.ItemDataRole.UserRole, group.get("id"))
            name_item = QTableWidgetItem(group.get("name", ""))
            desc_item = QTableWidgetItem(group.get("description", ""))
            teacher_id_item = QTableWidgetItem(
                str(group.get("teacher_id", "")) if group.get("teacher_id") else ""
            )
            capacity_item = QTableWidgetItem(
                str(group.get("capacity", "")) if group.get("capacity") else ""
            )
            age_range = (
                f"{group.get('age_min', '?')}-{group.get('age_max', '?')}"
                if group.get("age_min") is not None
                else ""
            )
            age_item = QTableWidgetItem(age_range)

            self.table_widget.setItem(row, 0, id_item)
            self.table_widget.setItem(row, 1, name_item)
            self.table_widget.setItem(row, 2, desc_item)
            self.table_widget.setItem(row, 3, teacher_id_item)
            self.table_widget.setItem(row, 4, capacity_item)
            self.table_widget.setItem(row, 5, age_item)

        self.table_widget.setSortingEnabled(True)

    def on_selection_changed(self):
        """Активирует/деактивирует кнопки при изменении выбора в таблице."""
        selected_rows = self.table_widget.selectionModel().selectedRows()
        is_selected = bool(selected_rows)
        self.edit_button.setEnabled(is_selected)
        self.delete_button.setEnabled(is_selected)

    def get_selected_group_id(self) -> Optional[int]:
        """Возвращает ID выбранной группы или None."""
        selected_items = self.table_widget.selectedItems()
        if selected_items:

            return selected_items[0].data(Qt.ItemDataRole.UserRole)
        return None

    def get_group_data_by_id(self, group_id: int) -> Optional[Dict]:
        """Находит данные группы по ID в self.groups_data."""
        for group in self.groups_data:
            if group.get("id") == group_id:
                return group
        return None

    def add_group(self):
        """Открывает диалог добавления новой группы."""
        dialog = GroupDialog(api_client=self.api_client, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Group added/updated dialog accepted. Refreshing list.")
            self.load_groups()
            self.status_changed.emit("Группа успешно добавлена.")
        else:
            logger.debug("Group add dialog cancelled.")

    def edit_group(self):
        """Открывает диалог редактирования выбранной группы."""
        selected_id = self.get_selected_group_id()
        if selected_id is None:
            return

        group_data = self.get_group_data_by_id(selected_id)
        if not group_data:
            logger.error(f"Could not find group data for selected id {selected_id}")
            QMessageBox.warning(
                self, "Ошибка", "Не найдены данные для выбранной группы."
            )
            return

        dialog = GroupDialog(
            api_client=self.api_client, group_data=group_data, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info(f"Group {selected_id} edit dialog accepted. Refreshing list.")
            self.load_groups()
            self.status_changed.emit(f"Группа ID {selected_id} успешно обновлена.")
        else:
            logger.debug(f"Group {selected_id} edit dialog cancelled.")

    def delete_group(self):
        """Удаляет выбранную группу после подтверждения."""
        selected_id = self.get_selected_group_id()
        if selected_id is None:
            return

        group_data = self.get_group_data_by_id(selected_id)
        group_name = (
            group_data.get("name", f"ID {selected_id}")
            if group_data
            else f"ID {selected_id}"
        )

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить группу '{group_name}'?\nЭто действие необратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_changed.emit(f"Удаление группы '{group_name}'...")
            try:
                success = self.api_client.delete_group(selected_id)
                if success:
                    logger.info(
                        f"Group {selected_id} ('{group_name}') deleted successfully."
                    )
                    QMessageBox.information(
                        self, "Удалено", f"Группа '{group_name}' успешно удалена."
                    )
                    self.load_groups()
                    self.status_changed.emit(f"Группа '{group_name}' удалена.")
                else:

                    QMessageBox.warning(
                        self,
                        "Ошибка удаления",
                        f"Не удалось удалить группу '{group_name}'.",
                    )
                    self.status_changed.emit(f"Ошибка удаления группы '{group_name}'.")

            except (ApiClientError, Exception) as e:
                logger.exception(
                    f"Failed to delete group {selected_id} ('{group_name}')."
                )
                QMessageBox.critical(
                    self,
                    "Ошибка удаления",
                    f"Не удалось удалить группу '{group_name}':\n{e}",
                )
                self.status_changed.emit(f"Ошибка удаления группы '{group_name}'.")
