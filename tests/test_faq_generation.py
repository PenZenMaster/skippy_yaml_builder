"""Tests for faq_generation.py -- seed cleaning, PAA search variants, the
AI top-up for a short Google result, and question/answer alignment. The three
collaborators (fetch_people_also_ask, generate_faq_questions,
generate_faq_answers) are patched at faq_generation.<name>, so no real
DataForSEO/OpenAI calls are made."""

import pytest

import faq_generation as fg
from ai_content_generator import AiContentError
from keyword_research_api import KeywordResearchError


def _patch_paa(monkeypatch, by_phrase, calls=None):
    """fetch_people_also_ask fake: {phrase: [questions]} (an Exception value
    is raised instead). Records (phrase, max_questions, click_depth)."""

    def fake(phrase, max_questions=10, click_depth=0):
        if calls is not None:
            calls.append((phrase, max_questions, click_depth))
        value = by_phrase.get(phrase, [])
        if isinstance(value, Exception):
            raise value
        return list(value)

    monkeypatch.setattr(fg, "fetch_people_also_ask", fake)


def _patch_ai(monkeypatch, top_up=None, answers=None):
    captured = {"top_up_calls": [], "answer_calls": []}

    def fake_questions(*args, **kwargs):
        captured["top_up_calls"].append((args, kwargs))
        return list(top_up or [])

    def fake_answers(business_name, category, cities, services, questions, **kwargs):
        captured["answer_calls"].append((list(questions), kwargs))
        if answers is not None:
            return list(answers)
        return [f"Answer to {q}" for q in questions]

    monkeypatch.setattr(fg, "generate_faq_questions", fake_questions)
    monkeypatch.setattr(fg, "generate_faq_answers", fake_answers)
    return captured


def _run(count=3, cities=None, **kwargs):
    return fg.generate_faqs(
        seed_keyword=kwargs.pop("seed_keyword", "emergency-plumber-dallas-01"),
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=cities if cities is not None else ["Dallas, TX"],
        services=["Drain Cleaning"],
        count=count,
        **kwargs,
    )


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("emergency-plumber-dallas-01", "emergency plumber dallas"),
        ("acme_plumbing_02", "acme plumbing"),
        ("  garage   door repair ", "garage door repair"),
        ("garage door repair", "garage door repair"),
        ("24-hour plumber", "24 hour plumber"),
        ("route 66 diner", "route 66 diner"),
    ],
)
def test_clean_seed_keyword(raw, expected):
    assert fg.clean_seed_keyword(raw) == expected


def test_search_phrases_adds_city_variants_and_skips_cities_already_in_seed():
    phrases = fg.search_phrases(
        "plumber dallas", ["Dallas, TX", "Fort Worth, TX", "Plano, TX"]
    )
    assert phrases == [
        "plumber dallas",
        "plumber dallas Fort Worth",
        "plumber dallas Plano",
    ]


def test_search_phrases_is_capped():
    cities = [f"City{i}, TX" for i in range(10)]
    assert len(fg.search_phrases("plumber", cities)) == fg.MAX_PAA_SEARCHES


def test_collect_paa_stops_after_the_first_search_when_count_is_met(monkeypatch):
    calls = []
    _patch_paa(monkeypatch, {"plumber": ["Q1?", "Q2?", "Q3?"]}, calls)
    questions, searched = fg.collect_paa_questions("plumber", ["Dallas"], 3)
    assert questions == ["Q1?", "Q2?", "Q3?"]
    assert searched == ["plumber"]
    # The PAA box is expanded, and the requested count is passed through.
    assert calls == [("plumber", 3, fg.PAA_CLICK_DEPTH)]


def test_collect_paa_falls_through_to_city_variants_and_dedupes(monkeypatch):
    calls = []
    _patch_paa(
        monkeypatch,
        {
            "plumber": ["Q1?", "Q2?"],
            "plumber Dallas": ["q1?", "Q3?"],  # q1? duplicates Q1? (case)
            "plumber Plano": ["Q4?", "Q5?"],
        },
        calls,
    )
    questions, searched = fg.collect_paa_questions(
        "plumber", ["Dallas, TX", "Plano, TX"], 4
    )
    assert questions == ["Q1?", "Q2?", "Q3?", "Q4?"]
    assert searched == ["plumber", "plumber Dallas", "plumber Plano"]


def test_collect_paa_truncates_to_the_requested_count(monkeypatch):
    _patch_paa(monkeypatch, {"plumber": [f"Q{i}?" for i in range(8)]})
    questions, _ = fg.collect_paa_questions("plumber", [], 3)
    assert len(questions) == 3


def test_collect_paa_propagates_a_first_search_failure(monkeypatch):
    _patch_paa(monkeypatch, {"plumber": KeywordResearchError("no credentials")})
    with pytest.raises(KeywordResearchError):
        fg.collect_paa_questions("plumber", ["Dallas"], 3)


def test_collect_paa_skips_a_failed_variant_and_keeps_earlier_results(monkeypatch):
    _patch_paa(
        monkeypatch,
        {
            "plumber": ["Q1?"],
            "plumber Dallas": KeywordResearchError("timeout"),
            "plumber Plano": ["Q2?"],
        },
    )
    questions, searched = fg.collect_paa_questions(
        "plumber", ["Dallas, TX", "Plano, TX"], 5
    )
    assert questions == ["Q1?", "Q2?"]
    assert searched == ["plumber", "plumber Plano"]


def test_generate_faqs_searches_with_the_cleaned_seed(monkeypatch):
    calls = []
    _patch_paa(monkeypatch, {"emergency plumber dallas": ["Q1?", "Q2?", "Q3?"]}, calls)
    _patch_ai(monkeypatch)
    _run(count=3, cities=[])
    assert calls[0][0] == "emergency plumber dallas"


def test_generate_faqs_does_not_call_ai_for_questions_when_google_is_enough(
    monkeypatch,
):
    _patch_paa(monkeypatch, {"emergency plumber dallas": ["Q1?", "Q2?", "Q3?"]})
    captured = _patch_ai(monkeypatch)
    result = _run(count=3, cities=[])
    assert captured["top_up_calls"] == []
    assert [i.source for i in result.items] == [fg.SOURCE_GOOGLE] * 3
    assert result.requested == 3
    assert result.google_count == 3 and result.ai_count == 0


def test_generate_faqs_tops_up_a_short_google_result_and_labels_the_source(
    monkeypatch,
):
    _patch_paa(monkeypatch, {"emergency plumber dallas": ["G1?", "G2?"]})
    captured = _patch_ai(monkeypatch, top_up=["A1?", "A2?", "A3?"])
    result = _run(count=5, cities=[], company_facts={"Phone": "555"})

    args, kwargs = captured["top_up_calls"][0]
    assert kwargs["count"] == 3  # exactly the shortfall
    assert kwargs["existing_questions"] == ["G1?", "G2?"]
    assert kwargs["company_facts"] == {"Phone": "555"}
    assert [(i.question, i.source) for i in result.items] == [
        ("G1?", fg.SOURCE_GOOGLE),
        ("G2?", fg.SOURCE_GOOGLE),
        ("A1?", fg.SOURCE_AI),
        ("A2?", fg.SOURCE_AI),
        ("A3?", fg.SOURCE_AI),
    ]
    assert result.google_count == 2 and result.ai_count == 3
    # Answers were requested for every question, google first, with the facts.
    questions, answer_kwargs = captured["answer_calls"][0]
    assert questions == ["G1?", "G2?", "A1?", "A2?", "A3?"]
    assert answer_kwargs["company_facts"] == {"Phone": "555"}


def test_generate_faqs_is_all_ai_when_google_shows_no_paa_box(monkeypatch):
    _patch_paa(monkeypatch, {})
    _patch_ai(monkeypatch, top_up=["A1?", "A2?"])
    result = _run(count=2, cities=[])
    assert result.google_count == 0 and result.ai_count == 2
    assert result.searched_phrases == ["emergency plumber dallas"]


def test_generate_faqs_pairs_answers_by_position_and_counts_blanks(monkeypatch):
    _patch_paa(monkeypatch, {"emergency plumber dallas": ["Q1?", "Q2?"]})
    _patch_ai(monkeypatch, answers=["Answer one.", ""])
    result = _run(count=2, cities=[])
    assert [(i.question, i.answer) for i in result.items] == [
        ("Q1?", "Answer one."),
        ("Q2?", ""),
    ]
    assert result.blank_answer_count == 1


def test_generate_faqs_returns_no_items_without_calling_answers_when_nothing_found(
    monkeypatch,
):
    _patch_paa(monkeypatch, {})
    captured = _patch_ai(monkeypatch, top_up=[])
    result = _run(count=4, cities=[])
    assert result.items == []
    assert captured["answer_calls"] == []


def test_generate_faqs_propagates_ai_failures(monkeypatch):
    _patch_paa(monkeypatch, {"emergency plumber dallas": ["Q1?"]})

    def boom(*args, **kwargs):
        raise AiContentError("no key configured")

    monkeypatch.setattr(fg, "generate_faq_questions", boom)
    with pytest.raises(AiContentError):
        _run(count=3, cities=[])
