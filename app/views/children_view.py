import logging
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
    QLineEdit,
    QSpacerItem,
    QSizePolicy,
    QDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon
from typing import Optional, Dict, List

from utils.api_client import ApiClient, ApiClientError, ApiHttpError


from app.dialogs.child_dialog import ChildDialog
from app.dialogs.manage_parents_dialog import ManageParentsDialog

logger = logging.getLogger("KindergartenApp")


class ChildrenView(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.children_data: List[Dict] = []  
        self.groups_data: List[Dict] = []  

        self.initUI()
        self.load_initial_data()  

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Верхняя панель: Фильтры и Кнопки ---
        top_bar_layout = QHBoxLayout()

        # Фильтр по группе
        group_filter_layout = QHBoxLayout()
        group_filter_layout.addWidget(QLabel("Группа:"))
        self.group_filter_combo = QComboBox()
        self.group_filter_combo.setMinimumWidth(150)
        self.group_filter_combo.addItem(
            "Все группы", None
        )  
        self.group_filter_combo.currentIndexChanged.connect(
            self.load_children
        )  
        group_filter_layout.addWidget(self.group_filter_combo)

        top_bar_layout.addLayout(group_filter_layout)

        top_bar_layout.addStretch()  

        # Кнопки
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.clicked.connect(self.load_children)
        self.add_button = QPushButton("Добавить")
        self.add_button.setIcon(QIcon.fromTheme("list-add"))
        self.add_button.clicked.connect(self.add_child)
        self.edit_button = QPushButton("Редактировать")
        self.edit_button.setIcon(QIcon.fromTheme("document-edit"))
        self.edit_button.clicked.connect(self.edit_child)
        self.edit_button.setEnabled(False)
        self.delete_button = QPushButton("Удалить")
        self.delete_button.setIcon(QIcon.fromTheme("list-remove"))
        self.delete_button.clicked.connect(self.delete_child)
        self.delete_button.setEnabled(False)
        self.manage_parents_button = QPushButton("Родители")
        self.manage_parents_button.setIcon(QIcon.fromTheme("system-users"))
        self.manage_parents_button.setToolTip(
            "Просмотр и управление привязанными родителями"
        )
        self.manage_parents_button.clicked.connect(self.manage_parents)
        self.manage_parents_button.setEnabled(False)

        top_bar_layout.addWidget(self.refresh_button)
        top_bar_layout.addWidget(self.add_button)
        top_bar_layout.addWidget(self.edit_button)
        top_bar_layout.addWidget(self.delete_button)
        top_bar_layout.addWidget(self.manage_parents_button)
        main_layout.addLayout(top_bar_layout)

        # --- Таблица Детей ---
        self.table_widget = QTableWidget()
        
        self.table_widget.setColumnCount(6)
        self.table_widget.setHorizontalHeaderLabels(
            ["ID", "ФИО", "Дата рождения", "Группа", "Адрес", "Мед. инфо"]
        )
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
       
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )  
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)  
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)  
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)  
        self.table_widget.setSortingEnabled(True)
        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)
        
        self.table_widget.itemDoubleClicked.connect(
            lambda item: self.edit_child() if self.edit_button.isEnabled() else None
        )

        main_layout.addWidget(self.table_widget)
        self.setLayout(main_layout)

    def load_initial_data(self):
        """Загружает группы для фильтра и затем список детей."""
        self.load_groups_for_filter()
        

    def load_groups_for_filter(self):
        """Загружает список групп для QComboBox фильтра."""
        logger.info("Loading groups for filter...")
        try:
            
            self.groups_data = self.api_client.get_groups(limit=1000)  
            
            self.group_filter_combo.clear()
            self.group_filter_combo.addItem("Все группы", None)  
            
            self.groups_data.sort(key=lambda g: g.get("name", ""))
            for group in self.groups_data:
                group_id = group.get("id")
                group_name = group.get("name", f"ID: {group_id}")
                if group_id is not None:
                    self.group_filter_combo.addItem(
                        group_name, group_id
                    )  
            logger.info(f"Loaded {len(self.groups_data)} groups for filter.")
            
            self.load_children()
        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load groups for filter.")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить список групп для фильтра:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки групп.")

    def on_search_text_changed(self, text):
        """Запускает таймер для отложенного поиска."""
        self.search_timer.start()  

    def load_children(self):
        """Загружает список детей из API с учетом фильтров и заполняет таблицу."""
        
        selected_group_id = self.group_filter_combo.currentData()

        filter_info = (
            f"Группа: {'Все' if selected_group_id is None else selected_group_id}"
        )

        self.status_changed.emit(f"Загрузка детей ({filter_info})...")
        logger.info(f"Loading children with filter: group_id={selected_group_id}")

        self.table_widget.setRowCount(0)
        self.edit_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.manage_parents_button.setEnabled(False)

        try:
            self.children_data = self.api_client.get_children(
                group_id=selected_group_id,
                limit=200,  
            )
            self.populate_table()
            self.status_changed.emit(f"Загружено {len(self.children_data)} детей.")
            logger.info(f"Successfully loaded {len(self.children_data)} children.")
        except ApiHttpError as e:
            
            if e.status_code == 403:
                logger.warning(f"Access denied loading children: {e.message}")
                self.children_data = []
                self.populate_table()
                QMessageBox.warning(
                    self,
                    "Доступ запрещен",
                    f"Не удалось загрузить список детей:\n{e.message}",
                )
                self.status_changed.emit("Доступ к списку детей запрещен.")
            else:
                logger.exception("HTTP error loading children.")
                QMessageBox.critical(
                    self, "Ошибка загрузки", f"Не удалось загрузить список детей:\n{e}"
                )
                self.status_changed.emit("Ошибка загрузки детей.")
        except (ApiClientError, Exception) as e:
            logger.exception("Failed to load children from API.")
            QMessageBox.critical(
                self, "Ошибка загрузки", f"Не удалось загрузить список детей:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки детей.")

    def populate_table(self):
        """Заполняет таблицу данными из self.children_data."""
        self.table_widget.setRowCount(len(self.children_data))
        self.table_widget.setSortingEnabled(False)

        groups_map = {
            g["id"]: g.get("name", f"ID:{g['id']}") for g in self.groups_data
        }  

        for row, child in enumerate(self.children_data):
            child_id = child.get("id")
            group_id = child.get("group_id")
            group_name = groups_map.get(group_id, "") if group_id else "Без группы"

            id_item = QTableWidgetItem(str(child_id))
            id_item.setData(Qt.ItemDataRole.UserRole, child_id)  
            fullname_item = QTableWidgetItem(child.get("full_name", ""))
            birthdate_item = QTableWidgetItem(child.get("birth_date", ""))
            group_item = QTableWidgetItem(group_name)
            address_item = QTableWidgetItem(child.get("address", ""))
            medinfo_item = QTableWidgetItem(child.get("medical_info", ""))

            self.table_widget.setItem(row, 0, id_item)
            self.table_widget.setItem(row, 1, fullname_item)
            self.table_widget.setItem(row, 2, birthdate_item)
            self.table_widget.setItem(row, 3, group_item)
            self.table_widget.setItem(row, 4, address_item)
            self.table_widget.setItem(row, 5, medinfo_item)

        self.table_widget.setSortingEnabled(True)

    def on_selection_changed(self):
        """Активирует/деактивирует кнопки при изменении выбора."""
        is_selected = bool(self.table_widget.selectionModel().selectedRows())
        self.edit_button.setEnabled(is_selected)
        self.delete_button.setEnabled(is_selected)
        self.manage_parents_button.setEnabled(is_selected)

    def get_selected_child_id(self) -> Optional[int]:
        """Возвращает ID выбранного ребенка."""
        selected_items = self.table_widget.selectedItems()
        if selected_items:
            return selected_items[0].data(Qt.ItemDataRole.UserRole)
        return None

    # --- Слоты для кнопок ---
    def add_child(self):
        """Открывает диалог добавления ребенка."""
        
        dialog = ChildDialog(
            api_client=self.api_client, groups=self.groups_data, parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info("Child added dialog accepted. Refreshing list.")
            self.load_children()  
            self.status_changed.emit("Ребенок успешно добавлен.")
        else:
            logger.debug("Child add dialog cancelled.")

    def edit_child(self):
        """Открывает диалог редактирования ребенка."""
        selected_id = self.get_selected_child_id()
        if selected_id is None:
            return

        self.status_changed.emit(f"Загрузка данных ребенка ID {selected_id}...")
        try:
            
            child_data = self.api_client.get_child(selected_id)
            self.status_changed.emit(f"Данные ребенка ID {selected_id} загружены.")
        except (ApiClientError, Exception) as e:
            logger.exception(f"Failed to load child data for editing id={selected_id}")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось загрузить данные ребенка:\n{e}"
            )
            self.status_changed.emit("Ошибка загрузки данных ребенка.")
            return

        if not child_data:
            logger.error(
                f"Could not find child data for selected id {selected_id} after API call"
            )
            QMessageBox.warning(
                self, "Ошибка", "Не найдены данные для выбранного ребенка."
            )
            return

        
        dialog = ChildDialog(
            api_client=self.api_client,
            child_data=child_data,
            groups=self.groups_data,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            logger.info(f"Child {selected_id} edit dialog accepted. Refreshing list.")
            self.load_children()  
            self.status_changed.emit(f"Ребенок ID {selected_id} успешно обновлен.")
        else:
            logger.debug(f"Child {selected_id} edit dialog cancelled.")

    def delete_child(self):
        """Удаляет выбранного ребенка после подтверждения."""
        selected_id = self.get_selected_child_id()
        if selected_id is None:
            return

        
        selected_row = self.table_widget.currentRow()
        child_name_item = self.table_widget.item(selected_row, 1)  
        child_display = (
            child_name_item.text() if child_name_item else f"ID {selected_id}"
        )

        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить запись о ребенке\n'{child_display}'?\nЭто действие необратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.status_changed.emit(f"Удаление ребенка '{child_display}'...")
            try:
                success = self.api_client.delete_child(selected_id)
                if success:
                    logger.info(
                        f"Child {selected_id} ('{child_display}') deleted successfully."
                    )
                    QMessageBox.information(
                        self,
                        "Удалено",
                        f"Запись о ребенке '{child_display}' успешно удалена.",
                    )
                    self.load_children()  
                    self.status_changed.emit(f"Ребенок '{child_display}' удален.")
                else:
                    
                    QMessageBox.warning(
                        self,
                        "Ошибка удаления",
                        f"Не удалось удалить запись о ребенке '{child_display}'.\n(Возможно, нет прав или запись уже удалена).",
                    )
                    self.status_changed.emit(
                        f"Ошибка удаления ребенка '{child_display}'."
                    )
            except (ApiClientError, Exception) as e:
                logger.exception(
                    f"Failed to delete child {selected_id} ('{child_display}')."
                )
                QMessageBox.critical(
                    self,
                    "Ошибка удаления",
                    f"Не удалось удалить '{child_display}':\n{e}",
                )
                self.status_changed.emit(f"Ошибка удаления ребенка '{child_display}'.")

    def manage_parents(self):
        """Открывает диалог управления родителями для выбранного ребенка."""
        selected_child_id = self.get_selected_child_id()
        if selected_child_id is None:
            
            logger.warning("Manage parents button clicked, but no child selected.")
            return

        
        selected_row = self.table_widget.currentRow()
        child_name_item = self.table_widget.item(
            selected_row, 1
        )  
        child_name = (
            child_name_item.text()
            if child_name_item
            else f"Ребенок ID {selected_child_id}"
        )

        logger.info(
            f"Opening manage parents dialog for child_id={selected_child_id} ('{child_name}')"
        )
        self.status_changed.emit(f"Управление родителями для '{child_name}'...")

        
        try:
            dialog = ManageParentsDialog(
                api_client=self.api_client,
                child_id=selected_child_id,
                child_name=child_name,
                parent=self,  
            )
            dialog.exec()  
            self.status_changed.emit("Готово.")
            logger.debug("Manage parents dialog closed.")
        except Exception as e:
            
            logger.exception("Failed to create or execute ManageParentsDialog")
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось открыть диалог управления родителями:\n{e}"
            )
            self.status_changed.emit("Ошибка открытия диалога.")
