import logging
from typing import List, Dict, Optional
from functools import partial
from datetime import (
    datetime,
    timezone,
)

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QMessageBox,
    QApplication,
    QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QPixmap

from utils.api_client import ApiClient, ApiClientError


try:
    from app.dialogs.post_dialog import PostDialog

    post_dialog_available = True
except ImportError:
    logger_dv = logging.getLogger("KindergartenApp.DashboardView")
    logger_dv.error(
        "CRITICAL: PostDialog could not be imported! Create/Edit post functionality will be MISSING."
    )

    class PostDialog(QDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))
            QMessageBox.critical(self, "Ошибка", "Диалог постов не загружен.")

    post_dialog_available = False

try:
    from app.dialogs.manage_notifications_dialog import ManageNotificationsDialog

    manage_notifications_dialog_available = True
except ImportError:
    logger_dv = logging.getLogger("KindergartenApp.DashboardView")
    logger_dv.error(
        "CRITICAL: ManageNotificationsDialog could not be imported! Notifications functionality will be MISSING."
    )

    class ManageNotificationsDialog(QDialog):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))
            QMessageBox.critical(
                self, "Ошибка", "Диалог управления уведомлениями не загружен."
            )

    manage_notifications_dialog_available = False

logger = logging.getLogger("KindergartenApp.DashboardView")


# --- Кастомный виджет для одного поста ---
class PostItemWidget(QFrame):
    edit_requested = pyqtSignal(dict)
    delete_requested = pyqtSignal(int)

    def __init__(
        self,
        post_data: Dict,
        api_client: ApiClient,
        image_cache: Dict[str, QPixmap],
        parent_view: "DashboardView",
    ):
        super().__init__(parent_view)
        self.post_data = post_data
        self.api_client = api_client
        self.parent_view = parent_view
        self.image_cache = image_cache
        self.image_preview_label: Optional[QLabel] = None

        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._init_item_ui()
        self._load_thumbnail_pseudo_async()

    def _init_item_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        if self.post_data.get("title"):
            title_label = QLabel(f"<b>{self.post_data['title']}</b>")
            title_font = title_label.font()
            title_font.setPointSize(title_font.pointSize() + 2)
            title_label.setFont(title_font)
            layout.addWidget(title_label)

        text_label = QLabel(self.post_data.get("text_content", "Нет текста."))
        text_label.setWordWrap(True)
        text_label.setMaximumHeight(100)
        layout.addWidget(text_label)

        self.image_preview_label = QLabel("Загрузка превью...")
        self.image_preview_label.setMinimumSize(200, 120)
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setFrameShape(QFrame.Shape.Box)
        layout.addWidget(self.image_preview_label)

        meta_layout = QHBoxLayout()
        author_info = self.post_data.get("author")
        author_text = "Автор: Неизвестен"
        if author_info and isinstance(author_info, dict):
            author_name = author_info.get("full_name", author_info.get("username"))
            if not author_name and self.post_data.get("author_id"):
                author_name = f"ID: {self.post_data.get('author_id')}"
            author_text = f"Автор: {author_name or 'Не указан'}"
        elif self.post_data.get("author_id"):
            author_text = f"Автор ID: {self.post_data.get('author_id')}"

        created_at_str = self.post_data.get("created_at", "")
        date_text = f"Дата: {created_at_str}"
        try:
            created_dt_utc = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
            created_dt_local = created_dt_utc.astimezone(None)
            date_text = f"Дата: {created_dt_local.strftime('%d.%m.%Y %H:%M')}"
        except (ValueError, TypeError) as e_date:
            logger.warning(
                f"Could not parse date '{created_at_str}' for post {self.post_data.get('id')}: {e_date}"
            )

        meta_label = QLabel(f"<small>{author_text} | {date_text}</small>")
        meta_layout.addWidget(meta_label)
        meta_layout.addStretch()
        if self.post_data.get("is_pinned"):
            pinned_label = QLabel("<b>📌 Закреплено</b>")
            pinned_label.setStyleSheet("color: #FF0000;")
            meta_layout.addWidget(pinned_label)
        layout.addLayout(meta_layout)

        post_actions_layout = QHBoxLayout()
        post_actions_layout.addStretch()
        edit_button = QPushButton(QIcon.fromTheme("document-edit"), "Редактировать")
        edit_button.clicked.connect(lambda: self.edit_requested.emit(self.post_data))
        post_actions_layout.addWidget(edit_button)
        delete_button = QPushButton(QIcon.fromTheme("edit-delete"), "Удалить")
        delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self.post_data["id"])
        )
        post_actions_layout.addWidget(delete_button)
        layout.addLayout(post_actions_layout)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            logger.debug(
                f"PostItemWidget double-clicked for post ID: {self.post_data.get('id')}"
            )
            self.edit_requested.emit(self.post_data)
        super().mouseDoubleClickEvent(event)

    def _load_thumbnail_pseudo_async(self):
        media_files = self.post_data.get("media_files", [])
        if not media_files or not self.image_preview_label:
            if self.image_preview_label:
                self.image_preview_label.setText("Нет изображения")
            return

        thumb_filename = media_files[0].get("thumbnail_path")
        if not thumb_filename:
            self.image_preview_label.setText("Превью недоступно")
            return

        # Проверка кэша
        if thumb_filename in self.image_cache:
            pixmap = self.image_cache[thumb_filename]
            self._set_pixmap_to_label(
                pixmap, media_files[0].get("original_filename", "файл")
            )
            return

        QTimer.singleShot(
            10,
            lambda tf=thumb_filename, of=media_files[0].get(
                "original_filename", "файл"
            ): self._fetch_and_set_thumbnail(tf, of),
        )

    def _fetch_and_set_thumbnail(self, thumb_filename: str, original_filename: str):
        if not self.image_preview_label:
            return

        relative_path_for_api = f"post_media/{thumb_filename}"
        logger.debug(
            f"PostItem ID {self.post_data.get('id')}: Fetching thumbnail from {relative_path_for_api}"
        )

        image_bytes = self.api_client.get_image_bytes(relative_path_for_api)
        pixmap = None
        if image_bytes:
            temp_pixmap = QPixmap()
            if temp_pixmap.loadFromData(image_bytes):
                pixmap = temp_pixmap
                self.image_cache[thumb_filename] = pixmap  # Кэшируем
            else:
                logger.warning(
                    f"Could not load QPixmap from bytes for {original_filename} (post {self.post_data.get('id')})"
                )
        else:
            logger.warning(
                f"get_image_bytes returned None for {original_filename} (post {self.post_data.get('id')})"
            )

        if self.image_preview_label:
            self._set_pixmap_to_label(pixmap, original_filename)

    def _set_pixmap_to_label(self, pixmap: Optional[QPixmap], original_filename: str):
        if pixmap and not pixmap.isNull():
            self.image_preview_label.setPixmap(
                pixmap.scaled(
                    self.image_preview_label.width(),
                    self.image_preview_label.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.image_preview_label.setText(f"Ошибка\nзагрузки\n{original_filename}")


# --- Основной класс DashboardView ---
class DashboardView(QWidget):
    status_changed = pyqtSignal(str)
    PAGE_LIMIT = 10

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.posts_data: List[Dict] = []
        self.image_cache: Dict[str, QPixmap] = {}
        self.current_skip = 0
        self.can_load_more_posts = True

        self.initUI()
        self.load_initial_posts()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        controls_layout = QHBoxLayout()
        self.refresh_button = QPushButton(
            QIcon.fromTheme("view-refresh"), "Обновить ленту"
        )
        self.refresh_button.clicked.connect(self.refresh_all_posts)
        controls_layout.addWidget(self.refresh_button)
        self.create_post_button = QPushButton(
            QIcon.fromTheme("document-new"), "Создать пост"
        )
        self.create_post_button.clicked.connect(self.open_create_post_dialog)
        if not post_dialog_available:
            self.create_post_button.setEnabled(False)
        controls_layout.addWidget(self.create_post_button)
        controls_layout.addStretch()

        self.manage_notifications_button = QPushButton(
            QIcon.fromTheme(
                "mail-mark-unread", QIcon.fromTheme("emblem-synchronizing")
            ),
            "🔔Уведомления/События",
        )
        self.manage_notifications_button.setToolTip(
            "Открыть окно управления уведомлениями и событиями"
        )
        self.manage_notifications_button.clicked.connect(
            self.open_manage_notifications_dialog
        )
        if not manage_notifications_dialog_available:
            self.manage_notifications_button.setEnabled(False)
            self.manage_notifications_button.setToolTip(
                "Функционал уведомлений недоступен (ошибка загрузки модуля)."
            )
        controls_layout.addWidget(self.manage_notifications_button)

        main_layout.addLayout(controls_layout)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.StyledPanel)

        self.posts_container_widget = (
            QWidget()
        )  # Этот виджет будет содержать posts_layout
        self.posts_layout = QVBoxLayout(
            self.posts_container_widget
        )  # Этот layout будет внутри posts_container_widget
        self.posts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.posts_layout.setSpacing(10)

        scroll_area.setWidget(
            self.posts_container_widget
        )  # Устанавливаем контейнер в scroll_area
        main_layout.addWidget(scroll_area)

        self.load_more_button = QPushButton("Загрузить еще посты...")
        self.load_more_button.clicked.connect(self.load_more_posts_action)
        self.load_more_button.setVisible(False)
        main_layout.addWidget(self.load_more_button, 0, Qt.AlignmentFlag.AlignCenter)
        self.setLayout(main_layout)

    def refresh_all_posts(self):
        logger.info("DashboardView: Refreshing all posts.")
        self.current_skip = 0
        self.posts_data.clear()
        self.can_load_more_posts = True

        while self.posts_layout.count():
            item = self.posts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

        self.load_posts_segment()

    def load_initial_posts(self):
        self.refresh_all_posts()

    def load_more_posts_action(self):
        if self.can_load_more_posts:
            self.current_skip += self.PAGE_LIMIT
            self.load_posts_segment()

    def load_posts_segment(self):
        if not self.can_load_more_posts:
            self.load_more_button.setVisible(False)
            return
        self.status_changed.emit(f"Загрузка постов (с {self.current_skip})...")
        logger.info(
            f"DashboardView: Loading posts segment, skip={self.current_skip}, limit={self.PAGE_LIMIT}"
        )
        self.load_more_button.setEnabled(False)
        try:
            new_posts = self.api_client.get_posts(
                skip=self.current_skip, limit=self.PAGE_LIMIT, pinned_only=None
            )
            if self.current_skip == 0:
                self.posts_data = new_posts
            else:
                self.posts_data.extend(new_posts)
            self.display_new_posts(new_posts)
            if len(new_posts) < self.PAGE_LIMIT:
                self.can_load_more_posts = False
                self.load_more_button.setVisible(False)
                self.status_changed.emit("Все посты загружены.")
            else:
                self.can_load_more_posts = True
                self.load_more_button.setVisible(True)
                self.status_changed.emit(
                    f"Загружено {len(self.posts_data)} постов. Можно загрузить еще."
                )
        except ApiClientError as e:
            logger.exception("Failed to load posts segment.")
            QMessageBox.warning(self, "Ошибка", f"{e.message}")
            self.status_changed.emit("Ошибка загрузки постов.")
        finally:
            self.load_more_button.setEnabled(True)

    def open_manage_notifications_dialog(self):
        if not manage_notifications_dialog_available:
            QMessageBox.critical(
                self, "Ошибка", "Диалог управления уведомлениями не доступен."
            )
            return

        dialog = ManageNotificationsDialog(api_client=self.api_client, parent=self)
        dialog.exec()
        logger.info("ManageNotificationsDialog closed.")

    def display_new_posts(self, new_posts_data: List[Dict]):

        if self.current_skip == 0 and self.posts_layout.count() > 0:
            item = self.posts_layout.itemAt(0)
            if (
                item
                and item.widget()
                and isinstance(item.widget(), QLabel)
                and "Нет доступных постов" in item.widget().text()
            ):
                widget_to_remove = self.posts_layout.takeAt(0).widget()
                if widget_to_remove:
                    widget_to_remove.deleteLater()

        if self.posts_layout.count() > 0:
            last_item_index = self.posts_layout.count() - 1
            last_item = self.posts_layout.itemAt(last_item_index)
            if not last_item.widget():
                self.posts_layout.removeItem(last_item)

        if not new_posts_data and not self.posts_data:
            no_posts_label = QLabel("Нет доступных постов.")
            no_posts_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.posts_layout.addWidget(no_posts_label)
            self.posts_layout.addStretch()
            return

        for post_data in new_posts_data:
            post_item_widget = PostItemWidget(
                post_data, self.api_client, self.image_cache, self
            )
            post_item_widget.edit_requested.connect(self.open_edit_post_dialog)
            post_item_widget.delete_requested.connect(self.handle_delete_post)
            self.posts_layout.addWidget(post_item_widget)

        self.posts_layout.addStretch()

    def open_create_post_dialog(self):
        if not post_dialog_available:
            QMessageBox.critical(self, "Ошибка", "Диалог создания поста не доступен.")
            return
        dialog = PostDialog(api_client=self.api_client, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_changed.emit("Новый пост успешно создан. Обновление ленты...")
            self.refresh_all_posts()
        else:
            self.status_changed.emit("Создание поста отменено.")

    def open_edit_post_dialog(self, post_to_edit_data: Dict):
        if not post_dialog_available:
            QMessageBox.critical(
                self, "Ошибка", "Диалог редактирования поста не доступен."
            )
            return
        if not post_to_edit_data or not post_to_edit_data.get("id"):
            logger.error("Invalid data for edit.")
            return

        logger.info(f"Opening PostDialog to edit post ID: {post_to_edit_data['id']}")
        dialog = PostDialog(
            api_client=self.api_client, post_data=post_to_edit_data, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.status_changed.emit(
                f"Пост ID {post_to_edit_data['id']} обновлен. Обновление ленты..."
            )
            self.refresh_all_posts()
        else:
            self.status_changed.emit("Редактирование поста отменено.")

    def handle_delete_post(self, post_id: int):
        if post_id is None:
            return
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Удалить пост ID {post_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.status_changed.emit(f"Удаление поста ID {post_id}...")
            try:
                if self.api_client.delete_post(post_id):
                    self.status_changed.emit(
                        f"Пост ID {post_id} удален. Обновление ленты..."
                    )
                    self.refresh_all_posts()
                else:
                    QMessageBox.warning(
                        self, "Ошибка", f"Не удалось удалить пост ID {post_id}."
                    )
                    self.status_changed.emit(f"Ошибка удаления поста ID {post_id}.")
            except ApiClientError as e:
                logger.exception(f"API error deleting post: {e.message}")
                QMessageBox.critical(
                    self, "Ошибка API", f"Не удалось удалить пост:\n{e.message}"
                )
                self.status_changed.emit("Ошибка API при удалении поста.")
            except Exception as e:
                logger.exception(f"Unexpected error deleting post {post_id}: {e}")
                QMessageBox.critical(
                    self,
                    "Непредвиденная ошибка",
                    f"Произошла ошибка при удалении поста:\n{e}",
                )
                self.status_changed.emit("Непредвиденная ошибка при удалении поста.")
