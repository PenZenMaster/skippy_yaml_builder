"""
Module/Script Name: stack_profile.py
Path: E:\\projects\\skippy_yaml_builder\\stack_profile.py

Description:
House "stack profiles": a YAML file of YACSS build settings (template,
tiers, cloud accounts per tier, AI platform/model, tone, content mode,
target-link text) applied on top of a client's saved .yaml so a Cloud
Stack can be built from just a client and a keyword. Same field names as
a client file. The profile WINS for every field it lists; the client file
supplies only client facts. The merged dict is what job_export.build_job()
takes. Headless only -- the GUI does not use this module.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-11-05

Last Modified Date:
2026-11-05

Comments:
- v1.00 Initial implementation (default profile: stack_profiles/default.yaml).
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

PROFILES_DIR = Path(__file__).resolve().parent / "stack_profiles"
DEFAULT_PROFILE = PROFILES_DIR / "default.yaml"

# Build settings a profile may set. Anything else (client facts such as
# "* Client Name", per-build content such as page titles) is rejected so a
# typo or a stray client field cannot silently override client data.
PROFILE_FIELDS = frozenset(
    {
        "YACSS Build Type",
        "YACSS Template",
        "YACSS Tier0 Pages",
        "YACSS Tiers (tier:pages, one per line)",
        "YACSS Diagram Tier Cloud Account IDs",
        "YACSS Cloud Account IDs (comma separated)",
        "YACSS AI Platform",
        "YACSS AI Model",
        "YACSS Tone",
        "YACSS Language",
        "YACSS Content Generation Mode",
        "YACSS Text Before Target Link",
        "YACSS Text Of Target Link",
        "YACSS Text After Target Link",
    }
)

KEYWORD_FIELD = "YACSS Bucket Keyword"


class StackProfileError(Exception):
    """A profile file is missing, unreadable or has fields it may not set."""


def load_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    """Reads a profile file. Raises StackProfileError when it is missing,
    is not a mapping, or names a field outside PROFILE_FIELDS."""
    path = Path(path)
    try:
        with open(path, encoding="utf-8") as f:
            profile = yaml.safe_load(f)
    except OSError as e:
        raise StackProfileError(f"Cannot read stack profile {path}: {e}") from e
    except yaml.YAMLError as e:
        raise StackProfileError(f"Stack profile {path} is not valid YAML: {e}") from e
    if not isinstance(profile, dict):
        raise StackProfileError(f"Stack profile {path} must be a mapping of fields")
    unknown = sorted(set(profile) - PROFILE_FIELDS)
    if unknown:
        raise StackProfileError(
            f"Stack profile {path} sets field(s) a profile may not set: "
            + ", ".join(repr(k) for k in unknown)
        )
    return profile


def _fill(value: Any, placeholders: Mapping[str, str]) -> Any:
    """Fills {client_name}/{keyword} in strings, recursing into lists and
    dicts. Plain replace (not str.format), so any other braces are left
    alone."""
    if isinstance(value, str):
        for name, text in placeholders.items():
            value = value.replace("{" + name + "}", text)
        return value
    if isinstance(value, list):
        return [_fill(item, placeholders) for item in value]
    if isinstance(value, dict):
        return {k: _fill(v, placeholders) for k, v in value.items()}
    return value


def apply_profile(
    client_data: Mapping[str, Any], profile: Mapping[str, Any], keyword: str
) -> dict[str, Any]:
    """A copy of client_data with every profile field overriding the
    client's own value, placeholders filled, and "YACSS Bucket Keyword" set
    to this build's keyword. client_data itself is not changed."""
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("A keyword is required to apply a stack profile")
    client_name = str(client_data.get("* Client Name") or "").strip()
    placeholders = {"client_name": client_name, "keyword": keyword}
    merged = dict(client_data)
    for field, value in profile.items():
        merged[field] = _fill(value, placeholders)
    merged[KEYWORD_FIELD] = keyword
    return merged
