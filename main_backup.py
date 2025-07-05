
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
        self.save_button.clicked.connect(self.save_yaml)
        self.save_button.setFont(QFont("Arial", self.font_size))
        self.layout.addWidget(self.save_button)

        central_widget.setLayout(self.layout)
