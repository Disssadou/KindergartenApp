import logging
from datetime import date, datetime, timedelta
import calendar
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
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QDialog,
    QFormLayout,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
from PyQt6.QtGui import QIcon
from typing import Optional, Dict, List

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


from app.dialogs.rates_dialog import RatesDialog  

logger = logging.getLogger("KindergartenApp")

try:
    from utils.report_generator import RUSSIAN_MONTHS_NOM
except ImportError:
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

PAYMENTS_VIEW_DEFAULT_DAY_RATE_KEY = "payments/default_day_rate"


class PaymentsView(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, settings: QSettings, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.settings = settings
        self.groups_data: List[Dict] = []
        self.children_in_selected_group_for_calc: List[Dict] = (
            []
        )  # Дети для диалога инд. ставок
        self.charge_history_data: List[Dict] = []
        self.current_individual_rates: Dict[int, float] = {}  # {child_id: rate}

        self.initUI()
        self.load_groups_for_filter()
        self.update_default_rate_from_settings()  

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # --- Секция "Расчет и сохранение ежемесячных начислений" ---
        calculation_groupbox = QGroupBox("Расчет ежемесячных начислений")
        calculation_main_layout = QVBoxLayout(calculation_groupbox)

        calc_filters_layout = QHBoxLayout()
        calc_filters_layout.addWidget(QLabel("Группа:"))
        self.group_combo_calc = QComboBox()
        self.group_combo_calc.setMinimumWidth(200)
        self.group_combo_calc.addItem("Выберите группу...", None)
        self.group_combo_calc.currentIndexChanged.connect(
            self.on_calculation_group_selected
        ) 
        calc_filters_layout.addWidget(self.group_combo_calc)

        calc_filters_layout.addWidget(QLabel("Год:"))
        self.year_spin_calc = QSpinBox()
        current_year = date.today().year
        self.year_spin_calc.setRange(current_year - 5, current_year + 1)
        self.year_spin_calc.setValue(current_year)
        calc_filters_layout.addWidget(self.year_spin_calc)

        calc_filters_layout.addWidget(QLabel("Месяц:"))
        self.month_combo_calc = QComboBox()
        for month_num in range(1, 13):
            self.month_combo_calc.addItem(
                RUSSIAN_MONTHS_NOM.get(month_num, str(month_num)), month_num
            )
        prev_month_dt = date.today().replace(day=1) - timedelta(days=1)
        self.month_combo_calc.setCurrentIndex(prev_month_dt.month - 1)
        self.year_spin_calc.setValue(prev_month_dt.year)
        calc_filters_layout.addWidget(self.month_combo_calc)

        calc_filters_layout.addStretch()
        calculation_main_layout.addLayout(calc_filters_layout)

        default_rate_layout = QHBoxLayout()
        default_rate_layout.addWidget(QLabel("Ставка по умолчанию (руб./день):"))
        self.default_day_cost_spinbox = QDoubleSpinBox()
        self.default_day_cost_spinbox.setDecimals(2)
        self.default_day_cost_spinbox.setRange(0.00, 9999.99)
        self.default_day_cost_spinbox.setValue(120.00)
        default_rate_layout.addWidget(self.default_day_cost_spinbox)
        default_rate_layout.addStretch()
        calculation_main_layout.addLayout(default_rate_layout)

        # Кнопка для вызова диалога индивидуальных ставок
        self.individual_rates_button = QPushButton("Задать индивидуальные ставки...")
        self.individual_rates_button.clicked.connect(self.open_individual_rates_dialog)
        self.individual_rates_button.setEnabled(False)  
        calculation_main_layout.addWidget(
            self.individual_rates_button, 0, Qt.AlignmentFlag.AlignLeft
        )

        

        self.calculate_button = QPushButton("Рассчитать и сохранить начисления")
        self.calculate_button.setFixedHeight(35)
        self.calculate_button.setIcon(QIcon.fromTheme("document-save"))
        self.calculate_button.clicked.connect(self.perform_monthly_charge_calculation)
        calculation_main_layout.addWidget(
            self.calculate_button, 0, Qt.AlignmentFlag.AlignCenter
        )

        main_layout.addWidget(calculation_groupbox)

        # --- Секция "История начислений" ---
        
        history_groupbox = QGroupBox("История ежемесячных начислений")
        history_layout = QVBoxLayout(history_groupbox)

        history_filters_layout = QHBoxLayout()
        history_filters_layout.addWidget(QLabel("Группа:"))
        self.history_group_combo = QComboBox()
        self.history_group_combo.setMinimumWidth(
            150
        )  
        self.history_group_combo.addItem("Все группы", None)
        history_filters_layout.addWidget(self.history_group_combo)

        history_filters_layout.addWidget(QLabel("Год:"))
        self.history_year_spin = QSpinBox()
        current_year = date.today().year
        self.history_year_spin.setRange(current_year - 10, current_year + 1)  
        self.history_year_spin.setValue(current_year)  
        history_filters_layout.addWidget(self.history_year_spin)

        history_filters_layout.addWidget(QLabel("Месяц:"))
        self.history_month_combo = QComboBox()
        self.history_month_combo.addItem("Все месяцы", None)  
        for month_num in range(1, 13):
            self.history_month_combo.addItem(
                RUSSIAN_MONTHS_NOM.get(month_num, f"Месяц {month_num}"), month_num
            )
        self.history_month_combo.setCurrentIndex(0)  
        history_filters_layout.addWidget(self.history_month_combo)

        
        self.history_group_combo.currentIndexChanged.connect(self.load_charge_history)
        self.history_year_spin.valueChanged.connect(self.load_charge_history)
        self.history_month_combo.currentIndexChanged.connect(self.load_charge_history)

        history_filters_layout.addStretch()
        self.refresh_history_button = QPushButton("Обновить историю")
        self.refresh_history_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_history_button.clicked.connect(self.load_charge_history)
        history_filters_layout.addWidget(self.refresh_history_button)

        history_layout.addLayout(history_filters_layout)
        self.charge_history_table = QTableWidget()  
        self.charge_history_table.setColumnCount(7)
        self.charge_history_table.setHorizontalHeaderLabels(
            [
                "ID",
                "ID Ребенка",
                "ФИО Ребенка",
                "Год",
                "Месяц",
                "Сумма (руб.)",
                "Дата расчета",
            ]
        )
        self.charge_history_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.charge_history_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.charge_history_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        header_history = self.charge_history_table.horizontalHeader()
        header_history.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_history.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_history.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_history.setSectionResizeMode(
            6, QHeaderView.ResizeMode.Interactive
        )  
        self.charge_history_table.itemDoubleClicked.connect(self.show_charge_details)
        history_layout.addWidget(self.charge_history_table)
        main_layout.addWidget(history_groupbox)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def update_default_rate_from_settings(self):
        try:

            default_rate_from_settings = self.settings.value(
                PAYMENTS_VIEW_DEFAULT_DAY_RATE_KEY, "120.00"
            )
            self.default_day_cost_spinbox.setValue(float(default_rate_from_settings))
            logger.info(
                f"PaymentsView: Default day rate set to {default_rate_from_settings} from settings."
            )
        except Exception as e:
            logger.warning(
                f"Could not load default day rate from settings (key: {PAYMENTS_VIEW_DEFAULT_DAY_RATE_KEY}): {e}"
            )
            self.default_day_cost_spinbox.setValue(120.00)

    def load_groups_for_filter(self):
        logger.info("PaymentsView: Loading groups for filters...")
        try:
            self.groups_data = self.api_client.get_groups(limit=1000)

            common_groups_items = [("Выберите группу...", None)] + sorted(
                [
                    (g.get("name", f"ID:{g['id']}"), g["id"])
                    for g in self.groups_data
                    if g.get("id") is not None
                ],
                key=lambda x: x[0],
            )

            self.group_combo_calc.clear()
            for name, id_val in common_groups_items:
                self.group_combo_calc.addItem(name, id_val)

            self.history_group_combo.clear()
            self.history_group_combo.addItem(
                "Все группы", None
            ) 
            for name, id_val in common_groups_items:
                if (
                    id_val is not None
                ):  
                    self.history_group_combo.addItem(name, id_val)

            self.status_changed.emit("Список групп загружен.")
            if self.group_combo_calc.count() > 1:
                self.group_combo_calc.setCurrentIndex(
                    1
                )  
            else:
                self.individual_rates_button.setEnabled(
                    False
                )  

            self.load_charge_history()
        except (ApiClientError, Exception) as e:
            logger.exception("PaymentsView: Failed to load groups.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить список групп:\n{e}"
            )

    def on_calculation_group_selected(self):
        selected_group_id = self.group_combo_calc.currentData()
        self.current_individual_rates = (
            {}
        )  
        self.children_in_selected_group_for_calc = []

        if selected_group_id is None:
            self.individual_rates_button.setEnabled(False)
            return

        self.status_changed.emit(
            f"Загрузка детей группы ID {selected_group_id} для индивидуальных ставок..."
        )
        self.individual_rates_button.setEnabled(False)  
        try:
            self.children_in_selected_group_for_calc = self.api_client.get_children(
                group_id=selected_group_id, limit=200
            )
            self.individual_rates_button.setEnabled(
                bool(self.children_in_selected_group_for_calc)
            )
            self.status_changed.emit(
                f"Загружено {len(self.children_in_selected_group_for_calc)} детей."
            )
        except (ApiClientError, Exception) as e:
            logger.exception(
                f"Failed to load children for group {selected_group_id} for individual rates."
            )
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить детей группы:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки детей для инд. ставок.")

    def open_individual_rates_dialog(self):
        """Открывает диалог для ввода индивидуальных ставок."""
        selected_group_id = self.group_combo_calc.currentData()
        if selected_group_id is None or not self.children_in_selected_group_for_calc:
            QMessageBox.warning(
                self,
                "Внимание",
                "Сначала выберите группу и дождитесь загрузки списка детей.",
            )
            return

        default_cost_from_spinbox = self.default_day_cost_spinbox.value()

        
        dialog = RatesDialog(
            children_list=self.children_in_selected_group_for_calc,
            default_rate=default_cost_from_spinbox,
            existing_rates=self.current_individual_rates,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.current_individual_rates = (
                dialog.get_individual_rates()
            ) 
            logger.info(f"Individual rates updated: {self.current_individual_rates}")
            self.status_changed.emit(
                f"Индивидуальные ставки обновлены ({len(self.current_individual_rates)} записей)."
            )
        else:
            logger.debug("IndividualRatesDialog cancelled.")

    def perform_monthly_charge_calculation(self):
        group_id = self.group_combo_calc.currentData()
        if group_id is None:
            QMessageBox.warning(
                self, "Внимание", "Пожалуйста, выберите группу для расчета."
            )
            return

        year = self.year_spin_calc.value()
        month = self.month_combo_calc.currentData()
        default_day_cost = self.default_day_cost_spinbox.value()

        
        individual_rates_list = [
            {"child_id": child_id, "day_cost": rate}
            for child_id, rate in self.current_individual_rates.items()
        ]

        payload = {
            "group_id": group_id,
            "year": year,
            "month": month,
            "default_day_cost": default_day_cost,
            "individual_rates": individual_rates_list,
        }

        self.status_changed.emit(
            f"Расчет начислений за {RUSSIAN_MONTHS_NOM.get(month, month)} {year}..."
        )
        logger.info(f"Performing monthly charge calculation with payload: {payload}")

        try:
            response_data = self.api_client.calculate_and_save_monthly_charges(payload)
            QMessageBox.information(
                self,
                "Успех",
                f"Начисления за {RUSSIAN_MONTHS_NOM.get(month, month)} {year} успешно рассчитаны и сохранены.\nОбработано записей: {len(response_data)}",
            )
            self.status_changed.emit("Начисления сохранены. Обновление истории...")
            self.load_charge_history()
        except (ApiHttpError, ApiClientError, Exception) as e:
            logger.exception("Error during monthly charge calculation.")
            QMessageBox.critical(
                self,
                "Ошибка расчета",
                f"Не удалось рассчитать и сохранить начисления:\n{e}",
            )
            self.status_changed.emit("Ошибка расчета начислений.")

    def load_charge_history(self):
        self.status_changed.emit("Обновление истории начислений...")
        self.charge_history_table.setRowCount(0)  
        self.charge_history_data = []  

        filter_group_id = self.history_group_combo.currentData()
        filter_year = (
            self.history_year_spin.value()
        )  
        filter_month = (
            self.history_month_combo.currentData()
        )  

       
        logger.debug(
            f"Attempting to load charge history with filters: "
            f"Group ID: {filter_group_id}, Year: {filter_year}, Month: {filter_month}"
        )

        # --- Логика принятия решения о загрузке ---
        # Вариант 1: Загружаем, только если выбрана конкретная группа, год и конкретный месяц.
        if filter_group_id is None:
            self.status_changed.emit("Для просмотра истории выберите группу.")
            self.populate_charge_history_table()  
            return

        if filter_month is None:  # Если выбрано "Все месяцы"
            
            self.status_changed.emit(
                f"Для группы '{self.history_group_combo.currentText()}' выберите конкретный месяц."
            )
            self.populate_charge_history_table()  
            return

        # Если все необходимые фильтры (group_id, year, month) установлены:
        logger.info(
            f"Loading charge history for Group ID: {filter_group_id}, Year: {filter_year}, Month: {filter_month}"
        )
        try:
            # ApiClient.get_monthly_charges ожидает group_id, year, month для группового запроса
            self.charge_history_data = self.api_client.get_monthly_charges(
                group_id=filter_group_id, year=filter_year, month=filter_month
            )

            if self.charge_history_data:
                self.status_changed.emit(
                    f"Загружено {len(self.charge_history_data)} записей истории начислений."
                )
            else:
                self.status_changed.emit(
                    "Записей истории начислений по указанным фильтрам не найдено."
                )

        except ApiHttpError as e:
            logger.error(
                f"API HTTP Error loading charge history: {e.message} (Status: {e.status_code})"
            )
            QMessageBox.critical(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось загрузить историю начислений:\n{e.message}",
            )
            self.status_changed.emit(f"Ошибка загрузки истории (API {e.status_code}).")
        except ApiClientError as e:
            logger.error(f"API Client Error loading charge history: {e.message}")
            QMessageBox.critical(
                self,
                "Ошибка клиента API",
                f"Не удалось загрузить историю начислений:\n{e.message}",
            )
            self.status_changed.emit("Ошибка клиента API при загрузке истории.")
        except Exception as e:
            logger.exception(
                "Unexpected error loading charge history."
            )  
            QMessageBox.critical(
                self,
                "Непредвиденная ошибка",
                f"Не удалось загрузить историю начислений:\n{e}",
            )
            self.status_changed.emit("Непредвиденная ошибка загрузки истории.")
        finally:
            self.populate_charge_history_table()  

    def populate_charge_history_table(self):

        self.charge_history_table.setRowCount(len(self.charge_history_data))
        self.charge_history_table.setSortingEnabled(False)
        for row, charge_entry in enumerate(self.charge_history_data):
            charge_id_val = charge_entry.get("id")
            child_id_val = charge_entry.get("child_id")
            child_info = charge_entry.get("child")
            child_name_str = (
                child_info.get("full_name", "N/A") if child_info else str(child_id_val)
            )
            year_val = charge_entry.get("year")
            month_val = charge_entry.get("month")
            amount_due_val = charge_entry.get("amount_due", 0.00)
            calculated_at_str = charge_entry.get("calculated_at", "")
            try:
                dt_obj = (
                    datetime.fromisoformat(calculated_at_str.replace("Z", "+00:00"))
                    if calculated_at_str
                    else None
                )
                calculated_at_display = (
                    dt_obj.strftime("%Y-%m-%d %H:%M") if dt_obj else ""
                )
            except ValueError:
                calculated_at_display = calculated_at_str
            details_data = charge_entry.get("calculation_details", "")

            items = [
                str(charge_id_val),
                str(child_id_val),
                child_name_str,
                str(year_val),
                RUSSIAN_MONTHS_NOM.get(month_val, str(month_val)),
                f"{float(amount_due_val):.2f}",
                calculated_at_display,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, details_data)
                if col == 5:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.charge_history_table.setItem(row, col, item)
        self.charge_history_table.setSortingEnabled(True)

    def show_charge_details(self, item: QTableWidgetItem):
        id_item = self.charge_history_table.item(item.row(), 0)
        if id_item:
            details = id_item.data(Qt.ItemDataRole.UserRole)
            if details:
                QMessageBox.information(self, "Детали расчета", str(details))
            else:
                QMessageBox.information(self, "Детали расчета", "Детали отсутствуют.")
