
import logging
from datetime import date
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,  
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QComboBox,
    QDateEdit,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QDate
from typing import Optional, Dict, List


from utils.api_client import ApiClient, ApiClientError, ApiHttpError



logger = logging.getLogger("KindergartenApp")


class ChildDialog(QDialog):
    def __init__(
        self,
        api_client: ApiClient,
        groups: List[Dict],
        child_data: Optional[Dict] = None,
        parent=None,
    ):
        """
        Диалог для добавления или редактирования ребенка.

        Args:
            api_client: Экземпляр API клиента.
            groups: Список словарей с данными групп [{'id': ..., 'name': ...}, ...].
            child_data: Словарь с данными ребенка для редактирования (None для добавления).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self.api_client = api_client
        self.groups = groups if groups else []  # Убедимся, что это список
        self.child_data = child_data
        self.is_edit_mode = self.child_data is not None

        self.setWindowTitle(
            "Редактирование данных ребенка"
            if self.is_edit_mode
            else "Добавление ребенка"
        )
        self.setMinimumWidth(450)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.initUI()

        if self.is_edit_mode:
            self.populate_fields()

        logger.debug(
            f"ChildDialog initialized in {'edit' if self.is_edit_mode else 'add'} mode."
        )

    def initUI(self):
        """Создает элементы интерфейса диалога."""
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Поля ввода ---
        self.fullname_input = QLineEdit()
        self.fullname_input.setMaxLength(100)
        form_layout.addRow("ФИО (*):", self.fullname_input)

        self.birthdate_edit = QDateEdit()
        self.birthdate_edit.setCalendarPopup(True)
        self.birthdate_edit.setDisplayFormat("dd.MM.yyyy")
        self.birthdate_edit.setDateRange(QDate(2000, 1, 1), QDate.currentDate())
        self.birthdate_edit.setDate(
            QDate.currentDate().addYears(-3)
        )  
        form_layout.addRow("Дата рождения (*):", self.birthdate_edit)

        self.group_combo = QComboBox()
        self.group_combo.addItem(
            "Без группы", None
        )  # Опция "Без группы", ее данные = None
        if self.groups:
            for group in self.groups:  # Заполняем группами, переданными из View
                group_id = group.get("id")
                group_name = group.get("name", f"ID: {group_id}")
                if group_id is not None:
                    self.group_combo.addItem(
                        group_name, group_id
                    )  # Сохраняем ID в данных
        form_layout.addRow("Группа:", self.group_combo)

        self.address_input = QLineEdit()
        self.address_input.setMaxLength(200)
        form_layout.addRow("Адрес:", self.address_input)

        # Используем QPlainTextEdit для многострочного текста
        self.medinfo_input = QPlainTextEdit()
        self.medinfo_input.setPlaceholderText("Особенности здоровья, аллергии и т.п.")
        self.medinfo_input.setFixedHeight(100)  
        form_layout.addRow("Мед. информация:", self.medinfo_input)

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
        self.fullname_input.setFocus()  

    def populate_fields(self):
        """Заполняет поля данными существующего ребенка (для режима редактирования)."""
        if not self.child_data:
            return

        self.fullname_input.setText(self.child_data.get("full_name", ""))
        
        birth_date_str = self.child_data.get("birth_date")
        if birth_date_str:
            try:
                birth_qdate = QDate.fromString(birth_date_str, "yyyy-MM-dd")
                if birth_qdate.isValid():
                    self.birthdate_edit.setDate(birth_qdate)
            except Exception as e:
                logger.error(f"Error parsing birth date '{birth_date_str}': {e}")

        # Группа
        group_id = self.child_data.get("group_id")
        index = (
            self.group_combo.findData(group_id)
            if group_id is not None
            else self.group_combo.findData(None)
        )  # Ищем None для "Без группы"
        if index >= 0:
            self.group_combo.setCurrentIndex(index)
        else:
            logger.warning(f"Group ID {group_id} not found in combo box.")
            self.group_combo.setCurrentIndex(0)  

        self.address_input.setText(self.child_data.get("address", ""))
        self.medinfo_input.setPlainText(self.child_data.get("medical_info", ""))

    def accept_data(self):
        """Проверяет введенные данные и отправляет запрос на сервер."""
        
        full_name = self.fullname_input.text().strip()
        birth_date_q = self.birthdate_edit.date()

        if not full_name:
            QMessageBox.warning(self, "Ошибка ввода", "ФИО ребенка обязательно.")
            return
        if not birth_date_q.isValid():
            QMessageBox.warning(self, "Ошибка ввода", "Некорректная дата рождения.")
            return

        # --- Сбор данных ---
        birth_date_str = birth_date_q.toString("yyyy-MM-dd")
        group_id = self.group_combo.currentData()  
        address = self.address_input.text().strip() or None  
        medical_info = (
            self.medinfo_input.toPlainText().strip() or None
        )  

        # Формируем словарь данных для API
        # Для создания (ChildCreate)
        data_to_send = {
            "full_name": full_name,
            "birth_date": birth_date_str,
            "group_id": group_id,
            "address": address,
            "medical_info": medical_info,
        }
        

        # --- Отправка на сервер ---
        self.setEnabled(False)  
        try:
            if self.is_edit_mode:
                child_id = self.child_data.get("id")
                if not child_id:
                    raise ValueError("Child ID missing for editing.")
                logger.debug(f"Updating child {child_id} with data: {data_to_send}")
                
                updated_child = self.api_client.update_child(child_id, data_to_send)
                logger.info(f"Child {child_id} updated successfully.")
            else:
                
                logger.debug(f"Creating new child with data: {data_to_send}")
                
                created_child = self.api_client.create_child(data_to_send)
                logger.info(
                    f"Child '{created_child.get('full_name')}' created. ID: {created_child.get('id')}."
                )

            self.accept()  

        except ApiHttpError as e:
            logger.error(f"API HTTP Error during child save: {e}")
            QMessageBox.warning(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось сохранить данные ребенка:\n{e.message}",
            )
            self.setEnabled(True) 
        except (ApiClientError, Exception) as e:
            logger.exception("Error saving child.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить данные ребенка:\n{e}"
            )
            self.setEnabled(True)  
