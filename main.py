from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QMenuBar,
    QMainWindow,
    QMenu,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
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

    def increase_font(self):
        self.font_size += 1
        self.update_fonts()

    def decrease_font(self):
        if self.font_size > 1:
            self.font_size -= 1
            self.update_fonts()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.setStyleSheet("QWidget { background-color: #2e2e2e; color: #f0f0f0; }")
        else:
            self.setStyleSheet("")

    def update_fonts(self):
        for key, label in self.labels.items():
            label.setFont(QFont("Arial", self.font_size))
        for key, widget in self.inputs.items():
            widget.setFont(QFont("Arial", self.font_size))
        self.save_button.setFont(QFont("Arial", self.font_size))

    def show_about(self):
        QMessageBox.information(
            self, "About", "Skippy Cloud Stack – YAML Builder v4\nCreated by Your Name"
        )

    def show_usage(self):
        QMessageBox.information(
            self,
            "How to Use",
            "Fill in the required fields and click 'Save YAML' to export your configuration.\n"
            "Fields marked with * are required. Use the menu to open existing YAML files or adjust the view.",
        )

        self.setGeometry(200, 200, 1100, 800)
        self.font_size = 10
        self.dark_mode = False
        self.labels = {}  # Store labels for font update

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QVBoxLayout()

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
        self.menu_bar.addMenu(file_menu)
        self.menu_bar.addMenu(view_menu)
        self.menu_bar.addMenu(help_menu)

        def load_yaml(self):
            file_name, _ = QFileDialog.getOpenFileName(
                self, "Open YAML File", "", "YAML Files (*.yaml *.yml)"
            )
            if file_name:
                try:
                    with open(file_name, "r") as file:
                        data = yaml.safe_load(file)
                    # Populate fields if keys match input names
                    for key in self.inputs:
                        if key in data:
                            if isinstance(self.inputs[key], QTextEdit):
                                self.inputs[key].setPlainText(str(data[key]))
                            else:
                                self.inputs[key].setText(str(data[key]))
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"Failed to load YAML file:\n{e}"
                    )

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
            "Social/Citation URLs (one per line)": QTextEdit(),
        }

        # New Fields (Extended Data)
        self.inputs["Hero Image URL"] = QLineEdit()
        self.inputs["City Page Hero Image Base URL"] = QLineEdit()
        self.inputs["Logo URL"] = QLineEdit()
        self.inputs["Contact Email Address"] = QLineEdit()
        self.inputs["Primary Business Category"] = (
            QLineEdit()
        )  # Will be upgraded to validated dropdown
        self.inputs["FAQ Questions (one per line)"] = QTextEdit()
        self.city_data = {}  # Stores cities and their embed codes

        grid_layout = QGridLayout()
        left_fields = [
            "* Client Name",
            "* Business Category",
            "* Phone",
            "Email",
            "* Website",
            "Street Address",
            "City",
            "State",
            "ZIP",
            "Country",
        ]
        right_fields = [
            "Broker Name",
            "Broker Website",
            "Broker Phone",
            "Google Maps Embed Code",
            "* Target Cities (one per line)",
            "* Services (one per line)",
            "Social/Citation URLs (one per line)",
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

        self.main_layout.addLayout(grid_layout)

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        self.save_button.setFont(QFont("Arial", self.font_size))
        self.main_layout.addWidget(self.save_button)

        central_widget.setLayout(self.main_layout)

        def save_yaml(self):
            # Collect data from inputs
            data = {}
            for key, widget in self.inputs.items():
                if isinstance(widget, QTextEdit):
                    data[key] = widget.toPlainText()
                else:
                    data[key] = widget.text()
            # Ask user for file location
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save YAML File", "", "YAML Files (*.yaml *.yml)"
            )
            if file_name:
                try:
                    with open(file_name, "w") as file:
                        yaml.dump(data, file, allow_unicode=True, sort_keys=False)
                    QMessageBox.information(
                        self, "Success", "YAML file saved successfully!"
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self, "Error", f"Failed to save YAML file:\n{e}"
                    )
