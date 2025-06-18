import logging
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialogButtonBox,
    QAbstractItemView,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Optional

logger = logging.getLogger("KindergartenApp.dialogs.RatesDialog")


class RatesDialog(QDialog):
    def __init__(
        self,
        children_list: List[
            Dict
        ],  # Ожидаем список словарей: [{'id': int, 'full_name': str}, ...]
        default_rate: float,
        existing_rates: Optional[Dict[int, float]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.children_list = children_list
        self.default_rate = default_rate
        self.existing_rates = existing_rates if existing_rates is not None else {}
        self.edited_rates: Dict[int, float] = (
            {}
        )  # Здесь будем хранить ставки, которые отличаются от default_rate

        self.setWindowTitle("Редактирование индивидуальных ставок")
        self.setMinimumSize(500, 400)
        self.setModal(True)

        self.initUI()
        self.populate_table()
        logger.debug(
            f"RatesDialog initialized. Children: {len(children_list)}, "
            f"Default Rate: {default_rate}, Existing Rates: {self.existing_rates}"
        )

    def initUI(self):
        main_layout = QVBoxLayout(self)

        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(3)
        self.table_widget.setHorizontalHeaderLabels(
            [
                "ID",
                "ФИО Ребенка",
                f"Ставка (по умолч.: {self.default_rate:.2f} руб.)",
            ]
        )
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_widget.horizontalHeader().setSectionHidden(0, True)
        self.table_widget.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table_widget.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Interactive,
        )
        self.table_widget.setColumnWidth(2, 150)
        main_layout.addWidget(self.table_widget)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def populate_table(self):
        self.table_widget.setRowCount(len(self.children_list))
        for row, child_data in enumerate(self.children_list):
            child_id = child_data.get("id")

            full_name = child_data.get("full_name", f"ID: {child_id}")

            if child_id is None:
                logger.warning(f"Child data at row {row} is missing 'id'. Skipping.")

                continue

            id_item = QTableWidgetItem(str(child_id))
            id_item.setData(Qt.ItemDataRole.UserRole, child_id)
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            name_item = QTableWidgetItem(full_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            rate_spinbox = QDoubleSpinBox(self)
            rate_spinbox.setDecimals(2)
            rate_spinbox.setRange(0.00, 9999.99)
            rate_spinbox.setSuffix(" руб.")
            rate_spinbox.setSingleStep(10.0)

            if child_id in self.existing_rates:
                rate_spinbox.setValue(float(self.existing_rates[child_id]))
            else:
                rate_spinbox.setValue(float(self.default_rate))

            self.table_widget.setItem(row, 0, id_item)
            self.table_widget.setItem(row, 1, name_item)
            self.table_widget.setCellWidget(row, 2, rate_spinbox)

    def accept_data(self):
        self.edited_rates.clear()
        for row in range(self.table_widget.rowCount()):
            child_id_item = self.table_widget.item(row, 0)

            rate_spinbox_widget = self.table_widget.cellWidget(row, 2)

            if child_id_item and isinstance(rate_spinbox_widget, QDoubleSpinBox):
                child_id = child_id_item.data(Qt.ItemDataRole.UserRole)
                entered_rate = rate_spinbox_widget.value()

                # Сохраняем ставку в edited_rates, только если она ОТЛИЧАЕТСЯ от default_rate.

                if abs(entered_rate - self.default_rate) > 0.001:
                    self.edited_rates[child_id] = round(entered_rate, 2)

            else:
                logger.warning(
                    f"Could not process row {row}: missing child_id_item or rate_spinbox_widget not a QDoubleSpinBox."
                )

        logger.info(
            f"RatesDialog accepted. Individual rates to apply: {self.edited_rates}"
        )
        self.accept()

    def get_individual_rates(
        self,
    ) -> Dict[int, float]:
        """Возвращает словарь индивидуальных ставок {child_id: rate},
        которые отличаются от ставки по умолчанию."""
        return self.edited_rates
