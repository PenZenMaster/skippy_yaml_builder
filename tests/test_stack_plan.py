"""Tests for stack_plan.read_stack_plan -- the playbook's Stack Plan tab."""

import pytest
from openpyxl import Workbook

from stack_plan import HEADERS, PlanRow, StackPlanError, read_stack_plan


def _workbook(tmp_path, rows, sheet="Stack Plan", headers=HEADERS):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    wb.create_sheet("Stack Links")
    path = tmp_path / "playbook.xlsx"
    wb.save(path)
    return path


def test_reads_keywords_with_optional_landing_url_and_topic(tmp_path):
    path = _workbook(
        tmp_path,
        [
            (
                "Commercial Garage Door",
                "https://odj.example/commercial/",
                "commercial doors",
            ),
            ("garage door repair", None, None),
        ],
    )

    assert read_stack_plan(path) == [
        PlanRow(
            2,
            "Commercial Garage Door",
            "https://odj.example/commercial/",
            "commercial doors",
        ),
        PlanRow(3, "garage door repair", None, None),
    ]


def test_blank_rows_are_skipped_and_spaces_tidied(tmp_path):
    path = _workbook(
        tmp_path, [(None,), ("  garage   door  ",), ("", "https://x.example/")]
    )

    assert read_stack_plan(path) == [PlanRow(3, "garage door")]


def test_result_columns_are_not_read(tmp_path):
    path = _workbook(
        tmp_path,
        [("garage door", None, None, "job-1", "https://a", "job-2", "https://b")],
    )

    assert read_stack_plan(path) == [PlanRow(2, "garage door")]


def test_headers_are_matched_ignoring_case(tmp_path):
    path = _workbook(tmp_path, [("garage door",)], headers=[h.upper() for h in HEADERS])

    assert read_stack_plan(path)[0].keyword == "garage door"


def test_wrong_headers_are_named(tmp_path):
    headers = list(HEADERS)
    headers[1] = "Landing Page"
    path = _workbook(tmp_path, [("garage door",)], headers=headers)

    with pytest.raises(StackPlanError, match="B should be 'Landing URL'"):
        read_stack_plan(path)


def test_duplicate_keywords_are_refused(tmp_path):
    path = _workbook(tmp_path, [("Garage Door",), ("garage door",)])

    with pytest.raises(StackPlanError, match="row 2 and row 3"):
        read_stack_plan(path)


def test_missing_tab_lists_the_tabs(tmp_path):
    path = _workbook(tmp_path, [("garage door",)], sheet="Plan")

    with pytest.raises(StackPlanError, match="no 'Stack Plan' tab.*Plan"):
        read_stack_plan(path)


def test_other_tab_name(tmp_path):
    path = _workbook(tmp_path, [("garage door",)], sheet="Plan")

    assert read_stack_plan(path, sheet="Plan")[0].keyword == "garage door"


def test_no_keywords(tmp_path):
    path = _workbook(tmp_path, [])

    with pytest.raises(StackPlanError, match="no keywords"):
        read_stack_plan(path)


def test_missing_file(tmp_path):
    with pytest.raises(StackPlanError, match="Cannot open workbook"):
        read_stack_plan(tmp_path / "nope.xlsx")
