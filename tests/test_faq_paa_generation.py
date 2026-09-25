"""Tests for the FAQ tab's "Generate FAQs from People Also Ask" button --
delegates to keyword_research_api.fetch_people_also_ask (patched at
main.fetch_people_also_ask, same pattern test_keyword_research.py uses for
main.fetch_clusters) for the questions and ai_content_generator.
generate_faq_answers (patched at main.generate_faq_answers, same pattern
test_ai_generate_buttons.py uses) for the answers. No real DataForSEO/
OpenAI calls."""

from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

import main
from keyword_research_api import MAX_PAA_QUESTIONS, KeywordResearchError
from main import YAMLForm


def _fill_seed(form, keyword="garage door repair"):
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText(keyword)


def test_faq_paa_count_spinbox_is_capped_at_the_feature_maximum(qapp):
    form = YAMLForm()
    assert form.faq_paa_count_spinbox.minimum() == 1
    assert form.faq_paa_count_spinbox.maximum() == MAX_PAA_QUESTIONS == 10


def test_generate_faq_from_paa_warns_when_no_seed_keyword(qapp):
    form = YAMLForm()
    with patch.object(QMessageBox, "warning") as mock_warning:
        form._generate_faq_from_paa()
    mock_warning.assert_called_once()
    assert form.faq_table.rowCount() == 0


def test_generate_faq_from_paa_warns_when_ai_unavailable(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: False)
    with patch.object(QMessageBox, "warning") as mock_warning:
        form._generate_faq_from_paa()
    mock_warning.assert_called_once()
    assert "AI Not Available" in mock_warning.call_args.args[1]
    assert form.faq_table.rowCount() == 0


def test_generate_faq_from_paa_shows_message_on_zero_paa_results(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form, "commercial rollup door service")
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(main, "fetch_people_also_ask", lambda seed, count: [])
    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()
    mock_information.assert_called_once()
    assert "commercial rollup door service" in mock_information.call_args.args[2]
    assert form.faq_table.rowCount() == 0


def test_generate_faq_from_paa_shows_error_when_paa_lookup_fails(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)

    def boom(seed, count):
        raise KeywordResearchError("DataForSEO unreachable")

    monkeypatch.setattr(main, "fetch_people_also_ask", boom)
    with patch.object(QMessageBox, "critical") as mock_critical:
        form._generate_faq_from_paa()
    mock_critical.assert_called_once()
    assert "People Also Ask lookup failed" in mock_critical.call_args.args[1]


def test_generate_faq_from_paa_shows_error_when_answer_generation_fails(
    qapp, monkeypatch
):
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(
        main, "fetch_people_also_ask", lambda seed, count: ["How much does it cost?"]
    )

    def boom(*a, **k):
        raise main.AiContentError("no key configured")

    monkeypatch.setattr(main, "generate_faq_answers", boom)
    with patch.object(QMessageBox, "critical") as mock_critical:
        form._generate_faq_from_paa()
    mock_critical.assert_called_once()
    assert "FAQ answer generation failed" in mock_critical.call_args.args[1]
    assert form.faq_table.rowCount() == 0


def test_generate_faq_from_paa_appends_generated_rows_to_existing_faqs(
    qapp, monkeypatch
):
    form = YAMLForm()
    _fill_seed(form)
    form._add_faq_row("Existing question?", "Existing answer.")
    form.faq_paa_count_spinbox.setValue(2)

    questions = ["How much does garage door repair cost?", "How long does it take?"]
    answers = [
        "It typically costs $150-$400 depending on the issue.",
        "Most repairs take under an hour.",
    ]

    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)

    captured_calls = {}

    def fake_fetch(seed, count):
        captured_calls["seed"] = seed
        captured_calls["count"] = count
        return questions

    monkeypatch.setattr(main, "fetch_people_also_ask", fake_fetch)
    monkeypatch.setattr(main, "generate_faq_answers", lambda *a, **k: answers)

    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()

    assert captured_calls == {"seed": "garage door repair", "count": 2}
    assert form.faq_table.rowCount() == 3
    assert form.faq_table.item(0, 0).text() == "Existing question?"
    assert form.faq_table.item(1, 0).text() == questions[0]
    assert form.faq_table.item(1, 1).text() == answers[0]
    assert form.faq_table.item(2, 0).text() == questions[1]
    assert form.faq_table.item(2, 1).text() == answers[1]
    mock_information.assert_called_once()


def test_generate_faq_from_paa_adds_a_blank_answer_when_the_model_skips_a_question(
    qapp, monkeypatch
):
    """generate_faq_answers can return "" for a question it didn't answer
    (see that function's own doc comment) -- the question must still be
    added to the table (blank answer, visibly needing manual follow-up),
    not silently dropped."""
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(
        main,
        "fetch_people_also_ask",
        lambda seed, count: ["Question A?", "Question B?"],
    )
    monkeypatch.setattr(main, "generate_faq_answers", lambda *a, **k: ["Answer A.", ""])

    form._generate_faq_from_paa()

    assert form.faq_table.rowCount() == 2
    assert form.faq_table.item(1, 0).text() == "Question B?"
    assert form.faq_table.item(1, 1).text() == ""
