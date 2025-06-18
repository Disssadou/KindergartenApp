
import logging
from typing import List, Dict, Optional
from datetime import date

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QMessageBox,
    QDialogButtonBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QLineEdit,
    QComboBox,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from utils.api_client import ApiClient

try:
    from database.models import AbsenceType  
except ImportError:
    
    logger_bd = logging.getLogger("KindergartenApp.BulkDialog")
    logger_bd.warning(
        "Could not import AbsenceType from database.models. Using string fallbacks."
    )

    class AbsenceType(str):
        SICK_LEAVE = "sick_leave"
        VACATION = "vacation"
        OTHER = "other"

    @classmethod
    def values(cls):
        return [cls.SICK_LEAVE, cls.VACATION, cls.OTHER]


logger = logging.getLogger("KindergartenApp")


class BulkAttendanceDialog(QDialog):
    ABSENCE_TYPE_DISPLAY = {  # ... (определение вашей карты)
        AbsenceType.SICK_LEAVE: "Больничный",
        AbsenceType.VACATION: "Отпуск",
        AbsenceType.OTHER: "Другое (уваж.)",
        None: "Не указано",
    }

    def __init__(
        self,
        api_client: ApiClient,
        children_list: List[Dict],
        group_id: int,
        group_name: str,  # <--- Аргумент есть
        target_date: date,
        existing_records_map: Dict[int, Dict],
        parent=None,
    ):
        super().__init__(parent)
        self.api_client = api_client
        self.children_list = sorted(children_list, key=lambda c: c.get("full_name", ""))
        self.group_id = group_id
        self.group_name = group_name  # <--- СОХРАНЯЕМ group_name В АТРИБУТ КЛАССА
        self.target_date = target_date
        self.existing_records_map = existing_records_map

        self.setWindowTitle(
            f"Массовая отметка: {self.group_name} на {target_date.strftime('%d.%m.%Y')}"
        )  # Теперь self.group_name доступен
        self.setMinimumSize(750, 500)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        self._collected_api_data: Optional[Dict] = None
        self.child_widgets: Dict[int, Dict[str, QWidget]] = {}

        self.initUI()  # Теперь initUI может безопасно использовать self.group_name
        self.populate_table()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        # Теперь self.group_name будет доступен здесь:
        main_layout.addWidget(
            QLabel(
                f"<b>Отметьте посещаемость для группы '{self.group_name}' на {self.target_date.strftime('%d.%m.%Y')}</b>"
            )
        )
        # ... (остальной код initUI без изменений) ...
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(4)
        self.table_widget.setHorizontalHeaderLabels(
            ["ФИО Ребенка", "Присутствует", "Причина отсутствия", "Тип отсутствия"]
        )
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_widget.verticalHeader().setVisible(False)
        main_layout.addWidget(self.table_widget)
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.handle_save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)

    def populate_table(self):
        # ... (ваш populate_table, он теперь может безопасно использовать self.child_widgets)
        self.table_widget.setRowCount(len(self.children_list))
        for row, child_data in enumerate(self.children_list):
            child_id = child_data["id"]
            child_name = child_data.get("full_name", f"ID: {child_id}")
            existing_record = self.existing_records_map.get(child_id)
            name_item = QTableWidgetItem(child_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row, 0, name_item)
            present_checkbox = QCheckBox()
            present_checkbox.setChecked(
                existing_record["present"] if existing_record else False
            )
            self.table_widget.setCellWidget(row, 1, present_checkbox)
            reason_edit = QLineEdit()
            reason_edit.setPlaceholderText("Если отсутствует...")
            if existing_record and not existing_record["present"]:
                reason_edit.setText(existing_record.get("absence_reason", ""))
            self.table_widget.setCellWidget(row, 2, reason_edit)
            type_combo = QComboBox()
            type_combo.addItem("Выберите тип...", None)

            # Корректная итерация по Enum, если AbsenceType это ваш класс Enum
            enum_values_to_iterate = []
            if hasattr(AbsenceType, "values") and callable(
                AbsenceType.values
            ):  # Если есть метод values
                enum_values_to_iterate = AbsenceType.values()
            elif hasattr(AbsenceType, "__members__"):  # Если это стандартный enum.Enum
                enum_values_to_iterate = [member.value for member in AbsenceType]
            else:  # Если это просто класс-заглушка с атрибутами класса
                enum_values_to_iterate = [
                    AbsenceType.SICK_LEAVE,
                    AbsenceType.VACATION,
                    AbsenceType.OTHER,
                ]

            for enum_val_str in enum_values_to_iterate:
                # Приводим строковое значение обратно к экземпляру Enum для поиска в карте, если ключи - экземпляры
                # Если ключи в ABSENCE_TYPE_DISPLAY строки, то AbsenceType(enum_val_str) не нужно
                # Судя по вашему ABSENCE_TYPE_DISPLAY, ключи - экземпляры Enum.
                try:
                    enum_member_instance = AbsenceType(enum_val_str)
                    display_name = self.ABSENCE_TYPE_DISPLAY.get(
                        enum_member_instance, enum_val_str
                    )
                except (
                    ValueError
                ):  # Если enum_val_str не является валидным значением для AbsenceType
                    display_name = enum_val_str  # Показать как есть
                type_combo.addItem(display_name, enum_val_str)

            if (
                existing_record
                and not existing_record["present"]
                and existing_record.get("absence_type")
            ):
                current_absence_type_val = existing_record["absence_type"]
                index = type_combo.findData(current_absence_type_val)
                if index >= 0:
                    type_combo.setCurrentIndex(index)
            self.table_widget.setCellWidget(row, 3, type_combo)

            def create_toggle_slot(current_reason_edit, current_type_combo):
                def toggle_absence_fields(is_present_state):
                    current_reason_edit.setEnabled(not is_present_state)
                    current_type_combo.setEnabled(not is_present_state)
                    if is_present_state:
                        current_reason_edit.clear()
                        current_type_combo.setCurrentIndex(0)

                return toggle_absence_fields

            slot_for_this_row = create_toggle_slot(reason_edit, type_combo)
            present_checkbox.stateChanged.connect(slot_for_this_row)
            slot_for_this_row(present_checkbox.isChecked())

            self.child_widgets[child_id] = {
                "present_cb": present_checkbox,
                "reason_edit": reason_edit,
                "type_combo": type_combo,
            }
        self.table_widget.resizeRowsToContents()

    def handle_save(self):
        # ... (ваш handle_save без изменений)
        logger.debug("BulkAttendanceDialog: Save button clicked, collecting data...")
        attendance_list_api = []
        for child_id, widgets in self.child_widgets.items():
            is_present = widgets["present_cb"].isChecked()
            absence_reason = (
                widgets["reason_edit"].text().strip() if not is_present else None
            )
            absence_type_value = (
                widgets["type_combo"].currentData() if not is_present else None
            )
            attendance_list_api.append(
                {
                    "child_id": child_id,
                    "present": is_present,
                    "absence_reason": absence_reason,
                    "absence_type": absence_type_value,
                }
            )
        self._collected_api_data = {
            "group_id": self.group_id,
            "date": self.target_date.strftime("%Y-%m-%d"),
            "attendance_list": attendance_list_api,
        }
        logger.debug(
            f"BulkAttendanceDialog: Data collected: {self._collected_api_data}"
        )
        self.accept()

    def get_attendance_data_for_api(
        self,
    ) -> Optional[Dict]:  # Этот метод вызывается из AttendanceView
        return self._collected_api_data

    # Убрал get_collected_api_data, так как get_attendance_data_for_api делает то же самое
