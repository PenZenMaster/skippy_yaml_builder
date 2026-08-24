from PyQt6.QtWidgets import QFileDialog

from main import YAMLForm, parse_faq_csv


def test_parse_faq_csv_skips_header_row():
    rows = [["Question", "Answer"], ["Q1?", "A1."], ["Q2?", "A2."]]
    assert parse_faq_csv(rows) == [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]


def test_parse_faq_csv_header_detection_is_case_insensitive():
    rows = [["QUESTION", "ANSWER"], ["Q1?", "A1."]]
    assert parse_faq_csv(rows) == [{"question": "Q1?", "answer": "A1."}]


def test_parse_faq_csv_treats_first_row_as_data_when_not_a_header():
    rows = [["How long does install take?", "2-4 hours."], ["Q2?", "A2."]]
    assert parse_faq_csv(rows) == [
        {"question": "How long does install take?", "answer": "2-4 hours."},
        {"question": "Q2?", "answer": "A2."},
    ]


def test_parse_faq_csv_skips_blank_question_rows():
    rows = [["Q1?", "A1."], ["", "orphaned answer"], ["  ", "also blank"], ["Q2?", "A2."]]
    assert parse_faq_csv(rows) == [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]


def test_parse_faq_csv_defaults_missing_answer_to_empty_string():
    rows = [["Q1?"]]
    assert parse_faq_csv(rows) == [{"question": "Q1?", "answer": ""}]


def test_parse_faq_csv_rejoins_extra_columns_into_the_answer():
    # An unquoted comma inside the answer produces extra columns rather
    # than losing data -- rejoin instead of silently dropping it.
    rows = [["Q1?", "First part", "second part"]]
    assert parse_faq_csv(rows) == [{"question": "Q1?", "answer": "First part,second part"}]


def test_parse_faq_csv_handles_empty_input():
    assert parse_faq_csv([]) == []


def test_parse_faq_csv_skips_completely_empty_rows():
    rows = [["Q1?", "A1."], [], ["Q2?", "A2."]]
    assert parse_faq_csv(rows) == [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]


def test_import_faq_csv_populates_table(qapp, tmp_path, monkeypatch):
    csv_file = tmp_path / "faqs.csv"
    csv_file.write_text(
        "Question,Answer\nHow long?,2-4 hours.\nDo you offer warranty?,\"Yes, 5 years.\"\n",
        encoding="utf-8",
    )
    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(csv_file), "")
    )

    form.import_faq_csv()

    assert form._serialize_faq_rows() == [
        {"question": "How long?", "answer": "2-4 hours."},
        {"question": "Do you offer warranty?", "answer": "Yes, 5 years."},
    ]


def test_import_faq_csv_appends_to_existing_rows(qapp, tmp_path, monkeypatch):
    csv_file = tmp_path / "faqs.csv"
    csv_file.write_text("Q2?,A2.\n", encoding="utf-8")
    form = YAMLForm()
    form._add_faq_row("Q1?", "A1.")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(csv_file), "")
    )

    form.import_faq_csv()

    assert form._serialize_faq_rows() == [
        {"question": "Q1?", "answer": "A1."},
        {"question": "Q2?", "answer": "A2."},
    ]


def test_import_faq_csv_handles_excel_bom(qapp, tmp_path, monkeypatch):
    csv_file = tmp_path / "faqs_bom.csv"
    csv_file.write_bytes("Question,Answer\r\nQ1?,A1.\r\n".encode("utf-8-sig"))
    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(csv_file), "")
    )

    form.import_faq_csv()

    assert form._serialize_faq_rows() == [{"question": "Q1?", "answer": "A1."}]


def test_import_faq_csv_does_nothing_when_dialog_is_cancelled(qapp, monkeypatch):
    form = YAMLForm()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))

    form.import_faq_csv()

    assert form.faq_table.rowCount() == 0


def test_import_faq_csv_warns_on_empty_file_without_crashing(qapp, tmp_path, monkeypatch):
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("", encoding="utf-8")
    form = YAMLForm()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(csv_file), "")
    )

    form.import_faq_csv()

    assert form.faq_table.rowCount() == 0
