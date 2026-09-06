"""Tests for the "Content Silo" tab -- category/service discovery
(delegates to keyword_research_api.fetch_clusters, patched at
main.fetch_clusters same as test_keyword_research.py does), content
generation (delegates to silo_content_generator.generate_service_page_
content, patched at main.generate_service_page_content), and the
Markdown export. No real DataForSEO/OpenAI calls."""

from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from main import YAMLForm
from silo_content_generator import AiContentError as SiloContentError


def _cluster(title, volume=100, flagged=False, keywords=None):
    return {
        "label": "test",
        "total_search_volume": volume,
        "candidate_page_title": title,
        "candidate_page_title_flagged": flagged,
        "candidate_page_title_flag_reason": "possible brand" if flagged else None,
        "keywords": keywords or [{"keyword": title.lower(), "search_volume": volume}],
    }


def _check_row(table, row, column=0):
    table.item(row, column).setCheckState(Qt.CheckState.Checked)


def test_content_silo_tab_exists_with_its_widgets(qapp):
    form = YAMLForm()
    tab_labels = [form.main_tabs.tabText(i) for i in range(form.main_tabs.count())]
    assert "Content Silo" in tab_labels
    assert form.silo_seed_input is not None
    assert form.silo_categories_table.columnCount() == 5
    assert form.silo_services_table.columnCount() == 6


def test_content_silo_fields_are_not_part_of_the_saved_client_yaml_contract(qapp):
    # This tab's own state is deliberately excluded from self.inputs (see
    # _build_tabs's own doc comment on that contract) -- confirmed here so
    # a future change can't silently pull silo state into save_yaml/
    # load_yaml without a conscious decision to do so.
    form = YAMLForm()
    assert "Silo Seed Keyword" not in form.inputs
    assert not any("Silo" in key for key in form.inputs)


def test_find_categories_requires_a_seed(qapp):
    form = YAMLForm()
    with patch.object(QMessageBox, "warning") as mock_warning:
        form._run_silo_category_research()
    mock_warning.assert_called_once()
    assert form.silo_categories_table.rowCount() == 0


def test_find_categories_populates_the_categories_table(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    clusters = [_cluster("Garage Door Repair", volume=500), _cluster("Garage Door Installation", volume=300)]

    with patch("main.fetch_clusters", return_value=clusters) as mock_fetch:
        form._run_silo_category_research()

    mock_fetch.assert_called_once()
    assert mock_fetch.call_args.args[0] == ["garage door services"]
    assert form.silo_categories_table.rowCount() == 2
    assert form.silo_categories_table.item(0, 1).text() == "Garage Door Repair"
    assert form.silo_categories_table.item(0, 2).text() == "500"


def test_find_categories_replaces_prior_results_rather_than_appending(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("First Run")]):
        form._run_silo_category_research()
    with patch("main.fetch_clusters", return_value=[_cluster("Second Run A"), _cluster("Second Run B")]):
        form._run_silo_category_research()

    assert form.silo_categories_table.rowCount() == 2
    titles = [form.silo_categories_table.item(r, 1).text() for r in range(2)]
    assert titles == ["Second Run A", "Second Run B"]


def test_find_services_requires_at_least_one_checked_category(qapp):
    form = YAMLForm()
    with patch("main.fetch_clusters", return_value=[_cluster("Garage Door Repair")]):
        form._run_silo_category_research()
    form.silo_seed_input.setText("garage door services")

    with patch.object(QMessageBox, "warning") as mock_warning:
        form._run_silo_service_research()
    mock_warning.assert_called_once()
    assert form.silo_services_table.rowCount() == 0


def test_find_services_populates_services_table_with_category_column(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Garage Door Repair")]):
        form._run_silo_category_research()
    _check_row(form.silo_categories_table, 0)

    with patch(
        "main.fetch_clusters", return_value=[_cluster("Spring Replacement"), _cluster("Opener Repair")]
    ) as mock_fetch:
        form._run_silo_service_research()

    mock_fetch.assert_called_once_with(["Garage Door Repair"], set())
    assert form.silo_services_table.rowCount() == 2
    assert form.silo_services_table.item(0, 1).text() == "Garage Door Repair"
    assert form.silo_services_table.item(0, 2).text() == "Spring Replacement"


def test_find_services_clears_the_whole_table_each_run(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Category A"), _cluster("Category B")]):
        form._run_silo_category_research()
    _check_row(form.silo_categories_table, 0)
    _check_row(form.silo_categories_table, 1)

    with patch("main.fetch_clusters", return_value=[_cluster("Service 1")]):
        form._run_silo_service_research()
    assert form.silo_services_table.rowCount() == 2  # one per checked category

    # Re-run with only the first category checked -- the second
    # category's stale rows must be gone, not left behind.
    form.silo_categories_table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    with patch("main.fetch_clusters", return_value=[_cluster("Service 1")]):
        form._run_silo_service_research()
    assert form.silo_services_table.rowCount() == 1
    assert form.silo_services_table.item(0, 1).text() == "Category A"


def test_generate_content_requires_ai_availability(qapp):
    form = YAMLForm()
    with patch("main.silo_content_is_available", return_value=False), patch.object(
        QMessageBox, "warning"
    ) as mock_warning:
        form._generate_silo_content()
    mock_warning.assert_called_once()
    assert form.silo_pages == []


def test_generate_content_requires_at_least_one_checked_row(qapp):
    form = YAMLForm()
    with patch("main.silo_content_is_available", return_value=True), patch.object(
        QMessageBox, "warning"
    ) as mock_warning:
        form._generate_silo_content()
    mock_warning.assert_called_once()


def _fake_content(title):
    return {
        "title": title,
        "meta_description": f"Meta for {title}.",
        "intro": f"Intro for {title}.",
        "body": f"Body for {title}.",
        "faqs": [{"question": f"Why {title}?", "answer": "Because we're the best."}],
    }


def test_generate_content_builds_pages_for_checked_categories_and_services(qapp):
    form = YAMLForm()
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Business Category"].setText("Plumbing")
    form.silo_seed_input.setText("garage door services")

    with patch("main.fetch_clusters", return_value=[_cluster("Garage Door Repair")]):
        form._run_silo_category_research()
    _check_row(form.silo_categories_table, 0)
    with patch("main.fetch_clusters", return_value=[_cluster("Spring Replacement")]):
        form._run_silo_service_research()
    _check_row(form.silo_services_table, 0)

    with patch("main.silo_content_is_available", return_value=True), patch(
        "main.generate_service_page_content", side_effect=lambda **kwargs: _fake_content(kwargs["page_topic"])
    ) as mock_generate:
        form._generate_silo_content()

    assert len(form.silo_pages) == 2
    category_page = next(p for p in form.silo_pages if p["kind"] == "category")
    service_page = next(p for p in form.silo_pages if p["kind"] == "service")
    assert category_page["title"] == "Garage Door Repair"
    assert category_page["children"] == ["Spring Replacement"]
    assert category_page["content"]["title"] == "Garage Door Repair"
    assert service_page["title"] == "Spring Replacement"
    assert service_page["category"] == "Garage Door Repair"
    assert service_page["content"]["title"] == "Spring Replacement"
    assert mock_generate.call_count == 2


def test_generate_content_continues_after_one_page_fails(qapp):
    form = YAMLForm()
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Category A"), _cluster("Category B")]):
        form._run_silo_category_research()
    _check_row(form.silo_categories_table, 0)
    _check_row(form.silo_categories_table, 1)

    def fake_generate(**kwargs):
        if kwargs["page_topic"] == "Category A":
            raise SiloContentError("boom")
        return _fake_content(kwargs["page_topic"])

    with patch("main.silo_content_is_available", return_value=True), patch(
        "main.generate_service_page_content", side_effect=fake_generate
    ), patch.object(QMessageBox, "warning") as mock_warning:
        form._generate_silo_content()

    assert len(form.silo_pages) == 2
    failed = next(p for p in form.silo_pages if p["title"] == "Category A")
    succeeded = next(p for p in form.silo_pages if p["title"] == "Category B")
    assert failed["content"] is None
    assert failed["error"] == "boom"
    assert succeeded["content"] is not None
    mock_warning.assert_called_once()


def test_export_silo_requires_generated_content(qapp):
    form = YAMLForm()
    with patch.object(QMessageBox, "warning") as mock_warning:
        form._export_silo()
    mock_warning.assert_called_once()


def test_export_silo_writes_category_and_nested_service_markdown_files(qapp, tmp_path):
    form = YAMLForm()
    form.silo_pages = [
        {
            "kind": "category",
            "category": "Garage Door Repair",
            "title": "Garage Door Repair",
            "children": ["Spring Replacement"],
            "content": _fake_content("Garage Door Repair"),
            "error": None,
        },
        {
            "kind": "service",
            "category": "Garage Door Repair",
            "title": "Spring Replacement",
            "children": [],
            "content": _fake_content("Spring Replacement"),
            "error": None,
        },
    ]

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(tmp_path)):
        form._export_silo()

    category_file = tmp_path / "garage-door-repair.md"
    service_file = tmp_path / "garage-door-repair" / "spring-replacement.md"
    index_file = tmp_path / "_silo_structure.md"
    assert category_file.exists()
    assert service_file.exists()
    assert index_file.exists()

    category_text = category_file.read_text(encoding="utf-8")
    assert category_text.startswith("# Garage Door Repair")
    assert "> Meta for Garage Door Repair." in category_text
    assert "## FAQ" in category_text
    assert "Why Garage Door Repair?" in category_text

    index_text = index_file.read_text(encoding="utf-8")
    assert "garage-door-repair.md" in index_text
    assert "garage-door-repair/spring-replacement.md" in index_text


def test_export_silo_skips_pages_that_failed_generation(qapp, tmp_path):
    form = YAMLForm()
    form.silo_pages = [
        {
            "kind": "category",
            "category": "Garage Door Repair",
            "title": "Garage Door Repair",
            "children": [],
            "content": None,
            "error": "boom",
        }
    ]

    with patch.object(QMessageBox, "warning") as mock_warning:
        form._export_silo()

    mock_warning.assert_called_once()


def test_export_silo_cancelled_folder_picker_does_nothing(qapp, tmp_path):
    form = YAMLForm()
    form.silo_pages = [
        {
            "kind": "category",
            "category": "Garage Door Repair",
            "title": "Garage Door Repair",
            "children": [],
            "content": _fake_content("Garage Door Repair"),
            "error": None,
        }
    ]

    with patch.object(QFileDialog, "getExistingDirectory", return_value=""):
        form._export_silo()

    assert list(tmp_path.iterdir()) == []
