import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QCheckBox,
    QDateTimeEdit,
    QComboBox,
    QDialogButtonBox,
    QMessageBox,
    QWidget,
)
from PyQt6.QtCore import Qt, QDateTime, QTimeZone
from PyQt6.QtGui import QIcon

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


try:
    from database.models import NotificationAudience
except ImportError:
    logger_nfd = logging.getLogger("KindergartenApp.NotificationFormDialog")
    logger_nfd.error(
        "CRITICAL: Could not import NotificationAudience from database.models!"
    )

    class NotificationAudience(str):
        ALL = "all"
        PARENTS = "parents"
        TEACHERS = "teachers"

    def __init__(self, value):
        self.value = value


logger = logging.getLogger("KindergartenApp.NotificationFormDialog")


class NotificationFormDialog(QDialog):
    # Карта для отображения аудиторий на русском
    AUDIENCE_DISPLAY = {
        NotificationAudience.ALL: "Всем пользователям",
        NotificationAudience.PARENTS: "Только родителям",
        NotificationAudience.TEACHERS: "Только воспитателям",
    }

    def __init__(
        self,
        api_client: ApiClient,
        notification_data: Optional[Dict] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.api_client = api_client
        self.notification_data = notification_data
        self.is_editing = notification_data is not None

        title = (
            "Создать уведомление/событие"
            if not self.is_editing
            else "Редактировать уведомление/событие"
        )
        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        if self.is_editing and self.notification_data:
            self._load_data_to_form()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Краткий заголовок")
        form_layout.addRow("Заголовок:", self.title_edit)

        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText(
            "Полный текст уведомления или описание события"
        )
        self.content_edit.setMinimumHeight(100)
        form_layout.addRow("Текст:", self.content_edit)

        self.audience_combo = QComboBox()
        for audience_enum in NotificationAudience:
            self.audience_combo.addItem(
                self.AUDIENCE_DISPLAY.get(audience_enum, audience_enum.value),
                audience_enum.value,
            )
        form_layout.addRow("Аудитория:", self.audience_combo)

        self.is_event_checkbox = QCheckBox("Это событие (будет иметь дату и время)")
        self.is_event_checkbox.stateChanged.connect(self._toggle_event_date_edit_state)
        form_layout.addRow(self.is_event_checkbox)

        self.event_date_edit = QDateTimeEdit()
        self.event_date_edit.setCalendarPopup(True)
        self.event_date_edit.setDateTime(QDateTime.currentDateTime().addDays(1))
        self.event_date_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.event_date_edit.setEnabled(False)
        form_layout.addRow("Дата и время события:", self.event_date_edit)

        main_layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        button_box.accepted.connect(self._handle_save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _toggle_event_date_edit_state(self):
        is_event = self.is_event_checkbox.isChecked()
        self.event_date_edit.setEnabled(is_event)
        if not is_event:

            pass

    def _load_data_to_form(self):
        if not self.notification_data:
            return

        self.title_edit.setText(self.notification_data.get("title", ""))
        self.content_edit.setPlainText(self.notification_data.get("content", ""))

        audience_val = self.notification_data.get("audience")
        if audience_val:
            index = self.audience_combo.findData(audience_val)
            if index >= 0:
                self.audience_combo.setCurrentIndex(index)

        is_event_val = self.notification_data.get("is_event", False)
        self.is_event_checkbox.setChecked(is_event_val)
        self._toggle_event_date_edit_state()

        event_date_str = self.notification_data.get("event_date")
        if is_event_val and event_date_str:
            try:
                # API возвращает datetime в UTC (с 'Z' или смещением +00:00)
                # QDateTime.fromisoformat ожидает строку без 'Z', но может парсить со смещением
                # Преобразуем в локальное время для QDateTimeEdit
                dt_utc = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                # Указываем, что это UTC, если нет информации о зоне
                if dt_utc.tzinfo is None:
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)

                dt_local = dt_utc.astimezone(None)
                self.event_date_edit.setDateTime(QDateTime(dt_local))

            except ValueError as e:
                logger.error(f"Error parsing event_date '{event_date_str}': {e}")
                self.event_date_edit.setDateTime(
                    QDateTime.currentDateTime().addDays(1)
                )  # Ставим дефолтное
        else:
            self.event_date_edit.setDateTime(QDateTime.currentDateTime().addDays(1))

    def _handle_save(self):
        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        audience_value = self.audience_combo.currentData()
        is_event_checked = self.is_event_checkbox.isChecked()

        event_date_iso: Optional[str] = None
        if is_event_checked:
            q_datetime_local = self.event_date_edit.dateTime()

            dt_python_with_offset = q_datetime_local.toTimeZone(
                QTimeZone.utc()
            )  # Получаем QDateTime в UTC
            event_date_iso = dt_python_with_offset.toString(Qt.DateFormat.ISODateWithMs)

        if not title:
            QMessageBox.warning(self, "Ошибка ввода", "Заголовок не может быть пустым.")
            return
        if not content:
            QMessageBox.warning(self, "Ошибка ввода", "Текст не может быть пустым.")
            return
        if is_event_checked and not event_date_iso:
            QMessageBox.warning(
                self, "Ошибка ввода", "Для события необходимо указать дату и время."
            )
            return

        payload: Dict[str, Any] = {
            "title": title,
            "content": content,
            "audience": audience_value,
            "is_event": is_event_checked,
            "event_date": event_date_iso,
        }

        if not is_event_checked:
            payload["event_date"] = None

        try:
            if self.is_editing and self.notification_data:

                notif_id = self.notification_data["id"]
                logger.info(
                    f"Updating notification/event ID {notif_id} with payload: {payload}"
                )
                self.api_client.update_notification(notif_id, payload)
                QMessageBox.information(
                    self, "Успех", "Уведомление/событие успешно обновлено."
                )
            else:

                logger.info(f"Creating new notification/event with payload: {payload}")
                self.api_client.create_notification(payload)
                QMessageBox.information(
                    self, "Успех", "Новое уведомление/событие успешно создано."
                )

            self.accept()

        except ApiHttpError as e:
            logger.error(
                f"API HTTP Error saving notification: {e.message} (Status: {e.status_code})"
            )
            QMessageBox.critical(
                self,
                f"Ошибка API ({e.status_code})",
                f"Не удалось сохранить:\n{e.message}",
            )
        except ApiClientError as e:
            logger.exception(f"API Client Error saving notification: {e.message}")
            QMessageBox.critical(
                self, "Ошибка API", f"Не удалось сохранить:\n{e.message}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error saving notification: {e}")
            QMessageBox.critical(
                self, "Критическая ошибка", f"Произошла непредвиденная ошибка:\n{e}"
            )
