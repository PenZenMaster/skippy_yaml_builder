"""Tests for the "Generate with AI" buttons on the YACSS Build tab (YACSS
Diagram Page Titles / YACSS Diagram Content). Exercises the validation
guards and the apply-to-field methods directly rather than driving
_AIGeneratedTextDialog's exec() loop, matching this suite's existing style
of not clicking through modal dialogs (see test_diagram_tier_accounts.py).
"""

from PyQt6.QtWidgets import QMessageBox

import main
from main import YAMLForm, _AIGeneratedTextDialog


def _fill_diagram_required_fields(form):
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Business Category"].setText("Plumbing")
    form.inputs["* Target Cities (one per line)"].setPlainText("Dallas\nFort Worth")
    form.inputs["* Services (one per line)"].setPlainText("Drain Cleaning\nWater Heater Repair")
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText("emergency plumber dallas")
    form.inputs["YACSS Tier0 Pages"].setText("1")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("1:3")


def test_ai_generate_buttons_exist_on_yacss_build_tab(qapp):
    form = YAMLForm()
    # _build_field_grid adds one per AI_GENERATABLE_FIELDS entry; there is
    # no dedicated attribute name for them (they're created inline), so
    # this asserts via the mapping itself plus that the handlers exist.
    assert set(form.AI_GENERATABLE_FIELDS) == {
        "YACSS Diagram Page Titles (one per line)",
        "YACSS Diagram Content",
    }
    for handler_name in form.AI_GENERATABLE_FIELDS.values():
        assert callable(getattr(form, handler_name))


def test_generate_page_titles_warns_when_ai_unavailable(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: False)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form._generate_diagram_page_titles()

    assert len(warnings) == 1
    assert "AI Not Available" in warnings[0]


def test_generate_page_titles_warns_when_not_diagram_build_type(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form.inputs["YACSS Build Type"].setCurrentText("Listicle")
    form._generate_diagram_page_titles()

    assert len(warnings) == 1
    assert "Diagram Only" in warnings[0]


def test_generate_page_titles_warns_on_missing_business_info(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    # Client Name / Business Category / Bucket Keyword left blank.
    form._generate_diagram_page_titles()

    assert len(warnings) == 1
    assert "Missing Information" in warnings[0]


def test_generate_page_titles_names_only_the_actually_missing_field(qapp, monkeypatch):
    """Regression test for a real report: Client Name and Business
    Category were filled in on the Client Info tab, YACSS Bucket Keyword
    (a different tab) was left blank, and the warning's fixed "fill in all
    three" wording named Client Name/Business Category anyway -- reading
    as though those two weren't being read at all. The message must name
    only the field(s) that are actually blank."""
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["* Client Name"].setText("Acme Plumbing")
    form.inputs["* Business Category"].setText("Plumbing")
    # YACSS Bucket Keyword left blank -- the only real gap.
    form._generate_diagram_page_titles()

    assert len(warnings) == 1
    message = warnings[0][2]
    assert "YACSS Bucket Keyword" in message
    assert "Client Name" not in message
    assert "Business Category" not in message


def test_generate_page_titles_warns_when_expected_count_is_zero(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form.inputs["YACSS Tier0 Pages"].setText("0")
    form.inputs["YACSS Tiers (tier:pages, one per line)"].setPlainText("")
    form._generate_diagram_page_titles()

    assert len(warnings) == 1
    assert "Missing Information" in warnings[0]


def test_generate_content_warns_on_missing_business_info(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a) or None)

    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form._generate_diagram_content()

    assert len(warnings) == 1
    assert "Missing Information" in warnings[0]


def test_generate_page_titles_shows_dialog_and_applies_accepted_text(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(
        main,
        "generate_diagram_page_titles",
        lambda **kwargs: ["Title One", "Title Two", "Title Three", "Title Four"],
    )

    class _FakeDialog:
        def __init__(self, *a, **k):
            self._text = "Title One\nTitle Two\nTitle Three\nTitle Four"

        def exec(self):
            return main.QDialog.DialogCode.Accepted

        def result_text(self):
            return self._text

    monkeypatch.setattr(main, "_AIGeneratedTextDialog", _FakeDialog)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form._generate_diagram_page_titles()

    assert form.inputs["YACSS Diagram Page Titles (one per line)"].toPlainText() == (
        "Title One\nTitle Two\nTitle Three\nTitle Four"
    )


def test_generate_page_titles_does_not_apply_when_dialog_cancelled(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(
        main, "generate_diagram_page_titles", lambda **kwargs: ["Title One"]
    )

    class _FakeDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return main.QDialog.DialogCode.Rejected

        def result_text(self):
            return "should not be used"

    monkeypatch.setattr(main, "_AIGeneratedTextDialog", _FakeDialog)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form.inputs["YACSS Diagram Page Titles (one per line)"].setPlainText("Existing")
    form._generate_diagram_page_titles()

    assert form.inputs["YACSS Diagram Page Titles (one per line)"].toPlainText() == "Existing"


def test_generate_page_titles_shows_error_on_generation_failure(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)

    def boom(**kwargs):
        raise main.AiContentError("no key configured")

    monkeypatch.setattr(main, "generate_diagram_page_titles", boom)
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: errors.append(a) or None)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form._generate_diagram_page_titles()

    assert len(errors) == 1
    assert "Generation Failed" in errors[0]


def test_generate_content_shows_dialog_and_applies_accepted_text(qapp, monkeypatch):
    monkeypatch.setattr(main, "ai_content_is_available", lambda: True)
    monkeypatch.setattr(
        main,
        "generate_diagram_content",
        lambda **kwargs: "Some {spun|generated} content.",
    )

    class _FakeDialog:
        def __init__(self, *a, **k):
            self._text = "Some {spun|generated} content."

        def exec(self):
            return main.QDialog.DialogCode.Accepted

        def result_text(self):
            return self._text

    monkeypatch.setattr(main, "_AIGeneratedTextDialog", _FakeDialog)

    form = YAMLForm()
    _fill_diagram_required_fields(form)
    form._generate_diagram_content()

    assert form.inputs["YACSS Diagram Content"].toPlainText() == "Some {spun|generated} content."


def test_ai_generated_text_dialog_shows_live_count_mismatch_and_updates_on_edit(qapp):
    """Regression test for a real report: the AI returned 20 lines for a
    19-required batch, and the mismatch was only visible from the
    underlying form's own counter *after* the user had already clicked
    Accept. The preview dialog itself must show a live count against
    `required_line_count` and update it as the user edits, before Accept."""
    dialog = _AIGeneratedTextDialog(
        title="AI Generated Page Titles",
        field_name="Page Titles (3 required)",
        content="Title One\nTitle Two\nTitle Three\nTitle Four",
        regenerate_callback=lambda: None,
        required_line_count=3,
    )
    assert "4/3" in dialog.count_label.text()
    assert "did not return the exact count" in dialog.count_label.text()

    dialog.content_preview.setPlainText("Title One\nTitle Two\nTitle Three")
    assert "3/3" in dialog.count_label.text()
    assert "OK" in dialog.count_label.text()


def test_ai_generated_text_dialog_has_no_count_label_when_count_not_required(qapp):
    """YACSS Diagram Content has no exact-count requirement (unlike Page
    Titles) -- its dialog call omits required_line_count, and no count
    label should exist at all."""
    dialog = _AIGeneratedTextDialog(
        title="AI Generated Diagram Content",
        field_name="Diagram Content",
        content="Some content.",
        regenerate_callback=lambda: None,
    )
    assert dialog.count_label is None
