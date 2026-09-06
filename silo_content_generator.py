"""
Module/Script Name: silo_content_generator.py
Path: E:\\projects\\skippy_yaml_builder\\silo_content_generator.py

Description:
AI content generation for the "Content Silo" tab -- real, landing-page-
depth prose (title, meta description, intro, body, optional FAQs) for a
client's services/products silo (a Services/Category page linking to
individual Service pages), built from the category/service titles the
Content Silo tab discovers via keyword_research_api.fetch_clusters().
Deliberately NOT spintax and NOT the same prompt shape as
ai_content_generator.py's Diagram-tuned generators: this content is meant
to be pasted directly into a real client-site page, not spun by YACSS's
own auto_content mechanism, so it is a genuinely different content shape,
not a reuse of the Diagram prompts. Reads OPENAI_API_KEY from the sibling
`cloud-stack-generator` project's own .env, same "one key to manage, not
two" reasoning and same self-contained-module pattern as
ai_content_generator.py/yacss_api.py/keyword_research_api.py each already
use independently (this project deliberately does not share a common
HTTP/config module across these small, standalone modules).

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-09-06

Last Modified Date:
2026-09-06

Comments:
- v1.00 Initial implementation.
"""

from pathlib import Path

from dotenv import dotenv_values

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when openai isn't installed
    OPENAI_AVAILABLE = False

# Same sibling-project layout assumption as ai_content_generator.py.
CLOUD_STACK_GENERATOR_ENV = (
    Path(__file__).resolve().parent.parent / "cloud-stack-generator" / ".env"
)

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.7

# Markers the prompt instructs the model to use, parsed back out by
# _parse_page_content(). Chosen to be simple, greppable, and unlikely to
# collide with real generated prose (all-caps, colon-terminated, own
# line) rather than asking for JSON -- a real live report from this
# project's own ai_content_generator.py history (see that file's tests)
# shows models don't always follow an exact-format instruction perfectly,
# so parsing here is deliberately forgiving (missing sections are left
# empty/omitted rather than raising).
_SECTION_MARKERS = ("TITLE:", "META:", "INTRO:", "BODY:", "FAQS:")


class AiContentError(Exception):
    """Raised for any generation failure -- missing/unreadable .env, no
    API key configured, the openai package not installed, or the API call
    itself failing, or a response with no usable TITLE/BODY content at
    all. Callers should catch this and let the user retry or skip the
    page rather than letting it propagate into the UI as an unhandled
    exception."""


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
    offering the Content Silo tab's "Generate Content" button's action
    and show a clear fallback message (point at CLOUD_STACK_GENERATOR_ENV)
    if False."""
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


def _parse_page_content(text: str) -> dict:
    """Parses the marker-delimited response format the prompt requests
    into {"title", "meta_description", "intro", "body", "faqs"}. Forgiving
    by design (see _SECTION_MARKERS' own comment): a section the model
    skipped is simply left as an empty string / empty list rather than
    raising, since a partially-useful page (e.g. missing FAQs) is still
    worth showing to the operator for manual cleanup, unlike a hard
    all-or-nothing failure. Raises AiContentError only when NEITHER a
    title nor a body could be found at all -- i.e. the response is
    unusable, not just imperfect."""
    sections: dict[str, list[str]] = {marker: [] for marker in _SECTION_MARKERS}
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        matched_marker = next(
            (m for m in _SECTION_MARKERS if stripped.upper().startswith(m)), None
        )
        if matched_marker:
            current = matched_marker
            remainder = stripped[len(matched_marker):].strip()
            if remainder:
                sections[current].append(remainder)
            continue
        if current is not None and stripped:
            sections[current].append(stripped)

    title = " ".join(sections["TITLE:"]).strip()
    meta_description = " ".join(sections["META:"]).strip()
    intro = "\n".join(sections["INTRO:"]).strip()
    body = "\n".join(sections["BODY:"]).strip()

    faqs = []
    faq_lines = sections["FAQS:"]
    pending_question = None
    for line in faq_lines:
        if line.upper().startswith("Q:"):
            pending_question = line[2:].strip()
        elif line.upper().startswith("A:") and pending_question is not None:
            faqs.append({"question": pending_question, "answer": line[2:].strip()})
            pending_question = None

    if not title and not body:
        raise AiContentError(
            "Could not parse a usable TITLE or BODY from the AI response -- "
            "the model may not have followed the requested format. Try "
            "regenerating this page."
        )

    return {
        "title": title,
        "meta_description": meta_description,
        "intro": intro,
        "body": body,
        "faqs": faqs,
    }


def generate_service_page_content(
    business_name: str,
    business_category: str,
    target_cities: list,
    page_topic: str,
    page_kind: str,
    silo_topic: str = "",
    child_topics: list = None,
    tone: str = "",
) -> dict:
    """Generates real, landing-page-depth prose for one silo page --
    either a category/silo-landing page (page_kind="category") or an
    individual service page beneath one (page_kind="service"). Unlike
    ai_content_generator.generate_diagram_content, this is plain prose
    (no spintax) meant to be pasted directly into a real page, and unlike
    that function's fixed 3-5 paragraph spec, includes a real title, meta
    description, and optional FAQs matching what an actual service page
    needs.

    `page_topic` is this page's own subject (e.g. "Garage Door Spring
    Replacement"); `silo_topic` is the parent silo's overall theme (e.g.
    "Garage Door Services") for context; `child_topics` (category pages
    only) lists the service titles beneath this category so the category
    page's intro can gesture at what the silo covers, matching the real
    services-silo structure this feature was built for.

    Returns {"title", "meta_description", "intro", "body", "faqs"} --
    "faqs" is a list of {"question", "answer"} dicts (3-5 typical, may be
    empty if the model produced none), the same shape the FAQ tab's own
    table already uses.

    Raises:
        AiContentError: on any failure to reach/parse a usable response.
    """
    cities_text = _format_list(target_cities, "its general service area")
    tone_text = tone.strip() or "professional and approachable"
    location_context = (
        f' for {business_name}, a {business_category} business serving {cities_text}'
    )

    if page_kind == "category":
        children_text = _format_list(
            child_topics or [], "a range of related services"
        )
        page_instruction = (
            f'This is a CATEGORY/silo landing page for "{page_topic}" within the '
            f'"{silo_topic}" silo. It should introduce the category as a whole and '
            f"naturally reference that it covers: {children_text}. Do not write "
            "full detail on each individual service -- that lives on their own "
            "pages; this page orients the reader and invites them to explore the "
            "category."
        )
    else:
        page_instruction = (
            f'This is an individual SERVICE page for "{page_topic}"'
            + (f', part of the "{silo_topic}" silo/category' if silo_topic else "")
            + ". Write specific, concrete detail about this exact service -- what "
            "it is, why a customer would need it, and what makes this business "
            "a credible provider of it."
        )

    prompt = f"""Write real, publish-ready landing-page copy{location_context}.

{page_instruction}

TONE: {tone_text}

REQUIREMENTS:
1. Plain prose. NO spintax, NO markdown formatting, NO placeholder text.
2. Naturally mention the business name and service area at least once.
3. The body should be 2-4 solid paragraphs -- landing-page depth, not a
   long-form article.
4. Include 3-5 relevant FAQs a real customer would ask about this specific
   topic, each with a real, specific answer (not generic filler).

OUTPUT FORMAT -- respond with EXACTLY this structure, each marker on its
own line, nothing before TITLE: or after the last FAQ answer:

TITLE: <a real, specific page title, 40-70 characters>
META: <a real meta description, 120-155 characters>
INTRO: <one short intro paragraph>
BODY:
<2-4 paragraphs of body content, blank line between paragraphs>
FAQS:
Q: <question 1>
A: <answer 1>
Q: <question 2>
A: <answer 2>
(3-5 Q/A pairs total)"""

    content = _call_openai(
        system_message=(
            "You are a professional web copywriter who writes real, "
            "publish-ready service-page content for local-business "
            "websites -- never spintax, never placeholder text."
        ),
        prompt=prompt,
        max_tokens=_get_max_tokens(DEFAULT_MAX_TOKENS),
    )
    return _parse_page_content(content)
