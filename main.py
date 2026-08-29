
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit, QPushButton,
    QFileDialog, QMessageBox, QMenuBar, QMainWindow, QMenu, QListWidget, QListWidgetItem, QGridLayout,
    QScrollArea, QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QAbstractItemDelegate,
    QDialog, QTextBrowser, QTabWidget, QProgressBar
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
from theme import ThemeManager
from yacss_api import (
    fetch_templates,
    fetch_cloud_accounts,
    fetch_ai_providers,
    fetch_ai_models,
    YacssApiError,
)
from ai_content_generator import (
    generate_diagram_page_titles,
    generate_diagram_content,
    is_available as ai_content_is_available,
    AiContentError,
)

# Bumped by hand alongside CHANGELOG.md -- see that file for what changed
# at each version. Shown in the window title and the About dialog so a
# running instance is identifiable, unlike the old hardcoded "v4" (a
# leftover UI-redesign label, not a real version, that stopped being
# updated years before this was added).
__version__ = "0.4.0"

README_PATH = Path(__file__).resolve().parent / "README.md"

# Export Job JSON's default save directory -- rr_yacss_factory's own jobs/
# folder, where every existing job file (example-*.json, real client jobs)
# already lives, so `factory run -f jobs/<name>.json` works with no path
# juggling. Same sibling-directory assumption as yacss_api.py's
# RR_YACSS_FACTORY_ENV (both projects checked out under the same parent,
# e.g. E:\projects\rr_yacss_factory and E:\projects\skippy_yaml_builder).
# Falls back to this file's own directory if that folder doesn't exist
# (e.g. rr_yacss_factory not checked out on this machine) rather than
# pointing the save dialog at a nonexistent path.
_RR_YACSS_FACTORY_JOBS_DIR = Path(__file__).resolve().parent.parent / "rr_yacss_factory" / "jobs"
DEFAULT_JOB_EXPORT_DIR = (
    _RR_YACSS_FACTORY_JOBS_DIR if _RR_YACSS_FACTORY_JOBS_DIR.is_dir() else Path(__file__).resolve().parent
)


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


class _CloudAccountPickerDialog(QDialog):
    """A checkable-list picker for one Diagram tier's cloud accounts,
    opened from that tier row's "Select..." button in
    diagram_tier_accounts_table. Exists because raw numeric Cloud Account
    IDs aren't exposed anywhere in the YACSS dashboard UI -- a user without
    rr_yacss_factory's own `factory list-cloud-accounts` open in another
    window has no way to know what id "28205" even refers to. Shows the
    same "id -- provider -- name (client: ...)" label
    _populate_cloud_account_list already uses for the flat (non-Diagram)
    checklist, so the two pickers read consistently; the underlying
    tier-table cell still stores plain comma-separated ids, so nothing
    downstream (save_yaml, export_job_json, rr_yacss_factory itself) needs
    to change to consume this."""

    def __init__(self, accounts: list, selected_ids: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Cloud Accounts for This Tier")
        self.setMinimumWidth(500)

        layout = QVBoxLayout()
        if not accounts:
            layout.addWidget(
                QLabel(
                    "No live cloud account data available (no token, offline, "
                    "or the API call failed at startup). Close this dialog and "
                    "type account IDs directly into the tier's text field instead."
                )
            )
        self.list_widget = QListWidget()
        self.list_widget.setFixedHeight(220)
        selected = set(selected_ids)
        for account in accounts:
            label_parts = [account["id"], account.get("provider", ""), account.get("name", "")]
            if account.get("client"):
                label_parts.append(f"(client: {account['client']})")
            item = QListWidgetItem(" -- ".join(part for part in label_parts if part))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if account["id"] in selected else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, account["id"])
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(ok_button)
        button_row.addWidget(cancel_button)
        layout.addLayout(button_row)

        self.setLayout(layout)

    def selected_ids(self) -> list:
        ids = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids


class _AIGeneratedTextDialog(QDialog):
    """Preview/edit dialog shown after a "Generate with AI" button call --
    used by both YACSS Diagram Page Titles and YACSS Diagram Content.
    Never writes into the form field itself; the caller does that from
    `result_text()` after `exec()` returns Accepted, same as every other
    modal picker in this file (e.g. _CloudAccountPickerDialog). Mirrors
    cloud-stack-generator's AIContentPreviewDialog (Accept/Regenerate/
    Cancel, editable preview) so both apps' AI-generation UX matches."""

    def __init__(
        self,
        title: str,
        field_name: str,
        content: str,
        regenerate_callback,
        parent=None,
        required_line_count: int = None,
    ):
        super().__init__(parent)
        self.regenerate_callback = regenerate_callback
        self.required_line_count = required_line_count
        self.setWindowTitle(title)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        info_label = QLabel(
            f"Review the AI-generated {field_name} below. Edit directly if needed, "
            "then Accept, or Regenerate for a new version."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Live count check for callers that pass required_line_count (page
        # titles only) -- a real report showed the AI returning 20 lines
        # for a 19-required batch and the user only finding out from the
        # underlying form's own counter *after* already clicking Accept.
        # Same "X/Y OK" live-feedback pattern as the main form's
        # _update_page_titles_count_label, so a count mismatch is visible
        # here, before Accept, not after.
        self.count_label = None
        if required_line_count is not None:
            self.count_label = QLabel()
            self.count_label.setWordWrap(True)
            layout.addWidget(self.count_label)

        self.content_preview = QTextEdit()
        self.content_preview.setPlainText(content)
        if self.count_label is not None:
            self.content_preview.textChanged.connect(self._update_count_label)
        layout.addWidget(self.content_preview)

        if self.count_label is not None:
            self._update_count_label()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.accept_button = QPushButton("Accept")
        self.accept_button.clicked.connect(self.accept)
        ThemeManager.apply_button_style(self.accept_button, "success")
        button_row.addWidget(self.accept_button)

        self.regenerate_button = QPushButton("Regenerate")
        self.regenerate_button.clicked.connect(self._on_regenerate)
        ThemeManager.apply_button_style(self.regenerate_button, "export")
        button_row.addWidget(self.regenerate_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        ThemeManager.apply_button_style(cancel_button, "secondary")
        button_row.addWidget(cancel_button)

        layout.addLayout(button_row)
        self.setLayout(layout)

    def result_text(self) -> str:
        return self.content_preview.toPlainText()

    def _update_count_label(self):
        if self.count_label is None:
            return
        current = len(
            [line for line in self.content_preview.toPlainText().splitlines() if line.strip()]
        )
        required = self.required_line_count
        if current == required:
            self.count_label.setText(f"{current}/{required} lines -- OK")
            self.count_label.setStyleSheet("color: green;")
        else:
            self.count_label.setText(
                f"{current}/{required} lines -- the AI did not return the exact "
                "count required; add or remove a line before accepting."
            )
            self.count_label.setStyleSheet("color: #b00000; font-weight: bold;")

    def _on_regenerate(self):
        self.accept_button.setEnabled(False)
        self.regenerate_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            new_content = self.regenerate_callback()
            if new_content:
                self.content_preview.setPlainText(new_content)
        except AiContentError as exc:
            QMessageBox.critical(self, "Generation Failed", str(exc))
        finally:
            QApplication.restoreOverrideCursor()
            self.accept_button.setEnabled(True)
            self.regenerate_button.setEnabled(True)
            self.progress_bar.setVisible(False)


class YAMLForm(QMainWindow):
    # Fields whose QTextEdit holds one entry per line; saved as a real YAML
    # list rather than the raw multi-line string. Loading still accepts the
    # older flat-string format for backward compatibility with existing files.
    LIST_FIELDS = {
        "* Target Cities (one per line)",
        "* Services (one per line)",
        "Social/Citation URLs (one per line)",
        "YACSS Diagram Page Titles (one per line)",
        "YACSS Competitor URLs (one per line)",
        "YACSS Target URLs (one per line)",
    }

    # Which tab each self.inputs field appears on -- every key in self.inputs
    # must appear in exactly one of these three lists (checked implicitly:
    # a field left out of all three would still work for save/load, since
    # that loop iterates self.inputs directly, but would be invisible/
    # unreachable in the UI). Tabs replace the old single long scroll with
    # one QGridLayout each, both to keep any one screen shorter and to
    # group genuinely related fields together -- see _build_field_grid.
    CLIENT_INFO_FIELDS = [
        "* Client Name", "* Business Category", "* Phone", "Email", "* Website",
        "Street Address", "City", "State", "ZIP", "Country",
        "Broker Name", "Broker Website", "Broker Phone",
    ]
    CONTENT_FIELDS = [
        "Google Maps Embed Code", "* Target Cities (one per line)", "* Services (one per line)",
        "Social/Citation URLs (one per line)", "Hero Image URL", "City Page Hero Image Base URL",
        "Logo URL", "Contact Email Address", "Primary Business Category",
    ]
    YACSS_BUILD_FIELDS = [
        "YACSS Build Type", "YACSS Template", "YACSS Bucket Keyword", "YACSS Topic Keyword",
        "YACSS Tier0 Pages", "YACSS Tiers (tier:pages, one per line)", "YACSS AI Platform",
        "YACSS AI Model", "YACSS Tone", "YACSS Language", "YACSS Items Per Listicle",
        "YACSS Brand Name", "YACSS Brand URL", "YACSS Brand Position",
        "YACSS Competitor URLs (one per line)", "YACSS Target URLs (one per line)",
        "YACSS Diagram Page Titles (one per line)", "YACSS Diagram Content",
    ]

    # Fields that get a "Generate with AI" button in _build_field_grid,
    # mapped to the YAMLForm method that handles that button's click.
    # Diagram-only for now (see each handler's own guard) -- this is the
    # #1 next-session item from docs/projectStatus.md's "Resume From":
    # a faster path than hand-authoring page titles/content per client.
    AI_GENERATABLE_FIELDS = {
        "YACSS Diagram Page Titles (one per line)": "_generate_diagram_page_titles",
        "YACSS Diagram Content": "_generate_diagram_content",
    }

    # The only real enum this project has ever confirmed for "tone":
    # rr_yacss_factory's src/engine/batch-runner.ts documents these exact
    # values from a live GET /build-fields?type=listicle capture of that
    # field's real select options. Not independently confirmed for
    # Diagram/Masspage tone fields, but used as the one dropdown option set
    # regardless of build type since it's the only real data available --
    # the combo stays editable so an unconfirmed/future value can still be
    # typed and preserved.
    TONE_OPTIONS = [
        "", "Conversational", "ProfessionalWarm", "Authoritative", "Empathetic",
        "Witty", "Inspirational", "Persuasive", "Relatable", "Educational", "Urgent",
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Skippy Cloud Stack – YAML Builder v{__version__}")
        self.setGeometry(200, 200, 950, 700)
        self.font_size = 10
        self.dark_mode = False
        self.labels = {}
        self.city_data = {}
        # Raw live-fetched data cached for reuse beyond the widgets they
        # first populate: self._cloud_accounts backs both the flat
        # checklist (_populate_cloud_account_list) and each Diagram tier's
        # _CloudAccountPickerDialog; self._ai_models backs YACSS AI Model,
        # re-filtered by provider whenever YACSS AI Platform changes (see
        # _populate_ai_model_combo). Empty by default so a signal firing
        # before _populate_live_dropdowns runs (or a fetch failure) doesn't
        # crash on a missing attribute.
        self._cloud_accounts = []
        self._ai_models = []

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

        # Editable, same as yacss_template above and for the same reason:
        # populated live on startup (YACSS AI Platform from GET
        # /ai-providers, YACSS AI Model from GET /ai-models filtered to
        # whichever platform is currently selected -- see
        # _populate_ai_platform_combo/_populate_ai_model_combo), but a
        # value entered while the API is unreachable, or one not in the
        # live list for some other reason, must still be typeable and
        # preserved on save/load.
        yacss_ai_platform = QComboBox()
        yacss_ai_platform.setEditable(True)
        yacss_ai_model = QComboBox()
        yacss_ai_model.setEditable(True)
        # Not live-fetched (no YACSS endpoint exposes tone options) --
        # pre-populated from TONE_OPTIONS, the one real enum this project
        # has confirmed (see that constant's own comment). Still editable
        # so an untested value isn't blocked.
        yacss_tone = QComboBox()
        yacss_tone.setEditable(True)
        yacss_tone.addItems(self.TONE_OPTIONS)

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
            # Listicle/Masspage only -- their real ListicleJob/MasspageJob.keyword
            # (see rr_yacss_factory's src/jobs/schema.ts) is the job's own SEO
            # topic (e.g. "best coffee shops in Austin"), a genuinely different
            # value than "YACSS Bucket Keyword", which for these two types holds
            # lsi_keyword instead (the EXISTING Diagram build's keyword whose
            # bucket this publishes into -- see _update_build_type_ui's doc
            # comment and rr_yacss_factory's bucketAndDirectoryForJob(), which
            # derives bucket=slugify(lsi_keyword) / directory=slugify(keyword)
            # for these two types). Diagram/cloud_stack has no lsi_keyword
            # field at all, so this input is hidden for that type -- see
            # _update_build_type_ui.
            "YACSS Topic Keyword": QLineEdit(),
            "YACSS Tier0 Pages": QLineEdit(),
            "YACSS Tiers (tier:pages, one per line)": QTextEdit(),
            "YACSS AI Platform": yacss_ai_platform,
            "YACSS AI Model": yacss_ai_model,
            "YACSS Tone": yacss_tone,
            "YACSS Language": QLineEdit(),
            "YACSS Items Per Listicle": QLineEdit(),
            # Listicle-only, all optional in the real ListicleJob schema
            # (src/jobs/schema.ts's brandPlacementSchema/competitor_urls/
            # target_urls) -- brand is a client's own site placed inside the
            # generated listicle at a given rank; competitor/target URLs feed
            # the AI's own competitive research. brand.name/brand.url are
            # both required if brand is used at all (position is optional
            # within it) -- see _build_listicle_job's own doc comment for
            # the omit-if-blank / warn-if-partial handling.
            "YACSS Brand Name": QLineEdit(),
            "YACSS Brand URL": QLineEdit(),
            "YACSS Brand Position": QLineEdit(),
            "YACSS Competitor URLs (one per line)": QTextEdit(),
            "YACSS Target URLs (one per line)": QTextEdit(),
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
            "YACSS Topic Keyword": "e.g. best coffee shops in Austin -- the listicle/masspage subject",
            "YACSS Tier0 Pages": "1",
            "YACSS Tiers (tier:pages, one per line)": "1:5",
            "YACSS AI Platform": "openai",
            "YACSS AI Model": "gpt-5-mini",
            "YACSS Tone": "friendly",
            "YACSS Language": "en",
            "YACSS Items Per Listicle": "6",
            "YACSS Brand Name": "e.g. Acme Coffee Co (optional -- leave blank to skip brand placement)",
            "YACSS Brand URL": "https://acmecoffee.example",
            "YACSS Brand Position": "e.g. 1 (optional, must be a positive whole number)",
            "YACSS Competitor URLs (one per line)": "https://someothercafe.example",
            "YACSS Target URLs (one per line)": "https://acmecoffee.example",
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

        self.main_tabs = QTabWidget()

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
        # Third column ("Pick Accounts") is a friendlier alternative to
        # typing raw numeric ids into column 1 directly -- those ids are
        # never shown anywhere in the YACSS dashboard UI, only via this
        # project's own live GET /cloud-accounts lookup, so a user without
        # rr_yacss_factory's `factory list-cloud-accounts` open in another
        # window has no way to know what "28205" refers to. The picker
        # (_open_cloud_account_picker/_CloudAccountPickerDialog) writes its
        # result as plain comma-separated ids back into column 1, so column
        # 1 itself is untouched and still directly editable/typeable as a
        # fallback -- nothing downstream needs to change to consume it.
        self.diagram_tier_accounts_table = QTableWidget(0, 3)
        self.diagram_tier_accounts_table.setHorizontalHeaderLabels(
            ["Tier", "Cloud Account IDs (comma separated)", "Pick Accounts"]
        )
        self.diagram_tier_accounts_table.horizontalHeader().setStretchLastSection(True)
        self.diagram_tier_accounts_table.setFont(QFont("Arial", self.font_size))
        self.diagram_tier_accounts_table.setFixedHeight(120)

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
        ThemeManager.apply_button_style(self.add_faq_row_button, "success")
        self.remove_faq_row_button = QPushButton("Remove Selected FAQ Row")
        self.remove_faq_row_button.clicked.connect(self._remove_selected_faq_row)
        ThemeManager.apply_button_style(self.remove_faq_row_button, "danger")
        self.import_faq_csv_button = QPushButton("Import FAQs from CSV")
        self.import_faq_csv_button.clicked.connect(self.import_faq_csv)
        ThemeManager.apply_button_style(self.import_faq_csv_button, "import")

        self.city_list = QListWidget()
        self.city_list.setFont(QFont("Arial", self.font_size))
        self.city_list.setFixedHeight(150)
        self.manage_cities_button = QPushButton("Manage Cities")
        self.manage_cities_button.setFont(QFont("Arial", self.font_size))
        self.manage_cities_button.clicked.connect(self.open_city_dialog)
        ThemeManager.apply_button_style(self.manage_cities_button, "secondary")

        self.save_button = QPushButton("Save YAML")
        self.save_button.clicked.connect(self.save_yaml)
        ThemeManager.apply_button_style(self.save_button, "success")

        # Diagram-only for now (see export_job_json's own doc comment) --
        # Listicle/Masspage_Silo_Local export isn't built yet (missing
        # fields: a Listicle-specific target keyword, brand/competitor
        # info; page_titles/content are shared with Diagram and already
        # exist above, so those two types are closer once their own
        # export path is added).
        self.export_job_button = QPushButton("Export Job JSON (Diagram only)")
        self.export_job_button.clicked.connect(self.export_job_json)
        ThemeManager.apply_button_style(self.export_job_button, "export")

        self._build_tabs()

        # Buttons live in QHBoxLayout rows with addStretch() (see
        # _build_tabs and the action bar below), not bare
        # addWidget()-onto-a-QVBoxLayout -- a plain QVBoxLayout stretches
        # every child to the container's full width, which is why every
        # button in this form used to span the entire window.
        self.main_layout = QVBoxLayout()
        self.main_layout.addWidget(self.main_tabs)

        actions_row = QHBoxLayout()
        actions_row.addWidget(self.save_button)
        actions_row.addWidget(self.export_job_button)
        actions_row.addStretch()
        self.main_layout.addLayout(actions_row)

        central_widget.setLayout(self.main_layout)

        # Wrapped in a scroll area rather than a fixed-height window: even
        # with fields split across tabs, the YACSS Build tab (12 fields
        # plus the cloud-account checklist/per-tier table) can still run
        # long on a small display.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(central_widget)
        self.setCentralWidget(scroll_area)

        yacss_build_type.currentTextChanged.connect(self._update_build_type_ui)
        yacss_ai_platform.currentTextChanged.connect(self._populate_ai_model_combo)
        self.inputs["YACSS Tiers (tier:pages, one per line)"].textChanged.connect(
            self._sync_diagram_tier_table
        )
        # _sync_diagram_tier_table (above) already refreshes the counter
        # whenever Tiers changes; these two also affect the expected/actual
        # count directly and need their own wiring.
        self.inputs["YACSS Tier0 Pages"].textChanged.connect(self._update_page_titles_count_label)
        self.inputs["YACSS Diagram Page Titles (one per line)"].textChanged.connect(
            self._update_page_titles_count_label
        )
        self._update_build_type_ui(yacss_build_type.currentText())
        self._update_page_titles_count_label()

        self._populate_live_dropdowns()

    def _build_field_grid(self, field_keys: list) -> QGridLayout:
        """One QGridLayout (label column 0, widget column 1) for the given
        self.inputs keys, in order -- the per-tab replacement for the old
        single 4-column grid that held every field on one screen at once."""
        grid_layout = QGridLayout()
        for row, key in enumerate(field_keys):
            lbl = QLabel(key)
            lbl.setFont(QFont("Arial", self.font_size))
            widget = self.inputs[key]
            widget.setFont(QFont("Arial", self.font_size))
            self.labels[key] = lbl
            if "Phone" in key:
                widget.setInputMask("(000) 000-0000;_")
            if key in self.placeholders:
                widget.setPlaceholderText(self.placeholders[key])
            grid_layout.addWidget(lbl, row, 0)
            grid_layout.addWidget(widget, row, 1)
            handler_name = self.AI_GENERATABLE_FIELDS.get(key)
            if handler_name:
                ai_button = QPushButton("Generate with AI")
                ai_button.setFont(QFont("Arial", self.font_size))
                ThemeManager.apply_button_style(ai_button, "export")
                ai_button.clicked.connect(getattr(self, handler_name))
                grid_layout.addWidget(ai_button, row, 2)
        return grid_layout

    def _build_tabs(self):
        """Builds self.main_tabs' four tabs. Every self.inputs field must
        appear in exactly one of CLIENT_INFO_FIELDS/CONTENT_FIELDS/
        YACSS_BUILD_FIELDS (checked by test_ui_tabs.py) -- a field left out
        of all three would still work for save/load (that loop iterates
        self.inputs directly, not the tab layouts), but would be invisible
        in the UI. FAQ has no self.inputs fields of its own (self.faq_table
        is a dedicated widget, not in that dict), so it isn't in that
        contract -- see _serialize_faq_rows/_load_faq_rows."""
        client_info_tab = QWidget()
        client_info_layout = QVBoxLayout()
        client_info_layout.addLayout(self._build_field_grid(self.CLIENT_INFO_FIELDS))
        client_info_layout.addStretch()
        client_info_tab.setLayout(client_info_layout)
        self.main_tabs.addTab(client_info_tab, "Client Info")

        content_tab = QWidget()
        content_layout = QVBoxLayout()
        content_layout.addLayout(self._build_field_grid(self.CONTENT_FIELDS))
        content_layout.addWidget(QLabel("Added Cities:"))
        content_layout.addWidget(self.city_list)
        manage_cities_row = QHBoxLayout()
        manage_cities_row.addWidget(self.manage_cities_button)
        manage_cities_row.addStretch()
        content_layout.addLayout(manage_cities_row)
        content_layout.addStretch()
        content_tab.setLayout(content_layout)
        self.main_tabs.addTab(content_tab, "Content")

        faq_tab = QWidget()
        faq_layout = QVBoxLayout()
        faq_layout.addWidget(QLabel("FAQ Questions & Answers:"))
        faq_layout.addWidget(self.faq_table)
        faq_buttons_row = QHBoxLayout()
        faq_buttons_row.addWidget(self.add_faq_row_button)
        faq_buttons_row.addWidget(self.remove_faq_row_button)
        faq_buttons_row.addWidget(self.import_faq_csv_button)
        faq_buttons_row.addStretch()
        faq_layout.addLayout(faq_buttons_row)
        faq_layout.addStretch()
        faq_tab.setLayout(faq_layout)
        self.main_tabs.addTab(faq_tab, "FAQ")

        yacss_tab = QWidget()
        yacss_layout = QVBoxLayout()
        yacss_layout.addLayout(self._build_field_grid(self.YACSS_BUILD_FIELDS))
        yacss_layout.addWidget(self.cloud_account_list_label)
        yacss_layout.addWidget(self.cloud_account_list)
        yacss_layout.addWidget(self.cloud_account_manual_input)
        yacss_layout.addWidget(self.diagram_tier_table_label)
        yacss_layout.addWidget(self.diagram_tier_accounts_table)
        yacss_layout.addStretch()
        yacss_tab.setLayout(yacss_layout)
        self.main_tabs.addTab(yacss_tab, "YACSS Build")

    def _populate_live_dropdowns(self):
        """Fetches templates/cloud accounts/AI providers/AI models from the
        live YACSS API to populate the Template combo, Cloud Account
        checklist (plus each Diagram tier's picker dialog), and the AI
        Platform/AI Model combos. Failure (no token, offline, API error) is
        non-fatal by design, per field -- each affected widget is simply
        left empty/unfiltered and the form stays fully usable via manual
        entry (every combo here is editable). A single combined warning
        covers all four calls so an expected failure mode (e.g. no
        network) doesn't produce four popups."""
        errors = []
        try:
            self._populate_template_combo(fetch_templates())
        except YacssApiError as exc:
            errors.append(str(exc))
        try:
            self._cloud_accounts = fetch_cloud_accounts()
            self._populate_cloud_account_list(self._cloud_accounts)
        except YacssApiError as exc:
            errors.append(str(exc))
        try:
            self._populate_ai_platform_combo(fetch_ai_providers())
        except YacssApiError as exc:
            errors.append(str(exc))
        try:
            self._ai_models = fetch_ai_models()
        except YacssApiError as exc:
            errors.append(str(exc))
        # Always runs, even if the fetch above failed (self._ai_models
        # stays [] in that case) -- keeps whatever the user already typed/
        # selected rather than leaving the combo in whatever state it had
        # before this method ran.
        self._populate_ai_model_combo()
        if errors:
            QMessageBox.warning(
                self,
                "YACSS live lookup unavailable",
                "Could not load some live YACSS data -- affected fields "
                "still work manually.\n\n" + "\n".join(errors),
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

    def _populate_ai_platform_combo(self, providers: list):
        """Populates YACSS AI Platform from GET /ai-providers, configured
        providers first (usable on this account without further setup),
        then the rest -- shown, not hidden, since a provider unconfigured
        on THIS account may still be valid to select for a different
        account/build, or get configured later. Each item's tooltip states
        whether it's configured, since selecting an unconfigured one fails
        generation with a real 401 (confirmed live, see rr_yacss_factory's
        docs/projectStatus.md session-5 notes) with no other warning
        anywhere in this form."""
        combo = self.inputs["YACSS AI Platform"]
        current = combo.currentText()
        combo.clear()
        combo.addItem("")
        for provider in sorted(providers, key=lambda p: not p.get("configured", False)):
            combo.addItem(provider["provider"])
            tooltip = (
                "Configured on this account"
                if provider.get("configured")
                else "NOT configured on this account -- generation will fail with this provider"
            )
            combo.setItemData(combo.count() - 1, tooltip, Qt.ItemDataRole.ToolTipRole)
        if current:
            idx = combo.findText(current, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(current)

    def _populate_ai_model_combo(self, platform: str = None):
        """Populates YACSS AI Model from self._ai_models, filtered to
        whichever provider is currently in YACSS AI Platform (or the
        `platform` arg, when called directly as that combo's
        currentTextChanged slot -- Qt passes the new text positionally).
        GET /ai-models is keyed by provider server-side (confirmed live,
        see rr_yacss_factory's src/api/client.ts), so without this filter
        the combo would mix every provider's models together with no way
        to tell which platform each one actually belongs to. Re-run
        whenever the platform changes; whatever was already typed/selected
        is preserved as an exact match if still offered, or as free text
        otherwise, same fallback _populate_ai_platform_combo/
        _populate_template_combo use."""
        combo = self.inputs["YACSS AI Model"]
        current = combo.currentText()
        platform = (platform if platform is not None else self.inputs["YACSS AI Platform"].currentText()).strip()
        combo.clear()
        combo.addItem("")
        for model in self._ai_models:
            if platform and model.get("provider") != platform:
                continue
            combo.addItem(model["id"])
            combo.setItemData(
                combo.count() - 1,
                f"{model.get('name', model['id'])} ({model.get('provider', '')})",
                Qt.ItemDataRole.ToolTipRole,
            )
        if current:
            idx = combo.findText(current, Qt.MatchFlag.MatchFixedString)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(current)

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
        # Topic Keyword (job.keyword's real SEO-subject meaning for these two
        # types -- see the field's own setup comment) has nothing to hold for
        # Diagram/cloud_stack, which has no separate topic concept.
        self.labels["YACSS Topic Keyword"].setVisible(not is_diagram)
        self.inputs["YACSS Topic Keyword"].setVisible(not is_diagram)
        # Brand placement + competitor/target URLs exist only on the real
        # ListicleJob schema (src/jobs/schema.ts) -- cloud_stack and masspage
        # have no equivalent fields at all, not even optional ones.
        is_listicle = build_type == "Listicle"
        for key in (
            "YACSS Brand Name",
            "YACSS Brand URL",
            "YACSS Brand Position",
            "YACSS Competitor URLs (one per line)",
            "YACSS Target URLs (one per line)",
        ):
            self.labels[key].setVisible(is_listicle)
            self.inputs[key].setVisible(is_listicle)

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
        else:
            self._update_page_titles_count_label()

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
            pick_button = QPushButton("Select...")
            pick_button.setFont(QFont("Arial", self.font_size))
            # Default args bind `row` at connect time, not call time --
            # without them every button would close over the same final
            # loop variable and all open the last row's picker.
            pick_button.clicked.connect(
                lambda checked=False, r=row: self._open_cloud_account_picker(r)
            )
            self.diagram_tier_accounts_table.setCellWidget(row, 2, pick_button)
        self._update_page_titles_count_label()

    def _open_cloud_account_picker(self, row: int):
        """Opens _CloudAccountPickerDialog for one tier row, seeded with
        whatever ids are already in that row's column-1 text, and writes
        the dialog's result back into that same cell as plain
        comma-separated ids on OK. A Cancel (or closing the dialog) leaves
        the row untouched."""
        ids_item = self.diagram_tier_accounts_table.item(row, 1)
        current_ids = [v.strip() for v in (ids_item.text() if ids_item else "").split(",") if v.strip()]
        dialog = _CloudAccountPickerDialog(self._cloud_accounts, current_ids, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.diagram_tier_accounts_table.setItem(
                row, 1, QTableWidgetItem(",".join(dialog.selected_ids()))
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
        (src/jobs/schema.ts v1.11) -- tiers multiply, not add, and
        tier0_pages is the multiplicative root of the whole pyramid, not
        just an additive starting point. tier_pages is an iterable of each
        tier's own page count, in tier order.

        Corrected 2026-08-26: originally seeded running_product at 1
        instead of tier0_pages, only ever confirmed live against a
        tier0_pages=1 example where that bug is invisible (multiplying by
        1 vs. not multiplying by it at all give the same result). A real
        tier0_pages=3 Salvo Metal Works build (id 127455) confirmed live
        that YACSS's real per-tier totals include tier0_pages in the
        running product -- see rr_yacss_factory's schema.ts for the full
        trail."""
        running_product = tier0_pages
        total = tier0_pages
        for pages in tier_pages:
            running_product *= pages
            total += running_product
        return total

    def _tier_pages_from_table(self) -> list:
        """Each row's page count (as an int, 0 if unparseable), in the same
        order as diagram_tier_accounts_table's rows -- parsed from the row
        label _sync_diagram_tier_table wrote (e.g. "Tier 1 (3 pages)").
        The single source of truth both _build_cloud_stack_job and the
        live page-titles counter (_update_page_titles_count_label) use, so
        the two can never disagree about the expected total."""
        pages = []
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            match = re.search(r"\((\d+) pages\)", tier_item.text()) if tier_item else None
            pages.append(int(match.group(1)) if match else 0)
        return pages

    def _update_page_titles_count_label(self):
        """Keeps the Page Titles field's own label showing, live, exactly
        how many titles are needed -- the multiplicative total isn't
        something a user can mentally compute from Tier0 Pages/Tiers
        alone, and previously the only feedback was a warning after
        clicking Export. This field is also reused (see its own setup
        comment) for Masspage's page_titles, which has no multiplicative-
        total requirement (MasspageJobSchema only requires at least one
        entry) -- the Tier0/Tiers-derived count would be actively wrong
        guidance there, so it's skipped entirely outside Diagram."""
        label = self.labels["YACSS Diagram Page Titles (one per line)"]
        if self.inputs["YACSS Build Type"].currentText() != "Diagram":
            label.setText("YACSS Diagram Page Titles (one per line)")
            label.setStyleSheet("")
            return
        try:
            tier0_pages = int(self.inputs["YACSS Tier0 Pages"].text().strip() or "0")
        except ValueError:
            tier0_pages = 0
        expected = self._compute_cloud_stack_total_pages(
            tier0_pages, self._tier_pages_from_table()
        )
        current = len(
            [
                line
                for line in self.inputs["YACSS Diagram Page Titles (one per line)"]
                .toPlainText()
                .splitlines()
                if line.strip()
            ]
        )
        if current == expected:
            label.setText(f"YACSS Diagram Page Titles (one per line) -- {current}/{expected} OK")
            label.setStyleSheet("color: green;")
        else:
            label.setText(
                f"YACSS Diagram Page Titles (one per line) -- need {expected}, have {current}"
            )
            label.setStyleSheet("color: #b00000;")

    def _diagram_ai_context(self) -> dict:
        """Shared context for both YACSS Diagram AI-generation buttons,
        pulled entirely from fields the user has already filled in
        elsewhere on the form -- no new required input."""
        return {
            "business_name": self.inputs["* Client Name"].text().strip(),
            "business_category": self.inputs["* Business Category"].text().strip(),
            "target_keyword": self.inputs["YACSS Bucket Keyword"].text().strip(),
            "target_cities": [
                line
                for line in self.inputs["* Target Cities (one per line)"].toPlainText().splitlines()
                if line.strip()
            ],
            "services": [
                line
                for line in self.inputs["* Services (one per line)"].toPlainText().splitlines()
                if line.strip()
            ],
        }

    def _expected_page_title_count(self) -> int:
        """The real required title count -- same computation
        _update_page_titles_count_label already uses, so what "Generate
        with AI" produces and what the live counter validates can never
        disagree."""
        try:
            tier0_pages = int(self.inputs["YACSS Tier0 Pages"].text().strip() or "0")
        except ValueError:
            tier0_pages = 0
        return self._compute_cloud_stack_total_pages(tier0_pages, self._tier_pages_from_table())

    def _check_ai_generation_available(self) -> bool:
        """Shared guard for both "Generate with AI" handlers: a configured
        key and Diagram build type (the exact-page-count / spintax-content
        prompts are both tuned for Diagram specifically -- see each
        generator function's own doc comment in ai_content_generator.py)."""
        if not ai_content_is_available():
            QMessageBox.warning(
                self,
                "AI Not Available",
                "AI content generation is not available. Set OPENAI_API_KEY "
                "in cloud-stack-generator's .env (../cloud-stack-generator/.env) "
                "to enable this feature.",
            )
            return False
        if self.inputs["YACSS Build Type"].currentText() != "Diagram":
            QMessageBox.warning(
                self,
                "Diagram Only",
                "Generate with AI is tuned for Diagram's exact page-count "
                "and spintax-content requirements -- switch YACSS Build "
                "Type to Diagram first.",
            )
            return False
        return True

    @staticmethod
    def _missing_diagram_ai_fields(context: dict) -> list:
        """Names exactly which required field(s) are blank, in the same
        order the form asks for them -- a real report showed the old fixed
        "fill in all three" wording named * Client Name and * Business
        Category even when both were already filled in and YACSS Bucket
        Keyword (a different tab) was the only one actually empty, which
        read as this project not reading the Client Info tab's fields at
        all. Naming only the real gap(s) makes that unambiguous."""
        missing = []
        if not context["business_name"]:
            missing.append("* Client Name (Client Info tab)")
        if not context["business_category"]:
            missing.append("* Business Category (Client Info tab)")
        if not context["target_keyword"]:
            missing.append("YACSS Bucket Keyword (YACSS Build tab)")
        return missing

    def _run_ai_generation(self, generate_fn):
        """Runs `generate_fn` (no args) with a busy cursor and the form
        disabled, same pattern cloud-stack-generator's business_tab.py
        uses for its own "Generate with AI" buttons. Returns the generated
        text, or None if generation failed (a message box is already shown
        in that case -- callers should just return)."""
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.setEnabled(False)
        try:
            return generate_fn()
        except AiContentError as exc:
            QMessageBox.critical(self, "Generation Failed", str(exc))
            return None
        finally:
            QApplication.restoreOverrideCursor()
            self.setEnabled(True)

    def _generate_diagram_page_titles(self):
        if not self._check_ai_generation_available():
            return
        context = self._diagram_ai_context()
        missing = self._missing_diagram_ai_fields(context)
        if missing:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in the following before generating page titles:\n- "
                + "\n- ".join(missing),
            )
            return
        title_count = self._expected_page_title_count()
        if title_count < 1:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Fill in YACSS Tier0 Pages and YACSS Tiers first so the "
                "real required page count is known.",
            )
            return

        def do_generate():
            titles = generate_diagram_page_titles(title_count=title_count, **context)
            return "\n".join(titles)

        content = self._run_ai_generation(do_generate)
        if content is None:
            return

        dialog = _AIGeneratedTextDialog(
            title="AI Generated Page Titles",
            field_name=f"Page Titles ({title_count} required)",
            content=content,
            regenerate_callback=do_generate,
            parent=self,
            required_line_count=title_count,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_generated_page_titles(dialog.result_text())

    def _apply_generated_page_titles(self, text: str):
        self.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText(text)

    def _generate_diagram_content(self):
        if not self._check_ai_generation_available():
            return
        context = self._diagram_ai_context()
        missing = self._missing_diagram_ai_fields(context)
        if missing:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in the following before generating content:\n- "
                + "\n- ".join(missing),
            )
            return

        def do_generate():
            return generate_diagram_content(
                city=self.inputs["City"].text().strip(),
                state=self.inputs["State"].text().strip(),
                **context,
            )

        content = self._run_ai_generation(do_generate)
        if content is None:
            return

        dialog = _AIGeneratedTextDialog(
            title="AI Generated Diagram Content",
            field_name="Diagram Content",
            content=content,
            regenerate_callback=do_generate,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_generated_diagram_content(dialog.result_text())

    def _apply_generated_diagram_content(self, text: str):
        self.inputs["YACSS Diagram Content"].setPlainText(text)

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

        tier_pages = self._tier_pages_from_table()
        tiers = []
        for row in range(self.diagram_tier_accounts_table.rowCount()):
            tier_item = self.diagram_tier_accounts_table.item(row, 0)
            ids_item = self.diagram_tier_accounts_table.item(row, 1)
            tier_num = tier_item.data(Qt.ItemDataRole.UserRole)
            ids_text = ids_item.text().strip() if ids_item else ""
            account_ids = [v.strip() for v in ids_text.split(",") if v.strip()]
            if not account_ids:
                warnings.append(f"Tier {tier_num} has no Cloud Account IDs assigned")
            tiers.append(
                {"tier": tier_num, "pages": tier_pages[row], "cloud_account_ids": account_ids}
            )

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

    def _build_listicle_job(self):
        """Builds a rr_yacss_factory ListicleJob dict (src/jobs/schema.ts's
        listicleJobSchema) plus advisory warnings, mirroring
        _build_cloud_stack_job's own pattern. job.keyword is the real SEO
        topic ("YACSS Topic Keyword"); job.lsi_keyword is the EXISTING
        Diagram build's own keyword whose bucket this publishes into
        ("YACSS Bucket Keyword", relabeled for this type -- see
        _update_build_type_ui and rr_yacss_factory's
        bucketAndDirectoryForJob()). brand/competitor_urls/target_urls are
        all optional in the real schema -- each is included only when the
        user actually filled it in, same as cloud_stack's FAQ
        extra_fields; brand itself requires BOTH name and url once used
        (brandPlacementSchema), so a partial entry (only one of the two)
        warns rather than silently sending an incomplete/rejected object."""
        warnings = []

        def require(value: str, label: str):
            if not value.strip():
                warnings.append(f"{label} is blank")

        client_name = self.inputs["* Client Name"].text()
        topic_keyword = self.inputs["YACSS Topic Keyword"].text()
        lsi_keyword = self.inputs["YACSS Bucket Keyword"].text()
        template = self.inputs["YACSS Template"].currentText()
        ai_platform = self.inputs["YACSS AI Platform"].currentText()
        ai_model = self.inputs["YACSS AI Model"].currentText()
        tone = self.inputs["YACSS Tone"].currentText()
        language = self.inputs["YACSS Language"].text()
        items_raw = self.inputs["YACSS Items Per Listicle"].text()

        require(client_name, "* Client Name")
        require(topic_keyword, "YACSS Topic Keyword")
        require(lsi_keyword, "YACSS Bucket Keyword (target stack keyword)")
        require(template, "YACSS Template")
        require(ai_platform, "YACSS AI Platform")
        require(ai_model, "YACSS AI Model")
        require(tone, "YACSS Tone")
        require(language, "YACSS Language")

        try:
            items_per_listicle = int(items_raw.strip() or "0")
        except ValueError:
            warnings.append(
                f"YACSS Items Per Listicle {items_raw!r} is not a whole number -- treated as 0"
            )
            items_per_listicle = 0
        if items_per_listicle <= 0:
            warnings.append("YACSS Items Per Listicle must be a positive whole number")

        cloud_account_ids = [v for v in self._serialize_cloud_account_ids().split(",") if v]
        if not cloud_account_ids:
            warnings.append("No YACSS Cloud Account IDs selected")

        job = {
            # "-listicle" suffix: without it this collides with the same
            # client's cloud_stack job_id (both slugify from the same
            # client name) -- rr_yacss_factory's manifest is keyed by
            # job_id, so a real Listicle export once silently inherited a
            # prior Diagram build's stale cloud_urls under the same key.
            # cloud_stack itself keeps its bare slug unchanged (see its own
            # job_id line) since real published builds already exist under
            # that exact job_id and renaming it would orphan them.
            "job_id": f"{self._slugify(client_name)}-listicle" if client_name.strip() else "listicle-job",
            "type": "listicle",
            "keyword": topic_keyword,
            "name": client_name,
            "template": template,
            "ai_platform": ai_platform,
            "ai_model": ai_model,
            "items_per_listicle": items_per_listicle,
            "tone": tone,
            "language": language,
            "cloud_account_ids": cloud_account_ids,
            "lsi_keyword": lsi_keyword,
        }

        brand_name = self.inputs["YACSS Brand Name"].text().strip()
        brand_url = self.inputs["YACSS Brand URL"].text().strip()
        brand_position_raw = self.inputs["YACSS Brand Position"].text().strip()
        if brand_name or brand_url:
            if not brand_name:
                warnings.append("YACSS Brand URL is set but YACSS Brand Name is blank -- brand omitted")
            elif not brand_url:
                warnings.append("YACSS Brand Name is set but YACSS Brand URL is blank -- brand omitted")
            else:
                brand = {"name": brand_name, "url": brand_url}
                if brand_position_raw:
                    try:
                        position = int(brand_position_raw)
                        if position <= 0:
                            raise ValueError
                        brand["position"] = position
                    except ValueError:
                        warnings.append(
                            f"YACSS Brand Position {brand_position_raw!r} is not a positive "
                            "whole number -- omitted"
                        )
                job["brand"] = brand

        competitor_urls = [
            line.strip()
            for line in self.inputs["YACSS Competitor URLs (one per line)"].toPlainText().splitlines()
            if line.strip()
        ]
        if competitor_urls:
            job["competitor_urls"] = competitor_urls

        target_urls = [
            line.strip()
            for line in self.inputs["YACSS Target URLs (one per line)"].toPlainText().splitlines()
            if line.strip()
        ]
        if target_urls:
            job["target_urls"] = target_urls

        return job, warnings

    def _build_masspage_job(self):
        """Builds a rr_yacss_factory MasspageJob dict (src/jobs/schema.ts's
        masspageJobSchema) plus advisory warnings -- see
        _build_listicle_job's doc comment for the keyword/lsi_keyword
        split, which applies identically here. page_titles/content reuse
        the same "YACSS Diagram Page Titles"/"YACSS Diagram Content"
        fields Diagram uses (their own setup comment already anticipated
        this); unlike Diagram's page_titles, masspageJobSchema has no
        multiplicative-total requirement, just at least one entry."""
        warnings = []

        def require(value: str, label: str):
            if not value.strip():
                warnings.append(f"{label} is blank")

        client_name = self.inputs["* Client Name"].text()
        topic_keyword = self.inputs["YACSS Topic Keyword"].text()
        lsi_keyword = self.inputs["YACSS Bucket Keyword"].text()
        template = self.inputs["YACSS Template"].currentText()
        landing_url = self.inputs["* Website"].text()
        ai_platform = self.inputs["YACSS AI Platform"].currentText()

        require(client_name, "* Client Name")
        require(topic_keyword, "YACSS Topic Keyword")
        require(lsi_keyword, "YACSS Bucket Keyword (target stack keyword)")
        require(template, "YACSS Template")
        require(landing_url, "* Website")
        require(ai_platform, "YACSS AI Platform")

        page_titles = [
            line.strip()
            for line in self.inputs["YACSS Diagram Page Titles (one per line)"]
            .toPlainText()
            .splitlines()
            if line.strip()
        ]
        if not page_titles:
            warnings.append("YACSS Diagram Page Titles (one per line) is blank")

        content = self.inputs["YACSS Diagram Content"].toPlainText().strip()
        if not content:
            warnings.append("YACSS Diagram Content is blank")

        cloud_account_ids = [v for v in self._serialize_cloud_account_ids().split(",") if v]
        if not cloud_account_ids:
            warnings.append("No YACSS Cloud Account IDs selected")

        job = {
            # "-masspage" suffix: see _build_listicle_job's own doc comment
            # for why -- same collision risk against the client's
            # cloud_stack job_id.
            "job_id": f"{self._slugify(client_name)}-masspage" if client_name.strip() else "masspage-job",
            "type": "masspage",
            "keyword": topic_keyword,
            "name": client_name,
            "template": template,
            "landing_url": landing_url,
            "page_titles": page_titles,
            "content": content,
            "ai_platform": ai_platform,
            "cloud_account_ids": cloud_account_ids,
            "lsi_keyword": lsi_keyword,
        }
        return job, warnings

    def export_job_json(self):
        """Writes a rr_yacss_factory job file (a JSON array containing one
        job dict, shaped for whichever YACSS Build Type is currently
        selected -- CloudStackJob/ListicleJob/MasspageJob). The two
        projects stay loosely coupled: this never calls the live YACSS API
        or duplicates rr_yacss_factory's own template/cloud-account name
        resolution -- it writes the same human-friendly job-file shape
        `factory run` already resolves itself."""
        build_type = self.inputs["YACSS Build Type"].currentText()
        job_builders = {
            "Diagram": self._build_cloud_stack_job,
            "Listicle": self._build_listicle_job,
            "Masspage_Silo_Local": self._build_masspage_job,
        }
        build_job = job_builders.get(build_type)
        if build_job is None:
            QMessageBox.warning(
                self,
                "Select a Build Type",
                "Choose a YACSS Build Type (Diagram, Listicle, or "
                "Masspage_Silo_Local) before exporting.",
            )
            return

        job, warnings = build_job()
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

        default_path = str(DEFAULT_JOB_EXPORT_DIR / f"{job['job_id']}.json")
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export Job JSON", default_path, "JSON Files (*.json)"
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
