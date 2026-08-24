from PyQt6.QtWidgets import QAbstractItemDelegate, QLineEdit

from main import YAMLForm


def test_enter_moves_question_to_answer_same_row(qapp):
    """QA-reported bug: pressing Enter after typing a question looked like
    it did nothing, and typing again silently overwrote the question --
    Qt's default Return handling on a table commits the edit and re-selects
    the same cell WITHOUT reopening it for editing (closeEditor is called
    with hint SubmitModelCache; confirmed live via a throwaway probe app
    that logged the real hint Qt sends, and the fix itself confirmed via a
    real windowed app + screenshots before this test was written).

    Exercises _FaqTableWidget.closeEditor directly with a substitute
    editor widget rather than simulating real keystrokes through Qt's
    live cell-editing machinery (QTest.keyClicks on a QTableWidget cell
    editor was found to crash the interpreter outright under the
    offscreen platform this suite runs under -- a real, reproducible
    native crash, not a flaky test, so that approach was abandoned)."""
    form = YAMLForm()
    form._add_faq_row("Q1?", "")
    form.faq_table.setCurrentCell(0, 0)

    form.faq_table.closeEditor(
        QLineEdit(), QAbstractItemDelegate.EndEditHint.SubmitModelCache
    )

    assert form.faq_table.currentRow() == 0
    assert form.faq_table.currentColumn() == 1
    assert form.faq_table.item(0, 0).text() == "Q1?"


def test_enter_on_last_answer_opens_a_new_row_question(qapp):
    form = YAMLForm()
    form._add_faq_row("Q1?", "A1.")
    form.faq_table.setCurrentCell(0, 1)

    form.faq_table.closeEditor(
        QLineEdit(), QAbstractItemDelegate.EndEditHint.SubmitModelCache
    )

    assert form.faq_table.rowCount() == 2
    assert form.faq_table.currentRow() == 1
    assert form.faq_table.currentColumn() == 0
    assert form._serialize_faq_rows() == [{"question": "Q1?", "answer": "A1."}]


def test_enter_on_answer_of_a_non_last_row_advances_to_next_rows_question(qapp):
    form = YAMLForm()
    form._add_faq_row("Q1?", "A1.")
    form._add_faq_row("Q2?", "")
    form.faq_table.setCurrentCell(0, 1)

    form.faq_table.closeEditor(
        QLineEdit(), QAbstractItemDelegate.EndEditHint.SubmitModelCache
    )

    # Must not insert a spurious extra row when a next row already exists.
    assert form.faq_table.rowCount() == 2
    assert form.faq_table.currentRow() == 1
    assert form.faq_table.currentColumn() == 0


def test_other_end_edit_hints_pass_through_unmodified(qapp):
    """Tab (EditNextItem) already does the right thing via Qt's own
    default handling -- only the Enter/Return hint (SubmitModelCache) is
    intercepted, so this must be a no-op for every other hint."""
    form = YAMLForm()
    form._add_faq_row("Q1?", "")
    form._add_faq_row("Q2?", "")
    form.faq_table.setCurrentCell(0, 0)

    form.faq_table.closeEditor(
        QLineEdit(), QAbstractItemDelegate.EndEditHint.EditNextItem
    )

    assert form.faq_table.rowCount() == 2
