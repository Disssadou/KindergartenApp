import logging
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
    QMessageBox,
    QCheckBox,
    QFileDialog,
    QWidget,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap

from utils.api_client import (
    ApiClient,
    ApiClientError,
    ApiHttpError,
)

logger = logging.getLogger("KindergartenApp.PostDialog")


class PostDialog(QDialog):

    def __init__(
        self,
        api_client: ApiClient,
        post_data: Optional[Dict] = None,
        parent: Optional[QWidget] = None,
    ):
        """
        Диалог для создания или редактирования поста.
        - Если post_data is None, диалог работает в режиме создания.
        - Если post_data предоставлен, диалог работает в режиме редактирования.
        """
        super().__init__(parent)
        self.api_client = api_client
        self.post_data = post_data
        self.is_editing = post_data is not None

        self.new_image_path: Optional[str] = None
        self.delete_current_image_flag: bool = False

        self.setWindowTitle(
            "Создать новый пост" if not self.is_editing else "Редактировать пост"
        )
        self.setMinimumWidth(600)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._init_ui()
        if self.is_editing and self.post_data:
            self._load_post_data_to_form()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()

        # Заголовок поста
        form_layout.addWidget(QLabel("Заголовок (необязательно):"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Введите заголовок поста")
        form_layout.addWidget(self.title_edit)

        # Текст поста
        form_layout.addWidget(QLabel("Текст поста (обязательно):"))
        self.text_content_edit = QTextEdit()
        self.text_content_edit.setPlaceholderText("Введите основной текст поста...")
        self.text_content_edit.setMinimumHeight(150)
        form_layout.addWidget(self.text_content_edit)

        # Флажок "Закрепить пост"
        self.pinned_checkbox = QCheckBox(
            "Закрепить пост (будет отображаться вверху ленты)"
        )
        form_layout.addWidget(self.pinned_checkbox)

        main_layout.addLayout(form_layout)

        # --- Секция для изображения  ---
        image_section_layout = QHBoxLayout()
        image_controls_layout = QVBoxLayout()

        self.image_preview_label = QLabel("Нет изображения")
        self.image_preview_label.setMinimumSize(
            150, 100
        )  # Минимальный размер для превью
        self.image_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_label.setFrameShape(
            QFrame.Shape.StyledPanel
        )  # Рамка для превью
        image_section_layout.addWidget(self.image_preview_label, 1)

        self.select_image_button = QPushButton(
            QIcon.fromTheme("document-open"), "Выбрать изображение..."
        )
        self.select_image_button.clicked.connect(self._select_image)
        image_controls_layout.addWidget(self.select_image_button)

        self.remove_image_button = QPushButton(
            QIcon.fromTheme("edit-delete"), "Удалить текущее изображение"
        )
        self.remove_image_button.clicked.connect(self._mark_image_for_deletion)
        self.remove_image_button.setEnabled(False)
        image_controls_layout.addWidget(self.remove_image_button)

        image_controls_layout.addStretch()
        image_section_layout.addLayout(image_controls_layout, 0)
        main_layout.addLayout(image_section_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.button(QDialogButtonBox.StandardButton.Save).setText("Сохранить")
        button_box.accepted.connect(self.handle_save)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def _load_post_data_to_form(self):
        """Заполняет поля формы данными существующего поста (для режима редактирования)."""
        if not self.post_data:
            return
        self.title_edit.setText(self.post_data.get("title", ""))
        self.text_content_edit.setPlainText(self.post_data.get("text_content", ""))
        self.pinned_checkbox.setChecked(self.post_data.get("is_pinned", False))

        self.new_image_path = None
        self.delete_current_image_flag = False
        self.image_preview_label.setText("Нет изображения")
        self.image_preview_label.setPixmap(QPixmap())
        self.remove_image_button.setEnabled(False)

        media_files = self.post_data.get("media_files", [])
        if media_files and isinstance(media_files, list) and len(media_files) > 0:
            first_media = media_files[0]
            thumb_relative_path = first_media.get("thumbnail_path")
            original_filename = first_media.get("original_filename", "файл")

            if thumb_relative_path:

                self.image_preview_label.setText(
                    f"Изобр.: {original_filename}\n(Превью: {thumb_relative_path})"
                )
                self.remove_image_button.setEnabled(True)
            else:
                self.image_preview_label.setText("Превью недоступно")
        else:
            self.image_preview_label.setText("Нет изображения")
            self.remove_image_button.setEnabled(False)

        self.new_image_path = None
        self.delete_current_image_flag = False

    def _select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите изображение для поста",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.gif)",
        )
        if file_path:
            self.new_image_path = file_path

            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                self.image_preview_label.setPixmap(
                    pixmap.scaled(
                        self.image_preview_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                self.image_preview_label.setText("Не удалось\nотобразить\nпревью")
            self.remove_image_button.setEnabled(True)
            self.delete_current_image_flag = False
            logger.info(f"New image selected for post: {file_path}")

    def _mark_image_for_deletion(self):
        if self.is_editing and self.post_data and self.post_data.get("media_files"):
            reply = QMessageBox.question(
                self,
                "Удаление изображения",
                "Вы уверены, что хотите удалить текущее изображение у этого поста?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.delete_current_image_flag = True
                self.new_image_path = None
                self.image_preview_label.setText("Изображение\nбудет удалено")
                self.remove_image_button.setEnabled(False)
                logger.info("Current image marked for deletion.")
        elif self.new_image_path:
            self.new_image_path = None
            self.image_preview_label.setText("Нет изображения")
            self.remove_image_button.setEnabled(False)
            self.delete_current_image_flag = False
            logger.info("Newly selected image cleared.")

    def handle_save(self):
        title = self.title_edit.text().strip() or None  # None если пустой заголовок
        text_content = self.text_content_edit.toPlainText().strip()
        is_pinned = self.pinned_checkbox.isChecked()

        if not text_content:
            QMessageBox.warning(
                self, "Ошибка ввода", "Текст поста не может быть пустым."
            )
            return

        try:
            if self.is_editing and self.post_data:
                # --- РЕДАКТИРОВАНИЕ ПОСТА ---
                post_id = self.post_data["id"]
                logger.info(f"Attempting to update post ID: {post_id}")

                # 1. Обновляем текстовые данные
                self.api_client.update_post_text(
                    post_id, title, text_content, is_pinned
                )
                logger.info(f"Post text data for ID {post_id} updated.")

                # 2. Управляем изображением
                if self.new_image_path:  # Загружаем новое/заменяем старое
                    logger.info(
                        f"Uploading new image {self.new_image_path} for post {post_id}"
                    )
                    self.api_client.upload_post_image(post_id, self.new_image_path)
                    logger.info(f"New image uploaded for post {post_id}.")
                elif self.delete_current_image_flag:  # Удаляем существующее
                    current_media = self.post_data.get("media_files", [])
                    if current_media:
                        logger.info(f"Deleting existing image for post {post_id}")
                        self.api_client.delete_post_image(post_id)
                        logger.info(f"Existing image for post {post_id} deleted.")
                    else:
                        logger.info(
                            f"No existing image to delete for post {post_id}, but flag was set."
                        )

                QMessageBox.information(self, "Успех", "Пост успешно обновлен.")

            else:
                # --- СОЗДАНИЕ НОВОГО ПОСТА ---
                logger.info("Attempting to create new post.")

                created_post_data = self.api_client.create_post_with_image(
                    title=title,
                    text_content=text_content,
                    is_pinned=is_pinned,
                    image_path=self.new_image_path,
                )
                logger.info(f"New post created with ID: {created_post_data.get('id')}")

                QMessageBox.information(self, "Успех", "Новый пост успешно создан.")
            self.accept()

        except ApiHttpError as e:
            logger.error(
                f"API HTTP Error saving post: {e.message} (Status: {e.status_code})"
            )
            if e.status_code == 413:
                max_size_for_dialog = 5
                friendly_message = (
                    f"Ошибка загрузки изображения: Файл слишком большой.\n"
                    f"Максимально допустимый размер файла: {max_size_for_dialog} МБ.\n\n"
                    f"Пожалуйста, выберите файл меньшего размера."
                )
                QMessageBox.warning(self, "Файл слишком большой", friendly_message)
            else:
                QMessageBox.critical(
                    self,
                    f"Ошибка API ({e.status_code})",
                    f"Не удалось сохранить пост:\n{e.message}",
                )

        except ApiClientError as e:
            logger.exception(f"API Client Error saving post: {e.message}")
            QMessageBox.critical(
                self, "Ошибка API", f"Не удалось сохранить пост:\n{e.message}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error saving post: {e}")
            QMessageBox.critical(
                self, "Критическая ошибка", f"Произошла непредвиденная ошибка:\n{e}"
            )

        except ApiClientError as e:
            logger.exception(f"API Error saving post: {e.message}")
            QMessageBox.critical(
                self, "Ошибка API", f"Не удалось сохранить пост:\n{e.message}"
            )
        except Exception as e:
            logger.exception(f"Unexpected error saving post: {e}")
            QMessageBox.critical(
                self, "Критическая ошибка", f"Произошла непредвиденная ошибка:\n{e}"
            )

    def _load_post_data_to_form(self):
        if not self.post_data:
            return
        self.title_edit.setText(self.post_data.get("title", ""))
        self.text_content_edit.setPlainText(self.post_data.get("text_content", ""))
        self.pinned_checkbox.setChecked(self.post_data.get("is_pinned", False))

        self.new_image_path = None
        self.delete_current_image_flag = False
        self.image_preview_label.setText("Загрузка превью...")
        self.image_preview_label.setPixmap(QPixmap())
        self.remove_image_button.setEnabled(False)

        media_files = self.post_data.get("media_files", [])
        if media_files and isinstance(media_files, list) and len(media_files) > 0:
            first_media = media_files[0]

            thumb_filename = first_media.get("thumbnail_path")
            original_filename = first_media.get("original_filename", "файл")

            if thumb_filename:

                relative_path_for_api = f"post_media/{thumb_filename}"

                logger.debug(
                    f"PostDialog: Attempting to load thumbnail from relative path: {relative_path_for_api}"
                )
                image_bytes = self.api_client.get_image_bytes(relative_path_for_api)

                if image_bytes:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(image_bytes):

                        self.image_preview_label.setPixmap(
                            pixmap.scaled(
                                self.image_preview_label.width(),
                                self.image_preview_label.height(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                        self.remove_image_button.setEnabled(True)
                        logger.debug(
                            f"PostDialog: Thumbnail for '{original_filename}' loaded and displayed."
                        )
                    else:
                        self.image_preview_label.setText(
                            f"Ошибка\nформата\n{original_filename}"
                        )
                        logger.warning(
                            f"PostDialog: Could not load QPixmap from bytes for {original_filename}."
                        )
                        self.remove_image_button.setEnabled(True)
                else:
                    self.image_preview_label.setText(
                        f"Не удалось\nзагрузить\n{original_filename}"
                    )
                    logger.warning(
                        f"PostDialog: get_image_bytes returned None for {original_filename} (path: {relative_path_for_api})."
                    )
                    self.remove_image_button.setEnabled(True)
            else:
                self.image_preview_label.setText("Превью\nнедоступно")
                self.remove_image_button.setEnabled(False)
        else:
            self.image_preview_label.setText("Нет изображения")
            self.remove_image_button.setEnabled(False)
