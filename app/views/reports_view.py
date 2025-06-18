import calendar
import logging
import os
from datetime import date
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QDoubleSpinBox,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QSpinBox,
    QDialog,
)
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QDate,
    QSettings,
    QStandardPaths,
)
from PyQt6.QtGui import QIcon
from typing import Optional, Dict, List


from utils.api_client import ApiClient, ApiClientError, ApiHttpError
from app.dialogs.rates_dialog import RatesDialog
from app.dialogs.settings_dialog import DEFAULT_REPORTS_PATH_KEY

logger = logging.getLogger("KindergartenApp")

try:
    from utils.report_generator import RUSSIAN_MONTHS_NOM
except ImportError:
    logger.warning(
        "Could not import RUSSIAN_MONTHS_NOM from report_generator, using local definition."
    )
    RUSSIAN_MONTHS_NOM = {
        1: "Январь",
        2: "Февраль",
        3: "Март",
        4: "Апрель",
        5: "Май",
        6: "Июнь",
        7: "Июль",
        8: "Август",
        9: "Сентябрь",
        10: "Октябрь",
        11: "Ноябрь",
        12: "Декабрь",
    }


class ReportsView(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, settings: QSettings, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.settings = settings
        self.groups_data: List[Dict] = []
        self.current_staff_rates: Dict[int, float] = {}

        self.initUI()
        self.load_initial_data()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        report_groupbox = QGroupBox("Формирование Табеля Посещаемости")
        report_layout = QVBoxLayout(report_groupbox)
        report_layout.setSpacing(15)

        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Группа:"))
        self.group_combo = QComboBox()
        self.group_combo.setMinimumWidth(250)
        self.group_combo.addItem("Загрузка...", None)
        self.group_combo.setEnabled(False)
        group_layout.addWidget(self.group_combo)
        group_layout.addStretch()
        report_layout.addLayout(group_layout)

        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Месяц и Год:"))
        self.month_edit = QComboBox()
        for month_num in range(1, 13):
            month_name = RUSSIAN_MONTHS_NOM.get(month_num, f"Месяц {month_num}")
            self.month_edit.addItem(month_name, month_num)
        self.month_edit.setCurrentIndex(date.today().month - 1)

        self.year_edit = QSpinBox()
        current_year = date.today().year
        self.year_edit.setRange(current_year - 5, current_year + 1)
        self.year_edit.setValue(current_year)
        date_layout.addWidget(self.month_edit)
        date_layout.addWidget(self.year_edit)
        date_layout.addStretch()
        report_layout.addLayout(date_layout)

        rates_layout = QHBoxLayout()
        rates_layout.addWidget(QLabel("Общая ставка (руб./день):"))
        self.default_rate_spinbox = QDoubleSpinBox()
        self.default_rate_spinbox.setDecimals(2)
        self.default_rate_spinbox.setRange(0.00, 9999.99)
        self.default_rate_spinbox.setValue(150.00)
        self.default_rate_spinbox.setSingleStep(10.0)
        rates_layout.addWidget(self.default_rate_spinbox)

        self.edit_rates_button = QPushButton("Индивидуальные ставки...")
        self.edit_rates_button.setToolTip(
            "Задать индивидуальные ставки оплаты для детей"
        )
        self.edit_rates_button.clicked.connect(self.open_rates_dialog)
        rates_layout.addWidget(self.edit_rates_button)
        rates_layout.addStretch()
        report_layout.addLayout(rates_layout)

        self.generate_button = QPushButton(
            QIcon.fromTheme("document-export"), "Сформировать Табель"
        )
        self.generate_button.setFixedHeight(40)
        self.generate_button.clicked.connect(self.generate_report)
        report_layout.addWidget(self.generate_button, 0, Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(report_groupbox)
        main_layout.addStretch()
        self.setLayout(main_layout)

    def load_initial_data(self):
        self.status_changed.emit("Загрузка списка групп для отчета...")
        logger.info("ReportsView: Loading groups...")
        self.group_combo.clear()
        self.group_combo.addItem("Выберите группу...", None)
        self.group_combo.setEnabled(False)
        try:
            self.groups_data = self.api_client.get_groups(limit=1000)
            self.groups_data.sort(key=lambda g: g.get("name", ""))
            for group in self.groups_data:
                group_id = group.get("id")
                group_name = group.get("name", f"ID:{group_id}")
                if group_id is not None:
                    self.group_combo.addItem(group_name, group_id)
            logger.info(f"ReportsView: Loaded {len(self.groups_data)} groups.")
            self.group_combo.setEnabled(True)
            self.status_changed.emit("Список групп загружен.")
        except (ApiClientError, Exception) as e:
            logger.exception("ReportsView: Failed to load groups.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить список групп:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки групп.")
            self.group_combo.addItem("Ошибка загрузки", None)
            self.group_combo.setEnabled(True)

    def open_rates_dialog(self):
        selected_group_id = self.group_combo.currentData()
        if selected_group_id is None:
            QMessageBox.warning(
                self, "Внимание", "Пожалуйста, сначала выберите группу."
            )
            return

        self.status_changed.emit(
            f"Загрузка детей группы ID {selected_group_id} для ставок..."
        )
        try:
            children_in_group = self.api_client.get_children(
                group_id=selected_group_id, limit=200
            )
        except (ApiClientError, Exception) as e:
            logger.exception(
                f"Failed to load children for group {selected_group_id} for rates dialog."
            )
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить список детей группы:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки детей.")
            return
        self.status_changed.emit(f"Загружено {len(children_in_group)} детей.")

        if not children_in_group:
            QMessageBox.information(self, "Информация", "В выбранной группе нет детей.")
            return

        dialog = RatesDialog(
            children_list=children_in_group,
            default_rate=self.default_rate_spinbox.value(),
            existing_rates=self.current_staff_rates,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_staff_rates = dialog.get_individual_rates()
            logger.info(f"Individual rates updated: {self.current_staff_rates}")
            self.status_changed.emit(
                f"Индивидуальные ставки обновлены ({len(self.current_staff_rates)} записей)."
            )
        else:
            logger.debug("RatesDialog cancelled.")

    def generate_report(self):
        group_id = self.group_combo.currentData()
        month = self.month_edit.currentData()
        year = self.year_edit.value()
        default_rate = self.default_rate_spinbox.value()

        if group_id is None:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите группу.")
            return

        self.status_changed.emit(
            f"Формирование табеля для группы ID {group_id} ({RUSSIAN_MONTHS_NOM.get(month, month)} {year})..."
        )
        logger.info(
            f"Requesting attendance report: GID={group_id}, M={month}, Y={year}, DR={default_rate}, SR={self.current_staff_rates}"
        )
        self.generate_button.setEnabled(False)

        try:
            file_bytes = self.api_client.download_attendance_report(
                group_id=group_id,
                year=year,
                month=month,
                default_rate=default_rate,
                staff_rates=self.current_staff_rates,
            )

            selected_group_name = (
                self.group_combo.currentText().replace(" ", "_").replace('"', "")
            )
            default_filename_only = (
                f"Табель_{selected_group_name}_{year}_{month:02d}.xlsx"
            )

            # Получаем путь по умолчанию из настроек
            default_save_directory = self.settings.value(
                DEFAULT_REPORTS_PATH_KEY,
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DocumentsLocation
                ),
            )

            default_save_directory_str = str(default_save_directory)

            full_default_path = os.path.join(
                default_save_directory_str, default_filename_only
            )
            logger.debug(f"Default save path for report dialog: {full_default_path}")

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить табель посещаемости",
                full_default_path,
                "Excel Files (*.xlsx);;All Files (*)",
            )

            if file_path:
                with open(file_path, "wb") as f:
                    f.write(file_bytes)
                logger.info(f"Attendance report saved to: {file_path}")
                QMessageBox.information(
                    self, "Успех", f"Табель посещаемости успешно сохранен:\n{file_path}"
                )
                self.status_changed.emit("Табель сохранен.")
            else:
                logger.info("Report saving cancelled by user.")
                self.status_changed.emit("Сохранение отчета отменено.")

        except ApiHttpError as e:
            logger.error(f"API HTTP Error generating report: {e}")
            QMessageBox.critical(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось сформировать отчет:\n{e.message}",
            )
            self.status_changed.emit("Ошибка формирования отчета (API).")
        except (ApiClientError, Exception) as e:
            logger.exception("Error generating or saving report.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сформировать или сохранить отчет:\n{e}"
            )
            self.status_changed.emit("Ошибка формирования отчета.")
        finally:
            self.generate_button.setEnabled(True)

    def update_default_paths_from_settings(self):
        """
        Этот метод вызывается из MainWindow, если настройки путей были изменены.
        В текущей реализации ReportsView он не делает ничего активного,
        так как путь всегда запрашивается из QSettings непосредственно перед
        открытием QFileDialog.

        """

        pass
