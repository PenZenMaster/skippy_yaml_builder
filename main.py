from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
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
        self.setGeometry(200, 200, 650, 750)
        self.font_size = 10
        self.dark_mode = False

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
            "Broker Name": QLineEdit(),
            "Broker Website": QLineEdit(),
            "Broker Phone": QLineEdit(),
            "Street Address": QLineEdit(),
            "City": QLineEdit(),
            "State": QLineEdit(),
            "ZIP": QLineEdit(),
            "Country": QLineEdit(),
            "Google Maps Embed Code": QTextEdit(),
            "* Target Cities (one per line)": QTextEdit(),
            "* Services (one per line)": QTextEdit(),
            "Social/Citation URLs (one per line)": QTextEdit(),
        }

        for label, widget in self.inputs.items():
            lbl = QLabel(label)
            lbl.setFont(QFont("Arial", self.font_size))
            widget.setFont(QFont("Arial", self.font_size))
            self.layout.addWidget(lbl)
            self.layout.addWidget(widget)
            if "Phone" in label:
                widget.setInputMask("(000) 000-0000;_")

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        self.save_button.setFont(QFont("Arial", self.font_size))
        self.layout.addWidget(self.save_button)

        central_widget.setLayout(self.layout)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        if self.dark_mode:
            self.setStyleSheet("background-color: #2b2b2b; color: white;")
        else:
            self.setStyleSheet("")

    def increase_font(self):
        self.font_size += 1
        self.refresh_fonts()

    def decrease_font(self):
        if self.font_size > 6:
            self.font_size -= 1
            self.refresh_fonts()

    def refresh_fonts(self):
        for label, widget in self.inputs.items():
            widget.setFont(QFont("Arial", self.font_size))
        self.save_button.setFont(QFont("Arial", self.font_size))

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
        text_label = QLabel(
            "Skippy Cloud Stack YAML Builder v4\nCreated by Skippy the Magnificent & Big G"
        )
        text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_label)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(about_dialog.accept)
        layout.addWidget(buttons)
        about_dialog.setLayout(layout)
        about_dialog.exec()

    def show_usage(self):
        QMessageBox.information(
            self,
            "How to Use",
            "Fill in the form and save a .yaml file.\nRequired fields are marked with '*'.\nPhone must match the (XXX) XXX-XXXX format.",
        )

    def sanitize_filename(self, name):
        name = name.lower()
        name = re.sub(r"[^a-z0-9_]+", "_", name.strip())
        return name.strip("_")

    def save_yaml(self):
        required = [
            "* Client Name",
            "* Business Category",
            "* Phone",
            "* Website",
            "* Target Cities (one per line)",
            "* Services (one per line)",
        ]
        for field in required:
            if (
                not self.inputs[field].toPlainText().strip()
                if isinstance(self.inputs[field], QTextEdit)
                else self.inputs[field].text().strip()
            ):
                QMessageBox.warning(
                    self, "Missing Info", f"The field '{field}' is required."
                )
                return

        client_name = self.inputs["* Client Name"].text().strip()
        folder_name = self.sanitize_filename(client_name)
        save_dir = os.path.join(os.getcwd(), folder_name)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "client_profile.yaml")

        if os.path.exists(save_path):
            reply = QMessageBox.question(
                self,
                "Overwrite?",
                f"The file already exists in {folder_name}. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
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
            "cities": [
                c.strip()
                for c in self.inputs["* Target Cities (one per line)"]
                .toPlainText()
                .splitlines()
                if c.strip()
            ],
            "services": [
                s.strip()
                for s in self.inputs["* Services (one per line)"]
                .toPlainText()
                .splitlines()
                if s.strip()
            ],
            "sameAs": [
                u.strip()
                for u in self.inputs["Social/Citation URLs (one per line)"]
                .toPlainText()
                .splitlines()
                if u.strip()
            ],
        }

        with open(save_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, sort_keys=False)

        QMessageBox.information(self, "Success", f"YAML file saved to:\n{save_path}")

    def load_yaml(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open YAML File", "", "YAML Files (*.yaml *.yml)"
        )
        if not filename:
            return
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        # Set field values
        self.inputs["* Client Name"].setText(data.get("client_name", ""))
        self.inputs["* Business Category"].setText(data.get("category", ""))
        self.inputs["* Phone"].setText(data.get("phone", ""))
        self.inputs["Email"].setText(data.get("email", ""))
        self.inputs["* Website"].setText(data.get("website", ""))

        broker = data.get("broker", {})
        self.inputs["Broker Name"].setText(broker.get("name", ""))
        self.inputs["Broker Website"].setText(broker.get("website", ""))
        self.inputs["Broker Phone"].setText(broker.get("phone", ""))

        address = data.get("address", {})
        self.inputs["Street Address"].setText(address.get("street", ""))
        self.inputs["City"].setText(address.get("city", ""))
        self.inputs["State"].setText(address.get("state", ""))
        self.inputs["ZIP"].setText(address.get("zip", ""))
        self.inputs["Country"].setText(address.get("country", ""))

        self.inputs["Google Maps Embed Code"].setPlainText(data.get("map_embed", ""))
        self.inputs["* Target Cities (one per line)"].setPlainText(
            "\n".join(data.get("cities", []))
        )
        self.inputs["* Services (one per line)"].setPlainText(
            "\n".join(data.get("services", []))
        )
        self.inputs["Social/Citation URLs (one per line)"].setPlainText(
            "\n".join(data.get("sameAs", []))
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YAMLForm()
    window.show()
    sys.exit(app.exec())
