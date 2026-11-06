"""GUI-free tests for job_export -- the job builders driven straight from a
client-file dict, the way a headless caller uses them. The GUI path is
still covered by test_export_job_json.py; test_gui_and_saved_file_agree
below ties the two together."""

import pytest
import yaml
from PyQt6.QtWidgets import QTableWidgetItem

import job_export
from main import YAMLForm


def _diagram_data(**overrides):
    data = {
        "* Client Name": "Acme Plumbing",
        "* Phone": "(214) 555-0100",
        "Email": "info@acmeplumbing.example",
        "* Website": "https://acmeplumbing.example",
        "Street Address": "123 Main St",
        "City": "Dallas",
        "State": "TX",
        "ZIP": "75201",
        "YACSS Build Type": "Diagram",
        "YACSS Template": "porto-001",
        "YACSS Bucket Keyword": "Emergency Plumber Dallas",
        "YACSS Text Before Target Link": "Visit",
        "YACSS Text Of Target Link": "Acme Plumbing",
        "YACSS Text After Target Link": "to learn more.",
        "YACSS Tier0 Pages": "1",
        "YACSS Tiers (tier:pages, one per line)": "1:2\n2:1",
        "YACSS Diagram Tier Cloud Account IDs": [
            {"tier": 1, "cloud_account_ids": "25398"},
            {"tier": 2, "cloud_account_ids": "25701,27504"},
        ],
        "YACSS Diagram Page Titles (one per line)": [
            "Title 1",
            "Title 2",
            "Title 3",
            "Title 4",
            "Title 5",
        ],
        "YACSS Diagram Content": "First paragraph.\n\nSecond paragraph.",
        "FAQ Questions & Answers": [
            {"question": "Q1?", "answer": "A1."},
            {"question": "", "answer": "orphan answer"},
        ],
    }
    data.update(overrides)
    return data


def test_cloud_stack_happy_path_has_no_warnings():
    job, warnings = job_export.build_job(_diagram_data())
    assert warnings == []
    assert job["job_id"] == "acme-plumbing"
    assert job["type"] == "cloud_stack"
    assert job["keyword"] == "emergency-plumber-dallas"
    # 1 + 1*2 + 1*2*1 = 5 pages, multiplicative.
    assert job["tiers"] == [
        {"tier": 1, "pages": 2, "cloud_account_ids": ["25398"]},
        {"tier": 2, "pages": 1, "cloud_account_ids": ["25701", "27504"]},
    ]
    assert job["content"] == "<p>First paragraph.</p><p>Second paragraph.</p>"
    assert job["faqs"] == [{"question": "Q1?", "answer": "A1."}]
    assert "cloud_buckets" not in job


def test_pinned_bucket_pins_every_tier_account_and_keeps_keyword():
    job, warnings = job_export.build_cloud_stack_job(
        _diagram_data(**{"YACSS Pinned Bucket": "acme-plumbing"})
    )
    assert warnings == []
    assert job["keyword"] == "Emergency Plumber Dallas"
    assert job["cloud_buckets"] == {
        "25398": "acme-plumbing",
        "25701": "acme-plumbing",
        "27504": "acme-plumbing",
    }
    assert job["directory"] == "emergency-plumber-dallas"


def test_values_as_yaml_loads_them():
    """A hand-written or older file can hold an unquoted ZIP (int), a
    None for an empty key, and multi-line strings where the form saves
    lists -- none of which should crash or change the job."""
    data = _diagram_data(
        ZIP=75201,
        **{
            "Legal / Company Name": None,
            "YACSS Tier0 Pages": 1,
            "YACSS Tiers (tier:pages, one per line)": "1:2\n\n2:1\n",
            "YACSS Diagram Page Titles (one per line)": "Title 1\nTitle 2\n\nTitle 3\nTitle 4\nTitle 5",
        },
    )
    job, warnings = job_export.build_job(data)
    assert warnings == []
    assert job["company"]["zip"] == "75201"
    assert job["company"]["name"] == "Acme Plumbing"
    assert len(job["page_titles"]) == 5


def test_legacy_flat_account_ids_fill_every_tier():
    data = _diagram_data(
        **{
            "YACSS Diagram Tier Cloud Account IDs": [],
            "YACSS Cloud Account IDs (comma separated)": "25398,25701",
        }
    )
    job, warnings = job_export.build_job(data)
    assert warnings == []
    assert [t["cloud_account_ids"] for t in job["tiers"]] == [
        ["25398", "25701"],
        ["25398", "25701"],
    ]


def test_missing_tier_accounts_and_title_count_warn():
    data = _diagram_data(
        **{
            "YACSS Diagram Tier Cloud Account IDs": [
                {"tier": 1, "cloud_account_ids": "25398"}
            ],
            "YACSS Diagram Page Titles (one per line)": ["Only one"],
        }
    )
    _, warnings = job_export.build_job(data)
    assert "Tier 2 has no Cloud Account IDs assigned" in warnings
    assert any("is 5" in w for w in warnings)


def test_missing_fields_warn_instead_of_crashing():
    _, warnings = job_export.build_job({"YACSS Build Type": "Diagram"})
    assert "* Client Name is blank" in warnings
    assert "YACSS Diagram Content is blank" in warnings


def test_job_id_override_wins():
    job, _ = job_export.build_job(
        _diagram_data(**{"YACSS Job ID (override)": " acme-02 "})
    )
    assert job["job_id"] == "acme-02"


def test_listicle_uses_flat_account_ids():
    data = {
        "* Client Name": "Acme Plumbing",
        "YACSS Build Type": "Listicle",
        "YACSS Topic Keyword": "best plumbers dallas",
        "YACSS Bucket Keyword": "emergency-plumber-dallas",
        "YACSS Template": "porto-001",
        "YACSS AI Platform": "openai",
        "YACSS AI Model": "gpt-5-mini",
        "YACSS Tone": "Conversational",
        "YACSS Language": "English",
        "YACSS Items Per Listicle": "5",
        "YACSS Cloud Account IDs (comma separated)": "25398, 25398,25701",
    }
    job, warnings = job_export.build_job(data)
    assert warnings == []
    assert job["job_id"] == "acme-plumbing-listicle"
    assert job["cloud_account_ids"] == ["25398", "25701"]


def test_legacy_faq_question_list():
    data = _diagram_data(**{"FAQ Questions & Answers": None})
    data["FAQ Questions (one per line)"] = ["Old question?", ""]
    job, _ = job_export.build_job(data)
    assert job["faqs"] == [{"question": "Old question?", "answer": ""}]


def test_unknown_build_type_raises():
    with pytest.raises(ValueError, match="Build Type"):
        job_export.build_job({"YACSS Build Type": ""})


def test_image_check_items_skip_single_content_image():
    job = {
        "hero_image_url": "https://x.example/hero.jpg",
        "logo_image_url": "https://x.example/logo.png",
        "content_image_url": "https://x.example/direct.jpg",
        "content_image_urls": ["https://x.example/a.jpg"],
    }
    assert job_export.image_check_items(job) == [
        ("Hero Image URL", "https://x.example/hero.jpg"),
        ("Logo URL", "https://x.example/logo.png"),
        ("Content Image URLs line 1", "https://x.example/a.jpg"),
    ]


def test_tier_page_count():
    assert job_export.tier_page_count("3") == 3
    assert job_export.tier_page_count(None) == 0
    assert job_export.tier_page_count("abc") == 0
    assert job_export.tier_page_count("-1") == 0


def test_gui_and_saved_file_agree(qapp):
    """The form's own export and a headless export of what Save YAML
    would write (round-tripped through YAML text) give the same job."""
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Phone"].setText("(214) 555-0100")
    form.inputs["Email"].setText("info@acmeplumbing.example")
    form.inputs["* Website"].setText("https://acmeplumbing.example")
    form.inputs["Street Address"].setText("123 Main St")
    form.inputs["City"].setText("Dallas")
    form.inputs["State"].setText("TX")
    form.inputs["ZIP"].setText("75201")
    form.inputs["YACSS Template"].setCurrentText("porto-001")
    form.inputs["YACSS Bucket Keyword"].setText("Emergency Plumber Dallas")
    form.inputs["YACSS Pinned Bucket"].setText("acme-plumbing")
    form.inputs["YACSS Text Before Target Link"].setText("Visit")
    form.inputs["YACSS Text Of Target Link"].setText("Acme Plumbing")
    form.inputs["YACSS Text After Target Link"].setText("to learn more.")
    form.inputs["YACSS Tier0 Pages"].setText("1")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:2\n2:1")
    form.diagram_tier_accounts_table.setItem(0, 1, QTableWidgetItem("25398"))
    form.diagram_tier_accounts_table.setItem(1, 1, QTableWidgetItem("25701"))
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText(
        "T1\nT2\nT3\nT4\nT5"
    )
    form.inputs["YACSS Diagram Content"].setPlainText("Para one.\n\nPara two.")
    form._add_faq_row("Q?", "A.")

    gui_job, gui_warnings = form._build_cloud_stack_job()
    saved = yaml.safe_load(
        yaml.dump(form._collect_form_data(), allow_unicode=True, sort_keys=False)
    )
    file_job, file_warnings = job_export.build_job(saved)

    assert file_job == gui_job
    assert file_warnings == gui_warnings
    assert gui_job["cloud_buckets"] == {
        "25398": "acme-plumbing",
        "25701": "acme-plumbing",
    }
