import json

from PyQt6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem

from main import DEFAULT_JOB_EXPORT_DIR, YAMLForm


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


def test_page_titles_count_label_updates_live_as_tiers_change(qapp):
    form = YAMLForm()
    label = form.labels["YACSS Diagram Page Titles (one per line)"]
    # The multiplicative counter only applies to Diagram -- see
    # _update_page_titles_count_label's own doc comment.
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")

    form.inputs["YACSS Tier0 Pages"].setText("1")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")
    assert "need 4, have 0" in label.text()

    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText(
        "Home\nPage 1\nPage 2\nPage 3"
    )
    assert "4/4 OK" in label.text()

    # Adding a tier changes the multiplicative total live, without
    # touching the Page Titles field itself.
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3\n2:2")
    assert "need 10, have 4" in label.text()


def test_page_titles_count_label_handles_non_numeric_tier0_pages(qapp):
    form = YAMLForm()
    label = form.labels["YACSS Diagram Page Titles (one per line)"]
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")

    form.inputs["YACSS Tier0 Pages"].setText("not a number")
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText("Home")

    # Must not raise -- non-numeric input is treated as 0 rather than
    # crashing the live update.
    assert "need 0, have 1" in label.text()


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


def test_export_job_json_refuses_blank_build_type(qapp, monkeypatch, tmp_path):
    form = YAMLForm()
    # Build type left at its default blank entry.
    save_dialog_called = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *a, **k: save_dialog_called.append(True) or (str(tmp_path / "x.json"), ""),
    )

    form.export_job_json()

    assert save_dialog_called == []


def _fill_listicle_masspage_shared_fields(form):
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Website"].setText("https://acmeplumbing.example")
    form.inputs["YACSS Template"].setCurrentText("porto-001")
    form.inputs["YACSS Bucket Keyword"].setText("acme-plumbing-diagram-stack")
    form.inputs["YACSS Topic Keyword"].setText("emergency plumber Dallas")
    form.inputs["YACSS AI Platform"].setText("openai")
    form.cloud_account_manual_input.setText("28205")


def test_build_listicle_job_happy_path_no_warnings(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")

    job, warnings = form._build_listicle_job()

    assert warnings == []
    assert job == {
        "job_id": "acme-plumbing-listicle",
        "type": "listicle",
        "keyword": "emergency plumber Dallas",
        "name": "Acme Plumbing",
        "template": "porto-001",
        "ai_platform": "openai",
        "ai_model": "gpt-5-mini",
        "items_per_listicle": 6,
        "tone": "friendly",
        "language": "en",
        "cloud_account_ids": ["28205"],
        "lsi_keyword": "acme-plumbing-diagram-stack",
    }


def test_build_listicle_job_warns_on_blank_required_fields(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    # Everything left blank.

    job, warnings = form._build_listicle_job()

    assert any("* Client Name" in w for w in warnings)
    assert any("YACSS Topic Keyword" in w for w in warnings)
    assert any("target stack keyword" in w for w in warnings)
    assert any("YACSS Items Per Listicle must be a positive" in w for w in warnings)
    assert any("No YACSS Cloud Account IDs selected" in w for w in warnings)
    assert job["job_id"] == "listicle-job"


def test_build_listicle_job_includes_brand_and_urls_when_filled_in(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")
    form.inputs["YACSS Brand Name"].setText("Acme Coffee Co")
    form.inputs["YACSS Brand URL"].setText("https://acmecoffee.example")
    form.inputs["YACSS Brand Position"].setText("1")
    form.inputs["YACSS Competitor URLs (one per line)"].setPlainText(
        "https://someothercafe.example"
    )
    form.inputs["YACSS Target URLs (one per line)"].setPlainText(
        "https://acmecoffee.example\nhttps://acmecoffee.example/menu"
    )

    job, warnings = form._build_listicle_job()

    assert warnings == []
    assert job["brand"] == {"name": "Acme Coffee Co", "url": "https://acmecoffee.example", "position": 1}
    assert job["competitor_urls"] == ["https://someothercafe.example"]
    assert job["target_urls"] == [
        "https://acmecoffee.example",
        "https://acmecoffee.example/menu",
    ]


def test_build_listicle_job_omits_brand_and_urls_when_blank(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")

    job, warnings = form._build_listicle_job()

    assert warnings == []
    assert "brand" not in job
    assert "competitor_urls" not in job
    assert "target_urls" not in job


def test_build_listicle_job_warns_on_brand_name_without_url(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")
    form.inputs["YACSS Brand Name"].setText("Acme Coffee Co")
    # Brand URL left blank.

    job, warnings = form._build_listicle_job()

    assert any("Brand Name is set but" in w and "Brand URL is blank" in w for w in warnings)
    assert "brand" not in job


def test_build_listicle_job_warns_on_brand_url_without_name(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")
    form.inputs["YACSS Brand URL"].setText("https://acmecoffee.example")
    # Brand Name left blank.

    job, warnings = form._build_listicle_job()

    assert any("Brand URL is set but" in w and "Brand Name is blank" in w for w in warnings)
    assert "brand" not in job


def test_build_listicle_job_warns_on_non_positive_brand_position(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")
    form.inputs["YACSS Brand Name"].setText("Acme Coffee Co")
    form.inputs["YACSS Brand URL"].setText("https://acmecoffee.example")
    form.inputs["YACSS Brand Position"].setText("0")

    job, warnings = form._build_listicle_job()

    assert any("Brand Position" in w and "not a positive" in w for w in warnings)
    assert job["brand"] == {"name": "Acme Coffee Co", "url": "https://acmecoffee.example"}


def test_build_masspage_job_happy_path_no_warnings(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Masspage_Silo_Local")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText(
        "Emergency Plumbing Repair\nDrain Cleaning"
    )
    form.inputs["YACSS Diagram Content"].setPlainText("Acme Plumbing serves greater Dallas.")

    job, warnings = form._build_masspage_job()

    assert warnings == []
    assert job == {
        "job_id": "acme-plumbing-masspage",
        "type": "masspage",
        "keyword": "emergency plumber Dallas",
        "name": "Acme Plumbing",
        "template": "porto-001",
        "landing_url": "https://acmeplumbing.example",
        "page_titles": ["Emergency Plumbing Repair", "Drain Cleaning"],
        "content": "Acme Plumbing serves greater Dallas.",
        "ai_platform": "openai",
        "cloud_account_ids": ["28205"],
        "lsi_keyword": "acme-plumbing-diagram-stack",
    }


def test_build_masspage_job_warns_on_blank_required_fields(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Masspage_Silo_Local")
    # Everything left blank.

    job, warnings = form._build_masspage_job()

    assert any("* Client Name" in w for w in warnings)
    assert any("YACSS Topic Keyword" in w for w in warnings)
    assert any("target stack keyword" in w for w in warnings)
    assert any("Page Titles" in w and "blank" in w for w in warnings)
    assert any("YACSS Diagram Content is blank" in w for w in warnings)
    assert any("No YACSS Cloud Account IDs selected" in w for w in warnings)
    assert job["job_id"] == "masspage-job"


def test_export_job_json_writes_listicle_job(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS AI Model"].setText("gpt-5-mini")
    form.inputs["YACSS Tone"].setText("friendly")
    form.inputs["YACSS Language"].setText("en")
    form.inputs["YACSS Items Per Listicle"].setText("6")

    out_file = tmp_path / "listicle-export.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), ""))

    form.export_job_json()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["type"] == "listicle"
    assert data[0]["job_id"] == "acme-plumbing-listicle"


def test_export_job_json_writes_masspage_job(qapp, tmp_path, monkeypatch):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Masspage_Silo_Local")
    _fill_listicle_masspage_shared_fields(form)
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText("Emergency Plumbing Repair")
    form.inputs["YACSS Diagram Content"].setPlainText("Acme Plumbing serves greater Dallas.")

    out_file = tmp_path / "masspage-export.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out_file), ""))

    form.export_job_json()

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["type"] == "masspage"
    assert data[0]["job_id"] == "acme-plumbing-masspage"


def test_export_job_json_defaults_save_dialog_to_rr_yacss_factory_jobs_dir(qapp, monkeypatch):
    form = YAMLForm()
    _fill_required_fields(form)
    form.inputs["YACSS Diagram Content"].setPlainText("content")

    captured_default_path = []
    # This form has warnings (no tiers/page_titles filled in) -- answering
    # "Yes" (proceed anyway) is required to reach the save dialog call at
    # all, which is what this test needs to observe.
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    def fake_save_dialog(*args, **kwargs):
        captured_default_path.append(args[2])
        return ("", "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_save_dialog)

    form.export_job_json()

    assert captured_default_path == [str(DEFAULT_JOB_EXPORT_DIR / "acme-plumbing.json")]


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
