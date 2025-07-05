from PyQt6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QTextEdit, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox
)
from PyQt6.QtGui import QFont


class CityEmbedDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add City with Embed Code")
        self.setMinimumWidth(500)

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City Name")
        self.state_input = QLineEdit()
        self.state_input.setPlaceholderText("State Abbreviation (e.g. MI)")
        self.embed_input = QTextEdit()
        self.embed_input.setPlaceholderText("Paste Google Maps Embed Code Here")
        self.embed_input.setFixedHeight(100)

        self.city_input.setFont(QFont("Arial", 10))
        self.state_input.setFont(QFont("Arial", 10))
        self.embed_input.setFont(QFont("Arial", 10))

        self.ok_button = QPushButton("Add City")
        self.cancel_button = QPushButton("Cancel")

        self.ok_button.clicked.connect(self.validate_and_accept)
        self.cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("City:"))
        layout.addWidget(self.city_input)
        layout.addWidget(QLabel("State:"))
        layout.addWidget(self.state_input)
        layout.addWidget(QLabel("Google Maps Embed Code:"))
        layout.addWidget(self.embed_input)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def validate_and_accept(self):
        if not self.city_input.text().strip() or not self.state_input.text().strip():
            QMessageBox.warning(self, "Missing Info", "City and State are required.")
            return
        self.accept()

    def get_data(self):
        return {
            "city": self.city_input.text().strip(),
            "state": self.state_input.text().strip(),
            "embed_code": self.embed_input.toPlainText().strip()
        }
