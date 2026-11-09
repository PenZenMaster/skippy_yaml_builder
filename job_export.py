"""
Module/Script Name: job_export.py
Path: E:\\projects\\skippy_yaml_builder\\job_export.py

Description:
Builds rr_yacss_factory job dicts (CloudStackJob / ListicleJob /
MasspageJob) from a client-intake data dict -- the same dict the YAML
Builder saves as a client .yaml file (same field names, e.g.
"* Client Name", "YACSS Tiers (tier:pages, one per line)"). No Qt: the
GUI's Export Job JSON gathers its widgets into that dict and calls
build_job(); a headless caller can yaml.safe_load() a saved client file
and call the same function, so both paths produce the same job.

Each builder returns (job, warnings). Warnings are advisory -- the
authoritative validation is rr_yacss_factory's own job schema
(src/jobs/schema.ts) when the file is used, not anything duplicated here.
This module never touches the network; the advisory image-size check
stays with the caller (see image_check_items).

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-11-05

Last Modified Date:
2026-11-09

Comments:
- v1.00 Moved out of main.py's YAMLForm (_build_cloud_stack_job,
  _build_listicle_job, _build_masspage_job and their helpers) unchanged in
  behavior, so the job export can run without the GUI.
- v1.01 Content Image URLs longer than the stack's page count are cut to
  one image per page (select_content_images), starting at the job's
  batch_position so the stacks of one batch use different images. Every
  per-page image costs one YACSS upload (300 per 24h), so unused extras
  are no longer sent. Replaces the "extra images will never be used"
  warning.
"""

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any

FormData = Mapping[str, Any]

BUILD_TYPE_FIELD = "YACSS Build Type"
BUILD_TYPES = ("Diagram", "Listicle", "Masspage_Silo_Local")

TIERS_FIELD = "YACSS Tiers (tier:pages, one per line)"
TIER_ACCOUNTS_FIELD = "YACSS Diagram Tier Cloud Account IDs"
FLAT_ACCOUNTS_FIELD = "YACSS Cloud Account IDs (comma separated)"
FAQ_FIELD = "FAQ Questions & Answers"
LEGACY_FAQ_FIELD = "FAQ Questions (one per line)"


# --------------------------------------------------------------------------
# Reading values out of the data dict. A dict built from the live form holds
# plain strings (and lists for the "one per line" fields); a dict loaded from
# a saved YAML file can also hold ints (an unquoted ZIP), None (an empty
# key) or a list where a string is expected, so every read goes through
# these two helpers.
# --------------------------------------------------------------------------


def _text(data: FormData, key: str) -> str:
    """The field as a string: "" when missing/None, list items joined by
    newlines, anything else str()-ed. Not stripped -- callers strip where
    the GUI code they replace did."""
    value = data.get(key)
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return str(value)


def _lines(data: FormData, key: str) -> list[str]:
    """A "one per line" field as its non-blank, stripped lines, whether
    it is stored as a list or as one multi-line string."""
    return [line.strip() for line in _text(data, key).splitlines() if line.strip()]


# --------------------------------------------------------------------------
# Pure helpers (formerly YAMLForm static methods; main.py still exposes them
# under their old names).
# --------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Mirrors rr_yacss_factory's src/jobs/loader.ts slugify() closely
    enough for a readable job_id: lowercase, non-alphanumerics become
    a single hyphen, no leading/trailing hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    return slug.strip("-")


def content_to_html_paragraphs(text: str) -> str:
    """Wraps blank-line-separated paragraphs (the format "YACSS
    Diagram Content" is written in -- see that field's setup comment
    and generate_diagram_content's prompt in ai_content_generator.py)
    in <p> tags, e.g. "First.\\n\\nSecond." -> "<p>First.</p><p>Second.
    </p>". A bare "\\n\\n"-separated string collapses to whitespace in
    HTML and renders as one contiguous block once YACSS publishes it
    -- confirmed live. A single newline inside a paragraph is treated
    as a soft wrap, not a break, and joined with a space."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "".join(
        f"<p>{' '.join(paragraph.split())}</p>"
        for paragraph in paragraphs
        if paragraph.strip()
    )


def extract_google_maps_embed_url(embed_code: str) -> tuple[str, str | None]:
    """Extracts the real src="..." URL from a pasted Google Maps
    "Embed a map" <iframe> snippet ("Google Maps Embed Code" field,
    Content tab) -- YACSS's real mymapsurl build field (live GET
    /build-fields, "Embed" group -- present for diagram/masspage only,
    confirmed absent for listicle/local_listicle) wants the bare URL,
    not the surrounding <iframe width=/height=/style=/...> HTML.
    Confirmed live 2026-09-14 against a real Google Maps Share ->
    Embed a map -> Copy HTML capture (Salvo Metal Works): the URL is
    standard Google "Embed a map" pb= format, not a Google "My Maps"
    mid= URL -- that field's own build-fields label uses a misleading
    mid= example. Returns (url, None) on a clean match, or ("",
    warning) when the field has content that isn't a real <iframe
    src="..."> snippet (e.g. a bare link was pasted instead)."""
    text = embed_code.strip()
    if not text:
        return "", None
    match = re.search(r'src="([^"]+)"', text)
    if not match:
        return (
            "",
            "Google Maps Embed Code doesn't look like a pasted <iframe> tag (no "
            'src="..." found) -- use Google Maps\' Share -> Embed a map -> Copy '
            "HTML, and paste the full HTML, not just a link",
        )
    return match.group(1), None


def compute_cloud_stack_total_pages(tier0_pages: int, tier_pages: Iterable[int]) -> int:
    """Exact port of rr_yacss_factory's computeCloudStackTotalPages()
    (src/jobs/schema.ts v1.11) -- tiers multiply, not add, and
    tier0_pages is the multiplicative root of the whole pyramid, not
    just an additive starting point. tier_pages is an iterable of each
    tier's own page count, in tier order.

    Corrected 2026-08-26: originally seeded running_product at 1
    instead of tier0_pages, only ever confirmed live against a
    tier0_pages=1 example where that bug is invisible (multiplying by
    1 vs. not multiplying by it at all give the same result). A real
    tier0_pages=3 Salvo Metal Works build (id 127455) confirmed live
    that YACSS's real per-tier totals include tier0_pages in the
    running product -- see rr_yacss_factory's schema.ts for the full
    trail."""
    running_product = tier0_pages
    total = tier0_pages
    for pages in tier_pages:
        running_product *= pages
        total += running_product
    return total


def parse_tier_lines(text: str) -> list[tuple[int, str | None]]:
    """Parses 'YACSS Tiers (tier:pages, one per line)' text into
    [(tier_number, pages_or_None), ...] in order, skipping blank lines
    (a real saved YAML file can fold this multi-line value with blank
    lines between entries -- see save_yaml/load_yaml's plain-scalar
    handling) and any line whose tier number isn't a plain integer."""
    result: list[tuple[int, str | None]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        tier_part, _, pages_part = line.partition(":")
        try:
            tier_num = int(tier_part.strip())
        except ValueError:
            continue
        pages_part = pages_part.strip()
        result.append((tier_num, pages_part if pages_part else None))
    return result


def tier_page_count(pages: str | None) -> int:
    """A parsed tier's page count as an int, 0 when blank or not a plain
    non-negative whole number -- the same result the GUI's tier table
    gives (its row label only carries a "(N pages)" count it can read
    back for a plain number)."""
    if pages and re.fullmatch(r"\d+", pages):
        return int(pages)
    return 0


def tier_account_ids(data: FormData) -> dict[int, str]:
    """Each tier's comma-separated cloud account ids from "YACSS Diagram
    Tier Cloud Account IDs" ([{tier, cloud_account_ids}, ...]). A file
    saved before that field existed has no per-tier rows but may have the
    older flat "YACSS Cloud Account IDs" value; then every tier in
    "YACSS Tiers" gets that flat value, exactly as the GUI's load_yaml
    pre-fills its tier table (_load_diagram_tier_accounts)."""
    by_tier: dict[int, str] = {}
    rows = data.get(TIER_ACCOUNTS_FIELD) or []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, Mapping) and "tier" in row:
                by_tier[row["tier"]] = str(row.get("cloud_account_ids", "") or "")
    if by_tier:
        return by_tier
    legacy = _text(data, FLAT_ACCOUNTS_FIELD).strip()
    if not legacy:
        return {}
    return {
        tier_num: legacy for tier_num, _ in parse_tier_lines(_text(data, TIERS_FIELD))
    }


def flat_account_ids(data: FormData) -> list[str]:
    """The flat "YACSS Cloud Account IDs" field (Listicle/Masspage) as a
    de-duplicated list, order kept."""
    ids: list[str] = []
    for value in _text(data, FLAT_ACCOUNTS_FIELD).split(","):
        value = value.strip()
        if value and value not in ids:
            ids.append(value)
    return ids


def faq_rows(data: FormData) -> list[dict[str, str]]:
    """FAQs as [{question, answer}], skipping rows with no question.
    Accepts the current "FAQ Questions & Answers" list of dicts and, like
    the GUI's _load_faq_rows, the older flat question list or newline
    string saved under "FAQ Questions (one per line)"."""
    rows = data.get(FAQ_FIELD)
    if rows is None:
        legacy = data.get(LEGACY_FAQ_FIELD)
        if isinstance(legacy, list):
            rows = [{"question": str(q), "answer": ""} for q in legacy]
        elif isinstance(legacy, str):
            rows = [{"question": line, "answer": ""} for line in legacy.splitlines()]
        else:
            rows = []
    result = []
    for row in rows if isinstance(rows, list) else []:
        if isinstance(row, Mapping):
            question = str(row.get("question", "") or "").strip()
            answer = str(row.get("answer", "") or "").strip()
        else:
            question, answer = str(row).strip(), ""
        if question:
            result.append({"question": question, "answer": answer})
    return result


def resolve_job_id(data: FormData, default: str) -> str:
    """ "YACSS Job ID (override)" when filled in, else the auto-derived
    default -- shared by all three builders."""
    return _text(data, "YACSS Job ID (override)").strip() or default


def _maps_url(data: FormData, job: dict[str, Any], warnings: list[str]) -> None:
    maps_url, maps_warning = extract_google_maps_embed_url(
        _text(data, "Google Maps Embed Code")
    )
    if maps_warning:
        warnings.append(maps_warning)
    elif maps_url:
        job.setdefault("extra_fields", {})["mymapsurl"] = maps_url


# --------------------------------------------------------------------------
# Job builders
# --------------------------------------------------------------------------


def select_content_images(
    urls: list[str], pages: int, batch_position: int = 0
) -> list[str]:
    """The per-page content images for one stack: one image per page,
    taken in order from the client's list starting at
    batch_position * pages and wrapping round at the end, so stack 0 of a
    batch gets images 1..pages, stack 1 the next `pages`, and so on. A list
    no longer than the page count (or a stack with no pages) is returned
    unchanged -- rr_yacss_factory already repeats a short list across the
    pages."""
    if pages < 1 or len(urls) <= pages:
        return list(urls)
    start = (max(batch_position, 0) * pages) % len(urls)
    return [urls[(start + i) % len(urls)] for i in range(pages)]


def build_cloud_stack_job(
    data: FormData, batch_position: int = 0
) -> tuple[dict[str, Any], list[str]]:
    """Builds a rr_yacss_factory CloudStackJob dict, plus a list of
    human-readable warnings for anything that looks incomplete or
    inconsistent (blank required fields, a page_titles count that doesn't
    match the real multiplicative total, a tier with no cloud accounts
    assigned). FAQs are sent via job["faqs"] (a plain {question, answer}
    list) matching CloudStackJob.faqs directly -- an earlier version sent
    them through extra_fields as a bracketed faq_question[]/faq_answer[]
    pair, which silently renders ZERO FAQs on a live page.
    Logo URL maps to CloudStackJob.logo_image_url. Content Image URLs (one
    per line) maps to CloudStackJob.content_image_urls -- a per-page image
    list rr_yacss_factory uploads and cycles across pages (1, 2, 3, 1, ...);
    it is rejected there together with Content Image URL, which is flagged
    as an advisory warning. Hero Image URL/Content Image URL map straight
    to CloudStackJob.hero_image_url/content_image_url.
    company["name"] defaults to "* Client Name" but prefers "Legal /
    Company Name" when filled in (Kilday Baxter's legal entity name
    differs from its brand name).
    job["keyword"] is YACSS Bucket Keyword run through slugify(), since it
    becomes the real cloud bucket name and only lowercase letters, digits
    and hyphens are safe there (underscores broke real bucket creation on
    Backblaze/Azure/AWS for Salvo Metal Works, 2026-08-26). The saved
    client YAML keeps whatever human-readable text was typed.
    With YACSS Pinned Bucket set, the keyword names no bucket and is
    exported as typed; the job instead gets `cloud_buckets` (that bucket
    on every tier cloud account) and `directory` (YACSS Stack Folder, or
    the slugified keyword when blank).
    Content Image URLs longer than the page count are cut to one image per
    page by select_content_images, starting at `batch_position` (the
    stack's place in a batch; 0 for a single export)."""
    warnings: list[str] = []

    def require(value: str, label: str) -> None:
        if not value.strip():
            warnings.append(f"{label} is blank")

    client_name = _text(data, "* Client Name")
    keyword = _text(data, "YACSS Bucket Keyword")
    template = _text(data, "YACSS Template")
    landing_url = _text(data, "* Website")
    target_link_text_before = _text(data, "YACSS Text Before Target Link")
    target_link_text = _text(data, "YACSS Text Of Target Link")
    target_link_text_after = _text(data, "YACSS Text After Target Link")
    tier0_pages_raw = _text(data, "YACSS Tier0 Pages")

    pinned_bucket = _text(data, "YACSS Pinned Bucket").strip()
    stack_folder = _text(data, "YACSS Stack Folder").strip()

    require(client_name, "* Client Name")
    require(keyword, "YACSS Bucket Keyword")
    bucket_keyword = slugify(keyword)
    if pinned_bucket:
        # Pinned: the keyword names no bucket, so only the folder
        # fallback needs it to slugify into something.
        if not stack_folder and keyword.strip() and not bucket_keyword:
            warnings.append(
                f"YACSS Stack Folder is blank and YACSS Bucket Keyword "
                f"{keyword.strip()!r} has no letters or digits to derive "
                "a folder from -- fill in YACSS Stack Folder"
            )
    elif stack_folder:
        warnings.append(
            "YACSS Stack Folder is set but YACSS Pinned Bucket is blank -- "
            "the folder is ignored (it only applies to a pinned bucket)"
        )
    if not pinned_bucket and keyword.strip() and not bucket_keyword:
        warnings.append(
            f"YACSS Bucket Keyword {keyword.strip()!r} has no letters or "
            "digits once slugified, so it cannot become a real cloud "
            "bucket name -- add some"
        )
    require(template, "YACSS Template")
    require(landing_url, "* Website")
    require(target_link_text_before, "YACSS Text Before Target Link")
    require(target_link_text, "YACSS Text Of Target Link")
    require(target_link_text_after, "YACSS Text After Target Link")

    try:
        tier0_pages = int(tier0_pages_raw.strip() or "0")
    except ValueError:
        warnings.append(
            f"YACSS Tier0 Pages {tier0_pages_raw!r} is not a whole number -- treated as 0"
        )
        tier0_pages = 0

    ids_by_tier = tier_account_ids(data)
    tiers: list[dict[str, Any]] = []
    for tier_num, pages in parse_tier_lines(_text(data, TIERS_FIELD)):
        account_ids = [
            v.strip() for v in ids_by_tier.get(tier_num, "").split(",") if v.strip()
        ]
        if not account_ids:
            warnings.append(f"Tier {tier_num} has no Cloud Account IDs assigned")
        tiers.append(
            {
                "tier": tier_num,
                "pages": tier_page_count(pages),
                "cloud_account_ids": account_ids,
            }
        )

    page_titles = _lines(data, "YACSS Diagram Page Titles (one per line)")
    expected_total = compute_cloud_stack_total_pages(
        tier0_pages, [t["pages"] for t in tiers]
    )
    if len(page_titles) != expected_total:
        warnings.append(
            f"YACSS Diagram Page Titles has {len(page_titles)} line(s), but the "
            f"real total page count (multiplicative, not additive) is {expected_total}"
        )

    content = _text(data, "YACSS Diagram Content").strip()
    if not content:
        warnings.append("YACSS Diagram Content is blank")

    company = {
        "name": _text(data, "Legal / Company Name").strip() or client_name,
        "address": _text(data, "Street Address"),
        "city": _text(data, "City"),
        "state": _text(data, "State"),
        "zip": _text(data, "ZIP"),
        "phone": _text(data, "* Phone"),
        "email": _text(data, "Email") or _text(data, "Contact Email Address"),
    }
    for field_name in ("address", "city", "state", "zip", "phone", "email"):
        require(company[field_name], f"Company {field_name}")

    job: dict[str, Any] = {
        "job_id": resolve_job_id(data, slugify(client_name) or "cloud-stack-job"),
        "type": "cloud_stack",
        "keyword": (
            keyword.strip() if pinned_bucket else bucket_keyword or keyword.strip()
        ),
        "name": client_name,
        "template": template,
        "landing_url": landing_url,
    }
    if pinned_bucket:
        # rr_yacss_factory's schema requires a pin for every tier
        # account; the same client bucket name is used on all of them.
        pinned_account_ids: list[str] = []
        for tier in tiers:
            for account_id in tier["cloud_account_ids"]:
                if account_id not in pinned_account_ids:
                    pinned_account_ids.append(account_id)
        job["cloud_buckets"] = {
            account_id: pinned_bucket for account_id in pinned_account_ids
        }
        job["directory"] = stack_folder or bucket_keyword
    job |= {
        "target_link_text_before": target_link_text_before,
        "target_link_text": target_link_text,
        "target_link_text_after": target_link_text_after,
        "company": company,
        "tier0_pages": tier0_pages,
        "tiers": tiers,
        "page_titles": page_titles,
        "content": content_to_html_paragraphs(content),
    }

    faqs = faq_rows(data)
    if faqs:
        job["faqs"] = faqs

    hero_image_url = _text(data, "Hero Image URL").strip()
    if hero_image_url:
        job["hero_image_url"] = hero_image_url
    logo_url = _text(data, "Logo URL").strip()
    if logo_url:
        job["logo_image_url"] = logo_url
    content_image_url = _text(data, "Content Image URL").strip()
    if content_image_url:
        job["content_image_url"] = content_image_url
    content_image_urls = _lines(data, "Content Image URLs (one per line)")
    if content_image_urls:
        job["content_image_urls"] = select_content_images(
            content_image_urls, expected_total, batch_position
        )
        if content_image_url:
            warnings.append(
                "Content Image URL and Content Image URLs are both filled in -- "
                "rr_yacss_factory rejects the combination; use one or the other"
            )

    # content_mode omitted entirely for the cheap/default option -- the
    # same export as before this field existed. See rr_yacss_factory's
    # CloudStackJob.content_mode (src/jobs/types.ts v1.15) for what
    # "ai_per_page" does server-side.
    if _text(data, "YACSS Content Generation Mode").startswith("AI-written"):
        job["content_mode"] = "ai_per_page"
        ai_platform = _text(data, "YACSS AI Platform").strip()
        ai_model = _text(data, "YACSS AI Model").strip()
        if ai_platform:
            job["ai_platform"] = ai_platform
        if ai_model:
            job["ai_model"] = ai_model

    _maps_url(data, job, warnings)
    return job, warnings


def build_listicle_job(data: FormData) -> tuple[dict[str, Any], list[str]]:
    """Builds a rr_yacss_factory ListicleJob dict (src/jobs/schema.ts's
    listicleJobSchema) plus advisory warnings. job.keyword is the real SEO
    topic ("YACSS Topic Keyword"); job.lsi_keyword is the EXISTING
    Diagram build's own keyword whose bucket this publishes into
    ("YACSS Bucket Keyword", relabeled for this type in the GUI -- see
    rr_yacss_factory's bucketAndDirectoryForJob()). brand/competitor_urls/
    target_urls are optional and included only when filled in; brand
    requires BOTH name and url once used (brandPlacementSchema), so a
    partial entry warns rather than sending a rejected object.
    job["name"] defaults to "* Client Name" but prefers "YACSS Listicle
    Display Title" when filled in (Royal Porta Johns' septic-maintenance
    listicles had their own display title)."""
    warnings: list[str] = []

    def require(value: str, label: str) -> None:
        if not value.strip():
            warnings.append(f"{label} is blank")

    client_name = _text(data, "* Client Name")
    display_title = _text(data, "YACSS Listicle Display Title").strip() or client_name
    topic_keyword = _text(data, "YACSS Topic Keyword")
    lsi_keyword = _text(data, "YACSS Bucket Keyword")
    template = _text(data, "YACSS Template")
    ai_platform = _text(data, "YACSS AI Platform")
    ai_model = _text(data, "YACSS AI Model")
    tone = _text(data, "YACSS Tone")
    language = _text(data, "YACSS Language")
    items_raw = _text(data, "YACSS Items Per Listicle")

    require(client_name, "* Client Name")
    require(topic_keyword, "YACSS Topic Keyword")
    require(lsi_keyword, "YACSS Bucket Keyword (target stack keyword)")
    require(template, "YACSS Template")
    require(ai_platform, "YACSS AI Platform")
    require(ai_model, "YACSS AI Model")
    require(tone, "YACSS Tone")
    require(language, "YACSS Language")

    try:
        items_per_listicle = int(items_raw.strip() or "0")
    except ValueError:
        warnings.append(
            f"YACSS Items Per Listicle {items_raw!r} is not a whole number -- treated as 0"
        )
        items_per_listicle = 0
    if items_per_listicle <= 0:
        warnings.append("YACSS Items Per Listicle must be a positive whole number")

    cloud_account_ids = flat_account_ids(data)
    if not cloud_account_ids:
        warnings.append("No YACSS Cloud Account IDs selected")

    job: dict[str, Any] = {
        # "-listicle" suffix: without it this collides with the same
        # client's cloud_stack job_id (both slugify from the same client
        # name) -- rr_yacss_factory's manifest is keyed by job_id, so a
        # real Listicle export once silently inherited a prior Diagram
        # build's stale cloud_urls under the same key. cloud_stack keeps
        # its bare slug, since real published builds already exist under
        # it. "YACSS Job ID (override)" wins outright when filled in.
        "job_id": resolve_job_id(
            data,
            (
                f"{slugify(client_name)}-listicle"
                if client_name.strip()
                else "listicle-job"
            ),
        ),
        "type": "listicle",
        "keyword": topic_keyword,
        "name": display_title,
        "template": template,
        "ai_platform": ai_platform,
        "ai_model": ai_model,
        "items_per_listicle": items_per_listicle,
        "tone": tone,
        "language": language,
        "cloud_account_ids": cloud_account_ids,
        "lsi_keyword": lsi_keyword,
    }

    brand_name = _text(data, "YACSS Brand Name").strip()
    brand_url = _text(data, "YACSS Brand URL").strip()
    brand_position_raw = _text(data, "YACSS Brand Position").strip()
    if brand_name or brand_url:
        if not brand_name:
            warnings.append(
                "YACSS Brand URL is set but YACSS Brand Name is blank -- brand omitted"
            )
        elif not brand_url:
            warnings.append(
                "YACSS Brand Name is set but YACSS Brand URL is blank -- brand omitted"
            )
        else:
            brand: dict[str, Any] = {"name": brand_name, "url": brand_url}
            if brand_position_raw:
                try:
                    position = int(brand_position_raw)
                    if position <= 0:
                        raise ValueError
                    brand["position"] = position
                except ValueError:
                    warnings.append(
                        f"YACSS Brand Position {brand_position_raw!r} is not a positive "
                        "whole number -- omitted"
                    )
            job["brand"] = brand

    competitor_urls = _lines(data, "YACSS Competitor URLs (one per line)")
    if competitor_urls:
        job["competitor_urls"] = competitor_urls

    target_urls = _lines(data, "YACSS Target URLs (one per line)")
    if target_urls:
        job["target_urls"] = target_urls

    return job, warnings


def build_masspage_job(data: FormData) -> tuple[dict[str, Any], list[str]]:
    """Builds a rr_yacss_factory MasspageJob dict (src/jobs/schema.ts's
    masspageJobSchema) plus advisory warnings -- see build_listicle_job
    for the keyword/lsi_keyword split, which applies identically here.
    page_titles/content reuse the "YACSS Diagram Page Titles"/"YACSS
    Diagram Content" fields; unlike Diagram, masspageJobSchema has no
    multiplicative-total requirement, just at least one title."""
    warnings: list[str] = []

    def require(value: str, label: str) -> None:
        if not value.strip():
            warnings.append(f"{label} is blank")

    client_name = _text(data, "* Client Name")
    topic_keyword = _text(data, "YACSS Topic Keyword")
    lsi_keyword = _text(data, "YACSS Bucket Keyword")
    template = _text(data, "YACSS Template")
    landing_url = _text(data, "* Website")
    ai_platform = _text(data, "YACSS AI Platform")

    require(client_name, "* Client Name")
    require(topic_keyword, "YACSS Topic Keyword")
    require(lsi_keyword, "YACSS Bucket Keyword (target stack keyword)")
    require(template, "YACSS Template")
    require(landing_url, "* Website")
    require(ai_platform, "YACSS AI Platform")

    page_titles = _lines(data, "YACSS Diagram Page Titles (one per line)")
    if not page_titles:
        warnings.append("YACSS Diagram Page Titles (one per line) is blank")

    content = _text(data, "YACSS Diagram Content").strip()
    if not content:
        warnings.append("YACSS Diagram Content is blank")

    cloud_account_ids = flat_account_ids(data)
    if not cloud_account_ids:
        warnings.append("No YACSS Cloud Account IDs selected")

    job: dict[str, Any] = {
        # "-masspage" suffix: same collision risk against the client's
        # cloud_stack job_id as build_listicle_job's "-listicle".
        "job_id": resolve_job_id(
            data,
            (
                f"{slugify(client_name)}-masspage"
                if client_name.strip()
                else "masspage-job"
            ),
        ),
        "type": "masspage",
        "keyword": topic_keyword,
        "name": client_name,
        "template": template,
        "landing_url": landing_url,
        "page_titles": page_titles,
        "content": content_to_html_paragraphs(content),
        "ai_platform": ai_platform,
        "cloud_account_ids": cloud_account_ids,
        "lsi_keyword": lsi_keyword,
    }

    _maps_url(data, job, warnings)
    return job, warnings


JobBuilder = Callable[[FormData], tuple[dict[str, Any], list[str]]]

JOB_BUILDERS: dict[str, JobBuilder] = {
    "Diagram": build_cloud_stack_job,
    "Listicle": build_listicle_job,
    "Masspage_Silo_Local": build_masspage_job,
}


def build_job(
    data: FormData, batch_position: int = 0
) -> tuple[dict[str, Any], list[str]]:
    """Dispatches on "YACSS Build Type". Raises ValueError when it isn't
    one of BUILD_TYPES (the GUI checks this first and shows its own
    message). `batch_position` only affects Cloud Stack jobs (which
    content images they get -- see select_content_images)."""
    build_type = _text(data, BUILD_TYPE_FIELD).strip()
    builder = JOB_BUILDERS.get(build_type)
    if builder is None:
        raise ValueError(
            f"YACSS Build Type {build_type!r} is not one of: {', '.join(BUILD_TYPES)}"
        )
    if builder is build_cloud_stack_job:
        return build_cloud_stack_job(data, batch_position)
    return builder(data)


def image_check_items(job: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(label, url) pairs for the images rr_yacss_factory pushes through
    POST /uploads/image (hero, logo, per-page content images -- all capped
    at 400KB), ready for image_size_check.check_image_sizes().
    content_image_url is deliberately skipped: YACSS gets it as a direct
    URL reference with no size cap. Only Cloud Stack jobs carry these."""
    items = []
    if job.get("hero_image_url"):
        items.append(("Hero Image URL", job["hero_image_url"]))
    if job.get("logo_image_url"):
        items.append(("Logo URL", job["logo_image_url"]))
    for i, url in enumerate(job.get("content_image_urls", []), start=1):
        items.append((f"Content Image URLs line {i}", url))
    return items
