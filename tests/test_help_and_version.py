import re

import main
from main import HelpDialog, README_PATH, YAMLForm


def test_version_looks_like_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", main.__version__)


def test_window_title_includes_the_real_version(qapp):
    form = YAMLForm()
    assert main.__version__ in form.windowTitle()
    assert "v4" not in form.windowTitle()


def test_help_dialog_renders_readme_content(qapp):
    dialog = HelpDialog()
    browser = dialog.findChild(main.QTextBrowser)
    assert browser is not None
    text = browser.toPlainText()
    # Spot-check for real section headings from README.md rather than an
    # exact match, so minor wording edits to the README don't break this.
    assert "Using the app" in text
    assert "YACSS Build Type" in text


def test_help_dialog_degrades_gracefully_when_readme_is_missing(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(main, "README_PATH", tmp_path / "does-not-exist.md")
    dialog = HelpDialog()
    browser = dialog.findChild(main.QTextBrowser)
    assert "Could not load README.md" in browser.toPlainText()
