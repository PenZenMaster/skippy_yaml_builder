from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QMessageBox, QMenuBar, QMainWindow, QMenu
)
import sys
import yaml
import os

class YAMLForm(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skippy Cloud Stack – YAML Builder")
        self.setGeometry(200, 200, 600, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)
        help_menu = QMenu("Help", self)
        help_menu.addAction("About", self.show_about)
        help_menu.addAction("How to Use", self.show_usage)
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
            "* Target Cities (comma-separated)": QLineEdit(),
            "* Services (comma-separated)": QLineEdit(),
            "Social/Citation URLs (one per line)": QTextEdit()
        }

        tooltips = {
            "* Client Name": "Required. Use the exact business or agent name as it appears on official records.",
            "* Business Category": "Required. E.g., Mortgage Lender, Painting Contractor, HVAC Company.",
            "* Phone": "Required. Format: (123) 456-7890. Will be used in schema and contact block.",
            "Email": "Optional. Will appear in the CTA if provided.",
            "* Website": "Required. Will be used in schema and canonical link.",
            "Broker Name": "Optional. Parent company or brand, if applicable.",
            "Google Maps Embed Code": "Optional. The full iframe embed code from the GBP.",
            "* Target Cities (comma-separated)": "Required. These are the geo targets used for generating cloud pages.",
            "* Services (comma-separated)": "Required. E.g., FHA Loans, VA Loans, Refinance.",
            "Social/Citation URLs (one per line)": "Optional. Used in JSON-LD sameAs array."
        }

        for label, widget in self.inputs.items():
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)
            if label in tooltips:
                widget.setToolTip(tooltips[label])
            if "Phone" in label:
                widget.setInputMask("(000) 000-0000;_")

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        layout.addWidget(self.save_button)

        central_widget.setLayout(layout)

    def show_about(self):
        QMessageBox.information(self, "About", "Skippy Cloud Stack YAML Builder v2\nCreated by Skippy the Magnificent & Big G")

    def show_usage(self):
        QMessageBox.information(self, "How to Use", "Fill in the form and save a .yaml file.\nRequired fields are marked with '*'.\nPhone must match the (XXX) XXX-XXXX format.")

    def save_yaml(self):
        required = ["* Client Name", "* Business Category", "* Phone", "* Website", "* Target Cities (comma-separated)", "* Services (comma-separated)"]
        for field in required:
            if not self.inputs[field].text().strip():
                QMessageBox.warning(self, "Missing Info", f"The field '{field}' is required.")
                return

        filename, _ = QFileDialog.getSaveFileName(self, "Save YAML File", "client_profile.yaml", "YAML Files (*.yaml *.yml)")
        if not filename:
            return

        data = {
            "client_name": self.inputs["* Client Name"].text(),
            "category": self.inputs["* Business Category"].text(),
            "phone": self.inputs["* Phone"].text(),
            "email": self.inputs["Email"].text(),
            "website": self.inputs["* Website"].text(),
            "broker": {
                "name": self.inputs["Broker Name"].text(),
                "website": self.inputs["Broker Website"].text(),
                "phone": self.inputs["Broker Phone"].text()
            },
            "address": {
                "street": self.inputs["Street Address"].text(),
                "city": self.inputs["City"].text(),
                "state": self.inputs["State"].text(),
                "zip": self.inputs["ZIP"].text(),
                "country": self.inputs["Country"].text()
            },
            "map_embed": self.inputs["Google Maps Embed Code"].toPlainText(),
            "cities": [c.strip() for c in self.inputs["* Target Cities (comma-separated)"].text().split(",")],
            "services": [s.strip() for s in self.inputs["* Services (comma-separated)"].text().split(",")],
            "sameAs": [u.strip() for u in self.inputs["Social/Citation URLs (one per line)"].toPlainText().splitlines() if u.strip()]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)

        QMessageBox.information(self, "Success", f"YAML file saved to:\n{filename}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YAMLForm()
    window.show()
    sys.exit(app.exec())
