import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QComboBox,
)
from PyQt6.QtCore import Qt
from typing import Optional, Dict, List

from utils.api_client import ApiClient, ApiClientError, ApiHttpError

logger = logging.getLogger("KindergartenApp")


class GroupDialog(QDialog):
    def __init__(
        self, api_client: ApiClient, group_data: Optional[Dict] = None, parent=None
    ):
        """
        Диалог для добавления или редактирования группы.
        :param api_client: Экземпляр API клиента.
        :param group_data: Словарь с данными группы для редактирования (None для добавления).
        :param parent: Родительский виджет.
        """
        super().__init__(parent)
        self.api_client = api_client
        self.group_data = group_data
        self.is_edit_mode = group_data is not None

        self.setWindowTitle(
            "Редактирование группы" if self.is_edit_mode else "Добавление группы"
        )
        self.setMinimumWidth(400)
        self.setModal(True)

        self.teachers: List[Dict] = []

        self.initUI()
        self.load_teachers()
        logger.debug(
            f"GroupDialog initialized in {'edit' if self.is_edit_mode else 'add'} mode."
        )

    def initUI(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setMaxLength(100)
        form_layout.addRow("Название группы (*):", self.name_input)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText(
            "Краткое описание группы (необязательно)"
        )
        self.description_input.setFixedHeight(80)
        form_layout.addRow("Описание:", self.description_input)

        # --- Параметры группы ---
        params_layout = QHBoxLayout()
        self.age_min_spin = QSpinBox()
        self.age_min_spin.setRange(0, 18)
        self.age_min_spin.setPrefix("Возраст от: ")
        self.age_max_spin = QSpinBox()
        self.age_max_spin.setRange(0, 18)
        self.age_max_spin.setPrefix(" до: ")
        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(1, 100)
        self.capacity_spin.setPrefix(" Мест: ")

        params_layout.addWidget(self.age_min_spin)
        params_layout.addWidget(self.age_max_spin)
        params_layout.addStretch()
        params_layout.addWidget(self.capacity_spin)
        form_layout.addRow("Параметры:", params_layout)

        # --- Выбор учителя ---
        self.teacher_combo = QComboBox()
        self.teacher_combo.addItem("Загрузка...", None)
        self.teacher_combo.setEnabled(False)
        form_layout.addRow("Воспитатель:", self.teacher_combo)

        main_layout.addLayout(form_layout)

        # --- Кнопки OK/Cancel ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def load_teachers(self):
        """Загружает список учителей из API и заполняет ComboBox."""
        logger.info("Loading teachers list...")
        self.teacher_combo.clear()
        self.teacher_combo.addItem(
            "Не назначен", None
        )  # Всегда есть опция "Не назначен"
        self.teacher_combo.setEnabled(False)
        load_successful = False

        try:
            self.teachers = self.api_client.get_teachers()
            if self.teachers:
                self.teachers.sort(key=lambda t: t.get("full_name", ""))
                for teacher in self.teachers:
                    display_text = f"{teacher.get('full_name', 'Без имени')} (ID: {teacher.get('id')})"
                    teacher_id = teacher.get("id")
                    if teacher_id is not None:
                        self.teacher_combo.addItem(display_text, teacher_id)
                logger.info(f"Loaded {len(self.teachers)} teachers.")
                load_successful = True
            else:
                logger.info("No teachers loaded (empty list or access denied).")
                load_successful = True

        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load teachers list.")
            self.teacher_combo.addItem("Ошибка загрузки", None)

        finally:
            self.teacher_combo.setEnabled(True)

            if self.is_edit_mode:
                logger.debug("Populating fields after teacher load attempt.")
                self.populate_fields()

    def populate_fields(self):
        """Заполняет поля данными существующей группы."""
        if not self.group_data:
            logger.warning("populate_fields called but no group_data available.")
            return
        self.name_input.setText(self.group_data.get("name", ""))
        self.description_input.setPlainText(self.group_data.get("description", ""))
        self.age_min_spin.setValue(self.group_data.get("age_min", 0))
        self.age_max_spin.setValue(self.group_data.get("age_max", 0))
        self.capacity_spin.setValue(self.group_data.get("capacity", 1))

        self.select_current_teacher()

    def select_current_teacher(self):
        """Выбирает текущего учителя группы в ComboBox."""
        if (
            not self.is_edit_mode
            or not self.group_data
            or not self.teacher_combo.isEnabled()
        ):
            logger.debug("Skipping teacher selection: combo disabled or no group data.")
            if self.teacher_combo.count() > 0:
                self.teacher_combo.setCurrentIndex(0)
            return

        teacher_id = self.group_data.get("teacher_id")
        if teacher_id is not None:
            index = self.teacher_combo.findData(teacher_id)
            if index >= 0:
                self.teacher_combo.setCurrentIndex(index)
                logger.debug(f"Selected teacher with ID {teacher_id} at index {index}.")
            else:
                logger.warning(
                    f"Teacher ID {teacher_id} from group data not found in current teacher list."
                )
                self.teacher_combo.setCurrentIndex(0)
        else:
            self.teacher_combo.setCurrentIndex(0)

    def accept_data(self):
        """Проверяет и отправляет данные на сервер."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Ошибка ввода", "Название группы не может быть пустым."
            )
            return

        age_min = self.age_min_spin.value()
        age_max = self.age_max_spin.value()
        if age_min > age_max:
            QMessageBox.warning(
                self,
                "Ошибка ввода",
                "Минимальный возраст не может быть больше максимального.",
            )
            return

        selected_teacher_id = self.teacher_combo.currentData()

        # Собираем данные для отправки
        data_to_send = {
            "name": name,
            "description": self.description_input.toPlainText().strip(),
            "age_min": age_min,
            "age_max": age_max,
            "capacity": self.capacity_spin.value(),
            "teacher_id": selected_teacher_id,
        }

        self.setEnabled(False)

        try:
            if self.is_edit_mode:
                # Редактирование существующей
                group_id = self.group_data.get("id")
                if not group_id:
                    raise ValueError("Group ID is missing for editing.")

                updated_group = self.api_client.update_group(group_id, data_to_send)
                logger.info(f"Group {group_id} updated successfully.")
            else:
                # Создание новой
                created_group = self.api_client.create_group(data_to_send)
                logger.info(
                    f"Group '{created_group.get('name')}' created successfully with ID {created_group.get('id')}."
                )

            self.accept()

        except (ApiHttpError, ApiClientError, Exception) as e:

            error_message = str(e)
            status_code = getattr(e, "status_code", "N/A")
            logger.error(
                f"API Error during group save: {error_message}",
                exc_info=isinstance(e, Exception) and not isinstance(e, ApiClientError),
            )
            QMessageBox.warning(
                self,
                f"Ошибка API ({status_code})",
                f"Не удалось сохранить группу:\n{error_message}",
            )
            self.setEnabled(True)
