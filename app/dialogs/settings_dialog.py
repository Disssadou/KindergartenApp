import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QDialogButtonBox,
    QPushButton,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
)
from PyQt6.QtCore import QSettings, QStandardPaths, Qt

logger = logging.getLogger("KindergartenApp")


DEFAULT_REPORTS_PATH_KEY = "paths/default_reports_path"
DEFAULT_BACKUPS_PATH_KEY = "paths/default_backups_path"


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки приложения")
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.settings = QSettings()
        self.initUI()
        self.load_settings()

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # --- Секция "Пути сохранения" ---
        paths_group = QGroupBox("Пути сохранения по умолчанию")
        paths_layout = QFormLayout(paths_group)

        self.reports_path_edit = QLineEdit()
        self.reports_path_edit.setReadOnly(True)
        reports_path_button = QPushButton("Выбрать...")
        reports_path_button.clicked.connect(self.select_reports_path)
        reports_path_layout = QHBoxLayout()
        reports_path_layout.addWidget(self.reports_path_edit)
        reports_path_layout.addWidget(reports_path_button)
        paths_layout.addRow("Папка для отчетов:", reports_path_layout)

        self.backups_path_edit = QLineEdit()
        self.backups_path_edit.setReadOnly(True)
        backups_path_button = QPushButton("Выбрать...")
        backups_path_button.clicked.connect(self.select_backups_path)
        backups_path_layout = QHBoxLayout()
        backups_path_layout.addWidget(self.backups_path_edit)
        backups_path_layout.addWidget(backups_path_button)
        paths_layout.addRow("Папка для резервных копий:", backups_path_layout)

        main_layout.addWidget(paths_group)

        # --- Кнопки OK и Cancel ---
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def select_reports_path(self):
        current_path = self.reports_path_edit.text()
        if not current_path or not self.settings.value(DEFAULT_REPORTS_PATH_KEY):
            current_path = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            )

        directory = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения отчетов", current_path
        )
        if directory:
            self.reports_path_edit.setText(directory)

    def select_backups_path(self):
        current_path = self.backups_path_edit.text()
        if not current_path or not self.settings.value(DEFAULT_BACKUPS_PATH_KEY):
            current_path = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DocumentsLocation
            )

        directory = QFileDialog.getExistingDirectory(
            self, "Выберите папку для сохранения резервных копий", current_path
        )
        if directory:
            self.backups_path_edit.setText(directory)

    def load_settings(self):
        logger.info("Loading application settings...")
        default_docs_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )

        reports_path = self.settings.value(DEFAULT_REPORTS_PATH_KEY, default_docs_path)
        self.reports_path_edit.setText(str(reports_path))

        backups_path = self.settings.value(DEFAULT_BACKUPS_PATH_KEY, default_docs_path)
        self.backups_path_edit.setText(str(backups_path))

        logger.info("Settings loaded (default day rate section removed).")

    def save_settings(self):
        logger.info("Saving application settings...")
        self.settings.setValue(DEFAULT_REPORTS_PATH_KEY, self.reports_path_edit.text())
        self.settings.setValue(DEFAULT_BACKUPS_PATH_KEY, self.backups_path_edit.text())

        logger.info("Settings saved (default day rate section removed).")
        self.accept()


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    QApplication.setOrganizationName("MyTestCompanyForSettings")
    QApplication.setApplicationName("MyTestAppSettingsDialog")

    app = QApplication(sys.argv)
    dialog = SettingsDialog()
    if dialog.exec() == QDialog.DialogCode.Accepted:
        print("Настройки сохранены (без ставки дня)")
        settings = QSettings()
        print(f"Путь отчетов: {settings.value(DEFAULT_REPORTS_PATH_KEY)}")
        print(f"Путь бэкапов: {settings.value(DEFAULT_BACKUPS_PATH_KEY)}")

    else:
        print("Сохранение настроек отменено")
    sys.exit()
