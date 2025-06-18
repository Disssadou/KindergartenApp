import logging
import enum
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QWidget,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, QTimer  
from typing import Optional, Dict

# Импортируем зависимости
from utils.api_client import ApiClient, ApiClientError, ApiHttpError

try:
    from database.models import AbsenceType
except ImportError:
    print(
        "WARNING in attendance_dialog.py: Could not import AbsenceType from models! Using fallback Enum."
    )

    class AbsenceType(str, enum.Enum):
        SICK_LEAVE = "sick_leave"
        VACATION = "vacation"
        OTHER = "other"



logger = logging.getLogger("KindergartenApp")



class AttendanceDialog(QDialog):
    ABSENCE_TYPE_MAP = {
        "Не указано / Другое": None,  
        "Больничный": AbsenceType.SICK_LEAVE,
        "Отпуск": AbsenceType.VACATION,
    }
    ABSENCE_VALUE_MAP = {  
        None: "Не указано / Другое",
        AbsenceType.SICK_LEAVE.value: "Больничный",
        AbsenceType.VACATION.value: "Отпуск",
        AbsenceType.OTHER.value: "Не указано / Другое",  
    }

    def __init__(
        self,
        api_client: ApiClient,
        record_data: Dict,
        child_name: str,
        record_date: str,
        parent=None,
    ):
        super().__init__(parent)
        self.api_client = api_client
        self.record_data = record_data
        self.record_id = self.record_data.get("id")

        self.setWindowTitle(f"Посещаемость: {child_name} ({record_date})")
        self.setMinimumWidth(400)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        if self.record_id is None:
            logger.critical("CRITICAL: AttendanceDialog opened without record ID!")
            QMessageBox.critical(
                self, "Ошибка", "Не передан ID записи для редактирования!"
            )
            QTimer.singleShot(0, self.reject)
            self.setLayout(QVBoxLayout())  
        else:
            self.initUI()
            self.populate_fields()
            logger.debug(
                f"AttendanceDialog initialized for record_id: {self.record_id}"
            )

    def initUI(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Статус присутствия
        status_label = QLabel("Статус:")
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        self.present_radio = QRadioButton("✅ Присутствовал")
        self.absent_radio = QRadioButton("❌ Отсутствовал")
        self.status_button_group = QButtonGroup(self)
        self.status_button_group.addButton(self.present_radio, 1)
        self.status_button_group.addButton(self.absent_radio, 0)
        status_layout.addWidget(self.present_radio)
        status_layout.addWidget(self.absent_radio)
        status_layout.addStretch()
        self.status_button_group.buttonClicked.connect(self.on_status_changed)
        form_layout.addRow(status_label, status_widget)

        # Тип отсутствия (ComboBox)
        self.absence_type_label = QLabel("Тип отсутствия:")
        self.absence_type_combo = QComboBox()
        
        self.absence_type_combo.addItems(self.ABSENCE_TYPE_MAP.keys())
        
        for i, type_enum in enumerate(self.ABSENCE_TYPE_MAP.values()):
            self.absence_type_combo.setItemData(i, type_enum)
        form_layout.addRow(self.absence_type_label, self.absence_type_combo)

        # Причина отсутствия (текст)
        self.reason_label = QLabel("Причина (описание):")
        self.reason_input = QLineEdit()
        self.reason_input.setMaxLength(200)
        self.reason_input.setPlaceholderText("Уточните причину (необязательно)")
        form_layout.addRow(self.reason_label, self.reason_input)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()

        # Кнопки
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

    def populate_fields(self):
        """Заполняет поля текущими данными записи."""
        if not self.record_data:
            return

        is_present = self.record_data.get("present", False)
        if is_present:
            self.present_radio.setChecked(True)
        else:
            self.absent_radio.setChecked(True)

        absence_reason = self.record_data.get("absence_reason")
        self.reason_input.setText(absence_reason if absence_reason is not None else "")

        absence_type_value = self.record_data.get(
            "absence_type"
        )  
        display_text = self.ABSENCE_VALUE_MAP.get(absence_type_value)

        if display_text:
            self.absence_type_combo.setCurrentText(display_text)
            logger.debug(
                f"Populating absence type: found '{display_text}' for value '{absence_type_value}'"
            )
        else:
            
            self.absence_type_combo.setCurrentText("Не указано / Другое")
            logger.debug(
                f"Populating absence type: value '{absence_type_value}' not in map, setting default."
            )

        self.on_status_changed() 

    def on_status_changed(self):
        """Включает/выключает поля причины и типа в зависимости от статуса."""
        is_absent = self.absent_radio.isChecked()
        self.reason_input.setEnabled(is_absent)
        self.reason_label.setEnabled(is_absent)
        self.absence_type_combo.setEnabled(is_absent)
        self.absence_type_label.setEnabled(is_absent)

        if not is_absent:
            self.reason_input.clear()
            
            self.absence_type_combo.setCurrentText("Не указано / Другое")

    def accept_data(self):
        """Собирает данные, проверяет изменения и отправляет запрос на обновление."""
        if self.record_id is None:
            return

        
        is_present = self.present_radio.isChecked()
        absence_reason = self.reason_input.text().strip() or None

        
        selected_type_index = self.absence_type_combo.currentIndex()
        absence_type_enum = self.absence_type_combo.itemData(
            selected_type_index
        )  

        
        absence_type_value = None
        if not is_present and absence_type_enum is not None:
            
            if absence_type_enum != AbsenceType.OTHER:  
                absence_type_value = absence_type_enum.value
        

        
        if is_present:
            absence_reason = None
            absence_type_value = None

        
        update_payload = {
            "present": is_present,
            "absence_reason": absence_reason,
            "absence_type": absence_type_value,
        }

        
        current_present = self.record_data.get("present", False)
        current_reason = self.record_data.get("absence_reason")
        current_type = self.record_data.get("absence_type")

        
        reason_changed = (absence_reason or "") != (current_reason or "")
        type_changed = absence_type_value != current_type

        if is_present == current_present and not reason_changed and not type_changed:
            logger.debug("No changes detected in attendance record. Closing dialog.")
            self.accept()  
            return

        logger.debug(
            f"Updating attendance record {self.record_id} with data: {update_payload}"
        )
        self.setEnabled(False)
        try:
            updated_record = self.api_client.update_attendance_record(
                self.record_id, update_payload
            )
            logger.info(
                f"Attendance record {self.record_id} updated successfully via API."
            )
            self.accept()  

        except ApiHttpError as e:
            logger.error(f"API HTTP Error during attendance update: {e}")
            QMessageBox.warning(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось обновить запись:\n{e.message}",
            )
            self.setEnabled(True)
        except (ApiClientError, Exception) as e:
            logger.exception("Error updating attendance record.")
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить запись:\n{e}")
            self.setEnabled(True)
