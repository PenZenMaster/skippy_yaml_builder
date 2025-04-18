"""
Module/Script Name: main.py

Description:
Skippy Cloud Stack YAML Builder – GUI tool for creating structured YAML profiles
for city-specific cloud pages. Includes two-column layout, validation, dark mode,
and file management.

Author(s):
Skippy the Magnificent with an eensy weensy bit of help from that filthy monkey, Big G

Created Date:
2025-04-17

Last Modified Date:
2025-04-17

Comments:
- Version 4.2: Grid layout, nested YAML loading, dark mode, and font control.
"""

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QMenuBar, QMainWindow, QMenu, QDialog, QDialogButtonBox, QGridLayout
)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt
import sys
import yaml
import os
import re

class YAMLForm(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skippy Cloud Stack – YAML Builder v4")
        self.setGeometry(200, 200, 1100, 800)
        self.font_size = 10
        self.dark_mode = False
        self.labels = {}  # Store labels for font update

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout()

        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)
        help_menu = QMenu("Help", self)
        help_menu.addAction("About", self.show_about)
        help_menu.addAction("How to Use", self.show_usage)
        view_menu = QMenu("View", self)
        view_menu.addAction("Increase Font Size", self.increase_font)
        view_menu.addAction("Decrease Font Size", self.decrease_font)
        view_menu.addAction("Toggle Dark Mode", self.toggle_dark_mode)
        file_menu = QMenu("File", self)
        file_menu.addAction("Open YAML", self.load_yaml)
        file_menu.addAction("Save YAML", self.save_yaml)
        file_menu.addAction("Close", self.close)
        self.menu_bar.addMenu(file_menu)
        self.menu_bar.addMenu(view_menu)
        self.menu_bar.addMenu(help_menu)

        self.inputs = {
            "* Client Name": QLineEdit(),
            "* Business Category": QLineEdit(),
            "* Phone": QLineEdit(),
            "Email": QLineEdit(),
            "* Website": QLineEdit(),
            "Street Address": QLineEdit(),
            "City": QLineEdit(),
            "State": QLineEdit(),
            "ZIP": QLineEdit(),
            "Country": QLineEdit(),
            "Broker Name": QLineEdit(),
            "Broker Website": QLineEdit(),
            "Broker Phone": QLineEdit(),
            "Google Maps Embed Code": QTextEdit(),
            "* Target Cities (one per line)": QTextEdit(),
            "* Services (one per line)": QTextEdit(),
            "Social/Citation URLs (one per line)": QTextEdit()
        }

        grid_layout = QGridLayout()
        grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        left_fields = [
            "* Client Name", "* Business Category", "* Phone", "Email",
            "* Website", "Street Address", "City", "State", "ZIP", "Country"
        ]
        right_fields = [
            "Broker Name", "Broker Website", "Broker Phone",
            "Google Maps Embed Code", "* Target Cities (one per line)",
            "* Services (one per line)", "Social/Citation URLs (one per line)"
        ]

        for i, key in enumerate(left_fields):
            lbl = QLabel(key)
            lbl.setFont(QFont("Arial", self.font_size))
            widget = self.inputs[key]
            widget.setFont(QFont("Arial", self.font_size))
            self.labels[key] = lbl
            if "Phone" in key:
                widget.setInputMask("(000) 000-0000;_")
            grid_layout.addWidget(lbl, i, 0)
            grid_layout.addWidget(widget, i, 1)

        for i, key in enumerate(right_fields):
            lbl = QLabel(key)
            lbl.setFont(QFont("Arial", self.font_size))
            widget = self.inputs[key]
            widget.setFont(QFont("Arial", self.font_size))
            self.labels[key] = lbl
            grid_layout.addWidget(lbl, i, 2)
            grid_layout.addWidget(widget, i, 3)

        self.layout.addLayout(grid_layout)

        self.save_button = QPushButton("Save YAML")
        self.save_button.setFixedWidth(int(self.width() * 0.25))
        self.save_button.clicked.connect(self.save_yaml)
        self.save_button.setFont(QFont("Arial", self.font_size))
        self.save_button.setStyleSheet(""
            QPushButton {
                background-color: lightgreen;
                border: 1px solid #999;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: lightblue;
            }
            QPushButton:pressed {
                background-color: yellow;
            }
        "")
        self.layout.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        central_widget.setLayout(self.layout)

    def increase_font(self):
        self.font_size += 1
        self.refresh_fonts()

    def decrease_font(self):
        if self.font_size > 6:
            self.font_size -= 1
            self.refresh_fonts()

    def refresh_fonts(self):
        for label, widget in self.inputs.items():
            font = QFont("Arial", self.font_size)
            widget.setFont(font)
            if label in self.labels:
                self.labels[label].setFont(font)
        self.save_button.setFont(QFont("Arial", self.font_size))

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.setStyleSheet("background-color: #2b2b2b; color: white;" if self.dark_mode else "")

    def show_about(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About Skippy")
        layout = QVBoxLayout()
        image_path = os.path.join("images", "skippy_the_magnificient.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path).scaled(250, 250)
            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(image_label)
        text_label = QLabel("Skippy Cloud Stack YAML Builder v4\nCreated by Skippy the Magnificent & Big G")
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(about_dialog.accept)
        layout.addWidget(buttons)
        about_dialog.setLayout(layout)
        about_dialog.exec()

    def show_usage(self):
        QMessageBox.information(self, "How to Use", "Fill in the form and save a .yaml file.\nRequired fields are marked with '*'.\nPhone must match the (XXX) XXX-XXXX format.")

    def load_yaml(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open YAML File", "client_yaml", "YAML Files (*.yaml *.yml)")
        if not filename:
            return
        with open(filename, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        broker = data.get("broker", {})
        address = data.get("address", {})
        for key in self.inputs:
            flat_key = key.lower().replace('* ', '').replace(' ', '_')
            if key.startswith("Broker"):
                source_key = flat_key.replace('broker_', '')
                value = broker.get(source_key, "")
            elif key in ["Street Address", "City", "State", "ZIP", "Country"]:
                source_key = flat_key
                value = address.get(source_key, "")
            else:
                value = data.get(flat_key, "")

            if isinstance(self.inputs[key], QLineEdit):
                self.inputs[key].setText(value)
            elif isinstance(self.inputs[key], QTextEdit):
                values = value
                self.inputs[key].setPlainText("\n".join(values) if isinstance(values, list) else values)

    def save_yaml(self):
        # NOTE: Location Page Builder may need to be updated to support nested 'address' and 'broker' blocks
        required = [
            "* Client Name", "* Business Category", "* Phone",
            "* Website", "* Target Cities (one per line)", "* Services (one per line)"
        ]
        for field in required:
            widget = self.inputs[field]
            value = widget.toPlainText().strip() if isinstance(widget, QTextEdit) else widget.text().strip()
            if not value:
                QMessageBox.warning(self, "Missing Info", f"The field '{field}' is required.")
                return

        client_name = self.inputs["* Client Name"].text().strip()
        folder_name = re.sub(r'[^a-z0-9_]+', '_', client_name.lower()).strip('_')
        save_root = os.path.join(os.getcwd(), "client_yaml")
        os.makedirs(save_root, exist_ok=True)
        save_dir = os.path.join(save_root, folder_name)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "client_profile.yaml")

        if os.path.exists(save_path):
            reply = QMessageBox.question(self, "Overwrite?", f"The file already exists in {folder_name}. Overwrite?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        data = {
            "client_name": client_name,
            "category": self.inputs["* Business Category"].text(),
            "phone": self.inputs["* Phone"].text(),
            "email": self.inputs["Email"].text(),
            "website": self.inputs["* Website"].text(),
            "broker": {
                "name": self.inputs["Broker Name"].text(),
                "website": self.inputs["Broker Website"].text(),
                "phone": self.inputs["Broker Phone"].text(),
            },
            "address": {
                "street": self.inputs["Street Address"].text(),
                "city": self.inputs["City"].text(),
                "state": self.inputs["State"].text(),
                "zip": self.inputs["ZIP"].text(),
                "country": self.inputs["Country"].text(),
            },
            "map_embed": self.inputs["Google Maps Embed Code"].toPlainText(),
            "cities": [c.strip() for c in self.inputs["* Target Cities (one per line)"].toPlainText().splitlines() if c.strip()],
            "services": [s.strip() for s in self.inputs["* Services (one per line)"].toPlainText().splitlines() if s.strip()],
            "sameAs": [u.strip() for u in self.inputs["Social/Citation URLs (one per line)"].toPlainText().splitlines() if u.strip()],
        }
        for key, widget in self.inputs.items():
            field_key = key.lower().replace('* ', '').replace(' ', '_')
            if isinstance(widget, QLineEdit):
                data[field_key] = widget.text()
            elif isinstance(widget, QTextEdit):
                lines = widget.toPlainText().splitlines()
                data[field_key] = [line.strip() for line in lines if line.strip()]

        with open(save_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)

        QMessageBox.information(self, "Success", f"YAML file saved to:\n{save_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YAMLForm()
    window.show()
    sys.exit(app.exec())
