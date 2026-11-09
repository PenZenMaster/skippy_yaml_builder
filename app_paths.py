"""
Module/Script Name: app_paths.py
Path: E:\\projects\\skippy_yaml_builder\\app_paths.py

Description:
The folder the app runs from, for every path the app derives from its own
location (README.md, stack_profiles/, and the sibling rr_yacss_factory and
cloud-stack-generator checkouts). From source that is this file's folder.
In the PyInstaller one-file exe, __file__ points into a temporary unpack
folder (%TEMP%\\_MEIxxxx), so the exe's own folder is used instead --
build_exe.bat copies the exe to the repo root as syb.exe for this reason.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-11-09

Last Modified Date:
2026-11-09

Comments:
- v1.00 Initial implementation.
"""

import sys
from pathlib import Path


def app_dir() -> Path:
    """The repo folder when run from source; the exe's folder when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
