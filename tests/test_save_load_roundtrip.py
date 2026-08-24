import yaml
from PyQt6.QtWidgets import QFileDialog

from main import YAMLForm


def test_save_splits_one_per_line_fields_into_lists(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["* Target Cities (one per line)"].setPlainText(
        "Chicago\n\n  Naperville  \nJoliet\n"
    )
    form.inputs["* Services (one per line)"].setPlainText("Roofing\nSiding")
    form.inputs["* Client Name"].setText("Test Client")

    out_file = tmp_path / "out.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )

    form.save_yaml()

    with open(out_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["* Target Cities (one per line)"] == [
        "Chicago",
        "Naperville",
        "Joliet",
    ]
    assert data["* Services (one per line)"] == ["Roofing", "Siding"]
    assert data["* Client Name"] == "Test Client"


def test_save_writes_empty_list_for_blank_list_field(qapp, tmp_path, monkeypatch):
    form = YAMLForm()

    out_file = tmp_path / "out.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    with open(out_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for key in YAMLForm.LIST_FIELDS:
        assert data[key] == []


def test_save_leaves_non_list_fields_as_strings(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["* Client Name"].setText("Acme Corp")
    form.inputs["Google Maps Embed Code"].setPlainText("<iframe></iframe>")

    out_file = tmp_path / "out.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    with open(out_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["* Client Name"] == "Acme Corp"
    assert data["Google Maps Embed Code"] == "<iframe></iframe>"


def test_load_reads_new_list_format(qapp, tmp_path, monkeypatch):
    src_file = tmp_path / "in.yaml"
    data = {
        "* Target Cities (one per line)": ["Chicago", "Naperville", "Joliet"],
        "* Client Name": "Test Client",
    }
    with open(src_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(src_file), "")
    )
    form.load_yaml()

    assert (
        form.inputs["* Target Cities (one per line)"].toPlainText()
        == "Chicago\nNaperville\nJoliet"
    )
    assert form.inputs["* Client Name"].text() == "Test Client"


def test_load_reads_legacy_flat_string_format(qapp, tmp_path, monkeypatch):
    src_file = tmp_path / "legacy.yaml"
    data = {"* Target Cities (one per line)": "Chicago\nNaperville\nJoliet"}
    with open(src_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(src_file), "")
    )
    form.load_yaml()

    assert (
        form.inputs["* Target Cities (one per line)"].toPlainText()
        == "Chicago\nNaperville\nJoliet"
    )


def test_full_round_trip_save_then_load(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["* Target Cities (one per line)"].setPlainText(
        "Chicago\nNaperville\nJoliet"
    )
    form.inputs["* Services (one per line)"].setPlainText("Roofing\nSiding")
    form.inputs["FAQ Questions (one per line)"].setPlainText("Q1?\nQ2?")
    form.inputs["* Client Name"].setText("Round Trip Co")
    form.city_data = {"Chicago, IL": {"embed_code": "<iframe></iframe>"}}

    out_file = tmp_path / "roundtrip.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    reloaded = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(out_file), "")
    )
    reloaded.load_yaml()

    assert (
        reloaded.inputs["* Target Cities (one per line)"].toPlainText()
        == "Chicago\nNaperville\nJoliet"
    )
    assert (
        reloaded.inputs["* Services (one per line)"].toPlainText()
        == "Roofing\nSiding"
    )
    assert reloaded.inputs["FAQ Questions (one per line)"].toPlainText() == "Q1?\nQ2?"
    assert reloaded.inputs["* Client Name"].text() == "Round Trip Co"
    assert reloaded.city_data == {"Chicago, IL": {"embed_code": "<iframe></iframe>"}}
