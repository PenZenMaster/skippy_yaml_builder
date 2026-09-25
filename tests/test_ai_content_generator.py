"""Unit tests for ai_content_generator.py -- no real OpenAI calls, no real
.env file read (module-level config lookup and the OpenAI client are both
monkeypatched). Covers is_available(), the exact-title-count guard, response
parsing, and error wrapping."""

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


def test_generate_faq_answers_returns_empty_list_for_no_questions(monkeypatch):
    _configure(monkeypatch)
    assert (
        acg.generate_faq_answers(
            "Acme Plumbing", "Plumbing", ["Dallas"], ["Drain Cleaning"], []
        )
        == []
    )


def test_generate_faq_answers_parses_numbered_answers_in_order(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(
        monkeypatch,
        content=(
            "1. Emergency repairs typically cost $150-$400 depending on the issue.\n"
            "2. Most repairs are completed within an hour by an Acme Plumbing technician.\n"
        ),
    )
    answers = acg.generate_faq_answers(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas", "Fort Worth"],
        services=["Drain Cleaning"],
        questions=[
            "How much does emergency plumbing cost?",
            "How long does a repair take?",
        ],
    )
    assert answers == [
        "Emergency repairs typically cost $150-$400 depending on the issue.",
        "Most repairs are completed within an hour by an Acme Plumbing technician.",
    ]
    # Both real questions are passed through into the prompt, in order.
    prompt = fake_client.completions.calls[0]["messages"][1]["content"]
    assert "1. How much does emergency plumbing cost?" in prompt
    assert "2. How long does a repair take?" in prompt


def test_generate_faq_answers_leaves_a_blank_for_a_question_the_model_skipped(
    monkeypatch,
):
    _configure(monkeypatch)
    _install_fake_client(
        monkeypatch,
        # Only answers question 1 and 3 -- question 2's answer is missing.
        content="1. First answer.\n3. Third answer.\n",
    )
    answers = acg.generate_faq_answers(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas"],
        services=["Drain Cleaning"],
        questions=["Question one?", "Question two?", "Question three?"],
    )
    assert answers == ["First answer.", "", "Third answer."]


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


def _sequenced_call_openai(monkeypatch, drafts):
    calls = []

    def fake(system_message, prompt, max_tokens):
        calls.append({"prompt": prompt, "max_tokens": max_tokens})
        return drafts[min(len(calls), len(drafts)) - 1]

    monkeypatch.setattr(acg, "_call_openai", fake)
    return calls


def test_generate_diagram_content_stops_when_first_draft_meets_minimum(monkeypatch):
    _configure(monkeypatch)
    long_draft = " ".join(["word"] * acg.MIN_DIAGRAM_CONTENT_WORDS)
    calls = _sequenced_call_openai(monkeypatch, [long_draft])

    assert acg.generate_diagram_content(**_content_kwargs()) == long_draft
    assert len(calls) == 1
    assert str(acg.MIN_DIAGRAM_CONTENT_WORDS) in calls[0]["prompt"]


def test_generate_diagram_content_retries_short_draft_with_feedback(monkeypatch):
    _configure(monkeypatch)
    short_draft = " ".join(["word"] * 100)
    long_draft = " ".join(["word"] * 800)
    calls = _sequenced_call_openai(monkeypatch, [short_draft, long_draft])

    assert acg.generate_diagram_content(**_content_kwargs()) == long_draft
    assert len(calls) == 2
    assert "only 100 words" in calls[1]["prompt"]


def test_generate_diagram_content_returns_longest_after_max_attempts(monkeypatch):
    _configure(monkeypatch)
    drafts = [
        " ".join(["word"] * 100),
        " ".join(["word"] * 300),
        " ".join(["word"] * 200),
    ]
    calls = _sequenced_call_openai(monkeypatch, drafts)

    assert acg.generate_diagram_content(**_content_kwargs()) == drafts[1]
    assert len(calls) == acg.DIAGRAM_CONTENT_MAX_ATTEMPTS


def test_generate_diagram_content_counts_rendered_not_raw_words(monkeypatch):
    """A draft padded with spintax alternatives has a high raw word count
    but a low rendered count, and must be treated as short."""
    _configure(monkeypatch)
    padded = " ".join(["{one|two words here|three}"] * 300)
    assert len(padded.split()) > acg.MIN_DIAGRAM_CONTENT_WORDS
    assert acg.count_rendered_words(padded) < acg.MIN_DIAGRAM_CONTENT_WORDS
    calls = _sequenced_call_openai(monkeypatch, [padded])

    acg.generate_diagram_content(**_content_kwargs())
    assert len(calls) == acg.DIAGRAM_CONTENT_MAX_ATTEMPTS


def test_generate_diagram_content_enforces_token_floor(monkeypatch):
    _configure(monkeypatch, OPENAI_MAX_TOKENS="500")
    long_draft = " ".join(["word"] * 800)
    calls = _sequenced_call_openai(monkeypatch, [long_draft])

    acg.generate_diagram_content(**_content_kwargs())
    assert calls[0]["max_tokens"] == acg.DIAGRAM_CONTENT_MIN_MAX_TOKENS


def test_generate_diagram_content_respects_higher_env_token_cap(monkeypatch):
    _configure(monkeypatch, OPENAI_MAX_TOKENS="9000")
    long_draft = " ".join(["word"] * 800)
    calls = _sequenced_call_openai(monkeypatch, [long_draft])

    acg.generate_diagram_content(**_content_kwargs())
    assert calls[0]["max_tokens"] == 9000
