"""Tests for the "Select All / Deselect All" checkbox above each of the
three generated-results tables (Keyword Research's results table, and
both Content Silo tables) -- bulk-toggles every row's own "Use?" checkbox
via YAMLForm._set_table_checkboxes. No real DataForSEO/OpenAI calls."""

from unittest.mock import patch

from PyQt6.QtCore import Qt

from main import YAMLForm


def _cluster(title, volume=100):
    return {
        "label": "test",
        "total_search_volume": volume,
        "candidate_page_title": title,
        "candidate_page_title_flagged": False,
        "candidate_page_title_flag_reason": None,
        "keywords": [{"keyword": title.lower(), "search_volume": volume}],
    }


def _row_states(table, column=0):
    return [table.item(row, column).checkState() for row in range(table.rowCount())]


def test_keyword_research_select_all_checks_every_row(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText("garage door repair")
    with patch("main.fetch_clusters", return_value=[_cluster("A"), _cluster("B"), _cluster("C")]):
        form._run_keyword_research()

    form.keyword_research_select_all_checkbox.setChecked(True)
    assert _row_states(form.keyword_research_results_table) == [Qt.CheckState.Checked] * 3

    form.keyword_research_select_all_checkbox.setChecked(False)
    assert _row_states(form.keyword_research_results_table) == [Qt.CheckState.Unchecked] * 3


def test_keyword_research_select_all_updates_the_selection_count_label(qapp):
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText("garage door repair")
    with patch("main.fetch_clusters", return_value=[_cluster("A"), _cluster("B")]):
        form._run_keyword_research()

    form.keyword_research_select_all_checkbox.setChecked(True)
    assert form.keyword_research_selection_count_label.text().startswith("2 /")


def test_keyword_research_select_all_resets_on_new_results(qapp):
    """A stale "checked" master checkbox from a prior run must not read
    as checked against a freshly (unchecked) repopulated table."""
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText("garage door repair")
    with patch("main.fetch_clusters", return_value=[_cluster("A")]):
        form._run_keyword_research()
    form.keyword_research_select_all_checkbox.setChecked(True)

    with patch("main.fetch_clusters", return_value=[_cluster("B"), _cluster("C")]):
        form._run_keyword_research()

    assert form.keyword_research_select_all_checkbox.isChecked() is False
    assert _row_states(form.keyword_research_results_table) == [Qt.CheckState.Unchecked] * 2


def test_silo_categories_select_all_checks_every_row(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Repair"), _cluster("Installation")]):
        form._run_silo_category_research()

    form.silo_categories_select_all_checkbox.setChecked(True)
    assert _row_states(form.silo_categories_table) == [Qt.CheckState.Checked] * 2

    form.silo_categories_select_all_checkbox.setChecked(False)
    assert _row_states(form.silo_categories_table) == [Qt.CheckState.Unchecked] * 2


def test_silo_services_select_all_checks_every_row(qapp):
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Repair")]):
        form._run_silo_category_research()
    form.silo_categories_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    with patch(
        "main.fetch_clusters",
        return_value=[_cluster("Spring Replacement"), _cluster("Opener Install")],
    ):
        form._run_silo_service_research()

    form.silo_services_select_all_checkbox.setChecked(True)
    assert _row_states(form.silo_services_table) == [Qt.CheckState.Checked] * 2

    form.silo_services_select_all_checkbox.setChecked(False)
    assert _row_states(form.silo_services_table) == [Qt.CheckState.Unchecked] * 2


def test_silo_services_select_all_resets_when_categories_select_all_is_untouched(qapp):
    """Re-running "Find Services for Selected Categories" clears and
    rebuilds the WHOLE services table (see that method's own doc comment)
    -- its own select-all checkbox must reset, but the categories table's
    select-all checkbox (a different table entirely) must not be touched,
    since that would silently uncheck the categories the operator is
    actively using as this run's input."""
    form = YAMLForm()
    form.silo_seed_input.setText("garage door services")
    with patch("main.fetch_clusters", return_value=[_cluster("Repair")]):
        form._run_silo_category_research()
    form.silo_categories_select_all_checkbox.setChecked(True)

    with patch("main.fetch_clusters", return_value=[_cluster("Spring Replacement")]):
        form._run_silo_service_research()

    assert form.silo_categories_select_all_checkbox.isChecked() is True
    assert form.silo_services_select_all_checkbox.isChecked() is False
