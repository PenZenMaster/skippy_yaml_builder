"""Unit tests for ai_content_generator.py -- no real OpenAI calls, no real
.env file read (module-level config lookup and the OpenAI client are both
monkeypatched). Covers is_available(), the exact-title-count guard, response
parsing, and error wrapping."""

import json

import ai_content_generator as acg


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)] if content is not None else []


class _FakeCompletions:
    def __init__(self, content, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        if isinstance(self.content, list):
            index = min(len(self.calls), len(self.content)) - 1
            return _FakeResponse(self.content[index])
        return _FakeResponse(self.content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeOpenAIClient:
    def __init__(self, content=None, error=None):
        self.completions = _FakeCompletions(content, error)
        self.chat = _FakeChat(self.completions)


def _install_fake_client(monkeypatch, content=None, error=None):
    fake_client = _FakeOpenAIClient(content=content, error=error)
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(acg, "OpenAI", lambda api_key: fake_client)
    return fake_client


def _configure(monkeypatch, api_key="sk-test-key", **overrides):
    config = {"OPENAI_API_KEY": api_key, **overrides}
    monkeypatch.setattr(acg, "_load_config", lambda: config)


def test_is_available_false_without_api_key(monkeypatch):
    _configure(monkeypatch, api_key="")
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", True)
    assert acg.is_available() is False


def test_is_available_false_when_openai_package_missing(monkeypatch):
    _configure(monkeypatch, api_key="sk-test-key")
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", False)
    assert acg.is_available() is False


def test_is_available_true_with_key_and_package(monkeypatch):
    _configure(monkeypatch, api_key="sk-test-key")
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", True)
    assert acg.is_available() is True


def test_generate_diagram_page_titles_rejects_non_positive_count(monkeypatch):
    _configure(monkeypatch)
    try:
        acg.generate_diagram_page_titles(
            business_name="Acme Plumbing",
            business_category="Plumbing",
            target_keyword="emergency plumber dallas",
            target_cities=["Dallas"],
            services=["Drain Cleaning"],
            title_count=0,
        )
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "title_count" in str(exc)


def test_generate_diagram_page_titles_parses_one_title_per_line(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch,
        content="Emergency Plumber Dallas | Acme Plumbing\n\n24/7 Drain Cleaning in Dallas\nBurst Pipe Repair Dallas TX\n",
    )
    titles = acg.generate_diagram_page_titles(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_keyword="emergency plumber dallas",
        target_cities=["Dallas", "Fort Worth"],
        services=["Drain Cleaning", "Water Heater Repair"],
        title_count=3,
    )
    assert titles == [
        "Emergency Plumber Dallas | Acme Plumbing",
        "24/7 Drain Cleaning in Dallas",
        "Burst Pipe Repair Dallas TX",
    ]
    # The exact required count is passed through into the prompt.
    assert "3" in fake_client.completions.calls[0]["messages"][1]["content"]


def test_generate_diagram_content_strips_and_returns_raw_text(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, content="  Some {spun|generated} content.  ")
    content = acg.generate_diagram_content(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_keyword="emergency plumber dallas",
        target_cities=["Dallas"],
        services=["Drain Cleaning"],
        city="Dallas",
        state="TX",
    )
    assert content == "Some {spun|generated} content."


def test_call_openai_raises_when_package_not_installed(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", False)
    try:
        acg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "openai" in str(exc).lower()


def test_call_openai_raises_when_no_api_key_configured(monkeypatch):
    _configure(monkeypatch, api_key="")
    monkeypatch.setattr(acg, "OPENAI_AVAILABLE", True)
    try:
        acg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "OPENAI_API_KEY" in str(exc)


def test_call_openai_wraps_client_exceptions(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, error=RuntimeError("network exploded"))
    try:
        acg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "network exploded" in str(exc)


def test_call_openai_raises_on_empty_response(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, content="   ")
    try:
        acg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "empty" in str(exc).lower()


def _answers_json(*pairs):
    return json.dumps({"answers": [{"number": n, "answer": a} for n, a in pairs]})


def _faq_kwargs(**overrides):
    kwargs = dict(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas", "Fort Worth"],
        services=["Drain Cleaning"],
        questions=["Question one?", "Question two?", "Question three?"],
    )
    kwargs.update(overrides)
    return kwargs


def test_generate_faq_answers_returns_empty_list_for_no_questions(monkeypatch):
    _configure(monkeypatch)
    assert acg.generate_faq_answers(**_faq_kwargs(questions=[])) == []


def test_generate_faq_answers_parses_json_answers_in_order(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch,
        content=_answers_json(
            (1, "Costs depend on the issue, so contact Acme Plumbing for a quote."),
            (2, "The time depends on the job."),
        ),
    )
    answers = acg.generate_faq_answers(
        **_faq_kwargs(
            questions=[
                "How much does emergency plumbing cost?",
                "How long does a repair take?",
            ]
        )
    )
    assert answers == [
        "Costs depend on the issue, so contact Acme Plumbing for a quote.",
        "The time depends on the job.",
    ]
    call = fake_client.completions.calls[0]
    prompt = call["messages"][1]["content"]
    assert "1. How much does emergency plumbing cost?" in prompt
    assert "2. How long does a repair take?" in prompt
    # JSON output is requested explicitly, not parsed out of free text.
    assert call["response_format"] == {"type": "json_object"}


def test_generate_faq_answers_prompt_is_grounded_in_client_facts(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content=_answers_json((1, "A.")))
    acg.generate_faq_answers(
        **_faq_kwargs(
            questions=["Are you licensed?"],
            company_facts={
                "Phone": "(214) 555-0100",
                "Website": "https://acmeplumbing.example",
                "ZIP": "",
                "Fax": "(   )    -",
            },
        )
    )
    prompt = fake_client.completions.calls[0]["messages"][1]["content"]
    assert "GROUNDING RULES" in prompt
    assert "- Business name: Acme Plumbing" in prompt
    assert "- Service area: Dallas, Fort Worth" in prompt
    assert "- Services: Drain Cleaning" in prompt
    assert "- Phone: (214) 555-0100" in prompt
    assert "- Website: https://acmeplumbing.example" in prompt
    # Blank values and an unfilled phone mask are not presented as facts.
    assert "ZIP" not in prompt
    assert "Fax" not in prompt
    flat_prompt = " ".join(prompt.split())
    for forbidden in ("prices", "years in business", "licences", "guarantees"):
        assert forbidden in flat_prompt


def test_generate_faq_answers_prompt_asks_for_first_person_voice(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content=_answers_json((1, "A.")))
    acg.generate_faq_answers(**_faq_kwargs(questions=["Are you licensed?"]))
    call = fake_client.completions.calls[0]
    prompt = " ".join(call["messages"][1]["content"].split())
    assert "VOICE" in prompt
    assert '"we", "our team"' in prompt
    assert "Never refer to the business in the third person" in prompt
    assert '"not specified"' in prompt
    # Live 2026-11-05 the first-person voice alone produced "We do provide
    # free estimates" and "we cannot disclose": both are now named.
    assert "free or paid estimates" in prompt
    assert "staff qualifications" in prompt
    assert '"cannot disclose"' in prompt
    assert "Contact us and we'll go over estimates" in prompt
    # The examples are first person, not "contact Acme Plumbing".
    assert "contact Acme Plumbing" not in prompt
    assert "first-person voice" in call["messages"][0]["content"]
    # FAQs stay on the general model, not the content model.
    assert call["model"] == acg.DEFAULT_MODEL


def test_generate_faq_questions_avoids_owner_only_topics(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content='{"questions": ["Q?"]}')
    acg.generate_faq_questions(
        "Acme Plumbing", "Plumbing", ["Dallas"], ["Drain Cleaning"], [], 1
    )
    prompt = " ".join(
        fake_client.completions.calls[0]["messages"][1]["content"].split()
    )
    assert "only the business owner could answer" in prompt
    for topic in ("estimates or quotes", "warranties or guarantees", "licensing"):
        assert topic in prompt


def test_generate_faq_answers_retries_only_the_blank_questions(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch,
        content=[
            # First call answers 1 and 3 only.
            _answers_json((1, "First answer."), (3, "Third answer.")),
            _answers_json((2, "Second answer.")),
        ],
    )
    answers = acg.generate_faq_answers(**_faq_kwargs())
    assert answers == ["First answer.", "Second answer.", "Third answer."]
    assert len(fake_client.completions.calls) == 2
    retry_prompt = fake_client.completions.calls[1]["messages"][1]["content"]
    # The retry keeps the ORIGINAL numbering and asks only for the blank one.
    assert "2. Question two?" in retry_prompt
    assert "1. Question one?" not in retry_prompt
    assert "3. Question three?" not in retry_prompt


def test_generate_faq_answers_gives_up_after_max_attempts_leaving_blanks(
    monkeypatch,
):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch, content=_answers_json((1, "First answer."))
    )
    answers = acg.generate_faq_answers(**_faq_kwargs())
    assert answers == ["First answer.", "", ""]
    assert len(fake_client.completions.calls) == acg.FAQ_ANSWER_MAX_ATTEMPTS


def test_generate_faq_answers_tolerates_fenced_json_and_string_numbers(
    monkeypatch,
):
    _configure(monkeypatch)
    _install_fake_client(
        monkeypatch,
        content='```json\n{"answers": [{"number": "1", "answer": "One."},'
        ' {"number": 99, "answer": "Out of range."},'
        ' {"number": 2, "answer": "   "}]}\n```',
    )
    answers = acg.generate_faq_answers(**_faq_kwargs(questions=["Q1?", "Q2?"]))
    # Fence stripped, "1" accepted, out-of-range and blank answers ignored
    # (question 2 stays blank through every retry).
    assert answers == ["One.", ""]


def test_generate_faq_answers_keeps_collected_answers_when_a_retry_fails(
    monkeypatch,
):
    _configure(monkeypatch)
    calls = {"n": 0}

    def fake_call(system_message, prompt, max_tokens, json_mode=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return _answers_json((1, "First answer."))
        raise acg.AiContentError("rate limited")

    monkeypatch.setattr(acg, "_call_openai", fake_call)
    answers = acg.generate_faq_answers(**_faq_kwargs())
    assert answers == ["First answer.", "", ""]


def test_generate_faq_answers_raises_when_the_first_call_fails(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, error=RuntimeError("boom"))
    try:
        acg.generate_faq_answers(**_faq_kwargs())
        assert False, "expected AiContentError"
    except acg.AiContentError as exc:
        assert "boom" in str(exc)


def test_generate_faq_questions_returns_fresh_deduplicated_questions(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch,
        content=json.dumps(
            {
                "questions": [
                    "How often should drains be cleaned?",
                    "how much does drain cleaning cost",  # dup of existing, no ?
                    "Can a clogged drain damage pipes?",
                    "Can a clogged drain damage pipes?",  # dup within reply
                    "",
                    42,
                    "What causes slow drains?",
                ]
            }
        ),
    )
    questions = acg.generate_faq_questions(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas"],
        services=["Drain Cleaning"],
        existing_questions=["How much does drain cleaning cost?"],
        count=2,
    )
    assert questions == [
        "How often should drains be cleaned?",
        "Can a clogged drain damage pipes?",
    ]
    call = fake_client.completions.calls[0]
    prompt = call["messages"][1]["content"]
    assert "- How much does drain cleaning cost?" in prompt
    assert "do NOT write answers" in prompt
    assert call["response_format"] == {"type": "json_object"}


def test_generate_faq_questions_returns_empty_for_non_positive_count(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content="{}")
    assert (
        acg.generate_faq_questions("A", "B", [], [], existing_questions=[], count=0)
        == []
    )
    assert fake_client.completions.calls == []


def test_generate_faq_questions_returns_empty_for_unusable_reply(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, content="not json at all")
    assert (
        acg.generate_faq_questions("A", "B", [], [], existing_questions=[], count=3)
        == []
    )


def test_render_spintax_min_picks_shortest_option_and_handles_nesting():
    text = "The {quick brown|fast} fox {a|b {c d|e}} ok"
    assert acg.render_spintax_min(text) == "The fast fox a ok"
    assert acg.count_rendered_words(text) == 5


def test_count_rendered_words_counts_plain_text_and_leaves_unbalanced_braces():
    assert acg.count_rendered_words("one two three") == 3
    assert acg.count_rendered_words("one {two three") == 3


def _content_kwargs():
    return dict(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_keyword="emergency plumber dallas",
        target_cities=["Dallas"],
        services=["Drain Cleaning"],
    )


def _words(n):
    return " ".join(["word"] * n)


def _spun(n):
    """Spun text whose shortest rendering is n words."""
    return " ".join(["{word|longer phrase}"] * n)


def _two_step(monkeypatch, articles, spins):
    """Fake _call_openai: plain-article calls get `articles` in turn, spin
    calls get `spins` in turn (the last one repeats)."""
    calls = []

    def fake(system_message, prompt, max_tokens):
        step = "spin" if "spintax" in system_message else "article"
        calls.append({"step": step, "prompt": prompt, "max_tokens": max_tokens})
        source = spins if step == "spin" else articles
        count = sum(1 for c in calls if c["step"] == step)
        return source[min(count, len(source)) - 1]

    monkeypatch.setattr(acg, "_call_openai", fake)
    return calls


def test_content_is_a_plain_article_then_a_spin_pass(monkeypatch):
    _configure(monkeypatch)
    article = _words(1000)
    calls = _two_step(monkeypatch, [article], [_spun(1000)])

    assert acg.generate_diagram_content(**_content_kwargs()) == _spun(1000)
    assert [c["step"] for c in calls] == ["article", "spin"]
    article_prompt = " ".join(calls[0]["prompt"].split())
    assert f"at least {acg.DIAGRAM_CONTENT_PROMPT_MIN_WORDS} words" in article_prompt
    assert f"{acg.DIAGRAM_CONTENT_PARAGRAPHS} paragraphs" in article_prompt
    assert "no spintax" in article_prompt
    spin_prompt = " ".join(calls[1]["prompt"].split())
    assert "AT LEAST as many words as the original" in spin_prompt
    assert (
        "FIRST option of every group is the article's original wording" in spin_prompt
    )
    assert article in calls[1]["prompt"]


def test_content_prompts_forbid_invented_claims(monkeypatch):
    """Live 2026-11-05 the article claimed "years of experience" and to
    "guarantee long-lasting results"; both prompts now rule that out."""
    _configure(monkeypatch)
    calls = _two_step(monkeypatch, [_words(1000)], [_spun(1000)])
    acg.generate_diagram_content(**_content_kwargs())

    article_prompt = " ".join(calls[0]["prompt"].split())
    assert "NO INVENTED CLAIMS" in article_prompt
    for claim in ("years in business or experience", "guarantees", '"highest quality"'):
        assert claim in article_prompt
    assert "why choose this business -- using only its services" in article_prompt

    spin_prompt = " ".join(calls[1]["prompt"].split())
    assert "must never add a claim the original wording does not make" in spin_prompt
    assert "is a leader in" not in spin_prompt


def test_short_plain_article_is_rewritten_with_feedback(monkeypatch):
    _configure(monkeypatch)
    calls = _two_step(monkeypatch, [_words(600), _words(950)], [_spun(950)])

    acg.generate_diagram_content(**_content_kwargs())
    assert [c["step"] for c in calls] == ["article", "article", "spin"]
    retry = " ".join(calls[1]["prompt"].split())
    assert "only 600 words" in retry
    assert "required minimum of 900" in retry
    assert _words(950) in calls[2]["prompt"]


def test_longest_plain_article_is_spun_after_max_attempts(monkeypatch):
    _configure(monkeypatch)
    articles = [_words(700), _words(850), _words(800)]
    calls = _two_step(monkeypatch, articles, [_spun(850)])

    acg.generate_diagram_content(**_content_kwargs())
    article_calls = [c for c in calls if c["step"] == "article"]
    assert len(article_calls) == acg.DIAGRAM_CONTENT_MAX_ATTEMPTS
    assert _words(850) in calls[-1]["prompt"]


def test_spin_that_drops_text_is_redone(monkeypatch):
    """A spin pass that renders well under the plain article lost text."""
    _configure(monkeypatch)
    calls = _two_step(monkeypatch, [_words(1000)], [_spun(700), _spun(990)])

    assert acg.generate_diagram_content(**_content_kwargs()) == _spun(990)
    assert [c["step"] for c in calls] == ["article", "spin", "spin"]


def test_longest_spin_is_kept_after_max_attempts(monkeypatch):
    _configure(monkeypatch)
    calls = _two_step(monkeypatch, [_words(1000)], [_spun(800), _spun(700)])

    assert acg.generate_diagram_content(**_content_kwargs()) == _spun(800)
    spin_calls = [c for c in calls if c["step"] == "spin"]
    assert len(spin_calls) == acg.DIAGRAM_SPIN_MAX_ATTEMPTS


def test_spin_rendered_count_uses_the_shortest_option(monkeypatch):
    """Spun text is judged by its shortest rendering, not its raw length."""
    padded = " ".join(["{one|two words here|three}"] * 300)
    assert len(padded.split()) > acg.MIN_DIAGRAM_CONTENT_WORDS
    assert acg.count_rendered_words(padded) < acg.MIN_DIAGRAM_CONTENT_WORDS
    assert acg.count_rendered_words(_spun(800)) == 800


def test_generate_diagram_content_enforces_token_floor(monkeypatch):
    _configure(monkeypatch, OPENAI_MAX_TOKENS="500")
    calls = _two_step(monkeypatch, [_words(1000)], [_spun(1000)])

    acg.generate_diagram_content(**_content_kwargs())
    assert {c["max_tokens"] for c in calls} == {acg.DIAGRAM_CONTENT_MIN_MAX_TOKENS}


def test_generate_diagram_content_respects_higher_env_token_cap(monkeypatch):
    _configure(monkeypatch, OPENAI_MAX_TOKENS="9000")
    calls = _two_step(monkeypatch, [_words(1000)], [_spun(1000)])

    acg.generate_diagram_content(**_content_kwargs())
    assert {c["max_tokens"] for c in calls} == {9000}


def test_page_title_prompt_forbids_claims_and_unlisted_services(monkeypatch):
    """Live 2026-11-06 the titles said "Leading", "Premier", "Best Choice",
    "Affordable" and named crawl space encapsulation, which is not a listed
    service."""
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content="A\nB\n")
    acg.generate_diagram_page_titles(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_keyword="drain cleaning",
        target_cities=["Dallas"],
        services=["Drain Cleaning"],
        title_count=2,
    )
    prompt = " ".join(
        fake_client.completions.calls[0]["messages"][1]["content"].split()
    )
    assert "NO INVENTED CLAIMS" in prompt
    for word in ('"leading"', '"premier"', '"best"', '"affordable"'):
        assert word in prompt
    assert "Only name services from the Services/products list" in prompt
