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
