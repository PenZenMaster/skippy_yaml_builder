from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QMessageBox

from keyword_research_api import (
    cluster_keywords,
    fetch_clusters,
    is_off_target_location,
    is_possible_brand_keyword,
    local_location_tokens,
    significant_tokens,
)
from main import YAMLForm

_NO_LOCAL_TOKENS: set[str] = set()


def _kw(
    keyword,
    search_volume=0,
    core_keyword=None,
    intent="commercial",
    possible_brand=None,
    off_target_location=False,
):
    seed_tokens = {"chimney", "cleaning", "service", "garage", "door", "repair", "commercial"}
    return {
        "keyword": keyword,
        "search_volume": search_volume,
        "core_keyword": core_keyword,
        "intent": intent,
        "possible_brand": (
            is_possible_brand_keyword(seed_tokens, keyword)
            if possible_brand is None
            else possible_brand
        ),
        "off_target_location": off_target_location,
    }


def test_significant_tokens_strips_stopwords_and_normalizes_plurals():
    assert significant_tokens("cheap porta potty rentals near me") == [
        "cheap",
        "porta",
        "potty",
        "rental",
    ]


def test_is_possible_brand_keyword_flags_a_real_competitor_name():
    # Confirmed live 2026-09-05: "billy sweet chimney sweep" (seed "chimney
    # cleaning service") is a real competitor's business name.
    seed_tokens = {"chimney", "cleaning", "service"}
    assert is_possible_brand_keyword(seed_tokens, "billy sweet chimney sweep") is True


def test_is_possible_brand_keyword_does_not_flag_known_generic_modifiers():
    seed_tokens = {"chimney", "cleaning", "service"}
    assert is_possible_brand_keyword(seed_tokens, "affordable chimney sweep near me") is False
    assert is_possible_brand_keyword(seed_tokens, "residential chimney cleaning near me") is False


def test_is_possible_brand_keyword_multi_seed_fix_recognizes_colloquial_synonym():
    # Confirmed live 2026-09-05: "porta potty" is industry slang for the
    # seed's own "portable toilet" -- flagged with one seed, not flagged
    # once the colloquial term is ALSO passed as a seed.
    single_seed_tokens = {"portable", "toilet", "rental"}
    assert is_possible_brand_keyword(single_seed_tokens, "porta potty rental") is True

    multi_seed_tokens = {"portable", "toilet", "rental", "porta", "potty"}
    assert is_possible_brand_keyword(multi_seed_tokens, "porta potty rental") is False


def test_cluster_keywords_groups_by_core_keyword_first():
    seed_tokens = {"chimney", "cleaning", "service"}
    keywords = [
        _kw("chimney cleaning service", search_volume=33100, core_keyword="chimney cleaning services"),
    ]
    clusters = cluster_keywords(seed_tokens, _NO_LOCAL_TOKENS, keywords)
    assert len(clusters) == 1
    assert clusters[0]["label"] == "core: chimney cleaning services"
    assert clusters[0]["candidate_page_title"] == "Chimney Cleaning Services"
    assert clusters[0]["candidate_page_title_flagged"] is False


def test_cluster_keywords_does_not_let_one_generic_word_swallow_everything():
    # Confirmed live 2026-09-05: a naive single-shared-word fallback let
    # "chimney" swallow 13 of 20 results into one meaningless bucket. The
    # fix caps a single-word merge to a minority of what's left.
    seed_tokens = {"chimney", "cleaning", "service"}
    keywords = [
        _kw("chimney cleaning near me", search_volume=60500),
        _kw("chimney sweep near me", search_volume=200),
        _kw("chimney inspection cost", search_volume=390),
        _kw("chimney repair estimate", search_volume=110),
        _kw("chimney liner replacement", search_volume=70),
    ]
    clusters = cluster_keywords(seed_tokens, _NO_LOCAL_TOKENS, keywords)
    biggest = max(clusters, key=lambda c: len(c["keywords"]))
    assert len(biggest["keywords"]) < len(keywords)


def test_cluster_keywords_excludes_brand_keyword_from_candidate_title_when_alternative_exists():
    # The frequency-capped tier-3 merge only admits a token covering a
    # MINORITY of what's left (max(2, remaining // 2)) -- padded with a few
    # unrelated keywords here so the "sweep" merge actually qualifies,
    # mirroring the real live run's proportions (5 of 20 total keywords)
    # rather than a too-small toy list where the cap itself would exclude
    # the merge and each keyword would fall to its own singleton instead.
    seed_tokens = {"chimney", "cleaning", "service"}
    keywords = [
        _kw("billy sweet chimney sweep", search_volume=480),
        _kw("affordable chimney sweep near me", search_volume=90),
        _kw("free chimney sweep near me", search_volume=30),
        _kw("chimney inspection cost", search_volume=200),
        _kw("chimney liner repair", search_volume=100),
        _kw("chimney flue cleaning", search_volume=50),
    ]
    clusters = cluster_keywords(seed_tokens, _NO_LOCAL_TOKENS, keywords)
    sweep_cluster = next(
        c for c in clusters if any(kw["keyword"] == "billy sweet chimney sweep" for kw in c["keywords"])
    )
    assert len(sweep_cluster["keywords"]) == 3
    assert sweep_cluster["candidate_page_title"] != "Billy Sweet Chimney Sweep"
    assert sweep_cluster["candidate_page_title_flagged"] is False


def test_cluster_keywords_flags_candidate_title_when_every_member_is_a_brand_name():
    seed_tokens = {"chimney", "cleaning", "service"}
    keywords = [
        _kw("billy sweet chimney sweep", search_volume=480),
        _kw("billy sweet chimney sweep reviews", search_volume=30),
    ]
    clusters = cluster_keywords(seed_tokens, _NO_LOCAL_TOKENS, keywords)
    assert len(clusters) == 1
    assert clusters[0]["candidate_page_title_flagged"] is True


def test_cluster_keywords_flags_a_brand_core_keyword_instead_of_bypassing_the_check():
    # Confirmed live 2026-09-05: the core_keyword tier originally bypassed
    # the brand check entirely -- "lowes garage door repair" (a real brand)
    # was used as a cluster's candidate title unflagged. Fixed by running
    # the same is_possible_brand_keyword check against candidate_title_source.
    seed_tokens = {"garage", "door", "repair"}
    keywords = [
        _kw(
            "lowe's garage door repair",
            search_volume=10,
            core_keyword="lowes garage door repair",
            intent="navigational",
        ),
    ]
    clusters = cluster_keywords(seed_tokens, _NO_LOCAL_TOKENS, keywords)
    assert len(clusters) == 1
    assert clusters[0]["candidate_page_title_flagged"] is True


def _fake_response(json_data):
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = json_data
    return response


def _related_keywords_envelope(items):
    return {
        "status_code": 20000,
        "status_message": "Ok.",
        "tasks": [
            {
                "status_code": 20000,
                "status_message": "Ok.",
                "result": [{"items": items}],
            }
        ],
    }


def _search_intent_envelope(items):
    return {
        "status_code": 20000,
        "status_message": "Ok.",
        "tasks": [
            {
                "status_code": 20000,
                "status_message": "Ok.",
                "result": [{"items": items}],
            }
        ],
    }


def test_fetch_clusters_parses_the_real_dataforseo_field_path():
    # Confirmed live 2026-09-05: the real field is keyword_data.keyword,
    # NOT keyword_data.keyword_info.keyword as an earlier docs-scrape had
    # claimed -- this test locks in the correct path.
    related_response = _fake_response(
        _related_keywords_envelope(
            [
                {
                    "keyword_data": {
                        "keyword": "chimney cleaning service",
                        "keyword_info": {"search_volume": 33100},
                        "keyword_properties": {"core_keyword": None},
                    }
                }
            ]
        )
    )
    intent_response = _fake_response(
        _search_intent_envelope(
            [
                {
                    "keyword": "chimney cleaning service",
                    "keyword_intent": {"label": "commercial", "probability": 0.9},
                }
            ]
        )
    )

    with patch("keyword_research_api._load_config", return_value=("login", "password")):
        with patch(
            "keyword_research_api.requests.post",
            side_effect=[related_response, intent_response],
        ):
            clusters = fetch_clusters(["chimney cleaning service"])

    assert len(clusters) == 1
    assert clusters[0]["keywords"][0]["keyword"] == "chimney cleaning service"
    assert clusters[0]["keywords"][0]["search_volume"] == 33100


def test_run_keyword_research_shows_a_message_when_dataforseo_returns_zero_results(qapp):
    # Confirmed live 2026-09-05: DataForSEO can genuinely return zero
    # related keywords for an overly niche/uncommon exact phrase (e.g.
    # "commercial rollup door service" -- not even the seed itself gets
    # keyword data back). A silently-empty table is indistinguishable from
    # "Run Research" not working at all -- this must show something.
    form = YAMLForm()
    form.inputs["YACSS Build Type"].setCurrentText("Diagram")
    form.inputs["YACSS Bucket Keyword"].setText("commercial rollup door service")

    with patch("main.fetch_clusters", return_value=[]), patch.object(
        QMessageBox, "information"
    ) as mock_information:
        form._run_keyword_research()

    assert form.keyword_research_results_table.rowCount() == 0
    mock_information.assert_called_once()
    assert "commercial rollup door service" in mock_information.call_args.args[2]


def test_local_location_tokens_resolves_state_abbreviation_and_target_cities():
    tokens = local_location_tokens("IL", ["Joliet, IL", "Aurora, IL"])
    assert "illinoi" in tokens  # "illinois" through the same normalizer LOCATION_WORDS uses
    assert "joliet" in tokens
    assert "aurora" in tokens


def test_is_off_target_location_flags_a_state_the_client_does_not_serve():
    # Confirmed live 2026-09-05: seeding "garage door repair" for a
    # Joliet, IL client returned "affordable garage door repair near
    # california" -- the brand filter doesn't catch this (LOCATION_WORDS
    # already excuses any known location from looking like a brand name).
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    assert is_off_target_location(local_tokens, "affordable garage door repair near california") is True


def test_is_off_target_location_does_not_flag_the_clients_own_state_or_city():
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    assert is_off_target_location(local_tokens, "garage door repair joliet il") is False
    assert is_off_target_location(local_tokens, "garage door repair illinois") is False


def test_is_off_target_location_does_not_flag_a_keyword_with_no_location_at_all():
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    assert is_off_target_location(local_tokens, "affordable garage door repair near me") is False


def test_cluster_keywords_flags_and_replaces_an_off_target_location_title():
    # The "good" alternative deliberately avoids naming any city not in
    # LOCATION_WORDS' hand-typed gazetteer (e.g. "joliet") -- an unlisted
    # small town would itself look like an unexplained leftover word to
    # the unrelated, pre-existing brand filter, which isn't what this
    # test is checking.
    seed_tokens = {"garage", "door", "repair"}
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    keywords = [
        _kw(
            "affordable garage door repair near california",
            search_volume=500,
            off_target_location=True,
        ),
        _kw("affordable garage door repair near me", search_volume=90),
    ]
    clusters = cluster_keywords(seed_tokens, local_tokens, keywords)
    off_target_cluster = next(
        c
        for c in clusters
        if any(kw["keyword"].endswith("california") for kw in c["keywords"])
    )
    # Confirmed live: without this fix, the highest-volume member would win
    # regardless of relevance -- the off-target one is 500 vs. 90.
    assert off_target_cluster["candidate_page_title"] != "Affordable Garage Door Repair Near California"
    assert off_target_cluster["candidate_page_title_flagged"] is False


def test_cluster_keywords_flags_candidate_title_when_every_member_is_off_target():
    seed_tokens = {"garage", "door", "repair"}
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    keywords = [
        _kw(
            "affordable garage door repair near california",
            search_volume=500,
            off_target_location=True,
        ),
    ]
    clusters = cluster_keywords(seed_tokens, local_tokens, keywords)
    assert len(clusters) == 1
    assert clusters[0]["candidate_page_title_flagged"] is True
    assert clusters[0]["candidate_page_title_flag_reason"] == "off-target location"


def test_cluster_keywords_flag_reason_combines_brand_and_off_target_location():
    seed_tokens = {"garage", "door", "repair"}
    local_tokens = local_location_tokens("IL", ["Joliet, IL"])
    keywords = [
        _kw(
            "billy sweet garage door repair california",
            search_volume=500,
            possible_brand=True,
            off_target_location=True,
        ),
    ]
    clusters = cluster_keywords(seed_tokens, local_tokens, keywords)
    assert clusters[0]["candidate_page_title_flag_reason"] == "possible brand + off-target location"
