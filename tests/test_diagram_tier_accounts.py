from PyQt6.QtWidgets import QFileDialog, QTableWidgetItem

from main import YAMLForm


def test_parse_tier_lines_basic():
    assert YAMLForm._parse_tier_lines("1:5\n2:3\n3:2") == [
        (1, "5"),
        (2, "3"),
        (3, "2"),
    ]


def test_parse_tier_lines_skips_blank_lines():
    # A real saved file can fold this value with blank lines between
    # entries (see save_yaml/load_yaml's plain-scalar handling).
    assert YAMLForm._parse_tier_lines("1:3\n\n2:3\n\n3:3") == [
        (1, "3"),
        (2, "3"),
        (3, "3"),
    ]


def test_parse_tier_lines_skips_lines_with_a_non_integer_tier():
    assert YAMLForm._parse_tier_lines("1:5\nbogus:3\n2:4") == [(1, "5"), (2, "4")]


def test_parse_tier_lines_handles_empty_input():
    assert YAMLForm._parse_tier_lines("") == []


def test_build_type_diagram_shows_per_tier_table_hides_flat_checklist(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")

    # isVisibleTo() reflects the widget's own setVisible() flag regardless
    # of whether the top-level window itself has ever been shown (it
    # hasn't, in this headless offscreen test suite).
    assert form.diagram_tier_accounts_table.isVisibleTo(form) is True
    assert form.cloud_account_list.isVisibleTo(form) is False


def test_build_type_listicle_shows_flat_checklist_hides_per_tier_table(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")

    assert form.diagram_tier_accounts_table.isVisibleTo(form) is False
    assert form.cloud_account_list.isVisibleTo(form) is True


def test_bucket_keyword_label_changes_by_build_type(qapp):
    form = YAMLForm()
    label = form.labels["YACSS Bucket Keyword"]

    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    assert "NEW bucket" in label.text()

    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    assert "EXISTING" in label.text()

    form.inputs["YACSS Build Type"].setCurrentText("Masspage_Silo_Local")
    assert "EXISTING" in label.text()


def test_sync_diagram_tier_table_builds_one_row_per_tier(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5\n2:3\n3:2")

    table = form.diagram_tier_accounts_table
    assert table.rowCount() == 3
    assert "Tier 1" in table.item(0, 0).text()
    assert "Tier 2" in table.item(1, 0).text()
    assert "Tier 3" in table.item(2, 0).text()


def test_sync_diagram_tier_table_preserves_entered_ids_for_surviving_tiers(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5\n2:3")
    form.diagram_tier_accounts_table.setItem(0, 1, QTableWidgetItem("28205"))

    # Adding a third tier must not wipe the already-entered tier 1 value.
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5\n2:3\n3:2")

    assert form.diagram_tier_accounts_table.rowCount() == 3
    assert form.diagram_tier_accounts_table.item(0, 1).text() == "28205"


def test_sync_diagram_tier_table_drops_rows_for_removed_tiers(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5\n2:3\n3:2")

    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5")

    assert form.diagram_tier_accounts_table.rowCount() == 1


def test_diagram_tier_accounts_round_trip_through_save_and_load(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QTableWidgetItem

    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:5\n2:3")
    form.diagram_tier_accounts_table.setItem(0, 1, QTableWidgetItem("28205,27502"))
    form.diagram_tier_accounts_table.setItem(1, 1, QTableWidgetItem("25702"))

    out_file = tmp_path / "diagram.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    # The flat field must be empty for a Diagram build -- see
    # _update_build_type_ui's doc comment on why these are mutually
    # exclusive.
    assert form._serialize_cloud_account_ids() == ""

    reloaded = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(out_file), "")
    )
    reloaded.load_yaml()

    assert reloaded.inputs["YACSS Build Type"].currentText() == "Diagram"
    assert reloaded.diagram_tier_accounts_table.rowCount() == 2
    assert reloaded.diagram_tier_accounts_table.item(0, 1).text() == "28205,27502"
    assert reloaded.diagram_tier_accounts_table.item(1, 1).text() == "25702"


def test_loading_a_legacy_diagram_file_migrates_flat_ids_onto_every_tier(
    qapp, tmp_path, monkeypatch
):
    """Regression test for a real bug found live against an actual client
    file (Overhead Door Joliet): a Diagram-type file saved before the
    per-tier table existed has its cloud accounts only in the flat field.
    Without migration, loading then re-saving such a file would silently
    lose that selection entirely, since the flat field is cleared on save
    for Diagram builds and the per-tier table would otherwise stay blank."""
    import yaml

    legacy_file = tmp_path / "legacy_diagram.yaml"
    with open(legacy_file, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "YACSS Build Type": "Diagram",
                "YACSS Tiers (tier:pages, one per line)": "1:5\n2:3",
                "YACSS Cloud Account IDs (comma separated)": "28205,27502",
            },
            f,
        )

    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(legacy_file), "")
    )
    form.load_yaml()

    assert form.diagram_tier_accounts_table.rowCount() == 2
    assert form.diagram_tier_accounts_table.item(0, 1).text() == "28205,27502"
    assert form.diagram_tier_accounts_table.item(1, 1).text() == "28205,27502"


def test_listicle_saves_flat_field_and_empty_per_tier_field(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    form.cloud_account_manual_input.setText("28205")

    out_file = tmp_path / "listicle.yaml"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), "")
    )
    form.save_yaml()

    import yaml

    with open(out_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["YACSS Cloud Account IDs (comma separated)"] == "28205"
    assert data["YACSS Diagram Tier Cloud Account IDs"] == []
