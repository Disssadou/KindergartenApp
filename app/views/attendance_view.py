import logging
from datetime import date, timedelta
from calendar import monthrange
from typing import Optional, Dict, List, Set

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
    QCalendarWidget,
    QDialog,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate, QTimer
from PyQt6.QtGui import (
    QIcon,
    QColor,
    QBrush,
    QTextCharFormat,
    QFont,
)

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


try:
    from app.dialogs.attendance_dialog import AttendanceDialog

    attendance_dialog_available = True
except ImportError:
    logger_att_view = logging.getLogger("KindergartenApp.AttendanceView")
    logger_att_view.warning(
        "Could not import AttendanceDialog. Edit functionality will be limited."
    )

    class AttendanceDialog(QDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))
            QMessageBox.critical(
                self, "Ошибка", "Диалог редактирования посещаемости не загружен."
            )

    attendance_dialog_available = False

try:
    from app.dialogs.bulk_attendance_dialog import BulkAttendanceDialog

    bulk_attendance_dialog_available = True
except ImportError:
    logger_att_view = logging.getLogger("KindergartenApp.AttendanceView")
    logger_att_view.error(
        "CRITICAL: Could not import BulkAttendanceDialog. Bulk attendance functionality will be MISSING."
    )

    class BulkAttendanceDialog(QDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))
            QMessageBox.critical(
                self, "Ошибка", "Диалог массовой отметки посещаемости не загружен."
            )

    bulk_attendance_dialog_available = False

logger = logging.getLogger("KindergartenApp")


class AttendanceView(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.groups_data: List[Dict] = []
        self.attendance_data: List[Dict] = []
        self.holidays_in_view: Set[date] = set()
        self.current_calendar_year_month: Optional[tuple[int, int]] = None

        self._setup_formats()
        self._init_ui()
        self._connect_signals()
        QTimer.singleShot(
            50, self.load_initial_data
        )  # Небольшая задержка для прорисовки UI

    def _setup_formats(self):
        self.weekend_format = QTextCharFormat()
        self.weekend_format.setForeground(QBrush(QColor(120, 120, 120)))

        self.holiday_format = QTextCharFormat()
        self.holiday_format.setBackground(QBrush(QColor(255, 220, 220)))
        self.holiday_format.setFontWeight(QFont.Weight.Bold)
        self.holiday_format.setToolTip("Праздничный/Дополнительный выходной день")

        self.workday_format = QTextCharFormat()
        self.workday_format.setForeground(QBrush(Qt.GlobalColor.black))
        self.workday_format.setBackground(QBrush(Qt.GlobalColor.white))

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(15)
        date_panel_layout = self._create_date_panel()
        controls_panel_layout = self._create_controls_panel()
        top_bar_layout.addLayout(date_panel_layout, 2)
        top_bar_layout.addLayout(controls_panel_layout, 3)
        main_layout.addLayout(top_bar_layout)

        main_layout.addWidget(QLabel("<b>Посещаемость на выбранную дату:</b>"))
        self.attendance_table = self._create_attendance_table()
        main_layout.addWidget(self.attendance_table)

        self.setLayout(main_layout)

    def _create_date_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.addWidget(QLabel("<b>Выберите дату:</b>"))
        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setGridVisible(True)
        self.calendar_widget.setMaximumHeight(280)
        self.calendar_widget.setMinimumDate(QDate(2020, 1, 1))
        self.calendar_widget.setMaximumDate(QDate.currentDate().addYears(1))
        self.calendar_widget.setSelectedDate(QDate.currentDate())
        layout.addWidget(self.calendar_widget)

        holiday_buttons_layout = QHBoxLayout()
        self.make_holiday_button = QPushButton("Сделать выходным")
        self.make_holiday_button.setIcon(
            QIcon.fromTheme("calendar- πολλά", QIcon.fromTheme("list-add"))
        )
        self.make_holiday_button.setToolTip(
            "Отметить выбранный день как дополнительный выходной/праздник"
        )
        self.make_workday_button = QPushButton("Сделать рабочим")
        self.make_workday_button.setIcon(
            QIcon.fromTheme("calendar-remove", QIcon.fromTheme("list-remove"))
        )
        self.make_workday_button.setToolTip(
            "Убрать отметку выходного/праздника (кроме Сб/Вс)"
        )
        holiday_buttons_layout.addStretch()
        holiday_buttons_layout.addWidget(self.make_holiday_button)
        holiday_buttons_layout.addWidget(self.make_workday_button)
        holiday_buttons_layout.addStretch()
        layout.addLayout(holiday_buttons_layout)
        layout.addStretch(1)
        return layout

    def _create_controls_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        group_filter_layout = QHBoxLayout()
        group_filter_layout.addWidget(QLabel("Группа:"))
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.setMinimumWidth(200)
        self.group_filter_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.group_filter_combo.addItem("Загрузка...", None)
        group_filter_layout.addWidget(self.group_filter_combo)
        layout.addLayout(group_filter_layout)

        self.refresh_button = QPushButton("Обновить список")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        layout.addWidget(self.refresh_button)
        self.bulk_attendance_button = QPushButton(
            QIcon.fromTheme(
                "document-edit-multiple", QIcon.fromTheme("accessories-text-editor")
            ),
            "Массовая отметка",
        )
        self.bulk_attendance_button.setToolTip(
            "Открыть диалог для массовой отметки посещаемости группы на выбранную дату"
        )
        layout.addWidget(self.bulk_attendance_button)
        self.edit_button = QPushButton("Изменить запись")
        self.edit_button.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_button.setToolTip("Изменить статус или причину выбранной записи")
        layout.addWidget(self.edit_button)
        layout.addStretch()
        return layout

    def _create_attendance_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(
            ["ID", "Ребенок (ФИО)", "Статус", "Причина отсутствия"]
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionHidden(0, True)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        return table

    def _connect_signals(self):
        self.calendar_widget.selectionChanged.connect(self.on_date_selection_changed)
        self.calendar_widget.currentPageChanged.connect(
            self.handle_calendar_page_changed
        )
        self.group_filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        self.attendance_table.itemSelectionChanged.connect(
            self.update_ui_element_states
        )
        self.attendance_table.itemDoubleClicked.connect(
            lambda item: (
                self.edit_attendance_record() if self.edit_button.isEnabled() else None
            )
        )
        self.make_holiday_button.clicked.connect(self.make_day_holiday)
        self.make_workday_button.clicked.connect(self.make_day_workday)
        self.refresh_button.clicked.connect(self.load_attendance_for_selected_filters)
        self.edit_button.clicked.connect(self.edit_attendance_record)
        self.bulk_attendance_button.clicked.connect(self.open_bulk_attendance_dialog)

    # --- Методы Загрузки Данных ---
    def load_initial_data(self):
        self.load_groups_for_filter()

    def load_groups_for_filter(self):
        self.status_changed.emit("Загрузка списка групп...")
        logger.info("AttendanceView: Loading groups for filter...")

        current_group_id = self.group_filter_combo.currentData()
        self.group_filter_combo.clear()
        self.group_filter_combo.addItem("Все группы", None)
        self.group_filter_combo.setEnabled(False)
        try:
            self.groups_data = self.api_client.get_groups(limit=1000)
            self.groups_data.sort(key=lambda g: g.get("name", ""))
            for group in self.groups_data:
                group_id, group_name = group.get("id"), group.get(
                    "name", f"ID:{group.get('id')}"
                )
                if group_id is not None:
                    self.group_filter_combo.addItem(group_name, group_id)
            logger.info(f"AttendanceView: Loaded {len(self.groups_data)} groups.")
            self.group_filter_combo.setEnabled(True)
            index_to_select = self.group_filter_combo.findData(current_group_id)
            self.group_filter_combo.setCurrentIndex(
                index_to_select if index_to_select >= 0 else 0
            )

            self.handle_calendar_page_changed(
                self.calendar_widget.yearShown(),
                self.calendar_widget.monthShown(),
                force_reload_holidays=True,
            )
        except (ApiClientError, Exception) as e:

            logger.exception("AttendanceView: Failed to load groups.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить список групп:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки групп.")
            self.group_filter_combo.addItem("Ошибка загрузки", None)
            self.group_filter_combo.setEnabled(True)

    def load_holidays_for_month(self, year: int, month: int):

        self.status_changed.emit(f"Загрузка календаря на {year}-{month:02d}...")
        logger.info(f"Loading holidays for {year}-{month:02d}")
        self.current_calendar_year_month = (year, month)
        self.holidays_in_view.clear()
        start_dt, end_dt = date(year, month, 1), date(
            year, month, monthrange(year, month)[1]
        )
        try:
            holidays_list = self.api_client.get_holidays(
                start_date=start_dt.isoformat(), end_date=end_dt.isoformat()
            )
            self.holidays_in_view = {
                date.fromisoformat(h["date"]) for h in holidays_list
            }
            logger.info(
                f"Loaded {len(self.holidays_in_view)} holidays for {year}-{month:02d}. Holidays: {self.holidays_in_view}"
            )
            self.status_changed.emit(f"Календарь на {year}-{month:02d} загружен.")
        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to load holidays for {year}-{month:02d}.")
            QMessageBox.warning(
                self, "Ошибка", f"Не удалось загрузить выходные дни:\n{e}"
            )
            self.status_changed.emit(f"Ошибка загрузки календаря.")
        finally:
            self.update_calendar_display_format()

    def load_attendance_for_selected_filters(self):

        selected_qdate = self.calendar_widget.selectedDate()
        if not selected_qdate.isValid():
            self.attendance_table.setRowCount(0)
            self.attendance_data = []
            self.update_ui_element_states()
            return
        selected_date_str = selected_qdate.toPyDate().isoformat()
        selected_group_id = self.group_filter_combo.currentData()
        group_info = self.group_filter_combo.currentText()
        self.status_changed.emit(
            f"Загрузка посещаемости на {selected_date_str} ({group_info})..."
        )
        logger.info(
            f"Loading attendance for date={selected_date_str}, group_id={selected_group_id}"
        )
        self.attendance_table.setRowCount(0)
        self.attendance_data = []
        self.update_ui_element_states()
        try:
            self.attendance_data = self.api_client.get_attendance(
                attendance_date=selected_date_str, group_id=selected_group_id
            )
            self._populate_attendance_table()
            self.status_changed.emit(
                f"Посещаемость загружена ({len(self.attendance_data)} записей)."
            )
            logger.info(
                f"Successfully loaded {len(self.attendance_data)} attendance records."
            )
        except ApiHttpError as e:
            if e.status_code == 403:
                logger.warning(f"Access denied: {e.message}")
                self._populate_attendance_table()
                QMessageBox.warning(self, "Доступ запрещен", f"{e.message}")
                self.status_changed.emit("Доступ запрещен.")
            else:
                logger.exception("HTTP error")
                QMessageBox.critical(self, "Ошибка", f"{e}")
                self.status_changed.emit("Ошибка загрузки.")
        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load attendance")
            QMessageBox.critical(self, "Ошибка", f"{e}")
            self.status_changed.emit("Ошибка загрузки.")
        finally:
            self.update_ui_element_states()

    # --- Методы Заполнения и Форматирования ---
    def _populate_attendance_table(self):

        self.attendance_table.setRowCount(len(self.attendance_data))
        self.attendance_table.setSortingEnabled(False)
        present_color_bg, absent_color_bg, text_brush = (
            QColor(230, 255, 230),
            QColor(255, 230, 230),
            QBrush(Qt.GlobalColor.black),
        )
        for row, record in enumerate(self.attendance_data):
            child_info = record.get("child", {})
            child_name = (
                child_info.get("full_name", f"Ребенок ID:{record.get('child_id')}")
                if isinstance(child_info, dict)
                else f"ID:{record.get('child_id')}"
            )
            is_present = record.get("present", False)
            status_text = "✅ Присутств." if is_present else "❌ Отсутств."
            if not is_present:
                absence_type_map = {"sick_leave": " (Б)", "vacation": " (О)"}
                status_text += absence_type_map.get(record.get("absence_type"), " (Н)")
            reason_text = record.get("absence_reason", "") if not is_present else ""
            items = [
                QTableWidgetItem(str(record.get("id"))),
                QTableWidgetItem(child_name),
                QTableWidgetItem(status_text),
                QTableWidgetItem(reason_text),
            ]
            items[0].setData(Qt.ItemDataRole.UserRole, record.get("id"))
            bg_color = present_color_bg if is_present else absent_color_bg
            for col, item_widget in enumerate(items):
                item_widget.setBackground(bg_color)
                item_widget.setForeground(text_brush)
                self.attendance_table.setItem(row, col, item_widget)
        self.attendance_table.resizeRowsToContents()
        self.attendance_table.setSortingEnabled(True)

    def update_calendar_display_format(self):
        if self.current_calendar_year_month is None:
            # Если месяц не установлен, форматируем текущую выбранную дату в календаре

            current_q_date = self.calendar_widget.selectedDate()
            if not current_q_date.isValid():
                return
            year, month, _ = current_q_date.getDate()
            self.current_calendar_year_month = (
                year,
                month,
            )

        year, month = self.current_calendar_year_month
        logger.debug(f"Updating calendar display format for {year}-{month:02d}")

        for day in range(1, monthrange(year, month)[1] + 1):
            q_date = QDate(year, month, day)
            py_date = q_date.toPyDate()

            current_format = QTextCharFormat(self.workday_format)

            if py_date in self.holidays_in_view:
                current_format.merge(self.holiday_format)
            elif q_date.dayOfWeek() >= 6:
                current_format.merge(self.weekend_format)

            self.calendar_widget.setDateTextFormat(q_date, current_format)
        logger.debug("Calendar display format updated.")
        self.update_ui_element_states()

    # --- Слоты Обработчики ---
    def handle_calendar_page_changed(
        self, year: int, month: int, force_reload_holidays: bool = False
    ):
        if force_reload_holidays or (year, month) != self.current_calendar_year_month:
            logger.info(
                f"Calendar page changed to: {year}-{month:02d}{' (forced holiday reload)' if force_reload_holidays else ''}"
            )
            self.load_holidays_for_month(year, month)
        else:
            self.update_ui_element_states()

    def _is_workday(self, py_date: date) -> bool:
        """Проверяет, является ли указанная дата рабочим днем (не Сб, Вс и не наш добавленный праздник)."""
        if py_date.weekday() >= 5:  # 0=Пн, 5=Сб, 6=Вс
            logger.debug(
                f"_is_workday: Date {py_date} is WEEKEND (weekday: {py_date.weekday()})"
            )
            return False
        if py_date in self.holidays_in_view:
            logger.debug(
                f"_is_workday: Date {py_date} is a HOLIDAY (found in self.holidays_in_view: {self.holidays_in_view})"
            )
            return False
        logger.debug(f"_is_workday: Date {py_date} is a WORKDAY.")
        return True

    def update_ui_element_states(self):
        selected_qdate = self.calendar_widget.selectedDate()
        date_is_valid = selected_qdate.isValid()
        py_date_for_debug = (
            selected_qdate.toPyDate() if date_is_valid else "Invalid/No Date Selected"
        )
        is_workday_flag_for_debug = (
            self._is_workday(selected_qdate.toPyDate()) if date_is_valid else False
        )
        group_data_for_debug = self.group_filter_combo.currentData()
        group_name_for_debug = self.group_filter_combo.currentText()
        group_selected_flag_for_debug = group_data_for_debug is not None
        table_selection_flag_for_debug = bool(
            self.attendance_table.selectionModel().selectedRows()
        )

        logger.debug(f"--- update_ui_element_states CALLED ---")
        logger.debug(
            f"  Selected Date from Calendar: {py_date_for_debug}, Is Valid: {date_is_valid}"
        )
        logger.debug(
            f"  _is_workday returned: {is_workday_flag_for_debug} (for attendance buttons)"
        )
        logger.debug(
            f"  Selected Group Combo Data: {group_data_for_debug}, Text: '{group_name_for_debug}', Is Group Selected (bool): {group_selected_flag_for_debug}"
        )
        logger.debug(f"  Table Has Selection: {table_selection_flag_for_debug}")
        logger.debug(f"  Attendance Dialog Available: {attendance_dialog_available}")
        logger.debug(
            f"  Bulk Attendance Dialog Available: {bulk_attendance_dialog_available}"
        )

        can_make_holiday, can_make_workday = False, False
        is_workday_selected_for_attendance = False

        if date_is_valid:
            selected_py_date = selected_qdate.toPyDate()
            # Логика для кнопок управления праздниками
            is_standard_weekend = (
                selected_py_date.weekday() >= 5
            )  # Это Сб или Вс по календарю
            is_marked_as_holiday = (
                selected_py_date in self.holidays_in_view
            )  # Отмечен ли как доп. выходной

            can_make_holiday = not is_standard_weekend and not is_marked_as_holiday
            can_make_workday = not is_standard_weekend and is_marked_as_holiday

            # Определяем, является ли день рабочим для отметки посещаемости
            is_workday_selected_for_attendance = self._is_workday(selected_py_date)

        self.make_holiday_button.setEnabled(can_make_holiday)
        self.make_workday_button.setEnabled(can_make_workday)

        has_selection_in_table = bool(
            self.attendance_table.selectionModel().selectedRows()
        )
        self.edit_button.setEnabled(
            has_selection_in_table
            and attendance_dialog_available
            and is_workday_selected_for_attendance
        )

        group_selected = self.group_filter_combo.currentData() is not None
        self.bulk_attendance_button.setEnabled(
            is_workday_selected_for_attendance
            and group_selected
            and bulk_attendance_dialog_available
        )

        self.refresh_button.setEnabled(
            self.group_filter_combo.count() > 0 and date_is_valid
        )  # Обновить можно если выбрана дата и есть группы
        logger.debug(
            f"  Button States After Update: make_holiday={self.make_holiday_button.isEnabled()}, make_workday={self.make_workday_button.isEnabled()}, edit_att={self.edit_button.isEnabled()}, bulk_att={self.bulk_attendance_button.isEnabled()}"
        )
        logger.debug(f"--- update_ui_element_states FINISHED ---")

    def on_date_selection_changed(self):
        self.update_ui_element_states()
        self.load_attendance_for_selected_filters()

    def on_filter_changed(self):
        self.update_ui_element_states()
        self.load_attendance_for_selected_filters()

    # --- Методы Действий ---
    def make_day_holiday(self):

        selected_qdate = self.calendar_widget.selectedDate()
        if not selected_qdate.isValid():
            return
        selected_date, date_str = selected_qdate.toPyDate(), selected_qdate.toString(
            "yyyy-MM-dd"
        )
        logger.info(f"Attempting to mark {date_str} as holiday.")
        self.status_changed.emit(f"Добавление выходного на {date_str}...")
        try:
            if self.api_client.add_holiday(
                {"date": date_str, "name": "Дополнительный выходной"}
            ):
                logger.info(f"Date {date_str} marked as holiday.")
                self.status_changed.emit(f"Дата {date_str} отмечена как выходной.")
                self.holidays_in_view.add(selected_date)
                self.update_calendar_display_format()
        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to mark {date_str} as holiday.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось отметить {date_str} как выходной:\n{e}"
            )
            self.status_changed.emit(f"Ошибка добавления выходного.")

    def make_day_workday(self):

        selected_qdate = self.calendar_widget.selectedDate()
        if (
            not selected_qdate.isValid()
            or selected_qdate.toPyDate() not in self.holidays_in_view
        ):
            return
        selected_date, date_str = selected_qdate.toPyDate(), selected_qdate.toString(
            "yyyy-MM-dd"
        )
        logger.info(f"Attempting to mark {date_str} as workday.")
        self.status_changed.emit(f"Удаление выходного на {date_str}...")
        try:
            if self.api_client.delete_holiday(date_str):
                logger.info(f"Date {date_str} unmarked as holiday.")
                self.status_changed.emit(f"Выходной на {date_str} отменен.")
                if selected_date in self.holidays_in_view:
                    self.holidays_in_view.remove(selected_date)
                self.update_calendar_display_format()
            else:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Не удалось отменить выходной на {date_str}. Сервер вернул ошибку.",
                )
                self.status_changed.emit(f"Ошибка отмены выходного.")
        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to mark {date_str} as workday.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось отменить выходной на {date_str}:\n{e}"
            )
            self.status_changed.emit(f"Ошибка отмены выходного.")

    def edit_attendance_record(self):

        selected_id = self._get_selected_attendance_id()
        if selected_id is None or not attendance_dialog_available:
            return
        selected_qdate = self.calendar_widget.selectedDate()
        if not selected_qdate.isValid() or not self._is_workday(
            selected_qdate.toPyDate()
        ):
            QMessageBox.information(
                self,
                "Информация",
                f"Редактирование посещаемости возможно только для рабочих дней.",
            )
            return

        record_data = next(
            (r for r in self.attendance_data if r.get("id") == selected_id), None
        )
        if not record_data:
            logger.error(f"No data for id {selected_id}")
            QMessageBox.warning(self, "Ошибка", "Данные не найдены.")
            return
        child_name = record_data.get("child", {}).get(
            "full_name", f"ID:{record_data.get('child_id')}"
        )
        dialog = AttendanceDialog(
            api_client=self.api_client,
            record_data=record_data,
            child_name=child_name,
            record_date=record_data.get("date"),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info(f"Record {selected_id} edited.")
            self.load_attendance_for_selected_filters()
            self.status_changed.emit(f"Запись ID {selected_id} обновлена.")
        else:
            logger.debug(f"Record {selected_id} edit cancelled.")

    def open_bulk_attendance_dialog(self):

        if not bulk_attendance_dialog_available:
            QMessageBox.critical(
                self, "Функция недоступна", "Модуль массовой отметки не загружен."
            )
            return
        selected_qdate, group_id, group_name = (
            self.calendar_widget.selectedDate(),
            self.group_filter_combo.currentData(),
            self.group_filter_combo.currentText(),
        )
        if group_id is None or not selected_qdate.isValid():
            QMessageBox.warning(self, "Внимание", "Выберите группу и корректную дату.")
            return
        selected_py_date = selected_qdate.toPyDate()
        if not self._is_workday(selected_py_date):
            QMessageBox.information(
                self,
                "Информация",
                f"Дата {selected_py_date.strftime('%d.%m.%Y')} нерабочая. Отметка посещаемости невозможна.",
            )
            return
        date_str = selected_qdate.toString("yyyy-MM-dd")
        logger.info(f"Bulk attendance GID {group_id} ('{group_name}') on {date_str}")
        self.status_changed.emit(f"Подготовка данных для '{group_name}'...")
        try:
            children = self.api_client.get_children(group_id=group_id, limit=200)
            if not children:
                QMessageBox.information(
                    self, "Информация", f"В группе '{group_name}' нет детей."
                )
                self.status_changed.emit("Нет детей.")
                return
            existing_records = {
                r["child_id"]: r
                for r in self.api_client.get_attendance(
                    attendance_date=date_str, group_id=group_id
                )
            }
            self.status_changed.emit("Данные загружены. Открытие диалога...")
            dialog = BulkAttendanceDialog(
                api_client=self.api_client,
                children_list=children,
                group_id=group_id,
                group_name=group_name,
                target_date=selected_py_date,
                existing_records_map=existing_records,
                parent=self,
            )
            dialog_result_code = dialog.exec()

            if dialog_result_code == QDialog.DialogCode.Accepted:

                bulk_update_data = dialog.get_attendance_data_for_api()

                if not bulk_update_data or not bulk_update_data.get("attendance_list"):
                    logger.info(
                        "No attendance data to submit from bulk dialog (collected data was empty)."
                    )
                    self.status_changed.emit("Нет данных для сохранения.")
                    return

                logger.info(f"Submitting bulk attendance data: {bulk_update_data}")
                self.status_changed.emit("Сохранение отметок...")

                updated_records = self.api_client.bulk_create_attendance(
                    bulk_update_data
                )

                QMessageBox.information(
                    self,
                    "Успех",
                    f"Посещаемость для группы '{group_name}' на {date_str} успешно обновлена.\nОбработано записей: {len(updated_records)}.",
                )
                self.status_changed.emit("Посещаемость обновлена.")
                self.load_attendance_for_selected_filters()
            else:
                logger.info("Bulk attendance dialog cancelled.")
                self.status_changed.emit("Массовая отметка отменена.")
        except (ApiClientError, Exception) as e:
            logger.exception("Error in bulk attendance process")
            QMessageBox.critical(self, "Ошибка", f"{e}")
            self.status_changed.emit(f"Ошибка: {str(e)[:50]}...")

    # --- Вспомогательные методы ---
    def _get_selected_attendance_id(self) -> Optional[int]:

        selected_rows = self.attendance_table.selectionModel().selectedRows()
        if selected_rows:
            id_item = self.attendance_table.item(selected_rows[0].row(), 0)
            if id_item:
                return id_item.data(Qt.ItemDataRole.UserRole)
        return None
