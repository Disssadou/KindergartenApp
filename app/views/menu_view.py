import logging
from datetime import date
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QCalendarWidget,
    QTextEdit,
    QPlainTextEdit,
    QLabel,
    QMessageBox,
    QFormLayout,
    QSpacerItem,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate
from PyQt6.QtGui import QIcon

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


try:

    from database.models import MealType
except ImportError:

    try:
        from database.schemas import MealType
    except ImportError:

        print("WARNING: Could not import MealType Enum. Using string literals.")

        class MealType:
            BREAKFAST = "breakfast"
            LUNCH = "lunch"
            SNACK = "snack"


logger = logging.getLogger("KindergartenApp")


class MenuView(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client

        self.current_day_menu = {}

        self.initUI()
        # Загружаем меню на СЕГОДНЯ при первом открытии
        today = QDate.currentDate()
        self.calendar_widget.setSelectedDate(today)
        self.load_menu_for_selected_date()

    def initUI(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Левая часть: Календарь ---
        left_layout = QVBoxLayout()
        left_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.calendar_widget = QCalendarWidget()
        self.calendar_widget.setGridVisible(True)

        self.calendar_widget.setMaximumSize(400, 300)
        self.calendar_widget.selectionChanged.connect(self.load_menu_for_selected_date)

        left_layout.addWidget(QLabel("Выберите дату:"))
        left_layout.addWidget(self.calendar_widget)
        left_layout.addSpacerItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        # --- Правая часть: Поля ввода и кнопка ---
        right_layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.breakfast_edit = QPlainTextEdit()
        self.breakfast_edit.setPlaceholderText("Введите описание завтрака...")
        self.breakfast_edit.setFixedHeight(80)
        form_layout.addRow("🍳 Завтрак:", self.breakfast_edit)

        self.lunch_edit = QPlainTextEdit()
        self.lunch_edit.setPlaceholderText("Введите описание обеда...")
        self.lunch_edit.setFixedHeight(100)
        form_layout.addRow("🍲 Обед:", self.lunch_edit)

        self.snack_edit = QPlainTextEdit()
        self.snack_edit.setPlaceholderText("Введите описание полдника...")
        self.snack_edit.setFixedHeight(80)
        form_layout.addRow("🍎 Полдник:", self.snack_edit)

        right_layout.addLayout(form_layout)

        # Кнопка сохранения
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = QPushButton(QIcon(), "Сохранить меню на выбранную дату")
        self.save_button.setToolTip(
            "Сохранить изменения для завтрака, обеда и полдника"
        )
        self.save_button.clicked.connect(self.save_menu)
        button_layout.addWidget(self.save_button)
        right_layout.addLayout(button_layout)

        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 3)

        self.setLayout(main_layout)

    def load_menu_for_selected_date(self):
        """Загружает меню для даты, выбранной в календаре."""
        selected_qdate = self.calendar_widget.selectedDate()
        selected_date = selected_qdate.toPyDate()
        date_str = selected_date.strftime("%Y-%m-%d")
        self.status_changed.emit(f"Загрузка меню на {date_str}...")
        logger.info(f"Loading menu for date: {date_str}")

        self.breakfast_edit.clear()
        self.lunch_edit.clear()
        self.snack_edit.clear()
        self.current_day_menu = {}

        try:

            endpoint = "/menus/"
            params = {"start_date": date_str, "end_date": date_str}
            menus_for_day = self.api_client.get_menus(
                start_date=date_str, end_date=date_str
            )

            if menus_for_day:
                for menu_item in menus_for_day:
                    meal_type_str = menu_item.get("meal_type")
                    description = menu_item.get("description", "")
                    self.current_day_menu[meal_type_str] = description

                    if meal_type_str == MealType.BREAKFAST.value:
                        self.breakfast_edit.setPlainText(description)
                    elif meal_type_str == MealType.LUNCH.value:
                        self.lunch_edit.setPlainText(description)
                    elif meal_type_str == MealType.SNACK.value:
                        self.snack_edit.setPlainText(description)
                self.status_changed.emit(f"Меню на {date_str} загружено.")
                logger.info(f"Menu loaded for {date_str}.")
            else:
                self.status_changed.emit(f"Меню на {date_str} не найдено.")
                logger.info(f"No menu found for {date_str}.")

        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to load menu for {date_str}: {e}")
            self.status_changed.emit(f"Ошибка загрузки меню: {e}")
            QMessageBox.warning(
                self,
                "Ошибка загрузки",
                f"Не удалось загрузить меню на {date_str}:\n{e}",
            )

    def save_menu(self):
        """Сохраняет данные меню для выбранной даты."""
        selected_qdate = self.calendar_widget.selectedDate()
        selected_date = selected_qdate.toPyDate()
        date_str = selected_date.strftime("%Y-%m-%d")
        self.status_changed.emit(f"Сохранение меню на {date_str}...")
        logger.info(f"Saving menu for date: {date_str}")

        menu_items_to_save = {
            MealType.BREAKFAST.value: self.breakfast_edit.toPlainText().strip(),
            MealType.LUNCH.value: self.lunch_edit.toPlainText().strip(),
            MealType.SNACK.value: self.snack_edit.toPlainText().strip(),
        }

        errors = []
        success_count = 0
        items_processed = 0

        for meal_type, description in menu_items_to_save.items():
            items_processed += 1
            payload = {
                "date": date_str,
                "meal_type": meal_type,
                # Описание может быть пустым для удаления через API
                "description": description,
            }
            try:

                result = self.api_client.upsert_menu(payload)
                if result is None and description == "":
                    logger.info(f"Menu item '{meal_type}' for {date_str} deleted.")
                    success_count += 1
                elif isinstance(result, dict) and description != "":
                    logger.info(
                        f"Menu item '{meal_type}' for {date_str} saved/updated. ID: {result.get('id')}"
                    )
                    success_count += 1
                else:

                    errors.append(f"Не удалось обработать {meal_type}.")
                    logger.warning(
                        f"Unexpected result for upserting {meal_type} on {date_str}: {result}"
                    )

            except (ApiClientError, Exception) as e:
                logger.exception(
                    f"Failed to save menu item '{meal_type}' for {date_str}: {e}"
                )
                errors.append(f"Ошибка сохранения {meal_type}: {e}")

        if not errors:
            self.status_changed.emit(f"Меню на {date_str} успешно сохранено.")
            QMessageBox.information(
                self, "Успех", f"Меню на {date_str} успешно сохранено."
            )

        else:
            error_details = "\n".join(errors)
            self.status_changed.emit(f"Ошибки при сохранении меню на {date_str}.")
            QMessageBox.warning(
                self,
                "Ошибки сохранения",
                f"Произошли ошибки при сохранении меню на {date_str}:\n{error_details}",
            )
