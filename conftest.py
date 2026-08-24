import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def no_blocking_dialogs(monkeypatch):
    """Stub QMessageBox popups so headless test runs never wait on a click."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )


@pytest.fixture(autouse=True)
def no_live_yacss_lookup(monkeypatch):
    """Every YAMLForm() construction calls out to the live YACSS API
    (GET /templates, GET /cloud-accounts) to populate the Template combo
    and Cloud Account checklist -- stubbed to return [] by default so the
    test suite stays fast, deterministic, and offline-safe. Tests that
    specifically exercise the live-population behavior should override
    this with their own monkeypatch of main.fetch_templates/
    main.fetch_cloud_accounts before constructing the form."""
    monkeypatch.setattr("main.fetch_templates", lambda: [])
    monkeypatch.setattr("main.fetch_cloud_accounts", lambda: [])
