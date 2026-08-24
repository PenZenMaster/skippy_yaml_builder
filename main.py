
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QMenuBar, QMainWindow, QMenu, QListWidget, QListWidgetItem, QGridLayout,
    QScrollArea, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QAbstractItemDelegate,
    QDialog, QTextBrowser
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
import csv
import json
from pathlib import Path
import re
import sys
import yaml
from city_embed_dialog import CityEmbedDialog
from yacss_api import fetch_templates, fetch_cloud_accounts, YacssApiError

# Bumped by hand alongside CHANGELOG.md -- see that file for what changed
# at each version. Shown in the window title and the About dialog so a
# running instance is identifiable, unlike the old hardcoded "v4" (a
# leftover UI-redesign label, not a real version, that stopped being
# updated years before this was added).
__version__ = "0.1.0"

README_PATH = Path(__file__).resolve().parent / "README.md"


class HelpDialog(QDialog):
    """Renders README.md directly -- see that file's own top note: it's
    deliberately the single source of truth for in-app help AND the
    GitHub-facing readme, so the two can never drift out of sync the way
    a hand-duplicated help string would. Gracefully degrades if README.md
    isn't found alongside main.py (e.g. a PyInstaller --onefile build that
    didn't bundle it -- see build_exe.bat) rather than crashing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How to Use")
        self.resize(700, 600)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        try:
            text = README_PATH.read_text(encoding="utf-8")
            browser.setMarkdown(text)
        except OSError as e:
            browser.setPlainText(
                f"Could not load README.md from {README_PATH}:\n{e}\n\n"
                "See the project's GitHub page for documentation instead."
            )
        layout.addWidget(browser)
        self.setLayout(layout)


def parse_faq_csv(rows: list) -> list:
    """Parses already-read CSV rows (as from csv.reader) into
    [{"question": ..., "answer": ...}, ...], skipping a header row if the
    first cell of the first row is literally "question" (case-insensitive,
    stripped) and skipping any row with a blank question. A row with more
    than 2 columns (e.g. an unquoted comma inside the answer) has its
    columns after the first rejoined with "," rather than silently
    dropping data. Pure/file-IO-free so it's directly unit-testable
    without a QApplication or a real file."""
    if not rows:
        return []
    start = 0
    if rows[0] and rows[0][0].strip().lower() == "question":
        start = 1
    faqs = []
    for row in rows[start:]:
        if not row:
            continue
        question = row[0].strip()
        if not question:
            continue
        answer = ",".join(row[1:]).strip() if len(row) > 1 else ""
        faqs.append({"question": question, "answer": answer})
    return faqs


class _FaqTableWidget(QTableWidget):
    """QTableWidget whose Enter/Return key advances Question -> Answer
    (same row, opened for editing) or Answer -> a new row's Question.

    Qt's own default for a plain Return/Enter press while editing a cell
    is to commit the edit and re-select the SAME cell without opening it
    for editing (closeEditor is called with hint SubmitModelCache -- Tab
    uses a different hint, EditNextItem, and already does the right thing
    unmodified, which is why only SubmitModelCache is intercepted here).
    QA found that default behavior effectively traps a user in the
    Question cell: pressing Enter after typing a question looks like
    nothing happened, and typing again silently overwrites the question
    just entered, since it starts a fresh edit on the still-selected,
    no-longer-editing cell. Overriding keyPressEvent does NOT work for
    this -- while a cell is being edited, key events go to the editor
    widget (a child QLineEdit), not to the table's own keyPressEvent, so
    Return never reaches it; closeEditor is the actual interception point,
    confirmed live via a throwaway probe subclass that logged the real
    hint Qt sends."""

    def closeEditor(self, editor, hint):
        if hint != QAbstractItemDelegate.EndEditHint.SubmitModelCache:
            super().closeEditor(editor, hint)
            return
        row, col = self.currentRow(), self.currentColumn()
        super().closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)
        if row < 0:
            return
        if col == 0:
            self.setCurrentCell(row, 1)
            self.editItem(self.item(row, 1))
        else:
            next_row = row + 1
            if next_row >= self.rowCount():
                self.insertRow(next_row)
                self.setItem(next_row, 0, QTableWidgetItem(""))
                self.setItem(next_row, 1, QTableWidgetItem(""))
            self.setCurrentCell(next_row, 0)
            self.editItem(self.item(next_row, 0))


class YAMLForm(QMainWindow):
    # Fields whose QTextEdit holds one entry per line; saved as a real YAML
    # list rather than the raw multi-line string. Loading still accepts the
    # older flat-string format for backward compatibility with existing files.
    LIST_FIELDS = {
        "* Target Cities (one per line)",
        "* Services (one per line)",
        "Social/Citation URLs (one per line)",
        "YACSS Diagram Page Titles (one per line)",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Skippy Cloud Stack – YAML Builder v{__version__}")
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

        # Editable (unlike yacss_build_type above): populated live from
        # GET /templates on startup (see _populate_live_dropdowns below),
        # but a template created after that fetch, or entered while the
        # YACSS API is unreachable, must still be typeable and preserved
        # on save/load -- see load_yaml's QComboBox branch.
        yacss_template = QComboBox()
        yacss_template.setEditable(True)

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
            # FAQ Questions and YACSS Cloud Account IDs are handled by
            # dedicated widgets below (self.faq_table / self.cloud_account_list),
            # not through this generic dict -- see _serialize_faq_rows/
            # _load_faq_rows and _serialize_cloud_account_ids/
            # _load_cloud_account_ids. Kept out of self.inputs the same way
            # city_data/city_list already is, for the same reason: each
            # needs custom (not string/list-of-strings) save/load logic.
            # YACSS build settings: these have no equivalent anywhere else in
            # this form -- they are pure build mechanics for the YACSS API
            # (rr_yacss_factory), not part of the client's own profile, so
            # they stay grouped and prefixed "YACSS " rather than mixed in
            # above. See rr_yacss_factory's docs/RR_YACSS_Factory_Specifications.md
            # for what each corresponds to on the wire.
            "YACSS Build Type": yacss_build_type,
            "YACSS Template": yacss_template,
            "YACSS Bucket Keyword": QLineEdit(),
            "YACSS Tier0 Pages": QLineEdit(),
            "YACSS Tiers (tier:pages, one per line)": QTextEdit(),
            "YACSS AI Platform": QLineEdit(),
            "YACSS AI Model": QLineEdit(),
            "YACSS Tone": QLineEdit(),
            "YACSS Language": QLineEdit(),
            "YACSS Items Per Listicle": QLineEdit(),
            # Required by rr_yacss_factory's real CloudStackJob (and, later,
            # MasspageJob) but never previously captured anywhere in this
            # form: page_titles must contain exactly one title per line
            # matching the build's real MULTIPLICATIVE total page count
            # (see _compute_cloud_stack_total_pages) -- export_job_json
            # warns, but does not block, on a mismatch. content is the
            # free-form paragraph YACSS's cheap "spin content1" mode uses.
            "YACSS Diagram Page Titles (one per line)": QTextEdit(),
            "YACSS Diagram Content": QTextEdit(),
        }

        # Placeholder hints for the YACSS fields only -- their valid values
        # aren't self-evident the way "Phone" or "Email" are. Applied in the
        # layout loops below rather than chained onto the dict literal above,
        # to keep that dict a plain widget-per-key mapping.
        self.placeholders = {
            "YACSS Template": "e.g. porto-001",
            "YACSS Bucket Keyword": "themed micro-site name -- becomes the real cloud bucket name",
            "YACSS Tier0 Pages": "1",
            "YACSS Tiers (tier:pages, one per line)": "1:5",
            "YACSS AI Platform": "openai",
            "YACSS AI Model": "gpt-5-mini",
            "YACSS Tone": "friendly",
            "YACSS Language": "en",
            "YACSS Items Per Listicle": "6",
            "YACSS Diagram Content": "free-form paragraph text for the stack's pages",
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

        # YACSS Cloud Account IDs: a checkable multi-select list populated
        # live from GET /cloud-accounts (see _populate_live_dropdowns),
        # showing each account's client the same way rr_yacss_factory's own
        # `factory list-cloud-accounts` does -- so two identically-named
        # accounts under different clients are distinguishable here too
        # (this is exactly what motivated that CLI command in the first
        # place). The manual field alongside it is a deliberate fallback,
        # not a redundant duplicate: if the live fetch fails (no token, no
        # network) the checklist is simply empty, and this is the only way
        # to still enter an account id. Also lets an id created after the
        # last fetch, or one from a plan/cloud not in this account's list,
        # be entered without needing to restart the app.
        self.cloud_account_list = QListWidget()
        self.cloud_account_list.setFont(QFont("Arial", self.font_size))
        self.cloud_account_list.setFixedHeight(120)
        self.cloud_account_manual_input = QLineEdit()
        self.cloud_account_manual_input.setFont(QFont("Arial", self.font_size))
        self.cloud_account_manual_input.setPlaceholderText(
            "extra/manual account IDs, comma separated -- use if the account "
            "isn't listed above or the live lookup failed"
        )
        self.cloud_account_list_label = QLabel("YACSS Cloud Account IDs (check one or more):")
        self.main_layout.addWidget(self.cloud_account_list_label)
        self.main_layout.addWidget(self.cloud_account_list)
        self.main_layout.addWidget(self.cloud_account_manual_input)

        # Diagram-only: a real Diagram (cloud_stack) build assigns cloud
        # accounts PER TIER, not one global list -- rr_yacss_factory's
        # CloudStackTierInput carries its own cloud_account_ids per tier
        # (confirmed live), which is exactly the "different platform per
        # tier of the stack" pattern real Diagram builds use for footprint
        # diversity. This table's rows are kept in sync with "YACSS Tiers
        # (tier:pages, one per line)" (see _sync_diagram_tier_table) --
        # Tier 0 is deliberately never a row here, since tier0_pages has no
        # cloud_account_ids concept of its own in the real API, only tiers
        # 1+ do. Shown only when YACSS Build Type is Diagram; the flat
        # checklist above is shown otherwise (see _update_build_type_ui) --
        # Listicle/masspage builds target one existing stack's bucket, not
        # a pyramid, so one flat list is the correct shape for those.
        self.diagram_tier_table_label = QLabel(
            "YACSS Diagram Cloud Account IDs Per Tier (synced to YACSS Tiers above):"
        )
        self.diagram_tier_accounts_table = QTableWidget(0, 2)
        self.diagram_tier_accounts_table.setHorizontalHeaderLabels(
            ["Tier", "Cloud Account IDs (comma separated)"]
        )
        self.diagram_tier_accounts_table.horizontalHeader().setStretchLastSection(True)
        self.diagram_tier_accounts_table.setFont(QFont("Arial", self.font_size))
        self.diagram_tier_accounts_table.setFixedHeight(120)
        self.main_layout.addWidget(self.diagram_tier_table_label)
        self.main_layout.addWidget(self.diagram_tier_accounts_table)

        # FAQ Questions & Answers: YACSS's diagram builder needs both, not
        # just a question -- GET /build-fields?type=diagram's FAQ group has
        # separate parallel faq_question[]/faq_answer[] arrays, matched by
        # position; Manual mode (faq_auto=2, no AI credits spent) needs both
        # filled in per question. A two-column table matches that shape
        # directly, one row per FAQ.
        self.faq_table = _FaqTableWidget(0, 2)
        self.faq_table.setHorizontalHeaderLabels(["Question", "Answer"])
        self.faq_table.horizontalHeader().setStretchLastSection(True)
        self.faq_table.setFont(QFont("Arial", self.font_size))
        self.faq_table.setFixedHeight(150)
        self.faq_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.add_faq_row_button = QPushButton("Add FAQ Row")
        self.add_faq_row_button.clicked.connect(lambda: self._add_faq_row())
        self.remove_faq_row_button = QPushButton("Remove Selected FAQ Row")
        self.remove_faq_row_button.clicked.connect(self._remove_selected_faq_row)
        self.import_faq_csv_button = QPushButton("Import FAQs from CSV")
        self.import_faq_csv_button.clicked.connect(self.import_faq_csv)
        faq_buttons_row = QHBoxLayout()
        faq_buttons_row.addWidget(self.add_faq_row_button)
        faq_buttons_row.addWidget(self.remove_faq_row_button)
        faq_buttons_row.addWidget(self.import_faq_csv_button)
        self.main_layout.addWidget(QLabel("FAQ Questions & Answers:"))
        self.main_layout.addWidget(self.faq_table)
        self.main_layout.addLayout(faq_buttons_row)

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

        # Diagram-only for now (see export_job_json's own doc comment) --
        # Listicle/Masspage_Silo_Local export isn't built yet (missing
        # fields: a Listicle-specific target keyword, brand/competitor
        # info; page_titles/content are shared with Diagram and already
        # exist above, so those two types are closer once their own
        # export path is added).
        self.export_job_button = QPushButton("Export Job JSON (Diagram only)")
        self.export_job_button.clicked.connect(self.export_job_json)
        self.main_layout.addWidget(self.export_job_button)

        central_widget.setLayout(self.main_layout)

        # Wrapped in a scroll area rather than a fixed 800px window: the
        # YACSS build-settings fields added this section pushed the right
        # column (23 fields) well past what fits on screen without one.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(central_widget)
        self.setCentralWidget(scroll_area)

        yacss_build_type.currentTextChanged.connect(self._update_build_type_ui)
        self.inputs["YACSS Tiers (tier:pages, one per line)"].textChanged.connect(
            self._sync_diagram_tier_table
        )
        self._update_build_type_ui(yacss_build_type.currentText())

        self._populate_live_dropdowns()

    def _populate_live_dropdowns(self):
        """Fetches templates/cloud accounts from the live YACSS API to
        populate the Template combo and Cloud Account checklist. Failure
        (no token, offline, API error) is non-fatal by design -- both
        widgets are simply left empty and the form stays fully usable via
        the Template combo's own editability and the cloud-account manual
        fallback field. A single combined warning covers both calls so an
        expected failure mode (e.g. no network) doesn't produce two popups."""
        errors = []
        try:
            self._populate_template_combo(fetch_templates())
        except YacssApiError as exc:
            errors.append(str(exc))
        try:
            self._populate_cloud_account_list(fetch_cloud_accounts())
        except YacssApiError as exc:
            errors.append(str(exc))
        if errors:
            QMessageBox.warning(
                self,
                "YACSS live lookup unavailable",
                "Could not load live YACSS Template/Cloud Account data -- "
                "both fields still work manually.\n\n" + "\n".join(errors),
            )

    def _populate_template_combo(self, templates: list):
        combo = self.inputs["YACSS Template"]
        combo.clear()
        combo.addItem("")
        for template in templates:
            combo.addItem(template["id"])
            combo.setItemData(
                combo.count() - 1, template["name"], Qt.ItemDataRole.ToolTipRole
            )

    def _populate_cloud_account_list(self, accounts: list):
        self.cloud_account_list.clear()
        for account in accounts:
            label_parts = [account["id"], account.get("provider", ""), account.get("name", "")]
            if account.get("client"):
                label_parts.append(f"(client: {account['client']})")
            item = QListWidgetItem(" -- ".join(part for part in label_parts if part))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, account["id"])
            self.cloud_account_list.addItem(item)

    def _serialize_cloud_account_ids(self) -> str:
        ids = []
        for i in range(self.cloud_account_list.count()):
            item = self.cloud_account_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        for extra in self.cloud_account_manual_input.text().split(","):
            extra = extra.strip()
            if extra and extra not in ids:
                ids.append(extra)
        return ",".join(ids)

    def _load_cloud_account_ids(self, raw):
        ids = [v.strip() for v in str(raw).split(",") if v.strip()]
        listed_ids = set()
        for i in range(self.cloud_account_list.count()):
            item = self.cloud_account_list.item(i)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            listed_ids.add(item_id)
            item.setCheckState(
                Qt.CheckState.Checked if item_id in ids else Qt.CheckState.Unchecked
            )
        # An id not in the live-fetched list (stale list, id created since
        # the last fetch, or the API was unreachable at load time) must not
        # be silently dropped -- it lands in the manual field instead.
        extras = [i for i in ids if i not in listed_ids]
        self.cloud_account_manual_input.setText(", ".join(extras))

    def _update_build_type_ui(self, build_type: str):
        """Toggles between the flat cloud-account checklist (Listicle/
        Masspage_Silo_Local -- one existing stack bucket to publish into)
        and the per-tier table (Diagram -- see the per-tier table's own
        comment for why these are genuinely different shapes, not just a
        UI preference), and relabels YACSS Bucket Keyword, whose real
        meaning differs by type: for Diagram it names a brand-new bucket
        YACSS auto-creates at generate time; for Listicle/Masspage it must
        instead name an EXISTING Diagram build's bucket to publish into
        (confirmed live in rr_yacss_factory: neither type ever creates a
        bucket of its own). The underlying YAML key is left unchanged
        either way -- only the label/placeholder shown to the user
        differs, so existing files keep loading correctly regardless of
        which type filled them in."""
        is_diagram = build_type == "Diagram"

        self.cloud_account_list_label.setVisible(not is_diagram)
        self.cloud_account_list.setVisible(not is_diagram)
        self.cloud_account_manual_input.setVisible(not is_diagram)
        self.diagram_tier_table_label.setVisible(is_diagram)
        self.diagram_tier_accounts_table.setVisible(is_diagram)

        bucket_label = self.labels["YACSS Bucket Keyword"]
        bucket_widget = self.inputs["YACSS Bucket Keyword"]
        if is_diagram:
            bucket_label.setText("YACSS Bucket Keyword (creates a NEW bucket)")
            bucket_widget.setPlaceholderText(
                "themed micro-site name -- becomes the real cloud bucket name"
            )
        elif build_type in ("Listicle", "Masspage_Silo_Local"):
            bucket_label.setText(
                "YACSS Target Stack Keyword (an EXISTING Diagram build's bucket)"
            )
            bucket_widget.setPlaceholderText(
                "must match an existing Diagram job's own keyword -- this type never creates its own bucket"
            )
        else:
            bucket_label.setText("YACSS Bucket Keyword")
            bucket_widget.setPlaceholderText(self.placeholders["YACSS Bucket Keyword"])

        if is_diagram:
            self._sync_diagram_tier_table()

    @staticmethod
    def _parse_tier_lines(text: str) -> list:
        """Parses 'YACSS Tiers (tier:pages, one per line)' text into
        [(tier_number, pages_or_None), ...] in order, skipping blank lines
        (a real saved YAML file can fold this multi-line value with blank
        lines between entries -- see save_yaml/load_yaml's plain-scalar
        handling) and any line whose tier number isn't a plain integer."""
        result = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            tier_part, _, pages_part = line.partition(":")
            try:
                tier_num = int(tier_part.strip())
            except ValueError:
                continue
            pages_part = pages_part.strip()
            result.append((tier_num, pages_part if pages_part else None))
        return result

    def _sync_diagram_tier_table(self):
        """Rebuilds diagram_tier_accounts_table's rows to match the tier
        numbers currently in 'YACSS Tiers (tier:pages, one per line)',
        preserving any already-entered account IDs for tier numbers that
        are still present and dropping rows for tier numbers no longer
        there. Tier 0 is deliberately never a row (see the table's own
        setup comment)."""
        existing = {}
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            ids_item = self.diagram_tier_accounts_table.item(row, 1)
            if tier_item is not None:
                existing[tier_item.data(Qt.ItemDataRole.UserRole)] = (
                    ids_item.text() if ids_item else ""
                )

        tiers = self.inputs["YACSS Tiers (tier:pages, one per line)"].toPlainText()
        parsed = self._parse_tier_lines(tiers)

        self.diagram_tier_accounts_table.setRowCount(0)
        for tier_num, pages in parsed:
            row = self.diagram_tier_accounts_table.rowCount()
            self.diagram_tier_accounts_table.insertRow(row)
            label = f"Tier {tier_num} ({pages} pages)" if pages else f"Tier {tier_num}"
            tier_item = QTableWidgetItem(label)
            tier_item.setFlags(tier_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            tier_item.setData(Qt.ItemDataRole.UserRole, tier_num)
            self.diagram_tier_accounts_table.setItem(row, 0, tier_item)
            self.diagram_tier_accounts_table.setItem(
                row, 1, QTableWidgetItem(existing.get(tier_num, ""))
            )

    def _serialize_diagram_tier_accounts(self) -> list:
        rows = []
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            ids_item = self.diagram_tier_accounts_table.item(row, 1)
            ids_text = ids_item.text().strip() if ids_item else ""
            if tier_item is not None and ids_text:
                rows.append(
                    {
                        "tier": tier_item.data(Qt.ItemDataRole.UserRole),
                        "cloud_account_ids": ids_text,
                    }
                )
        return rows

    def _load_diagram_tier_accounts(self, rows, legacy_flat_ids: str = ""):
        """rows is the new "YACSS Diagram Tier Cloud Account IDs" value (a
        list of {tier, cloud_account_ids} dicts, or None/[] on a file saved
        before this field existed). legacy_flat_ids is that older file's
        flat "YACSS Cloud Account IDs" value -- when a Diagram build has no
        per-tier data at all yet but DOES have a non-empty legacy flat
        value, every tier row is pre-filled with it as a migration
        starting point. Without this, loading an old Diagram-type file and
        saving it again would silently lose its cloud account selection
        entirely: the flat field is cleared on save for Diagram builds
        (see _update_build_type_ui's doc comment), and the new per-tier
        table would otherwise stay blank. Confirmed live against a real
        pre-existing client file (Overhead Door Joliet) that hit exactly
        this."""
        self._sync_diagram_tier_table()
        by_tier = {}
        for row in rows or []:
            if isinstance(row, dict) and "tier" in row:
                by_tier[row["tier"]] = str(row.get("cloud_account_ids", ""))
        has_per_tier_data = bool(by_tier)
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            tier_num = tier_item.data(Qt.ItemDataRole.UserRole)
            if tier_num in by_tier:
                value = by_tier[tier_num]
            elif not has_per_tier_data and legacy_flat_ids.strip():
                value = legacy_flat_ids.strip()
            else:
                continue
            self.diagram_tier_accounts_table.setItem(row, 1, QTableWidgetItem(value))

    @staticmethod
    def _slugify(text: str) -> str:
        """Mirrors rr_yacss_factory's src/jobs/loader.ts slugify() closely
        enough for a readable job_id: lowercase, non-alphanumerics become
        a single hyphen, no leading/trailing hyphens."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
        return slug.strip("-")

    @staticmethod
    def _compute_cloud_stack_total_pages(tier0_pages: int, tier_pages) -> int:
        """Exact port of rr_yacss_factory's computeCloudStackTotalPages()
        (src/jobs/schema.ts) -- tiers multiply, not add. tier_pages is an
        iterable of each tier's own page count, in tier order."""
        running_product = 1
        total = tier0_pages
        for pages in tier_pages:
            running_product *= pages
            total += running_product
        return total

    def _build_cloud_stack_job(self):
        """Builds a rr_yacss_factory CloudStackJob dict from the current
        form state, plus a list of human-readable warnings for anything
        that looks incomplete or inconsistent (blank required fields, a
        page_titles count that doesn't match the real multiplicative
        total, a tier with no cloud accounts assigned). Warnings are
        advisory -- export_job_json still writes the file, since the
        real, authoritative validation is rr_yacss_factory's own job
        schema (src/jobs/schema.ts) when the file is actually used, not
        anything duplicated here. FAQs have no dedicated field in the
        real CloudStackJob -- see the class's own doc comment -- so
        they're passed through extra_fields as the raw YACSS build-field
        keys confirmed live (GET /build-fields?type=diagram's FAQ group):
        faq_auto="2" (manual mode, no AI credits spent) plus parallel
        faq_question[]/faq_answer[] arrays.
        """
        warnings = []

        def require(value: str, label: str):
            if not value.strip():
                warnings.append(f"{label} is blank")

        client_name = self.inputs["* Client Name"].text()
        keyword = self.inputs["YACSS Bucket Keyword"].text()
        template = self.inputs["YACSS Template"].currentText()
        landing_url = self.inputs["* Website"].text()
        tier0_pages_raw = self.inputs["YACSS Tier0 Pages"].text()

        require(client_name, "* Client Name")
        require(keyword, "YACSS Bucket Keyword")
        require(template, "YACSS Template")
        require(landing_url, "* Website")

        try:
            tier0_pages = int(tier0_pages_raw.strip() or "0")
        except ValueError:
            warnings.append(f"YACSS Tier0 Pages {tier0_pages_raw!r} is not a whole number -- treated as 0")
            tier0_pages = 0

        tiers = []
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            ids_item = self.diagram_tier_accounts_table.item(row, 1)
            tier_num = tier_item.data(Qt.ItemDataRole.UserRole)
            ids_text = ids_item.text().strip() if ids_item else ""
            pages_match = re.search(r"\((\d+) pages\)", tier_item.text())
            pages = int(pages_match.group(1)) if pages_match else 0
            account_ids = [v.strip() for v in ids_text.split(",") if v.strip()]
            if not account_ids:
                warnings.append(f"Tier {tier_num} has no Cloud Account IDs assigned")
            tiers.append({"tier": tier_num, "pages": pages, "cloud_account_ids": account_ids})

        page_titles = [
            line.strip()
            for line in self.inputs["YACSS Diagram Page Titles (one per line)"].toPlainText().splitlines()
            if line.strip()
        ]
        expected_total = self._compute_cloud_stack_total_pages(
            tier0_pages, [t["pages"] for t in tiers]
        )
        if len(page_titles) != expected_total:
            warnings.append(
                f"YACSS Diagram Page Titles has {len(page_titles)} line(s), but the "
                f"real total page count (multiplicative, not additive) is {expected_total}"
            )

        content = self.inputs["YACSS Diagram Content"].toPlainText().strip()
        if not content:
            warnings.append("YACSS Diagram Content is blank")

        company = {
            "name": self.inputs["* Client Name"].text(),
            "address": self.inputs["Street Address"].text(),
            "city": self.inputs["City"].text(),
            "state": self.inputs["State"].text(),
            "zip": self.inputs["ZIP"].text(),
            "phone": self.inputs["* Phone"].text(),
            "email": self.inputs["Email"].text() or self.inputs["Contact Email Address"].text(),
        }
        for field_name in ("address", "city", "state", "zip", "phone", "email"):
            require(company[field_name], f"Company {field_name}")

        job = {
            "job_id": self._slugify(client_name) or "cloud-stack-job",
            "type": "cloud_stack",
            "keyword": keyword,
            "name": client_name,
            "template": template,
            "landing_url": landing_url,
            "company": company,
            "tier0_pages": tier0_pages,
            "tiers": tiers,
            "page_titles": page_titles,
            "content": content,
        }

        faqs = self._serialize_faq_rows()
        if faqs:
            job["extra_fields"] = {
                "faq_auto": "2",
                "faq_question[]": [f["question"] for f in faqs],
                "faq_answer[]": [f["answer"] for f in faqs],
            }

        return job, warnings

    def export_job_json(self):
        """Writes a rr_yacss_factory job file (a JSON array containing one
        CloudStackJob) for the Diagram build type -- Listicle/
        Masspage_Silo_Local aren't supported yet (see this button's own
        setup comment for what's missing). The two projects stay loosely
        coupled: this never calls the live YACSS API or duplicates
        rr_yacss_factory's own template/cloud-account name resolution --
        it writes the same human-friendly job-file shape `factory run`
        already resolves itself."""
        if self.inputs["YACSS Build Type"].currentText() != "Diagram":
            QMessageBox.warning(
                self,
                "Not Supported Yet",
                "Job JSON export is only implemented for YACSS Build Type "
                "'Diagram' so far.",
            )
            return

        job, warnings = self._build_cloud_stack_job()
        if warnings:
            reply = QMessageBox.question(
                self,
                "Export Warnings",
                "This job has potential issues:\n\n"
                + "\n".join(f"- {w}" for w in warnings)
                + "\n\nExport anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        default_name = f"{job['job_id']}.json"
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export Job JSON", default_name, "JSON Files (*.json)"
        )
        if not file_name:
            return
        try:
            with open(file_name, "w", encoding="utf-8") as f:
                json.dump([job], f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Exported", f"Job JSON written to:\n{file_name}")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Failed to write job JSON:\n{e}")

    def _add_faq_row(self, question: str = "", answer: str = ""):
        row = self.faq_table.rowCount()
        self.faq_table.insertRow(row)
        self.faq_table.setItem(row, 0, QTableWidgetItem(question))
        self.faq_table.setItem(row, 1, QTableWidgetItem(answer))

    def _remove_selected_faq_row(self):
        row = self.faq_table.currentRow()
        if row >= 0:
            self.faq_table.removeRow(row)

    def _serialize_faq_rows(self) -> list:
        rows = []
        for r in range(self.faq_table.rowCount()):
            q_item = self.faq_table.item(r, 0)
            a_item = self.faq_table.item(r, 1)
            question = q_item.text().strip() if q_item else ""
            answer = a_item.text().strip() if a_item else ""
            if question:
                rows.append({"question": question, "answer": answer})
        return rows

    def _load_faq_rows(self, data: dict):
        self.faq_table.setRowCount(0)
        rows = data.get("FAQ Questions & Answers")
        if rows is None:
            # Backward compat: older YAML files saved this as a flat list
            # of question strings (or, older still, a raw newline string)
            # under the field's old name, with no answer at all.
            legacy = data.get("FAQ Questions (one per line)")
            if isinstance(legacy, list):
                rows = [{"question": str(q), "answer": ""} for q in legacy]
            elif isinstance(legacy, str) and legacy.strip():
                rows = [
                    {"question": line.strip(), "answer": ""}
                    for line in legacy.splitlines()
                    if line.strip()
                ]
            else:
                rows = []
        for row in rows:
            if isinstance(row, dict):
                self._add_faq_row(str(row.get("question", "")), str(row.get("answer", "")))
            else:
                self._add_faq_row(str(row), "")

    def import_faq_csv(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Import FAQs from CSV", "", "CSV Files (*.csv)"
        )
        if not file_name:
            return
        try:
            # utf-8-sig transparently strips a leading BOM (common in
            # Excel-exported CSVs) while still reading a plain-utf-8 file
            # with no BOM identically to "utf-8".
            with open(file_name, "r", encoding="utf-8-sig", newline="") as f:
                faqs = parse_faq_csv(list(csv.reader(f)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import FAQs from CSV:\n{e}")
            return
        if not faqs:
            QMessageBox.warning(
                self,
                "No FAQs Found",
                "No question/answer rows were found in that CSV file.",
            )
            return
        for faq in faqs:
            self._add_faq_row(faq["question"], faq["answer"])
        QMessageBox.information(self, "Imported", f"Imported {len(faqs)} FAQ(s).")

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
        QMessageBox.information(
            self, "About", f"Skippy Cloud Stack – YAML Builder v{__version__}"
        )

    def show_usage(self):
        HelpDialog(self).exec()

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
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    elif widget.isEditable():
                        # YACSS Template: a saved value not in the live-
                        # fetched list (fetch failed, or the template was
                        # created since) must still be preserved verbatim,
                        # not silently replaced by whatever is at index 0
                        # -- unlike YACSS Build Type below, which has a
                        # fixed, non-editable option set.
                        widget.setEditText(str(value))
                    else:
                        widget.setCurrentIndex(0)
                else:
                    widget.setText(str(value))
            self._load_cloud_account_ids(data.get("YACSS Cloud Account IDs (comma separated)", ""))
            self._load_faq_rows(data)
            # Must run after the generic loop above (which just populated
            # "YACSS Tiers") -- _load_diagram_tier_accounts rebuilds the
            # per-tier table from that text before filling in saved values.
            self._load_diagram_tier_accounts(
                data.get("YACSS Diagram Tier Cloud Account IDs"),
                legacy_flat_ids=str(data.get("YACSS Cloud Account IDs (comma separated)", "")),
            )
            self._update_build_type_ui(self.inputs["YACSS Build Type"].currentText())
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
        # The two cloud-account fields are mutually exclusive by build type
        # (see _update_build_type_ui's doc comment) -- write "" / [] for
        # whichever doesn't apply rather than leaving a stale value in the
        # saved YAML from before the type was last changed.
        is_diagram = self.inputs["YACSS Build Type"].currentText() == "Diagram"
        data["YACSS Cloud Account IDs (comma separated)"] = (
            "" if is_diagram else self._serialize_cloud_account_ids()
        )
        data["YACSS Diagram Tier Cloud Account IDs"] = (
            self._serialize_diagram_tier_accounts() if is_diagram else []
        )
        data["FAQ Questions & Answers"] = self._serialize_faq_rows()
        data["city_embeds"] = self.city_data
        file_name, _ = QFileDialog.getSaveFileName(self, "Save YAML File", "", "YAML Files (*.yaml *.yml)")
        if file_name:
            try:
                # Explicit encoding is required here -- without it, open()
                # uses the platform's locale-default encoding (cp1252 on a
                # typical Windows install, not UTF-8). A real client file
                # containing an em dash, curly quote, or (R)/(TM) symbol
                # (common when FAQ content is pasted from Word or a web
                # page) got written as cp1252 bytes this way, then failed
                # to load at all with a UnicodeDecodeError, since
                # load_yaml's open() (below) has always hardcoded
                # encoding="utf-8". Confirmed live 2026-08-25 with a real
                # client YAML file that wouldn't load until manually
                # re-encoded.
                with open(file_name, "w", encoding="utf-8", newline="") as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False)
                QMessageBox.information(self, "Saved", "YAML saved successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save YAML:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = YAMLForm()
    form.show()
    sys.exit(app.exec())
