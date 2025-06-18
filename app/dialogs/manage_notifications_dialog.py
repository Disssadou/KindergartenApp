import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QHeaderView,
    QMessageBox,
    QComboBox,
    QCheckBox,
    QWidget,
)
from PyQt6.QtCore import (
    Qt,
    pyqtSignal,
    QDateTime,
    QTimeZone,
)
from PyQt6.QtGui import QIcon

from utils.api_client import ApiClient, ApiClientError


try:
    from database.models import NotificationAudience

    notification_audience_enum_available = True
except ImportError:
    logger_mnd_enum = logging.getLogger("KindergartenApp.ManageNotificationsDialog")
    logger_mnd_enum.error(
        "CRITICAL: Could not import NotificationAudience from database.models! Audience display will be raw."
    )

    class NotificationAudience(str):
        ALL = "all"
        PARENTS = "parents"
        TEACHERS = "teachers"

        def __init__(self, value):
            self.value = value

    notification_audience_enum_available = False


try:
    from .notification_form_dialog import NotificationFormDialog

    notification_form_dialog_available = True
except ImportError:

    logger_mnd = logging.getLogger("KindergartenApp.ManageNotificationsDialog")
    logger_mnd.error("CRITICAL: NotificationFormDialog could not be imported!")

    class NotificationFormDialog(QDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))
            QMessageBox.critical(self, "Ошибка", "Форма уведомления не загружена.")

    notification_form_dialog_available = False


logger = logging.getLogger("KindergartenApp.ManageNotificationsDialog")


class ManageNotificationsDialog(QDialog):

    AUDIENCE_DISPLAY_MAP = {
        NotificationAudience.ALL.value: "Всем пользователям",
        NotificationAudience.PARENTS.value: "Только родителям",
        NotificationAudience.TEACHERS.value: "Только воспитателям",
    }

    if notification_audience_enum_available and hasattr(
        NotificationAudience.ALL, "value"
    ):
        AUDIENCE_DISPLAY_MAP = {
            member.value: display_text
            for member, display_text in {
                NotificationAudience.ALL: "Всем пользователям",
                NotificationAudience.PARENTS: "Только родителям",
                NotificationAudience.TEACHERS: "Только воспитателям",
            }.items()
        }
    else:
        AUDIENCE_DISPLAY_MAP = {
            "all": "Всем пользователям",
            "parents": "Только родителям",
            "teachers": "Только воспитателям",
        }

    def __init__(
        self,
        api_client: ApiClient,
        notification_data: Optional[Dict] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.api_client = api_client
        self.notifications_data: List[Dict] = []

        self.setWindowTitle("Управление Уведомлениями и Событиями")
        self.setMinimumSize(800, 600)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        self.load_notifications()

    def _init_ui(self):

        main_layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Фильтр:"))
        self.type_filter_combo = QComboBox()
        self.type_filter_combo.addItem("Все типы", None)
        self.type_filter_combo.addItem("Только уведомления", False)
        self.type_filter_combo.addItem("Только события", True)
        self.type_filter_combo.currentIndexChanged.connect(self.load_notifications)
        filter_layout.addWidget(self.type_filter_combo)
        filter_layout.addStretch()
        self.refresh_button = QPushButton(QIcon.fromTheme("view-refresh"), "Обновить")
        self.refresh_button.clicked.connect(self.load_notifications)
        filter_layout.addWidget(self.refresh_button)
        main_layout.addLayout(filter_layout)
        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(6)
        self.notifications_table.setHorizontalHeaderLabels(
            ["ID", "Тип", "Заголовок", "Аудитория", "Дата события", "Создано"]
        )
        self.notifications_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.notifications_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.notifications_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.notifications_table.setSortingEnabled(True)
        self.notifications_table.verticalHeader().setVisible(False)
        self.notifications_table.setColumnHidden(0, True)
        header = self.notifications_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.notifications_table.itemSelectionChanged.connect(
            self._update_action_buttons_state
        )
        main_layout.addWidget(self.notifications_table)
        actions_layout = QHBoxLayout()
        self.create_button = QPushButton(QIcon.fromTheme("list-add"), "Создать новое")
        self.create_button.clicked.connect(self.handle_create_new)
        actions_layout.addWidget(self.create_button)
        self.edit_button = QPushButton(
            QIcon.fromTheme("document-edit"), "Редактировать"
        )
        self.edit_button.clicked.connect(self.handle_edit_selected)
        self.edit_button.setEnabled(False)
        actions_layout.addWidget(self.edit_button)
        self.delete_button = QPushButton(QIcon.fromTheme("edit-delete"), "Удалить")
        self.delete_button.clicked.connect(self.handle_delete_selected)
        self.delete_button.setEnabled(False)
        actions_layout.addWidget(self.delete_button)
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        main_layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        self.setLayout(main_layout)

    def load_notifications(self):

        logger.info("ManageNotificationsDialog: Loading notifications...")
        is_event_filter = self.type_filter_combo.currentData()
        self.notifications_table.setRowCount(0)
        self._update_action_buttons_state()
        try:
            self.notifications_data = self.api_client.get_notifications(
                limit=100, is_event=is_event_filter
            )
            self._populate_table()
            logger.info(f"Loaded {len(self.notifications_data)} notifications/events.")
        except ApiClientError as e:
            logger.exception("Failed to load notifications.")
            QMessageBox.critical(
                self,
                "Ошибка загрузки",
                f"Не удалось загрузить список уведомлений:\n{e.message}",
            )
        except Exception as e:
            logger.exception("Unexpected error loading notifications.")
            QMessageBox.critical(self, "Критическая ошибка", f"Произошла ошибка:\n{e}")

    def _populate_table(self):
        self.notifications_table.setRowCount(len(self.notifications_data))
        self.notifications_table.setSortingEnabled(False)

        for row, item_data in enumerate(self.notifications_data):
            item_id = item_data.get("id")
            is_event = item_data.get("is_event", False)

            type_icon = "📅 Событие" if is_event else "🔔 Увед."
            title = item_data.get("title", "Без заголовка")

            audience_value = item_data.get("audience", "N/A")

            audience_display = self.AUDIENCE_DISPLAY_MAP.get(
                audience_value, audience_value.capitalize()
            )

            event_date_str = item_data.get("event_date")
            display_event_date = ""
            if is_event and event_date_str:
                try:
                    dt_utc = datetime.fromisoformat(
                        event_date_str.replace("Z", "+00:00")
                    )
                    if dt_utc.tzinfo is None:
                        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                    dt_local = dt_utc.astimezone(None)
                    display_event_date = dt_local.strftime("%d.%m.%Y %H:%M")
                except ValueError:
                    display_event_date = event_date_str[:16]

            created_at_str = item_data.get("created_at", "")
            display_created_at = ""
            try:
                dt_c_utc = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                if dt_c_utc.tzinfo is None:
                    dt_c_utc = dt_c_utc.replace(tzinfo=timezone.utc)
                dt_c_local = dt_c_utc.astimezone(None)
                display_created_at = dt_c_local.strftime("%d.%m.%Y")
            except ValueError:
                display_created_at = created_at_str[:10]

            self.notifications_table.setItem(row, 0, QTableWidgetItem(str(item_id)))
            self.notifications_table.setItem(row, 1, QTableWidgetItem(type_icon))
            self.notifications_table.setItem(row, 2, QTableWidgetItem(title))
            self.notifications_table.setItem(row, 3, QTableWidgetItem(audience_display))
            self.notifications_table.setItem(
                row, 4, QTableWidgetItem(display_event_date)
            )
            self.notifications_table.setItem(
                row, 5, QTableWidgetItem(display_created_at)
            )

        self.notifications_table.resizeColumnsToContents()
        self.notifications_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.notifications_table.setSortingEnabled(True)
        self._update_action_buttons_state()

    def _update_action_buttons_state(self):
        has_selection = bool(self.notifications_table.selectionModel().selectedRows())
        self.edit_button.setEnabled(
            has_selection and notification_form_dialog_available
        )
        self.delete_button.setEnabled(has_selection)
        self.create_button.setEnabled(notification_form_dialog_available)

    def _get_selected_notification_id(self) -> Optional[int]:
        selected_rows = self.notifications_table.selectionModel().selectedRows()
        if selected_rows:
            id_item = self.notifications_table.item(selected_rows[0].row(), 0)
            if id_item:
                try:
                    return int(id_item.text())
                except ValueError:
                    return None
        return None

    def handle_create_new(self):
        logger.debug("Create new notification/event requested.")
        if not notification_form_dialog_available:
            QMessageBox.critical(
                self, "Ошибка", "Функционал создания уведомлений недоступен."
            )
            return
        dialog = NotificationFormDialog(api_client=self.api_client, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("New notification/event created successfully.")
            self.load_notifications()
        else:
            logger.info("Creation of new notification/event cancelled.")

    def handle_edit_selected(self):
        selected_id = self._get_selected_notification_id()
        if selected_id is None:
            return
        if not notification_form_dialog_available:
            QMessageBox.critical(
                self, "Ошибка", "Функционал редактирования уведомлений недоступен."
            )
            return
        notification_data_to_edit = next(
            (n for n in self.notifications_data if n.get("id") == selected_id), None
        )
        if not notification_data_to_edit:
            QMessageBox.warning(self, "Ошибка", "Не найдены данные для редактирования.")
            return
        dialog = NotificationFormDialog(
            api_client=self.api_client,
            notification_data=notification_data_to_edit,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info(f"Notification/event ID {selected_id} updated.")
            self.load_notifications()
        else:
            logger.info(f"Editing of notification/event ID {selected_id} cancelled.")

    def handle_delete_selected(self):
        selected_id = self._get_selected_notification_id()
        if selected_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить уведомление/событие ID {selected_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.api_client.delete_notification(selected_id):
                    QMessageBox.information(
                        self, "Успех", f"Уведомление/событие ID {selected_id} удалено."
                    )
                    self.load_notifications()
                else:
                    QMessageBox.warning(
                        self, "Ошибка", f"Не удалось удалить ID {selected_id}."
                    )
            except ApiClientError as e:
                QMessageBox.critical(
                    self, "Ошибка API", f"Не удалось удалить: {e.message}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {e}")
