from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QFileDialog, QMessageBox

from main import YAMLForm, _CloudAccountPickerDialog
from yacss_api import YacssApiError


SAMPLE_TEMPLATES = [
    {"id": "porto-001", "name": "Porto Business Template"},
    {"id": "classic-001", "name": "Classic Template"},
]

SAMPLE_ACCOUNTS = [
    {"id": "25399", "name": "Google Cloud", "provider": "google_cloud", "client": "George Penzenik"},
    {"id": "25398", "name": "Google Cloud", "provider": "google_cloud", "client": ""},
]

SAMPLE_AI_PROVIDERS = [
    {"provider": "openai", "configured": True, "model": "gpt-5-mini", "is_default": True},
    {"provider": "openrouter", "configured": False, "model": None, "is_default": False},
]

SAMPLE_AI_MODELS = [
    {"id": "gpt-5-mini", "name": "GPT-5 Mini", "provider": "openai"},
    {"id": "gpt-5", "name": "GPT-5", "provider": "openai"},
    {"id": "anthropic/claude-haiku-4.5", "name": "Claude Haiku 4.5", "provider": "openrouter"},
]


def test_template_combo_populates_from_live_fetch(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_templates", lambda: SAMPLE_TEMPLATES)
    form = YAMLForm()
    combo = form.inputs["YACSS Template"]
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == ["", "porto-001", "classic-001"]


def test_cloud_account_list_populates_with_client_disambiguation(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: SAMPLE_ACCOUNTS)
    form = YAMLForm()
    assert form.cloud_account_list.count() == 2
    labeled = [form.cloud_account_list.item(i).text() for i in range(2)]
    assert "(client: George Penzenik)" in labeled[0]
    assert "(client:" not in labeled[1]


def test_live_lookup_failure_shows_one_warning_and_leaves_fields_empty(qapp, monkeypatch):
    def boom():
        raise YacssApiError("no token configured")

    monkeypatch.setattr("main.fetch_templates", boom)
    monkeypatch.setattr("main.fetch_cloud_accounts", boom)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None
    )

    form = YAMLForm()

    assert len(warnings) == 1
    assert form.inputs["YACSS Template"].count() == 0
    assert form.cloud_account_list.count() == 0
    # Both fields must still be directly usable despite the failed fetch.
    assert form.inputs["YACSS Template"].isEditable()
    form.inputs["YACSS Template"].setEditText("porto-001")
    assert form.inputs["YACSS Template"].currentText() == "porto-001"


def test_serialize_cloud_account_ids_combines_checked_and_manual(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: SAMPLE_ACCOUNTS)
    form = YAMLForm()
    form.cloud_account_list.item(0).setCheckState(Qt.CheckState.Checked)
    form.cloud_account_manual_input.setText("11885, 25399")

    # 25399 is both checked and typed manually -- must not be duplicated.
    assert form._serialize_cloud_account_ids() == "25399,11885"


def test_load_cloud_account_ids_splits_listed_vs_unlisted(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: SAMPLE_ACCOUNTS)
    form = YAMLForm()

    form._load_cloud_account_ids("25399, 99999")

    assert form.cloud_account_list.item(0).checkState() == Qt.CheckState.Checked
    assert form.cloud_account_list.item(1).checkState() == Qt.CheckState.Unchecked
    assert form.cloud_account_manual_input.text() == "99999"


def test_faq_table_round_trips_question_and_answer(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form._add_faq_row("How long does install take?", "Usually 2-4 hours.")

    out_file = tmp_path / "faq.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    reloaded = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(out_file), "")
    )
    reloaded.load_yaml()

    assert reloaded._serialize_faq_rows() == [
        {"question": "How long does install take?", "answer": "Usually 2-4 hours."}
    ]


def test_faq_table_migrates_legacy_list_of_strings(qapp):
    form = YAMLForm()
    form._load_faq_rows({"FAQ Questions (one per line)": ["Q1?", "Q2?"]})

    assert form._serialize_faq_rows() == [
        {"question": "Q1?", "answer": ""},
        {"question": "Q2?", "answer": ""},
    ]


def test_faq_table_migrates_legacy_flat_string(qapp):
    form = YAMLForm()
    form._load_faq_rows({"FAQ Questions (one per line)": "Q1?\nQ2?"})

    assert form._serialize_faq_rows() == [
        {"question": "Q1?", "answer": ""},
        {"question": "Q2?", "answer": ""},
    ]


def test_ai_platform_combo_populates_configured_providers_first(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_ai_providers", lambda: SAMPLE_AI_PROVIDERS)
    form = YAMLForm()
    combo = form.inputs["YACSS AI Platform"]

    assert [combo.itemText(i) for i in range(combo.count())] == ["", "openai", "openrouter"]
    assert combo.itemData(1, Qt.ItemDataRole.ToolTipRole) == "Configured on this account"
    assert "NOT configured" in combo.itemData(2, Qt.ItemDataRole.ToolTipRole)
    # Still editable -- a provider not in this account's list must remain
    # enterable, same as YACSS Template's own fallback.
    assert combo.isEditable()


def test_ai_model_combo_filters_by_selected_platform(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_ai_providers", lambda: SAMPLE_AI_PROVIDERS)
    monkeypatch.setattr("main.fetch_ai_models", lambda: SAMPLE_AI_MODELS)
    form = YAMLForm()
    platform_combo = form.inputs["YACSS AI Platform"]
    model_combo = form.inputs["YACSS AI Model"]

    platform_combo.setCurrentText("openai")
    assert [model_combo.itemText(i) for i in range(model_combo.count())] == [
        "", "gpt-5-mini", "gpt-5",
    ]

    platform_combo.setCurrentText("openrouter")
    assert [model_combo.itemText(i) for i in range(model_combo.count())] == [
        "", "anthropic/claude-haiku-4.5",
    ]


def test_ai_model_combo_preserves_current_value_across_platform_change(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_ai_models", lambda: SAMPLE_AI_MODELS)
    form = YAMLForm()
    model_combo = form.inputs["YACSS AI Model"]

    # A value typed/loaded that isn't in the (empty, since no platform is
    # selected yet) filtered list must survive as free text, not be wiped.
    model_combo.setCurrentText("some-future-model")
    form.inputs["YACSS AI Platform"].setCurrentText("openai")
    assert model_combo.currentText() == "some-future-model"


def test_tone_combo_prepopulated_with_confirmed_options(qapp):
    form = YAMLForm()
    combo = form.inputs["YACSS Tone"]

    items = [combo.itemText(i) for i in range(combo.count())]
    assert items[0] == ""
    assert "Conversational" in items
    assert "Persuasive" in items
    assert combo.isEditable()


def test_diagram_tier_table_gets_a_pick_accounts_button_per_row(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3\n2:2")

    for row in range(form.diagram_tier_accounts_table.rowCount()):
        button = form.diagram_tier_accounts_table.cellWidget(row, 2)
        assert button is not None
        assert button.text() == "Select..."


def test_cloud_account_picker_dialog_seeds_existing_selection(qapp):
    dialog = _CloudAccountPickerDialog(SAMPLE_ACCOUNTS, ["25398"])

    assert dialog.list_widget.item(0).checkState() == Qt.CheckState.Unchecked
    assert dialog.list_widget.item(1).checkState() == Qt.CheckState.Checked
    assert dialog.selected_ids() == ["25398"]


def test_cloud_account_picker_writes_selected_ids_into_tier_row(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: SAMPLE_ACCOUNTS)
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")

    def fake_exec(self):
        self.list_widget.item(0).setCheckState(Qt.CheckState.Checked)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(_CloudAccountPickerDialog, "exec", fake_exec)
    form._open_cloud_account_picker(0)

    assert form.diagram_tier_accounts_table.item(0, 1).text() == "25399"


def test_cloud_account_picker_cancel_leaves_row_untouched(qapp, monkeypatch):
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: SAMPLE_ACCOUNTS)
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")
    form.diagram_tier_accounts_table.item(0, 1).setText("11884")

    monkeypatch.setattr(_CloudAccountPickerDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    form._open_cloud_account_picker(0)

    assert form.diagram_tier_accounts_table.item(0, 1).text() == "11884"
