from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
    QTextEdit, QPushButton, QFileDialog, QMessageBox
)
import sys
import yaml
import os

class YAMLForm(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skippy Cloud Stack – YAML Builder")
        self.setGeometry(200, 200, 500, 600)

        layout = QVBoxLayout()

        self.inputs = {
            "Client Name": QLineEdit(),
            "Business Category": QLineEdit(),
            "Phone": QLineEdit(),
            "Email": QLineEdit(),
            "Website": QLineEdit(),
            "Broker Name": QLineEdit(),
            "Broker Website": QLineEdit(),
            "Broker Phone": QLineEdit(),
            "Street Address": QLineEdit(),
            "City": QLineEdit(),
            "State": QLineEdit(),
            "ZIP": QLineEdit(),
            "Country": QLineEdit(),
            "Google Maps Embed Code": QTextEdit(),
            "Target Cities (comma-separated)": QLineEdit(),
            "Services (comma-separated)": QLineEdit(),
            "Social/Citation URLs (one per line)": QTextEdit()
        }

        for label, widget in self.inputs.items():
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    def save_yaml(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save YAML File", "client_profile.yaml", "YAML Files (*.yaml *.yml)")
        if not filename:
            return

        data = {
            "client_name": self.inputs["Client Name"].text(),
            "category": self.inputs["Business Category"].text(),
            "phone": self.inputs["Phone"].text(),
            "email": self.inputs["Email"].text(),
            "website": self.inputs["Website"].text(),
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
            "cities": [c.strip() for c in self.inputs["Target Cities (comma-separated)"].text().split(",")],
            "services": [s.strip() for s in self.inputs["Services (comma-separated)"].text().split(",")],
            "sameAs": [u.strip() for u in self.inputs["Social/Citation URLs (one per line)"].toPlainText().splitlines() if u.strip()]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, sort_keys=False)

        QMessageBox.information(self, "Success", f"YAML file saved to:\n{filename}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = YAMLForm()
    form.show()
    sys.exit(app.exec())
