"""Unit tests for silo_content_generator.py -- no real OpenAI calls, no
real .env file read (module-level config lookup and the OpenAI client are
both monkeypatched), mirroring test_ai_content_generator.py's own
mocking pattern exactly."""

import silo_content_generator as scg


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
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", True)
    monkeypatch.setattr(scg, "OpenAI", lambda api_key: fake_client)
    return fake_client


def _configure(monkeypatch, api_key="sk-test-key", **overrides):
    config = {"OPENAI_API_KEY": api_key, **overrides}
    monkeypatch.setattr(scg, "_load_config", lambda: config)


_WELL_FORMED_RESPONSE = """TITLE: Garage Door Spring Replacement in Dallas, TX
META: Fast, reliable garage door spring replacement for Dallas homeowners.
INTRO: A broken spring can leave your garage door unusable overnight.
BODY:
Acme Plumbing's certified technicians replace torsion and extension
springs safely, using OEM-grade parts rated for daily residential use.

Same-day service is available throughout Dallas and Fort Worth for most
spring failures, with upfront pricing before any work begins.
FAQS:
Q: How long does spring replacement take?
A: Most jobs are completed in under an hour.
Q: Is it safe to replace a spring myself?
A: No -- torsion springs are under high tension and require training."""


def test_is_available_false_without_api_key(monkeypatch):
    _configure(monkeypatch, api_key="")
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", True)
    assert scg.is_available() is False


def test_is_available_false_when_openai_package_missing(monkeypatch):
    _configure(monkeypatch, api_key="sk-test-key")
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", False)
    assert scg.is_available() is False


def test_is_available_true_with_key_and_package(monkeypatch):
    _configure(monkeypatch, api_key="sk-test-key")
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", True)
    assert scg.is_available() is True


def test_generate_service_page_content_parses_a_well_formed_response(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, content=_WELL_FORMED_RESPONSE)

    result = scg.generate_service_page_content(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas", "Fort Worth"],
        page_topic="Garage Door Spring Replacement",
        page_kind="service",
        silo_topic="Garage Door Services",
    )

    assert result["title"] == "Garage Door Spring Replacement in Dallas, TX"
    assert "Fast, reliable" in result["meta_description"]
    assert "broken spring" in result["intro"]
    assert "Acme Plumbing's certified technicians" in result["body"]
    assert "Same-day service" in result["body"]
    assert result["faqs"] == [
        {
            "question": "How long does spring replacement take?",
            "answer": "Most jobs are completed in under an hour.",
        },
        {
            "question": "Is it safe to replace a spring myself?",
            "answer": "No -- torsion springs are under high tension and require training.",
        },
    ]


def test_generate_service_page_content_category_prompt_mentions_children(monkeypatch):
    _configure(monkeypatch)
    fake_client = _install_fake_client(monkeypatch, content=_WELL_FORMED_RESPONSE)

    scg.generate_service_page_content(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas"],
        page_topic="Garage Door Repair",
        page_kind="category",
        silo_topic="Garage Door Services",
        child_topics=["Spring Replacement", "Opener Repair"],
    )

    prompt = fake_client.completions.calls[0]["messages"][1]["content"]
    assert "Spring Replacement" in prompt
    assert "Opener Repair" in prompt
    assert "CATEGORY" in prompt


def test_generate_service_page_content_raises_when_response_has_no_title_or_body(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, content="I could not think of anything.")

    try:
        scg.generate_service_page_content(
            business_name="Acme Plumbing",
            business_category="Plumbing",
            target_cities=["Dallas"],
            page_topic="Garage Door Repair",
            page_kind="service",
        )
        assert False, "expected AiContentError"
    except scg.AiContentError as exc:
        assert "TITLE" in str(exc) or "BODY" in str(exc)


def test_generate_service_page_content_tolerates_a_missing_faqs_section(monkeypatch):
    _configure(monkeypatch)
    response = (
        "TITLE: Garage Door Repair\n"
        "META: Reliable garage door repair.\n"
        "INTRO: We fix garage doors fast.\n"
        "BODY:\n"
        "Our team handles every repair with care."
    )
    _install_fake_client(monkeypatch, content=response)

    result = scg.generate_service_page_content(
        business_name="Acme Plumbing",
        business_category="Plumbing",
        target_cities=["Dallas"],
        page_topic="Garage Door Repair",
        page_kind="service",
    )

    assert result["title"] == "Garage Door Repair"
    assert result["faqs"] == []


def test_call_openai_raises_when_package_not_installed(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", False)
    try:
        scg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except scg.AiContentError as exc:
        assert "openai" in str(exc).lower()


def test_call_openai_raises_when_no_api_key_configured(monkeypatch):
    _configure(monkeypatch, api_key="")
    monkeypatch.setattr(scg, "OPENAI_AVAILABLE", True)
    try:
        scg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except scg.AiContentError as exc:
        assert "OPENAI_API_KEY" in str(exc)


def test_call_openai_wraps_client_exceptions(monkeypatch):
    _configure(monkeypatch)
    _install_fake_client(monkeypatch, error=RuntimeError("network exploded"))
    try:
        scg._call_openai("system", "prompt", 100)
        assert False, "expected AiContentError"
    except scg.AiContentError as exc:
        assert "network exploded" in str(exc)
