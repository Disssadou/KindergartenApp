# app/dialogs/manage_parents_dialog.py

import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QComboBox,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QSplitter,
    QGroupBox,  # Добавляем QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon  # Для иконок кнопок
from typing import Optional, Dict, List, Set

from utils.api_client import ApiClient, ApiClientError, ApiHttpError

# Импортируем UserRole
try:
    from database.schemas import UserRole
except ImportError:

    class UserRole:
        ADMIN = "admin"
        TEACHER = "teacher"
        PARENT = "parent"
        value = property(lambda self: self)  # Заглушка


logger = logging.getLogger("KindergartenApp")


class ManageParentsDialog(QDialog):
    # Сигнал для обновления строки состояния (если нужно)
    # status_changed = pyqtSignal(str)

    def __init__(
        self, api_client: ApiClient, child_id: int, child_name: str, parent=None
    ):
        super().__init__(parent)
        self.api_client = api_client
        self.child_id = child_id
        self.child_name = child_name

        # Данные
        self.linked_parents_data: List[Dict] = []  # Список словарей ChildParentRead
        self.all_parents_data: List[Dict] = (
            []
        )  # Список словарей UserRead (только родители)

        self.setWindowTitle(
            f"Родители ребенка: {self.child_name} (ID: {self.child_id})"
        )
        self.setMinimumSize(700, 500)  # Сделаем окно побольше
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.initUI()
        self.load_initial_data()  # Загружаем данные при открытии

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # Информация о ребенке сверху
        main_layout.addWidget(
            QLabel(
                f"<b>Управление родителями для:</b> {self.child_name} (ID: {self.child_id})"
            )
        )

        # Разделитель для двух основных панелей
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Левая панель: Привязанные родители ---
        left_groupbox = QGroupBox("Привязанные родители")
        left_layout = QVBoxLayout(left_groupbox)

        self.linked_parents_list = QListWidget()
        self.linked_parents_list.setToolTip(
            "Список родителей, уже связанных с ребенком"
        )
        self.linked_parents_list.itemSelectionChanged.connect(
            self.on_linked_parent_selected
        )  # Активация кнопки "Отвязать"
        left_layout.addWidget(self.linked_parents_list)

        self.unlink_button = QPushButton(
            QIcon.fromTheme("list-remove"), "Отвязать выбранного"
        )
        self.unlink_button.setToolTip(
            "Удалить связь выбранного родителя с этим ребенком"
        )
        self.unlink_button.setEnabled(False)  # Неактивна, пока не выбран родитель
        self.unlink_button.clicked.connect(self.unlink_parent)
        left_layout.addWidget(self.unlink_button)

        # --- Правая панель: Добавление нового родителя ---
        right_groupbox = QGroupBox("Добавить родителя")
        right_layout = QVBoxLayout(right_groupbox)
        add_form_layout = QFormLayout()

        self.available_parents_combo = QComboBox()
        self.available_parents_combo.setToolTip(
            "Выберите родителя из списка для привязки"
        )
        self.available_parents_combo.addItem(
            "Выберите родителя...", None
        )  # Пункт по умолчанию
        add_form_layout.addRow("Родитель:", self.available_parents_combo)

        self.relation_type_input = QLineEdit()
        self.relation_type_input.setPlaceholderText("Например: Мать, Отец, Опекун...")
        self.relation_type_input.setMaxLength(50)
        add_form_layout.addRow("Тип родства (*):", self.relation_type_input)

        right_layout.addLayout(add_form_layout)

        self.link_button = QPushButton(
            QIcon.fromTheme("list-add"), "Привязать родителя"
        )
        self.link_button.setToolTip("Установить связь выбранного родителя с ребенком")
        self.link_button.clicked.connect(self.link_parent)
        # Активируем кнопку, только если выбран родитель и введен тип родства
        self.link_button.setEnabled(False)
        self.available_parents_combo.currentIndexChanged.connect(
            self.update_link_button_state
        )
        self.relation_type_input.textChanged.connect(self.update_link_button_state)

        right_layout.addWidget(
            self.link_button, 0, Qt.AlignmentFlag.AlignRight
        )  # Кнопка справа
        right_layout.addStretch()  # Распорка вниз

        # Добавляем панели в разделитель
        splitter.addWidget(left_groupbox)
        splitter.addWidget(right_groupbox)
        splitter.setSizes([350, 350])  # Начальные размеры панелей

        main_layout.addWidget(splitter)

        # --- Кнопка Закрыть ---
        # Используем стандартный Rejected для закрытия
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def update_link_button_state(self):
        """Активирует кнопку 'Привязать', если выбран родитель и введен тип родства."""
        parent_selected = self.available_parents_combo.currentData() is not None
        relation_entered = bool(self.relation_type_input.text().strip())
        self.link_button.setEnabled(parent_selected and relation_entered)

    def on_linked_parent_selected(self):
        """Активирует кнопку 'Отвязать'."""
        self.unlink_button.setEnabled(bool(self.linked_parents_list.selectedItems()))

    def load_initial_data(self):
        """Загружает список всех родителей и привязанных к этому ребенку."""
        logger.info(f"Loading parents data for child {self.child_id}...")

        self.setEnabled(False)
        try:
            # 1. Загружаем ВСЕХ пользователей с ролью parent
            self.all_parents_data = self.api_client.get_users(
                role=UserRole.PARENT.value, limit=200
            )
            logger.debug(f"Loaded {len(self.all_parents_data)} total parents.")

            # 2. Загружаем УЖЕ ПРИВЯЗАННЫХ родителей к ЭТОМУ ребенку
            self.linked_parents_data = self.api_client.get_child_parents(self.child_id)
            logger.debug(
                f"Loaded {len(self.linked_parents_data)} linked parents for child {self.child_id}."
            )

            # 3. Обновляем UI
            self.update_linked_parents_list()
            self.update_available_parents_combo()

        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load parents data.")
            QMessageBox.critical(
                self, "Ошибка загрузки", f"Не удалось загрузить данные родителей:\n{e}"
            )

        finally:
            self.setEnabled(True)

    def update_linked_parents_list(self):
        """Обновляет список привязанных родителей."""
        self.linked_parents_list.clear()
        self.unlink_button.setEnabled(False)
        linked_parent_ids = set()

        # Сортируем по ФИО родителя
        self.linked_parents_data.sort(
            key=lambda link: link.get("parent", {}).get("full_name", "")
        )

        for link_data in self.linked_parents_data:
            parent_info = link_data.get("parent")
            if not parent_info:
                continue
            parent_id = parent_info.get("id")
            parent_name = parent_info.get("full_name", f"ID:{parent_id}")
            relation = link_data.get("relation_type", "Не указано")
            display_text = f"{parent_name} ({relation})"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, parent_id)
            self.linked_parents_list.addItem(item)
            if parent_id:
                linked_parent_ids.add(parent_id)

        return linked_parent_ids

    def update_available_parents_combo(self):
        """Обновляет комбобокс доступных родителей (все минус привязанные)."""
        self.available_parents_combo.clear()
        self.available_parents_combo.addItem("Выберите родителя...", None)

        linked_parent_ids = {
            link.get("parent", {}).get("id")
            for link in self.linked_parents_data
            if link.get("parent")
        }

        # Сортируем всех родителей
        self.all_parents_data.sort(key=lambda p: p.get("full_name", ""))

        count = 0
        for parent_data in self.all_parents_data:
            parent_id = parent_data.get("id")

            if parent_id and parent_id not in linked_parent_ids:
                display_text = (
                    f"{parent_data.get('full_name', 'Без имени')} (ID: {parent_id})"
                )
                self.available_parents_combo.addItem(display_text, parent_id)
                count += 1
        logger.debug(f"Populated available parents combo with {count} users.")
        self.update_link_button_state()

    def link_parent(self):
        """Привязывает выбранного родителя к ребенку."""
        selected_parent_id = self.available_parents_combo.currentData()
        relation_type = self.relation_type_input.text().strip()

        if selected_parent_id is None:
            QMessageBox.warning(
                self, "Ошибка", "Пожалуйста, выберите родителя из списка."
            )
            return
        if not relation_type:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, укажите тип родства.")
            return

        logger.info(
            f"Attempting to link parent {selected_parent_id} to child {self.child_id} as '{relation_type}'"
        )
        self.setEnabled(False)
        try:

            new_link = self.api_client.add_parent_to_child(
                self.child_id, selected_parent_id, relation_type
            )

            self.linked_parents_data.append(new_link)

            self.update_linked_parents_list()
            self.update_available_parents_combo()
            self.relation_type_input.clear()
            logger.info("Parent linked successfully.")

        except (ApiClientError, Exception) as e:
            logger.exception("Failed to link parent.")
            QMessageBox.critical(
                self, "Ошибка привязки", f"Не удалось привязать родителя:\n{e}"
            )
        finally:
            self.setEnabled(True)

    def unlink_parent(self):
        """Отвязывает выбранного родителя."""
        selected_items = self.linked_parents_list.selectedItems()
        if not selected_items:
            return

        selected_item = selected_items[0]
        parent_id = selected_item.data(Qt.ItemDataRole.UserRole)
        display_text = selected_item.text()  

        if parent_id is None:
            return  

        reply = QMessageBox.question(
            self,
            "Подтверждение отвязки",
            f"Вы уверены, что хотите отвязать родителя\n'{display_text}'\nот этого ребенка?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info(
                f"Attempting to unlink parent {parent_id} from child {self.child_id}"
            )
            self.setEnabled(False)
            try:
                success = self.api_client.remove_parent_from_child(
                    self.child_id, parent_id
                )
                if success:
                    logger.info("Parent unlinked successfully.")
                    
                    self.linked_parents_data = [
                        link
                        for link in self.linked_parents_data
                        if link.get("parent", {}).get("id") != parent_id
                    ]
                    
                    self.update_linked_parents_list()
                    self.update_available_parents_combo()
                    
                else:
                    
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        "Не удалось отвязать родителя (возможно, связь уже удалена).",
                    )

            except (ApiClientError, Exception) as e:
                logger.exception("Failed to unlink parent.")
                QMessageBox.critical(
                    self, "Ошибка отвязки", f"Не удалось отвязать родителя:\n{e}"
                )
            finally:
                self.setEnabled(True)
