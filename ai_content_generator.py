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
2026-09-25

Comments:
- v1.00 Initial implementation.
- v1.01 Added generate_faq_answers, backing the FAQ tab's "Generate FAQs
  from People Also Ask" button: writes one real answer per real Google
  PAA question (see keyword_research_api.fetch_people_also_ask for where
  the questions themselves come from -- this module never invents
  questions, only answers them).
- v1.02 generate_diagram_content now guarantees at least
  MIN_DIAGRAM_CONTENT_WORDS (750) words of *rendered* content (spintax
  resolved to each group's shortest option, so every possible rendering
  qualifies), retrying up to three times and returning the longest draft.
  Added count_rendered_words/render_spintax_min.
"""

import re
from pathlib import Path

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

# Diagram Content length contract. The floor is on RENDERED words (spintax
# resolved), and the prompt asks for a higher target so a model that lands a
# little short of what it was asked for still clears the floor. Spintax
# alternatives inflate the raw token count well past the rendered word count,
# hence the token floor (an .env OPENAI_MAX_TOKENS below it would truncate
# the draft mid-sentence).
MIN_DIAGRAM_CONTENT_WORDS = 750
DIAGRAM_CONTENT_TARGET_WORDS = 900
DIAGRAM_CONTENT_MAX_ATTEMPTS = 3
DIAGRAM_CONTENT_MIN_MAX_TOKENS = 6000

_SPINTAX_GROUP = re.compile(r"\{([^{}]*)\}")


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


def render_spintax_min(text: str) -> str:
    """Resolves every {a|b|c} spintax group to its shortest alternative
    (by word count; ties keep the first), innermost groups first. Any
    real rendering is at least as long as this one, so a word count taken
    from it is a guaranteed lower bound. Unbalanced braces are left as-is."""

    def shortest(match):
        options = match.group(1).split("|")
        return min(options, key=lambda option: len(option.split()))

    previous = None
    while previous != text:
        previous = text
        text = _SPINTAX_GROUP.sub(shortest, text)
    return text


def count_rendered_words(text: str) -> int:
    """Word count of `text` after spintax is resolved to its shortest
    rendering (see render_spintax_min)."""
    return len(render_spintax_min(text).split())


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

    The result is at least MIN_DIAGRAM_CONTENT_WORDS words once spintax is
    resolved (count_rendered_words). A draft that falls short is retried,
    up to DIAGRAM_CONTENT_MAX_ATTEMPTS calls in total, with feedback on how
    short it was; if every attempt is short the longest draft is returned
    rather than raised, so the caller can show the real count and let the
    user regenerate or extend it by hand.

    Raises:
        AiContentError: on any failure to reach/parse the API response.
    """
    cities_text = _format_list(target_cities, "its general service area")
    services_text = _format_list(services, "its core services")
    location = ", ".join(part for part in (city, state) if part.strip())

    base_prompt = f"""Write body content for a "{target_keyword}" supporting page for
{business_name}, a {business_category} business{f" based in {location}" if location else ""}
serving {cities_text}.

Services/products to reference naturally: {services_text}.

REQUIREMENTS:
1. LENGTH: at least {MIN_DIAGRAM_CONTENT_WORDS} words once the spintax is
   resolved (each {{a|b|c}} group counts as ONE of its options -- count the
   shortest). Aim for about {DIAGRAM_CONTENT_TARGET_WORDS} words across 8-12
   paragraphs, professional and specific -- no generic filler. Cover
   different angles (services, process, benefits, service area, why choose
   this business) instead of padding or repeating sentences.
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

    system_message = (
        "You are a professional SEO copywriter who writes spun "
        "(spintax) web copy for local-business supporting websites."
    )
    max_tokens = max(
        _get_max_tokens(DEFAULT_MAX_TOKENS), DIAGRAM_CONTENT_MIN_MAX_TOKENS
    )

    best = ""
    best_words = -1
    prompt = base_prompt
    for _ in range(DIAGRAM_CONTENT_MAX_ATTEMPTS):
        draft = _call_openai(
            system_message=system_message, prompt=prompt, max_tokens=max_tokens
        )
        words = count_rendered_words(draft)
        if words > best_words:
            best, best_words = draft, words
        if words >= MIN_DIAGRAM_CONTENT_WORDS:
            break
        prompt = (
            base_prompt
            + f"\n\nIMPORTANT: a previous draft was only {words} words when "
            f"rendered, below the required minimum of "
            f"{MIN_DIAGRAM_CONTENT_WORDS}. Write a fuller, longer version of "
            f"about {DIAGRAM_CONTENT_TARGET_WORDS} words -- more paragraphs "
            "and more detail, not repetition."
        )
    return best


def generate_faq_answers(
    business_name: str,
    business_category: str,
    target_cities: list,
    services: list,
    questions: list,
) -> list:
    """Generates one answer per question in `questions`, in the same
    order, for the FAQ tab's "Generate FAQs from People Also Ask" button
    -- the questions themselves come from real Google search data (see
    keyword_research_api.fetch_people_also_ask), this only writes the
    answers.

    Returns exactly len(questions) strings; any question the model's
    response didn't number correctly comes back as "" rather than
    shifting every later answer out of alignment -- callers should treat
    a blank entry as a generation shortfall for that one question, not
    fail the whole batch.

    Raises:
        AiContentError: on any failure to reach/parse the API response.
    """
    if not questions:
        return []

    cities_text = _format_list(target_cities, "its general service area")
    services_text = _format_list(services, "its core services")
    numbered_questions = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))

    prompt = f"""Answer each of the following {len(questions)} real Google "People Also
Ask" questions, on behalf of {business_name}, a {business_category}
business serving {cities_text}. Services/products to reference when
relevant: {services_text}.

QUESTIONS:
{numbered_questions}

REQUIREMENTS:
1. Answer EVERY question, in the same order, one answer per question.
2. Each answer is 2-4 sentences, factual and specific to this business/
   industry -- no generic filler, no invented statistics or claims you
   cannot support.
3. Plain prose only -- no markdown, no headings, no bullet points.
4. Do not repeat the question text in the answer.

OUTPUT FORMAT:
Return ONLY the answers, one per line, each prefixed with its question
number and a period (e.g. "1. <answer text>"), matching the question
numbering above exactly. No preamble, no explanations."""

    content = _call_openai(
        system_message=(
            "You are a customer-facing FAQ writer for local-service "
            "businesses, answering real Google 'People Also Ask' "
            "questions accurately and concisely."
        ),
        prompt=prompt,
        max_tokens=max(500, len(questions) * 150),
    )

    answers_by_number = {}
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)[.)]\s*(.+)$", line)
        if match:
            answers_by_number[int(match.group(1))] = match.group(2).strip()
    return [answers_by_number.get(i + 1, "") for i in range(len(questions))]
