"""
Module/Script Name: keyword_research_api.py
Path: E:\\projects\\skippy_yaml_builder\\keyword_research_api.py

Description:
DataForSEO Labs client plus keyword-clustering logic backing the new
"Keyword Research" tab's "Run Research" button: calls Related Keywords +
Search Intent for one or more seed keywords, groups the results into
volume-ranked clusters, and flags any keyword that looks like a brand/
competitor name rather than a generic search term. Reads
DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD from the sibling rr_yacss_factory
project's own .env, same pattern as yacss_api.py reads YACSS_API_TOKEN --
one set of credentials to manage, not two.

This is a direct, deliberate PORT (not a redesign) of
rr_yacss_factory/script/_prototype-keyword-cluster.ts (v1.03, committed
82ab6b9), which was live-tested through several rounds of real bug fixes
(the over-merge fallback, the brand-name filter, the core_keyword-tier
brand-check bypass, several missing generic-descriptor words, a
normalization mismatch, and the multi-seed union fix for colloquial
synonyms). Every hand-tuned word list and tiered-clustering rule here is
copied from that validated source, not reinvented -- see that file's own
header comment for the full history of what each guard actually fixes,
and the dataforseo-grammarly-content-apis / yacss-auto-content-3-real-
per-page-content project memories for the live evidence behind them.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-09-05

Last Modified Date:
2026-09-05

Comments:
- v1.00 Initial implementation, ported from
  rr_yacss_factory/script/_prototype-keyword-cluster.ts.
- v1.01 Added an off-target-location flag, independent of the brand-name
  filter: real usage against a client seed ("garage door repair" for a
  Joliet, IL client) surfaced results like "affordable garage door repair
  near california" -- LOCATION_WORDS already excuses any known state/city
  from looking like a brand name, so nothing caught these. Uses the
  client's own State/Target Cities (already collected on the form) to
  tell "local" locations from "everywhere else in the country" -- a
  keyword naming an unrelated state/city is flagged the same way a brand
  name is (excluded from the suggested title, shown for review, never
  silently dropped), not filtered out entirely. This is a change from the
  TS prototype this module was ported from (which has no client-profile
  concept at all) -- the two are now intentionally divergent here.
"""

from pathlib import Path

import requests
from dotenv import dotenv_values

API_BASE = "https://api.dataforseo.com/v3"
LOCATION_CODE = 2840  # United States
LANGUAGE_NAME = "English"
RELATED_KEYWORDS_DEPTH = 2
MAX_KEYWORDS_FOR_INTENT = 50
MAX_CLUSTERS = 12

# Sibling project layout assumed, same as yacss_api.py's RR_YACSS_FACTORY_ENV.
RR_YACSS_FACTORY_ENV = Path(__file__).resolve().parent.parent / "rr_yacss_factory" / ".env"


class KeywordResearchError(Exception):
    """Raised for any lookup failure -- missing .env/credentials,
    unreachable API, or a non-2xx/non-20000 response. Callers should catch
    this and show it to the operator rather than letting it propagate."""


def _load_config() -> tuple[str, str]:
    if not RR_YACSS_FACTORY_ENV.exists():
        raise KeywordResearchError(
            f"rr_yacss_factory .env not found at {RR_YACSS_FACTORY_ENV} -- "
            "cannot look up DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD."
        )
    values = dotenv_values(RR_YACSS_FACTORY_ENV)
    login = values.get("DATAFORSEO_LOGIN")
    password = values.get("DATAFORSEO_PASSWORD")
    if not login or not password:
        raise KeywordResearchError(
            "DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD are not both set in "
            "rr_yacss_factory's .env."
        )
    return login, password


def _post_task(path: str, body: dict) -> list:
    login, password = _load_config()
    try:
        response = requests.post(
            f"{API_BASE}{path}",
            auth=(login, password),
            json=[body],
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise KeywordResearchError(f"Could not reach DataForSEO ({path}): {exc}") from exc
    parsed = response.json()
    if parsed.get("status_code") != 20000:
        raise KeywordResearchError(
            f"DataForSEO error {parsed.get('status_code')}: {parsed.get('status_message')}"
        )
    tasks = parsed.get("tasks") or []
    task = tasks[0] if tasks else None
    if task is None or task.get("status_code") != 20000:
        status_code = task.get("status_code") if task else "unknown"
        status_message = task.get("status_message") if task else "no task returned"
        raise KeywordResearchError(f"DataForSEO task error {status_code}: {status_message}")
    return task.get("result") or []


STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "of", "in", "on", "to", "with",
    "near", "me", "how", "what", "is", "are", "vs", "best", "top", "much",
    "per",
}


def normalize_token(token: str) -> str:
    """Naive singularization so "service"/"services", "rental"/"rentals"
    etc. match as the same token -- good enough for clustering, not real
    stemming."""
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


# Generic modifier words common in local-service-business search queries
# (this project's actual client vertical -- garage doors, portables,
# chimney/roofing work, restaurants). Used only by the brand-name filter,
# not by clustering: a word here is "known generic," so its presence in a
# keyword's leftover (non-seed) tokens does NOT make that keyword look like
# a brand name. Hand-tuned, not exhaustive -- a keyword set in a different
# vertical (e.g. software, e-commerce) would need its own list added here
# or this filter will false-positive on that vertical's own generic jargon.
GENERIC_DESCRIPTORS = {
    normalize_token(word)
    for word in [
        "affordable", "cheap", "best", "top", "local", "emergency", "same",
        "day", "open", "now", "hour", "hours", "24", "cost", "price", "prices",
        "quote", "quotes", "review", "reviews", "within", "mile", "miles", "mi",
        "free", "month", "monthly", "annual", "insurance", "insured", "licensed",
        "warranty", "guarantee", "sweep", "sweeper", "technician", "specialist",
        "installer", "installation", "replacement", "maintenance", "restoration",
        "sink", "trailer", "station", "party", "luxury", "wood", "burner", "stove",
        "residential", "commercial", "overhead", "inspection", "inspect",
        "inspector", "manufacturer", "manufacturers", "operator", "operators",
        "company", "companies", "companie", "service", "services", "repairman",
        "repairmen", "repairwoman", "repairwomen", "rent", "buy", "buying",
        "week", "weekly",
    ]
}

# US state names + a modest set of major cities that showed up in the
# original TS prototype's own live test data. Not a real gazetteer -- a
# production version should use a geographic name dataset (or DataForSEO's
# own location list) instead of a hand-typed one.
LOCATION_WORDS = {
    normalize_token(word)
    for word in [
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
        "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
        "missouri", "montana", "nebraska", "nevada", "hampshire", "jersey",
        "mexico", "york", "carolina", "dakota", "ohio", "oklahoma", "oregon",
        "pennsylvania", "rhode", "island", "tennessee", "texas", "utah",
        "vermont", "virginia", "washington", "wisconsin", "wyoming",
        "los", "angeles", "chicago", "milwaukee", "houston", "phoenix",
        "philadelphia", "antonio", "diego", "dallas", "austin", "jacksonville",
    ]
}

STATE_ABBREVIATIONS = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota",
    "MS": "mississippi", "MO": "missouri", "MT": "montana", "NE": "nebraska",
    "NV": "nevada", "NH": "new hampshire", "NJ": "new jersey",
    "NM": "new mexico", "NY": "new york", "NC": "north carolina",
    "ND": "north dakota", "OH": "ohio", "OK": "oklahoma", "OR": "oregon",
    "PA": "pennsylvania", "RI": "rhode island", "SC": "south carolina",
    "SD": "south dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington",
    "WV": "west virginia", "WI": "wisconsin", "WY": "wyoming",
    "DC": "district of columbia",
}


def local_location_tokens(state: str, target_cities: list[str]) -> set[str]:
    """Builds the set of location words considered "local" for a client,
    from the State field (a 2-letter abbreviation, resolved to its full
    name -- an unrecognized value is used as-is, tokenized the same way)
    and Target Cities (one per line, typically "City, ST" -- only the part
    before the comma is used). Passed to is_off_target_location() so a
    keyword naming the client's own state/cities is never flagged."""
    tokens: set[str] = set()
    state = state.strip()
    if state:
        full_name = STATE_ABBREVIATIONS.get(state.upper(), state)
        tokens.update(significant_tokens(full_name))
    for city_line in target_cities:
        city = city_line.split(",")[0]
        tokens.update(significant_tokens(city))
    return tokens


def is_off_target_location(local_location_tokens: set[str], keyword: str) -> bool:
    """True if `keyword` names a specific location this project's
    LOCATION_WORDS list recognizes that is NOT among the client's own
    local_location_tokens -- e.g. "affordable garage door repair near
    california" for an Illinois client. Independent of
    is_possible_brand_keyword(), which deliberately excuses ANY known
    location (local or not) from looking like a brand name -- neither
    check catches what the other is for. Only fires for a location this
    project's own hand-typed LOCATION_WORDS recognizes; an unlisted small
    town on either side won't be caught, same documented gazetteer
    limitation as the brand filter."""
    found_locations = [t for t in significant_tokens(keyword) if t in LOCATION_WORDS]
    if not found_locations:
        return False
    return any(loc not in local_location_tokens for loc in found_locations)


def significant_tokens(keyword: str) -> list[str]:
    """Splits a keyword into significant (non-stopword) tokens for
    clustering."""
    return [
        token
        for token in (normalize_token(w) for w in keyword.lower().split())
        if len(token) > 2 and token not in STOPWORDS
    ]


def is_possible_brand_keyword(seed_tokens: set[str], keyword: str) -> bool:
    """Flags a keyword as a possible brand/business name: after removing
    every seed's own words (seed_tokens -- the union across all seeds
    passed in, not just one), known generic descriptors
    (GENERIC_DESCRIPTORS), and known locations (LOCATION_WORDS), any word
    still left over is plausibly a proper name rather than a generic
    search modifier -- e.g. "billy sweet chimney sweep" (seed "chimney
    cleaning service") leaves "billy"/"sweet" unexplained, so it's
    flagged; "affordable chimney sweep near me" leaves nothing unexplained
    (affordable/sweep/near/me are all known-generic), so it's not.

    This is a safety net, not a precise classifier: it will false-positive
    on genuine generic terms this project's hand-tuned word lists don't
    happen to cover (a different vertical's own jargon, an unlisted city,
    or a colloquial synonym of the seed that wasn't ALSO passed as a
    seed), and it can't detect a brand name that happens to consist
    entirely of otherwise-generic words. Flagged keywords should be
    reviewed, not silently trusted or silently discarded."""
    leftover = [
        token
        for token in significant_tokens(keyword)
        if token not in seed_tokens
        and token not in GENERIC_DESCRIPTORS
        and token not in LOCATION_WORDS
    ]
    return len(leftover) > 0


def fetch_related_keywords(seed: str) -> list[dict]:
    """Returns [{keyword, search_volume, core_keyword}, ...] from
    DataForSEO Labs' Related Keywords Live endpoint."""
    results = _post_task(
        "/dataforseo_labs/google/related_keywords/live",
        {
            "keyword": seed,
            "language_name": LANGUAGE_NAME,
            "location_code": LOCATION_CODE,
            "depth": RELATED_KEYWORDS_DEPTH,
            "limit": 200,
            "include_seed_keyword": True,
            "order_by": ["keyword_data.keyword_info.search_volume,desc"],
        },
    )
    items = (results[0].get("items") or []) if results else []
    fetched = []
    for item in items:
        keyword_data = item.get("keyword_data") or {}
        keyword = keyword_data.get("keyword") or ""
        if not keyword:
            continue
        fetched.append(
            {
                "keyword": keyword,
                "search_volume": (keyword_data.get("keyword_info") or {}).get(
                    "search_volume"
                )
                or 0,
                "core_keyword": (keyword_data.get("keyword_properties") or {}).get(
                    "core_keyword"
                ),
            }
        )
    return fetched


def merge_fetched_keywords(pools: list[list[dict]]) -> list[dict]:
    """Merges related-keyword pools from multiple seeds, deduping by
    keyword text (case-insensitive) and keeping the first-seen
    core_keyword/volume -- duplicates across seeds should carry identical
    DataForSEO data anyway."""
    by_keyword: dict[str, dict] = {}
    for pool in pools:
        for item in pool:
            key = item["keyword"].lower()
            if key not in by_keyword:
                by_keyword[key] = item
    return list(by_keyword.values())


def fetch_search_intents(keywords: list[str]) -> dict[str, str]:
    """Returns {keyword: intent_label} from DataForSEO Labs' Search Intent
    Live endpoint."""
    if not keywords:
        return {}
    results = _post_task(
        "/dataforseo_labs/google/search_intent/live",
        {"keywords": keywords, "language_code": "en"},
    )
    items = (results[0].get("items") or []) if results else []
    intent_by_keyword = {}
    for item in items:
        intent = item.get("keyword_intent") or {}
        intent_by_keyword[item["keyword"]] = intent.get("label") or "unknown"
    return intent_by_keyword


def _title_case(text: str) -> str:
    return " ".join(word[:1].upper() + word[1:] if word else word for word in text.split(" "))


def _flag_reason(kw: dict) -> str | None:
    """Human-readable reason a keyword is excluded from candidate-title
    selection, or None if it's usable. A keyword can be both a possible
    brand AND off-target location at once (independent checks) -- shown
    together rather than picking one arbitrarily."""
    reasons = []
    if kw.get("possible_brand"):
        reasons.append("possible brand")
    if kw.get("off_target_location"):
        reasons.append("off-target location")
    return " + ".join(reasons) if reasons else None


def _is_usable(kw: dict) -> bool:
    return not kw.get("possible_brand") and not kw.get("off_target_location")


def _make_cluster(
    seed_tokens: set[str],
    local_location_tokens: set[str],
    label: str,
    members: list[dict],
    candidate_title_source: str | None = None,
) -> dict:
    sorted_members = sorted(members, key=lambda m: m["search_volume"], reverse=True)
    total_search_volume = sum(m["search_volume"] for m in sorted_members)

    # A core_keyword override (DataForSEO's own synonym-clustering text) is
    # NOT automatically trusted -- it can itself be a brand name or an
    # off-target location (e.g. a core_keyword of "lowes garage door
    # repair", or one naming a state that isn't the client's own), so it
    # goes through the same checks as any heuristic-picked title before
    # being used.
    if (
        candidate_title_source is not None
        and not is_possible_brand_keyword(seed_tokens, candidate_title_source)
        and not is_off_target_location(local_location_tokens, candidate_title_source)
    ):
        return {
            "label": label,
            "total_search_volume": total_search_volume,
            "candidate_page_title": _title_case(candidate_title_source),
            "candidate_page_title_flagged": False,
            "candidate_page_title_flag_reason": None,
            "keywords": sorted_members,
        }

    # Prefer the highest-volume usable member (not a possible brand, not an
    # off-target location); only fall back to a flagged one (and mark it,
    # with a reason) if every member is flagged.
    best_usable = next((m for m in sorted_members if _is_usable(m)), None)
    title_source = best_usable or sorted_members[0]
    return {
        "label": label,
        "total_search_volume": total_search_volume,
        "candidate_page_title": _title_case(title_source["keyword"]),
        "candidate_page_title_flagged": best_usable is None,
        "candidate_page_title_flag_reason": (
            None if best_usable is not None else _flag_reason(title_source)
        ),
        "keywords": sorted_members,
    }


def cluster_keywords(
    seed_tokens: set[str], local_location_tokens: set[str], keywords: list[dict]
) -> list[dict]:
    """Groups keywords in four tiers, most-trustworthy first:

    1. DataForSEO's own `core_keyword` field (its synonym-clustering
       output -- real semantic grouping, not a guess).
    2. Exact match on the "modifier" words left after stripping the seed
       keyword's own words -- keywords that differ from the seed by the
       exact same extra words are almost certainly the same sub-topic.
    3. A single shared modifier word, picked greedily by frequency, but
       ONLY when it covers a minority of what's left. Seed words are
       excluded from candidacy entirely and a token covering more than
       half of the remaining pool is skipped -- both guards exist because
       an early version of this algorithm let one generic shared word
       ("rental", "chimney") swallow most of the results into one
       meaningless bucket.
    4. Whatever's still ungrouped is surfaced as its own singleton cluster
       rather than forced into a catch-all "unclustered" bucket that
       implies a shared topic which isn't actually there.

    Deliberately dependency-free (no NLP library) -- ported unchanged from
    the validated TypeScript prototype, not a production clustering
    algorithm."""
    clusters: list[dict] = []
    remaining = list(keywords)

    def modifiers_of(kw: dict) -> list[str]:
        return [t for t in significant_tokens(kw["keyword"]) if t not in seed_tokens]

    # Tier 1: DataForSEO's own core_keyword grouping.
    by_core_keyword: dict[str, list[dict]] = {}
    for kw in keywords:
        core_keyword = kw.get("core_keyword")
        if core_keyword is None:
            continue
        by_core_keyword.setdefault(core_keyword, []).append(kw)
    for core_keyword, members in by_core_keyword.items():
        for member in members:
            remaining.remove(member)
        clusters.append(_make_cluster(seed_tokens, local_location_tokens, f"core: {core_keyword}", members, core_keyword))

    # Tier 2: exact match on the full modifier-word signature.
    by_modifier_signature: dict[str, list[dict]] = {}
    for kw in remaining:
        modifiers = modifiers_of(kw)
        if not modifiers:
            continue
        signature = " ".join(sorted(set(modifiers)))
        by_modifier_signature.setdefault(signature, []).append(kw)
    for signature, members in by_modifier_signature.items():
        if len(members) < 2:
            continue
        for member in members:
            remaining.remove(member)
        clusters.append(_make_cluster(seed_tokens, local_location_tokens, f"modifiers: {signature}", members))

    # Tier 3: greedily group by one shared modifier word, capped so it can
    # only ever cover a minority of what's left.
    while len(remaining) > 1 and len(clusters) < MAX_CLUSTERS:
        token_frequency: dict[str, int] = {}
        for kw in remaining:
            for token in set(modifiers_of(kw)):
                token_frequency[token] = token_frequency.get(token, 0) + 1
        max_group_size = max(2, len(remaining) // 2)
        candidates = sorted(
            (
                (token, count)
                for token, count in token_frequency.items()
                if 2 <= count <= max_group_size
            ),
            key=lambda pair: pair[1],
            reverse=True,
        )
        if not candidates:
            break
        token = candidates[0][0]
        members = [kw for kw in remaining if token in modifiers_of(kw)]
        for member in members:
            remaining.remove(member)
        clusters.append(_make_cluster(seed_tokens, local_location_tokens, f"shared word: {token}", members))

    # Tier 4: true leftovers, each its own cluster.
    for kw in remaining:
        clusters.append(_make_cluster(seed_tokens, local_location_tokens, "singleton", [kw]))

    return sorted(clusters, key=lambda c: c["total_search_volume"], reverse=True)


def fetch_clusters(
    seeds: list[str], local_location_tokens: set[str] | None = None
) -> list[dict]:
    """Top-level entry point for the "Run Research" button: fetches
    related keywords + search intent for every seed, merges/clusters them,
    and returns volume-sorted clusters ready to display in the results
    table. `local_location_tokens` (see that function's own doc comment --
    typically built via local_location_tokens() from the client's own
    State/Target Cities) tells the off-target-location flag which
    locations are the client's own; omit/empty means every recognized
    location is treated as off-target. Raises KeywordResearchError on any
    DataForSEO failure."""
    if local_location_tokens is None:
        local_location_tokens = set()
    pools = [fetch_related_keywords(seed) for seed in seeds]
    related = merge_fetched_keywords(pools)

    seed_tokens: set[str] = set()
    for seed in seeds:
        seed_tokens.update(significant_tokens(seed))

    top_for_intent = [
        kw["keyword"]
        for kw in sorted(related, key=lambda k: k["search_volume"], reverse=True)[
            :MAX_KEYWORDS_FOR_INTENT
        ]
    ]
    intent_by_keyword = fetch_search_intents(top_for_intent)

    ranked = [
        {
            **kw,
            "intent": intent_by_keyword.get(kw["keyword"], "unknown"),
            "possible_brand": is_possible_brand_keyword(seed_tokens, kw["keyword"]),
            "off_target_location": is_off_target_location(
                local_location_tokens, kw["keyword"]
            ),
        }
        for kw in related
        if kw["keyword"] in intent_by_keyword
    ]

    return cluster_keywords(seed_tokens, local_location_tokens, ranked)
