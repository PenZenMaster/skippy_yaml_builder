import json

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from main import YAMLForm


def _fill_required_fields(form):
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Phone"].setText("(214) 555-0100")
    form.inputs["Email"].setText("info@acmeplumbing.example")
    form.inputs["* Website"].setText("https://acmeplumbing.example")
    form.inputs["Street Address"].setText("123 Main St")
    form.inputs["City"].setText("Dallas")
    form.inputs["State"].setText("TX")
    form.inputs["ZIP"].setText("75201")
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Template"].setCurrentText("porto-001")
    form.inputs["YACSS Bucket Keyword"].setText("emergency plumber dallas")
    form.inputs["YACSS Tier0 Pages"].setText("1")


def test_slugify_basic():
    assert YAMLForm._slugify("Acme Plumbing Co.") == "acme-plumbing-co"
    assert YAMLForm._slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert YAMLForm._slugify("") == ""


def test_compute_cloud_stack_total_pages_matches_rr_yacss_factory_formula():
    # tiers 2/3/2 with tier0_pages=1 -> 1 + 2 + (2x3=6) + (2x3x2=12) = 21,
    # the exact example from rr_yacss_factory's own schema.ts doc comment.
    assert YAMLForm._compute_cloud_stack_total_pages(1, [2, 3, 2]) == 21


def test_compute_cloud_stack_total_pages_no_tiers():
    assert YAMLForm._compute_cloud_stack_total_pages(1, []) == 1


def test_build_cloud_stack_job_happy_path_no_warnings(qapp):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")
    form.diagram_tier_accounts_table.setItem(0, 1, QTableWidgetItem("28205,27502"))
    # tier0_pages=1 + tier1(3) = 1 + 3 = 4 total pages
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText(
        "Home\nPage 1\nPage 2\nPage 3"
    )
    form.inputs["YACSS Diagram Content"].setPlainText("Some real content.")

    job, warnings = form._build_cloud_stack_job()

    assert warnings == []
    assert job["job_id"] == "acme-plumbing"
    assert job["type"] == "cloud_stack"
    assert job["keyword"] == "emergency plumber dallas"
    assert job["name"] == "Acme Plumbing"
    assert job["template"] == "porto-001"
    assert job["landing_url"] == "https://acmeplumbing.example"
    assert job["tier0_pages"] == 1
    assert job["tiers"] == [{"tier": 1, "pages": 3, "cloud_account_ids": ["28205", "27502"]}]
    assert job["page_titles"] == ["Home", "Page 1", "Page 2", "Page 3"]
    assert job["content"] == "Some real content."
    assert job["company"] == {
        "name": "Acme Plumbing",
        "address": "123 Main St",
        "city": "Dallas",
        "state": "TX",
        "zip": "75201",
        "phone": "(214) 555-0100",
        "email": "info@acmeplumbing.example",
    }
    assert "extra_fields" not in job


def test_build_cloud_stack_job_maps_faqs_into_extra_fields(qapp):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Diagram Content"].setPlainText("content")
    form._add_faq_row("Q1?", "A1.")
    form._add_faq_row("Q2?", "A2.")

    job, _ = form._build_cloud_stack_job()

    assert job["extra_fields"] == {
        "faq_auto": "2",
        "faq_question[]": ["Q1?", "Q2?"],
        "faq_answer[]": ["A1.", "A2."],
    }


def test_build_cloud_stack_job_warns_on_blank_required_fields(qapp):
    form = YAMLForm()
    # Deliberately leave everything blank.

    job, warnings = form._build_cloud_stack_job()

    assert any("* Client Name" in w for w in warnings)
    assert any("YACSS Bucket Keyword" in w for w in warnings)
    assert any("YACSS Template" in w for w in warnings)
    assert any("* Website" in w for w in warnings)
    assert job["job_id"] == "cloud-stack-job"  # fallback when name is blank


def test_build_cloud_stack_job_warns_on_page_titles_mismatch(qapp):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")
    form.diagram_tier_accounts_table.setItem(0, 1, QTableWidgetItem("28205"))
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText("Only One Title")
    form.inputs["YACSS Diagram Content"].setPlainText("content")

    job, warnings = form._build_cloud_stack_job()

    assert any("real total page count" in w and "4" in w for w in warnings)


def test_build_cloud_stack_job_warns_on_tier_with_no_accounts(qapp):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")
    # Leave the tier's account IDs cell empty.

    job, warnings = form._build_cloud_stack_job()

    assert any("Tier 1 has no Cloud Account IDs" in w for w in warnings)


def test_export_job_json_refuses_non_diagram_build_types(qapp, monkeypatch, tmp_path):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    save_dialog_called = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: save_dialog_called.append(True) or (str(tmp_path / "x.json"), ""),
    )

    form.export_job_json()

    assert save_dialog_called == []


def test_export_job_json_writes_valid_json_when_warnings_accepted(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Diagram Content"].setPlainText("content")
    # No tiers, no page_titles -- guarantees warnings, to exercise the
    # confirm-anyway path deliberately.

    out_file = tmp_path / "export.json"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), ""))

    form.export_job_json()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["type"] == "cloud_stack"
    assert data[0]["job_id"] == "acme-plumbing"


def test_export_job_json_does_not_write_when_warnings_declined(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    # Blank form guarantees warnings.
    out_file = tmp_path / "should-not-exist.json"
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), ""))

    form.export_job_json()

    assert not out_file.exists()
