"""
Module/Script Name: ai_content_generator.py
Path: E:\\projects\\skippy_yaml_builder\\ai_content_generator.py

Description:
"Generate with AI" support for the YACSS Build tab's two free-form
Diagram fields -- YACSS Diagram Page Titles and YACSS Diagram Content --
which previously had to be hand-authored per client (the #1 item in
docs/projectStatus.md's "Resume From" next-session plan: "find a faster
path to building a new client's YAML config set"). Reads OPENAI_API_KEY
(and OPENAI_MODEL/OPENAI_MAX_TOKENS/OPENAI_TEMPERATURE) from the sibling
`cloud-stack-generator` project's own `.env`, which already has a real,
working key configured -- same "one key to manage, not two" reasoning as
yacss_api.py reading rr_yacss_factory's `.env` for YACSS_API_TOKEN,
rather than asking for a third copy of an OpenAI key.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-08-27

Last Modified Date:
2026-08-27

Comments:
- v1.00 Initial implementation.
"""

from pathlib import Path
from typing import Optional

from dotenv import dotenv_values

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when openai isn't installed
    OPENAI_AVAILABLE = False

# Sibling project layout assumed: both projects live directly under the
# same parent directory (e.g. E:\projects\cloud-stack-generator and
# E:\projects\skippy_yaml_builder), same assumption yacss_api.py already
# makes for rr_yacss_factory.
CLOUD_STACK_GENERATOR_ENV = (
    Path(__file__).resolve().parent.parent / "cloud-stack-generator" / ".env"
)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 2000
DEFAULT_TEMPERATURE = 0.7


class AiContentError(Exception):
    """Raised for any generation failure -- missing/unreadable .env, no
    API key configured, the openai package not installed, or the API call
    itself failing. Callers should catch this and let the user fall back
    to typing the field by hand rather than letting it propagate into the
    UI as an unhandled exception."""


def _load_config() -> dict:
    if not CLOUD_STACK_GENERATOR_ENV.exists():
        return {}
    return dotenv_values(CLOUD_STACK_GENERATOR_ENV)


def _get_api_key() -> str:
    return _load_config().get("OPENAI_API_KEY", "") or ""


def _get_model() -> str:
    return _load_config().get("OPENAI_MODEL") or DEFAULT_MODEL


def _get_max_tokens(default: int) -> int:
    raw = _load_config().get("OPENAI_MAX_TOKENS")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _get_temperature() -> float:
    raw = _load_config().get("OPENAI_TEMPERATURE")
    try:
        return float(raw) if raw else DEFAULT_TEMPERATURE
    except ValueError:
        return DEFAULT_TEMPERATURE


def is_available() -> bool:
    """Whether AI generation can actually run right now -- the openai
    package is installed AND a real key is configured in
    cloud-stack-generator's .env. Callers should check this before
    offering the "Generate with AI" buttons' action and show a clear
    fallback message (point at CLOUD_STACK_GENERATOR_ENV) if False."""
    return OPENAI_AVAILABLE and bool(_get_api_key())


def _call_openai(system_message: str, prompt: str, max_tokens: int) -> str:
    if not OPENAI_AVAILABLE:
        raise AiContentError(
            "The 'openai' package is not installed in this project's venv "
            "(pip install openai)."
        )
    api_key = _get_api_key()
    if not api_key:
        raise AiContentError(
            f"No OPENAI_API_KEY found in {CLOUD_STACK_GENERATOR_ENV}. "
            "Set one there (cloud-stack-generator already uses it for its "
            "own AI content generation) to enable this feature."
        )

    client = OpenAI(api_key=api_key)
    try:
        response = client.chat.completions.create(
            model=_get_model(),
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=_get_temperature(),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced as one clear error type
        raise AiContentError(f"OpenAI API call failed: {exc}") from exc

    content = response.choices[0].message.content if response.choices else None
    if not content or not content.strip():
        raise AiContentError("OpenAI returned an empty response.")
    return content.strip()


def _format_list(items: list, fallback: str) -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    return ", ".join(cleaned) if cleaned else fallback


def generate_diagram_page_titles(
    business_name: str,
    business_category: str,
    target_keyword: str,
    target_cities: list,
    services: list,
    title_count: int,
) -> list:
    """Generates exactly `title_count` page titles for a Diagram
    (cloud_stack) build's YACSS Diagram Page Titles field -- one per line,
    the first being the target/money page, the rest distinct supporting
    subpage angles. `title_count` should come from
    YAMLForm._compute_cloud_stack_total_pages(), the same real
    multiplicative total YACSS itself requires (confirmed live in
    rr_yacss_factory: the line count must exactly equal it), so the
    generated batch drops straight in without a manual recount.

    Returns the parsed list of titles (may not be exactly title_count if
    the model didn't comply -- callers should show the count to the user
    before accepting, not assume it's exact).

    Raises:
        AiContentError: on any failure to reach/parse the API response.
    """
    if title_count < 1:
        raise AiContentError(
            "title_count must be at least 1 -- fill in YACSS Tier0 Pages "
            "and YACSS Tiers first so the real required page count is known."
        )

    cities_text = _format_list(target_cities, "the business's general service area")
    services_text = _format_list(services, "its core services")

    prompt = f"""Generate exactly {title_count} unique, SEO-friendly page titles for a
"{target_keyword}" themed micro-site supporting {business_name}, a
{business_category} business.

CONTEXT:
- Primary theme/keyword: {target_keyword}
- Service area: {cities_text}
- Services/products: {services_text}

REQUIREMENTS:
1. Exactly {title_count} titles, one per line, no numbering, no quotes, no bullet points.
2. The FIRST title is the target/money page -- it should read like a homepage
   title built around "{target_keyword}".
3. Every other title is a distinct supporting subpage angle (a specific
   service, city, benefit, or use case) -- never repeat the same topic twice.
4. Each title is 40-70 characters, natural and clickable, not keyword-stuffed.
5. Do not put the business name in every title -- vary it naturally.

OUTPUT FORMAT:
Return ONLY the {title_count} titles, one per line. No preamble, no
explanations, no blank lines between titles."""

    content = _call_openai(
        system_message=(
            "You are an SEO copywriter who writes concise, natural page "
            "titles for local-business supporting websites."
        ),
        prompt=prompt,
        max_tokens=max(500, title_count * 40),
    )
    return [line.strip() for line in content.splitlines() if line.strip()]


def generate_diagram_content(
    business_name: str,
    business_category: str,
    target_keyword: str,
    target_cities: list,
    services: list,
    city: str = "",
    state: str = "",
) -> str:
    """Generates the free-form paragraph content for a Diagram
    (cloud_stack) build's YACSS Diagram Content field -- YACSS's cheap
    "spin content1" mode (auto_content: "2", per rr_yacss_factory's
    cloudStackJobToBuildPayload) spins whatever spintax this contains, so
    the prompt asks for real {option1|option2|option3} spintax groups
    throughout, matching the style of every real client content field
    already written by hand for rr_yacss_factory (e.g. its Salvo Metal
    Works job file).

    Raises:
        AiContentError: on any failure to reach/parse the API response.
    """
    cities_text = _format_list(target_cities, "its general service area")
    services_text = _format_list(services, "its core services")
    location = ", ".join(part for part in (city, state) if part.strip())

    prompt = f"""Write body content for a "{target_keyword}" supporting page for
{business_name}, a {business_category} business{f" based in {location}" if location else ""}
serving {cities_text}.

Services/products to reference naturally: {services_text}.

REQUIREMENTS:
1. 3-5 paragraphs, professional and specific -- no generic filler.
2. Write using SPINTAX syntax so this single field can auto-spin unique
   variations per page: wrap 2-3 natural word/phrase alternatives in curly
   braces separated by pipes, e.g.
   "{{specializes in|is a leader in|has built its reputation on}}". Use
   spintax generously -- most sentences should contain at least one
   {{a|b|c}} group.
3. Naturally mention the service area and the services/products listed above.
4. Plain paragraph text only -- no markdown, no HTML, no headings. Separate
   paragraphs with a blank line.
5. Do not include a title or heading -- body text only.

OUTPUT FORMAT:
Return ONLY the content. No preamble, no explanations."""

    return _call_openai(
        system_message=(
            "You are a professional SEO copywriter who writes spun "
            "(spintax) web copy for local-business supporting websites."
        ),
        prompt=prompt,
        max_tokens=_get_max_tokens(DEFAULT_MAX_TOKENS),
    )
