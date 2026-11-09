import sys
from pathlib import Path

import app_paths

REPO = Path(app_paths.__file__).resolve().parent


def test_app_dir_is_the_source_folder_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert app_paths.app_dir() == REPO


def test_app_dir_is_the_exe_folder_when_frozen(monkeypatch, tmp_path):
    """A PyInstaller one-file exe unpacks to a temp folder, so __file__
    would point there; the exe's own folder is what the sibling-project
    and README paths need."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "syb.exe"))
    assert app_paths.app_dir() == tmp_path.resolve()


def test_sibling_env_paths_hang_off_the_app_folder():
    import ai_content_generator
    import stack_profile
    import yacss_api

    assert yacss_api.RR_YACSS_FACTORY_ENV == (REPO.parent / "rr_yacss_factory" / ".env")
    assert ai_content_generator.CLOUD_STACK_GENERATOR_ENV == (
        REPO.parent / "cloud-stack-generator" / ".env"
    )
    assert stack_profile.PROFILES_DIR == REPO / "stack_profiles"
