"""Tests for the FAQ tab's "Generate FAQs from People Also Ask" button
handler in main.py. The orchestration itself (seed cleaning, PAA search
variants, AI top-up, answers) is covered in test_faq_generation.py; here
main.generate_faqs is patched, so these tests cover only what the handler owns:
gathering the form's data, the guard-rail dialogs, error dialogs, and how the
result is written into the FAQ table and summarised. No real DataForSEO/OpenAI
calls."""

from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

import main
from faq_generation import SOURCE_AI, SOURCE_GOOGLE, FaqGenerationResult, FaqItem
from keyword_research_api import MAX_PAA_QUESTIONS, KeywordResearchError
from main import YAMLForm


def _fill_seed(form, keyword="garage-door-repair-01"):
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText(keyword)


def _result(*items, requested=None, searched=("garage door repair",)):
    return FaqGenerationResult(
        requested=requested if requested is not None else len(items),
        items=list(items),
        searched_phrases=list(searched),
    )


def _patch_generate(monkeypatch, result, captured=None):
    def fake(**kwargs):
        if captured is not None:
            captured.update(kwargs)
        return result

    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(main, "generate_faqs", fake)


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


def test_generate_faq_from_paa_passes_form_data_to_the_generator(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    form.inputs["* Client Name"].setText("Acme Doors")
    form.inputs["* Business Category"].setText("Garage door service")
    form.inputs["* Target Cities (one per line)"].setPlainText(
        "Dallas, TX\n\nPlano, TX"
    )
    form.inputs["* Services (one per line)"].setPlainText("Spring Repair\nOpeners")
    form.inputs["* Website"].setText("https://acmedoors.example")
    form.inputs["Email"].setText("hi@acmedoors.example")
    form.faq_paa_count_spinbox.setValue(7)

    captured = {}
    _patch_generate(monkeypatch, _result(), captured)
    with patch.object(QMessageBox, "information"):
        form._generate_faq_from_paa()

    # The raw seed is passed through; faq_generation owns cleaning it.
    assert captured["seed_keyword"] == "garage-door-repair-01"
    assert captured["business_name"] == "Acme Doors"
    assert captured["business_category"] == "Garage door service"
    assert captured["target_cities"] == ["Dallas, TX", "Plano, TX"]
    assert captured["services"] == ["Spring Repair", "Openers"]
    assert captured["count"] == 7
    assert captured["company_facts"]["Website"] == "https://acmedoors.example"
    assert captured["company_facts"]["Email"] == "hi@acmedoors.example"


def test_generate_faq_from_paa_shows_message_when_nothing_was_generated(
    qapp, monkeypatch
):
    form = YAMLForm()
    _fill_seed(form, "commercial rollup door service")
    _patch_generate(monkeypatch, _result(requested=5))
    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()
    mock_information.assert_called_once()
    assert "commercial rollup door service" in mock_information.call_args.args[2]
    assert form.faq_table.rowCount() == 0


def test_generate_faq_from_paa_shows_error_when_paa_lookup_fails(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)

    def boom(**kwargs):
        raise KeywordResearchError("DataForSEO unreachable")

    monkeypatch.setattr(main, "generate_faqs", boom)
    with patch.object(QMessageBox, "critical") as mock_critical:
        form._generate_faq_from_paa()
    mock_critical.assert_called_once()
    assert "People Also Ask lookup failed" in mock_critical.call_args.args[1]
    assert form.isEnabled()


def test_generate_faq_from_paa_shows_error_when_ai_generation_fails(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)

    def boom(**kwargs):
        raise main.AiContentError("no key configured")

    monkeypatch.setattr(main, "generate_faqs", boom)
    with patch.object(QMessageBox, "critical") as mock_critical:
        form._generate_faq_from_paa()
    mock_critical.assert_called_once()
    assert "FAQ answer generation failed" in mock_critical.call_args.args[1]
    assert form.faq_table.rowCount() == 0
    assert form.isEnabled()


def test_generate_faq_from_paa_appends_generated_rows_to_existing_faqs(
    qapp, monkeypatch
):
    form = YAMLForm()
    _fill_seed(form)
    form._add_faq_row("Existing question?", "Existing answer.")
    _patch_generate(
        monkeypatch,
        _result(
            FaqItem("Question A?", "Answer A.", SOURCE_GOOGLE),
            FaqItem("Question B?", "Answer B.", SOURCE_GOOGLE),
        ),
    )
    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()

    assert form.faq_table.rowCount() == 3
    assert form.faq_table.item(0, 0).text() == "Existing question?"
    assert form.faq_table.item(1, 0).text() == "Question A?"
    assert form.faq_table.item(1, 1).text() == "Answer A."
    assert form.faq_table.item(2, 0).text() == "Question B?"
    assert form.faq_table.item(2, 1).text() == "Answer B."
    # Real Google questions carry no AI note.
    assert form.faq_table.item(1, 0).toolTip() == ""
    mock_information.assert_called_once()
    message = mock_information.call_args.args[2]
    assert "Added 2 of 2 requested" in message
    assert "AI-suggested question row" not in message


def test_generate_faq_from_paa_labels_ai_suggested_rows(qapp, monkeypatch):
    form = YAMLForm()
    _fill_seed(form)
    form._add_faq_row("Existing question?", "Existing answer.")
    _patch_generate(
        monkeypatch,
        _result(
            FaqItem("Google Q?", "Answer.", SOURCE_GOOGLE),
            FaqItem("AI Q1?", "Answer.", SOURCE_AI),
            FaqItem("AI Q2?", "Answer.", SOURCE_AI),
            requested=5,
        ),
    )
    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()

    assert form.faq_table.item(1, 0).toolTip() == ""
    assert "AI-suggested" in form.faq_table.item(2, 0).toolTip()
    assert "AI-suggested" in form.faq_table.item(3, 0).toolTip()
    message = mock_information.call_args.args[2]
    assert (
        "Added 3 of 5 requested FAQ(s): 1 from Google People Also Ask, 2 AI" in message
    )
    # Row numbers are 1-based table rows, counting the pre-existing row.
    assert "AI-suggested question row(s): 3, 4" in message
    assert '"garage door repair"' in message


def test_generate_faq_from_paa_adds_a_blank_answer_and_says_so(qapp, monkeypatch):
    """A question the model left unanswered must still be added (blank
    answer, visibly needing manual follow-up), not silently dropped."""
    form = YAMLForm()
    _fill_seed(form)
    _patch_generate(
        monkeypatch,
        _result(
            FaqItem("Question A?", "Answer A.", SOURCE_GOOGLE),
            FaqItem("Question B?", "", SOURCE_GOOGLE),
        ),
    )
    with patch.object(QMessageBox, "information") as mock_information:
        form._generate_faq_from_paa()

    assert form.faq_table.rowCount() == 2
    assert form.faq_table.item(1, 0).text() == "Question B?"
    assert form.faq_table.item(1, 1).text() == ""
    assert "1 answer(s) came back blank" in mock_information.call_args.args[2]
