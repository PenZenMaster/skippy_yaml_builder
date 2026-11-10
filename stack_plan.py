"""
Module/Script Name: stack_plan.py
Path: E:\\projects\\skippy_yaml_builder\\stack_plan.py

Description:
Reads the "Stack Plan" tab of a client's SEO playbook workbook (.xlsx):
the list of keywords autobuild's batch mode (autobuild.py --workbook)
drafts one Cloud Stack for each. Read-only -- the workbook is never
written here (openpyxl drops some Excel features, such as conditional
formatting extensions, when it saves a workbook it did not create).

Layout (row 1 is headers, data from row 2; rows with no keyword are
skipped):

  A  Keyword                  required
  B  Landing URL              optional -- the page the stack links to
  C  Link Topic               optional -- the topic in the link sentence
  D  GCS Job ID               not read (results, filled in later)
  E  GCS Stack Link           not read
  F  Other Cloud Job ID       not read
  G  Other Cloud Stack Link   not read

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-11-09

Last Modified Date:
2026-11-09

Comments:
- v1.00 Initial implementation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SHEET = "Stack Plan"

HEADERS = (
    "Keyword",
    "Landing URL",
    "Link Topic",
    "GCS Job ID",
    "GCS Stack Link",
    "Other Cloud Job ID",
    "Other Cloud Stack Link",
)

# The columns this module reads; the rest are checked as headers only.
_READ_COLUMNS = 3


class StackPlanError(Exception):
    """The workbook or its Stack Plan tab cannot be used."""


@dataclass(frozen=True)
class PlanRow:
    row: int  # worksheet row number, for messages
    keyword: str
    landing_url: str | None = None
    link_topic: str | None = None


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def read_stack_plan(path: str | Path, sheet: str = DEFAULT_SHEET) -> list[PlanRow]:
    """The plan's rows in sheet order. Raises StackPlanError when the file
    or tab is missing, the headers in row 1 do not match HEADERS (case and
    spacing ignored), a keyword appears twice (case ignored), or there are
    no keywords."""
    from openpyxl import load_workbook

    path = Path(path)
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except Exception as e:  # openpyxl raises many types for a bad file
        raise StackPlanError(f"Cannot open workbook {path}: {e}") from e
    try:
        if sheet not in workbook.sheetnames:
            raise StackPlanError(
                f"Workbook {path.name} has no {sheet!r} tab "
                f"(tabs: {', '.join(workbook.sheetnames)})"
            )
        rows = list(workbook[sheet].iter_rows(values_only=True))
    finally:
        workbook.close()

    header = [_cell_text(v) for v in (rows[0] if rows else ())]
    header += [""] * (len(HEADERS) - len(header))
    wrong = [
        f"{chr(ord('A') + i)} should be {expected!r} (found {header[i]!r})"
        for i, expected in enumerate(HEADERS)
        if header[i].casefold() != expected.casefold()
    ]
    if wrong:
        raise StackPlanError(f"{sheet!r} tab row 1 headers: " + "; ".join(wrong))

    plan: list[PlanRow] = []
    seen: dict[str, int] = {}
    for row_number, values in enumerate(rows[1:], start=2):
        cells = [_cell_text(v) for v in values[:_READ_COLUMNS]]
        cells += [""] * (_READ_COLUMNS - len(cells))
        keyword, landing_url, link_topic = cells
        if not keyword:
            continue
        key = keyword.casefold()
        if key in seen:
            raise StackPlanError(
                f"Keyword {keyword!r} is in both row {seen[key]} and row {row_number}"
            )
        seen[key] = row_number
        plan.append(
            PlanRow(
                row=row_number,
                keyword=keyword,
                landing_url=landing_url or None,
                link_topic=link_topic or None,
            )
        )
    if not plan:
        raise StackPlanError(f"The {sheet!r} tab has no keywords (column A, row 2 on)")
    return plan
