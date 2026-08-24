
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QMenuBar, QMainWindow, QMenu, QListWidget, QListWidgetItem, QGridLayout,
    QScrollArea, QComboBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import sys
import yaml
from city_embed_dialog import CityEmbedDialog


class YAMLForm(QMainWindow):
    # Fields whose QTextEdit holds one entry per line; saved as a real YAML
    # list rather than the raw multi-line string. Loading still accepts the
    # older flat-string format for backward compatibility with existing files.
    LIST_FIELDS = {
        "* Target Cities (one per line)",
        "* Services (one per line)",
        "Social/Citation URLs (one per line)",
        "FAQ Questions (one per line)",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skippy Cloud Stack – YAML Builder v4")
        self.setGeometry(200, 200, 1100, 800)
        self.font_size = 10
        self.dark_mode = False
        self.labels = {}
        self.city_data = {}

        central_widget = QWidget()
        # Explicit colors on every input widget: without this, QTextEdit
        # fields (unlike QLineEdit) can inherit mismatched text/background
        # colors from a Windows dark-mode palette in PyQt6, rendering as
        # invisible white-on-white text even though the stored value is fine.
        central_widget.setStyleSheet(
            "QLineEdit, QTextEdit { background-color: white; color: #000000; }"
        )
        self.main_layout = QVBoxLayout()

        yacss_build_type = QComboBox()
        yacss_build_type.addItems(["", "Diagram", "Listicle", "Masspage_Silo_Local"])

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
            "Hero Image URL": QLineEdit(),
            "City Page Hero Image Base URL": QLineEdit(),
            "Logo URL": QLineEdit(),
            "Contact Email Address": QLineEdit(),
            "Primary Business Category": QLineEdit(),
            "FAQ Questions (one per line)": QTextEdit(),
            # YACSS build settings: these have no equivalent anywhere else in
            # this form -- they are pure build mechanics for the YACSS API
            # (rr_yacss_factory), not part of the client's own profile, so
            # they stay grouped and prefixed "YACSS " rather than mixed in
            # above. See rr_yacss_factory's docs/RR_YACSS_Factory_Specifications.md
            # for what each corresponds to on the wire.
            "YACSS Build Type": yacss_build_type,
            "YACSS Template": QLineEdit(),
            "YACSS Bucket Keyword": QLineEdit(),
            "YACSS Cloud Account IDs (comma separated)": QLineEdit(),
            "YACSS Tier0 Pages": QLineEdit(),
            "YACSS Tiers (tier:pages, one per line)": QTextEdit(),
            "YACSS AI Platform": QLineEdit(),
            "YACSS AI Model": QLineEdit(),
            "YACSS Tone": QLineEdit(),
            "YACSS Language": QLineEdit(),
            "YACSS Items Per Listicle": QLineEdit(),
        }

        # Placeholder hints for the YACSS fields only -- their valid values
        # aren't self-evident the way "Phone" or "Email" are. Applied in the
        # layout loops below rather than chained onto the dict literal above,
        # to keep that dict a plain widget-per-key mapping.
        self.placeholders = {
            "YACSS Template": "e.g. porto-001",
            "YACSS Bucket Keyword": "themed micro-site name -- becomes the real cloud bucket name",
            "YACSS Cloud Account IDs (comma separated)": "e.g. 28205",
            "YACSS Tier0 Pages": "1",
            "YACSS Tiers (tier:pages, one per line)": "1:5",
            "YACSS AI Platform": "openai",
            "YACSS AI Model": "gpt-5-mini",
            "YACSS Tone": "friendly",
            "YACSS Language": "en",
            "YACSS Items Per Listicle": "6",
        }

        self.menu_bar = QMenuBar()
        self.setMenuBar(self.menu_bar)
        help_menu = QMenu("Help", self)
        help_menu.addAction("About", self.show_about)
        help_menu.addAction("How to Use", self.show_usage)
        file_menu = QMenu("File", self)
        file_menu.addAction("Open YAML", self.load_yaml)
        self.menu_bar.addMenu(file_menu)
        self.menu_bar.addMenu(help_menu)

        grid_layout = QGridLayout()
        left = list(self.inputs.keys())[:10]
        right = list(self.inputs.keys())[10:]

        for i, key in enumerate(left):
            lbl = QLabel(key)
            lbl.setFont(QFont("Arial", self.font_size))
            widget = self.inputs[key]
            widget.setFont(QFont("Arial", self.font_size))
            self.labels[key] = lbl
            if "Phone" in key:
                widget.setInputMask("(000) 000-0000;_")
            if key in self.placeholders:
                widget.setPlaceholderText(self.placeholders[key])
            grid_layout.addWidget(lbl, i, 0)
            grid_layout.addWidget(widget, i, 1)

        for i, key in enumerate(right):
            lbl = QLabel(key)
            lbl.setFont(QFont("Arial", self.font_size))
            widget = self.inputs[key]
            widget.setFont(QFont("Arial", self.font_size))
            self.labels[key] = lbl
            if key in self.placeholders:
                widget.setPlaceholderText(self.placeholders[key])
            grid_layout.addWidget(lbl, i, 2)
            grid_layout.addWidget(widget, i, 3)

        self.main_layout.addLayout(grid_layout)

        self.city_list = QListWidget()
        self.city_list.setFont(QFont("Arial", self.font_size))
        self.city_list.setFixedHeight(150)
        self.manage_cities_button = QPushButton("Manage Cities")
        self.manage_cities_button.setFont(QFont("Arial", self.font_size))
        self.manage_cities_button.clicked.connect(self.open_city_dialog)
        self.main_layout.addWidget(QLabel("Added Cities:"))
        self.main_layout.addWidget(self.city_list)
        self.main_layout.addWidget(self.manage_cities_button)

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        self.main_layout.addWidget(self.save_button)

        central_widget.setLayout(self.main_layout)

        # Wrapped in a scroll area rather than a fixed 800px window: the
        # YACSS build-settings fields added this section pushed the right
        # column (23 fields) well past what fits on screen without one.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(central_widget)
        self.setCentralWidget(scroll_area)

    def open_city_dialog(self):
        dialog = CityEmbedDialog(self)
        if dialog.exec():
            city_data = dialog.get_data()
            key = f"{city_data['city']}, {city_data['state']}"
            self.city_data[key] = {"embed_code": city_data['embed_code']}
            self.refresh_city_list()

    def refresh_city_list(self):
        self.city_list.clear()
        for city, data in self.city_data.items():
            has_embed = bool(data.get("embed_code"))
            status = "✅" if has_embed else "⚠️"
            self.city_list.addItem(QListWidgetItem(f"{status} {city}"))

    def show_about(self):
        QMessageBox.information(self, "About", "Skippy Cloud Stack – YAML Builder v4")

    def show_usage(self):
        QMessageBox.information(self, "How to Use", "Complete the form, manage city embed codes, and save your YAML file.")

    def load_yaml(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Open YAML File", "", "YAML Files (*.yaml *.yml)")
        if not file_name:
            return
        try:
            with open(file_name, "r", encoding="utf-8") as file:
                data = yaml.safe_load(file)
            for key, widget in self.inputs.items():
                value = data.get(key, "")
                if isinstance(value, list):
                    value = "\n".join(str(item) for item in value)
                if isinstance(widget, QTextEdit):
                    widget.setPlainText(str(value))
                elif isinstance(widget, QComboBox):
                    idx = widget.findText(str(value), Qt.MatchFlag.MatchFixedString)
                    widget.setCurrentIndex(idx if idx >= 0 else 0)
                else:
                    widget.setText(str(value))
            if "city_embeds" in data and isinstance(data["city_embeds"], dict):
                self.city_data = data["city_embeds"]
                self.refresh_city_list()
            QMessageBox.information(self, "Loaded", "YAML loaded successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load YAML file:\n{e}")

    def save_yaml(self):
        missing = [c for c, d in self.city_data.items() if not d.get("embed_code")]
        if missing:
            reply = QMessageBox.question(self, "Missing Embeds",
                                         f"{len(missing)} cities are missing embeds. Add them now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                return
        data = {}
        for k, w in self.inputs.items():
            if isinstance(w, QTextEdit):
                text = w.toPlainText()
            elif isinstance(w, QComboBox):
                text = w.currentText()
            else:
                text = w.text()
            if k in self.LIST_FIELDS:
                data[k] = [line.strip() for line in text.splitlines() if line.strip()]
            else:
                data[k] = text
        data["city_embeds"] = self.city_data
        file_name, _ = QFileDialog.getSaveFileName(self, "Save YAML File", "", "YAML Files (*.yaml *.yml)")
        if file_name:
            try:
                with open(file_name, "w") as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                QMessageBox.information(self, "Saved", "YAML saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save YAML:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = YAMLForm()
    form.show()
    sys.exit(app.exec())
