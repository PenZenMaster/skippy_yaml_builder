"""
Module/Script Name: faq_generation.py
Path: E:\\projects\\skippy_yaml_builder\\faq_generation.py

Description:
Orchestrates the FAQ tab's "Generate FAQs" button so the GUI handler in
main.py only gathers form data and shows results. Steps:
  1. Turn the seed keyword (normally YACSS Bucket Keyword, a hyphenated
     bucket name such as "acme-plumbing-01") into a phrase a person would
     actually search for.
  2. Collect real Google "People Also Ask" questions, trying a few search
     phrasings (the cleaned seed, then seed + each target city) with the PAA
     box expanded, until the requested count is met.
  3. If Google still supplied fewer than requested, top up with AI-suggested
     questions, kept distinct (source == "ai") so the operator can tell them
     from real Google questions.
  4. Write a grounded answer for every question
     (ai_content_generator.generate_faq_answers).

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-09-26

Last Modified Date:
2026-09-26

Comments:
- v1.00 Initial implementation. Replaces the handler-local flow that made one
  un-expanded SERP call on the raw bucket keyword and returned whatever came
  back, however few.
"""

import re
from dataclasses import dataclass, field

from ai_content_generator import generate_faq_answers, generate_faq_questions
from keyword_research_api import KeywordResearchError, fetch_people_also_ask

# One click may run this many SERP searches (the cleaned seed plus city
# variants); each is billed by DataForSEO, so the total is bounded.
MAX_PAA_SEARCHES = 4
# How many times each search expands the PAA box (see
# keyword_research_api.fetch_people_also_ask).
PAA_CLICK_DEPTH = 2

SOURCE_GOOGLE = "google"
SOURCE_AI = "ai"

# A trailing zero-padded counter such as the "-01" in "acme-plumbing-01".
_TRAILING_COUNTER = re.compile(r"\s+0\d+$")


@dataclass
class FaqItem:
    question: str
    answer: str
    source: str  # SOURCE_GOOGLE or SOURCE_AI


@dataclass
class FaqGenerationResult:
    requested: int
    items: list = field(default_factory=list)
    searched_phrases: list = field(default_factory=list)

    @property
    def google_count(self) -> int:
        return sum(1 for item in self.items if item.source == SOURCE_GOOGLE)

    @property
    def ai_count(self) -> int:
        return sum(1 for item in self.items if item.source == SOURCE_AI)

    @property
    def blank_answer_count(self) -> int:
        return sum(1 for item in self.items if not item.answer)


def clean_seed_keyword(raw: str) -> str:
    """A bucket-style keyword as a search phrase: hyphens and underscores
    become spaces, whitespace is collapsed, and a trailing zero-padded
    counter ("-01") is dropped. "emergency-plumber-dallas-01" ->
    "emergency plumber dallas"."""
    text = re.sub(r"[-_\s]+", " ", raw).strip()
    return _TRAILING_COUNTER.sub("", text).strip()


def _city_name(target_city: str) -> str:
    """ "Dallas, TX" -> "Dallas"."""
    return target_city.split(",")[0].strip()


def search_phrases(seed: str, target_cities: list) -> list:
    """The seed first, then seed + city for each target city that the seed
    does not already mention, capped at MAX_PAA_SEARCHES."""
    phrases = [seed]
    for city in target_cities:
        name = _city_name(city)
        if name and name.lower() not in seed.lower():
            phrases.append(f"{seed} {name}")
    return phrases[:MAX_PAA_SEARCHES]


def collect_paa_questions(seed: str, target_cities: list, count: int) -> tuple:
    """Returns (questions, phrases_searched): up to `count` distinct real
    Google PAA questions, stopping as soon as the count is met. A failure on
    the first search propagates (nothing to fall back on, and it usually
    means credentials or connectivity); a failure on a later variant is
    skipped, keeping what was already found."""
    questions: list = []
    seen: set = set()
    searched: list = []
    for index, phrase in enumerate(search_phrases(seed, target_cities)):
        try:
            found = fetch_people_also_ask(
                phrase, max_questions=count, click_depth=PAA_CLICK_DEPTH
            )
        except KeywordResearchError:
            if index == 0:
                raise
            continue
        searched.append(phrase)
        for question in found:
            key = question.lower()
            if key not in seen:
                seen.add(key)
                questions.append(question)
        if len(questions) >= count:
            break
    return questions[:count], searched


def generate_faqs(
    seed_keyword: str,
    business_name: str,
    business_category: str,
    target_cities: list,
    services: list,
    count: int,
    company_facts: dict | None = None,
) -> FaqGenerationResult:
    """Builds up to `count` FAQ items (real Google questions first, then
    AI-suggested ones to make up any shortfall), each with a grounded answer.

    Raises:
        KeywordResearchError: the first Google PAA search failed.
        AiContentError: question top-up or answer generation failed.
    """
    seed = clean_seed_keyword(seed_keyword)
    google_questions, searched = collect_paa_questions(seed, target_cities, count)

    ai_questions: list = []
    shortfall = count - len(google_questions)
    if shortfall > 0:
        ai_questions = generate_faq_questions(
            business_name,
            business_category,
            target_cities,
            services,
            existing_questions=google_questions,
            count=shortfall,
            company_facts=company_facts,
        )

    questions = google_questions + ai_questions
    result = FaqGenerationResult(requested=count, searched_phrases=searched)
    if not questions:
        return result

    answers = generate_faq_answers(
        business_name,
        business_category,
        target_cities,
        services,
        questions,
        company_facts=company_facts,
    )
    for index, question in enumerate(questions):
        source = SOURCE_GOOGLE if index < len(google_questions) else SOURCE_AI
        result.items.append(FaqItem(question, answers[index], source))
    return result
