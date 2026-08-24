from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from main import YAMLForm
from yacss_api import YacssApiError


SAMPLE_TEMPLATES = [
    {"id": "porto-001", "name": "Porto Business Template"},
    {"id": "classic-001", "name": "Classic Template"},
]

SAMPLE_ACCOUNTS = [
    {"id": "25399", "name": "Google Cloud", "provider": "google_cloud", "client": "George Penzenik"},
    {"id": "25398", "name": "Google Cloud", "provider": "google_cloud", "client": ""},
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
