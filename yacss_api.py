"""
Module/Script Name: yacss_api.py
Path: E:\\projects\\skippy_yaml_builder\\yacss_api.py

Description:
Minimal read-only YACSS REST API client used to populate the YAML
Builder's "YACSS Template", "YACSS Cloud Account IDs", "YACSS AI
Platform", and "YACSS AI Model" fields from live data instead of
free-text guessing. Reads the same YACSS_API_TOKEN the sibling
rr_yacss_factory CLI uses, from rr_yacss_factory's own .env -- one token
to manage, not two. Mirrors rr_yacss_factory/src/api/client.ts's confirmed
real request shapes (Bearer auth, GET /templates, GET /cloud-accounts,
GET /ai-providers, GET /ai-models envelopes) -- see that file if any
shape changes.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-08-24

Last Modified Date:
2026-08-26

Comments:
- v1.00 Initial implementation.
- v1.01 Added fetch_ai_providers/fetch_ai_models, mirroring
  rr_yacss_factory's confirmed-live listAiProviders()/listAiModels()
  (src/api/client.ts) -- GET /ai-models is a real oddity, an object keyed
  by provider rather than a flat list, with a non-array "counts" key
  alongside the per-provider arrays that must be skipped rather than
  assumed to be a model list too.
"""

from pathlib import Path

import requests
from dotenv import dotenv_values

DEFAULT_BASE_URL = "https://app.yacss.site/api/v1"

# Sibling project layout assumed: both projects live directly under the
# same parent directory (e.g. E:\projects\rr_yacss_factory and
# E:\projects\skippy_yaml_builder).
RR_YACSS_FACTORY_ENV = Path(__file__).resolve().parent.parent / "rr_yacss_factory" / ".env"


class YacssApiError(Exception):
    """Raised for any lookup failure -- missing .env/token, unreachable
    API, or a non-2xx response. Callers should catch this and fall back to
    manual entry rather than letting it propagate into the UI."""


def _load_config() -> tuple[str, str]:
    if not RR_YACSS_FACTORY_ENV.exists():
        raise YacssApiError(
            f"rr_yacss_factory .env not found at {RR_YACSS_FACTORY_ENV} -- "
            "cannot look up YACSS_API_TOKEN."
        )
    values = dotenv_values(RR_YACSS_FACTORY_ENV)
    token = values.get("YACSS_API_TOKEN")
    if not token:
        raise YacssApiError("YACSS_API_TOKEN is not set in rr_yacss_factory's .env.")
    base_url = (values.get("YACSS_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    return token, base_url


def _get(path: str) -> dict:
    token, base_url = _load_config()
    try:
        response = requests.get(
            f"{base_url}{path}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise YacssApiError(f"Could not reach YACSS API ({path}): {exc}") from exc
    return response.json()


def fetch_templates() -> list[dict]:
    """Returns [{id, name}, ...] from GET /templates."""
    data = _get("/templates")
    return [
        {"id": str(t["id"]), "name": t.get("name", str(t["id"]))}
        for t in data.get("templates", [])
    ]


def fetch_cloud_accounts() -> list[dict]:
    """Returns [{id, name, provider, client}, ...] from GET /cloud-accounts.
    `client` is '' for an unscoped (house/shared) account -- see
    rr_yacss_factory's CloudAccount.client_id/client doc comment for why
    that distinction matters (two accounts can share the same name and
    differ only by client)."""
    data = _get("/cloud-accounts")
    return [
        {
            "id": str(a["id"]),
            "name": a.get("account_name", str(a["id"])),
            "provider": a.get("provider", ""),
            "client": a.get("client") or "",
        }
        for a in data.get("accounts", [])
    ]


def fetch_ai_providers() -> list[dict]:
    """Returns [{provider, configured, model, is_default}, ...] from
    GET /ai-providers. `configured` is real per-account state (confirmed
    live: a provider with no key connected on this account comes back
    `configured: False` and fails generation with a 401 if used anyway) --
    callers should use it to warn about, not necessarily hide, an
    unconfigured provider, since it may be configured on a different
    account or get configured later."""
    data = _get("/ai-providers")
    return list(data.get("providers", []))


def fetch_ai_models() -> list[dict]:
    """Returns [{id, name, provider}, ...] flattened from GET /ai-models,
    whose real response is NOT a list -- it's an object keyed by provider
    (`{openai: [{id, label}], openrouter: [...], counts: {...}}`). The
    `counts` key (and any other non-array value) is skipped rather than
    assumed to be a model list, mirroring rr_yacss_factory's
    listAiModels()."""
    data = _get("/ai-models")
    models = []
    for provider, items in data.items():
        if not isinstance(items, list):
            continue
        for item in items:
            models.append(
                {
                    "id": str(item.get("id", "")),
                    "name": item.get("label", str(item.get("id", ""))),
                    "provider": provider,
                }
            )
    return models
