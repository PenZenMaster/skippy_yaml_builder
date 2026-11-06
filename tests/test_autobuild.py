"""Tests for autobuild: the client + keyword -> client YAML + job JSON
pipeline. Every external service (DataForSEO, OpenAI, image checks) is
stubbed, and all files live under tmp_path."""

import json
import os

import pytest
import yaml

import autobuild
from faq_generation import SOURCE_AI, SOURCE_GOOGLE, FaqGenerationResult, FaqItem
from keyword_research_api import KeywordResearchError

KEYWORD = "commercial foundation repair"


def _client_file(**overrides):
    data = {
        "* Client Name": "UNITED STRUCTURAL SYSTEMS OF ILLINOIS, INC",
        "* Business Category": "concrete contractor",
        "* Phone": "847-382-2882",
        "Email": "rick@example.com",
        "* Website": "https://uss.example/foundation-repair/",
        "Street Address": "2124 Stonington Ave",
        "City": "Hoffman Estates",
        "State": "IL",
        "ZIP": "60169",
        "* Target Cities (one per line)": ["Wheaton, IL", "Elmhurst, IL"],
        "* Services (one per line)": ["Foundation Repair", "Micro Pile Installation"],
        "Hero Image URL": "https://uss.example/hero.jpg",
        "YACSS Build Type": "Diagram",
        "YACSS Bucket Keyword": "Commercial Micro Pile Installer",
        "YACSS Pinned Bucket": "united-structural-systems",
        "YACSS Stack Folder": "commercial-micro-pile-installer",
        "YACSS AI Model": "gpt-3.5-turbo",
        "YACSS Diagram Page Titles (one per line)": ["Old title"] * 14,
        "YACSS Diagram Content": "Old content.",
        "FAQ Questions & Answers": [{"question": "Old?", "answer": "Old."}],
    }
    data.update(overrides)
    return data


@pytest.fixture
def env(tmp_path):
    root = tmp_path / "client_yaml"
    folder = root / "united_structural_systems"
    folder.mkdir(parents=True)
    diagram = folder / "uss-stack.yaml"
    diagram.write_text(yaml.dump(_client_file()), encoding="utf-8")
    listicle = folder / "uss-listicle.yaml"
    listicle.write_text(
        yaml.dump({"* Client Name": "x", "YACSS Build Type": "Listicle"}),
        encoding="utf-8",
    )
    # The listicle is newer, so "newest Diagram" must skip it.
    os.utime(diagram, (1_000_000, 1_000_000))
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    return {
        "root": root,
        "folder": folder,
        "diagram": diagram,
        "jobs": jobs,
        "manifest": manifest,
    }


def _cluster(title, volume, flagged=False):
    return {
        "candidate_page_title": title,
        "total_search_volume": volume,
        "candidate_page_title_flagged": flagged,
    }


def _services(clusters=None, calls=None):
    calls = calls if calls is not None else {}

    def fetch(seeds, local_tokens):
        calls["seeds"] = seeds
        calls["local_tokens"] = local_tokens
        return clusters if clusters is not None else []

    def titles(**kwargs):
        calls.setdefault("title_calls", []).append(kwargs)
        n = kwargs["title_count"]
        return [f"AI Title {i}" for i in range(n)]

    def content(**kwargs):
        calls["content"] = kwargs
        return " ".join(["word"] * 400) + "\n\n" + " ".join(["more"] * 400)

    def faqs(**kwargs):
        calls["faqs"] = kwargs
        items = [FaqItem(f"Google Q{i}?", f"A{i}.", SOURCE_GOOGLE) for i in range(10)]
        items += [FaqItem(f"AI Q{i}?", f"A{i}.", SOURCE_AI) for i in range(5)]
        return FaqGenerationResult(requested=kwargs["count"], items=items)

    return autobuild.Services(
        ai_available=lambda: True,
        fetch_clusters=fetch,
        generate_titles=titles,
        generate_content=content,
        generate_faqs=faqs,
        check_images=lambda items: [],
    )


def _draft(env, services, **kwargs):
    return autobuild.draft_stack(
        "United Structural Systems",
        KEYWORD,
        client_root=env["root"],
        jobs_dir=env["jobs"],
        manifest=env["manifest"],
        services=services,
        **kwargs,
    )


TOPICS = [
    "Helical",
    "Pier",
    "Slab",
    "Crack",
    "Basement",
    "Crawlspace",
    "Waterproofing",
    "Underpinning",
    "Leveling",
    "Drainage",
]


def test_full_draft_with_research_and_ai_top_up(env):
    clusters = [
        _cluster(f"{word} Repair Work", 1000 - i) for i, word in enumerate(TOPICS)
    ]
    clusters.append(_cluster("Lowes Foundation Repair", 5000, flagged=True))
    clusters.append(_cluster("commercial foundation repair", 9000))  # = keyword
    calls = {}
    result = _draft(env, _services(clusters, calls))

    assert result.source_file == env["diagram"]
    assert result.job_id == "united-structural-systems-commercial-foundation-repair"
    job = result.job
    assert len(job["page_titles"]) == 14
    assert job["page_titles"][0] == "Commercial Foundation Repair"
    assert job["page_titles"][1] == "Helical Repair Work"
    assert "Lowes Foundation Repair" not in job["page_titles"]
    assert result.title_sources == ["keyword"] + ["research"] * 10 + ["AI"] * 3
    # AI asked for one extra (its first title is a money page) and it was dropped.
    assert calls["title_calls"][0]["title_count"] == 4
    assert job["page_titles"][11:] == ["AI Title 1", "AI Title 2", "AI Title 3"]

    assert job["template"] == "gardinbus-001"
    assert job["directory"] == "commercial-foundation-repair"
    assert set(job["cloud_buckets"].values()) == {"united-structural-systems"}
    assert job["target_link_text"] == "United Structural Systems Of Illinois, Inc"
    assert job["target_link_text_after"] == f"to learn more about {KEYWORD}."
    assert job["company"]["phone"] == "(847) 382-2882"
    assert job["job_id"] == result.job_id
    assert len(job["faqs"]) == 15
    assert job["content"].startswith("<p>word")
    assert result.warnings == []

    assert calls["seeds"] == [KEYWORD]
    assert calls["faqs"]["count"] == 15
    assert (
        calls["faqs"]["business_name"] == "United Structural Systems Of Illinois, Inc"
    )
    assert calls["content"]["target_keyword"] == KEYWORD


def test_nothing_is_written_by_draft_and_write_outputs_writes_both(env):
    result = _draft(env, _services([]))
    assert not result.client_yaml_path.exists()
    assert not result.job_json_path.exists()

    autobuild.write_outputs(result)
    saved = yaml.safe_load(result.client_yaml_path.read_text(encoding="utf-8"))
    assert saved["YACSS Job ID (override)"] == result.job_id
    assert saved["YACSS Stack Folder"] == ""
    assert saved["YACSS AI Model"] == "gpt-5"
    jobs = json.loads(result.job_json_path.read_text(encoding="utf-8"))
    assert jobs == [result.job]
    # The source client file is untouched.
    assert yaml.safe_load(env["diagram"].read_text(encoding="utf-8")) == _client_file()

    with pytest.raises(autobuild.AutobuildError, match="already exists"):
        autobuild.write_outputs(result)


def test_job_id_skips_manifest_entries_and_existing_job_files(env):
    base = "united-structural-systems-commercial-foundation-repair"
    env["manifest"].write_text(json.dumps({base: {}}), encoding="utf-8")
    (env["jobs"] / f"{base}-02.json").write_text("[]", encoding="utf-8")
    result = _draft(env, _services([]))
    assert result.job_id == f"{base}-03"


def test_research_failure_propagates_before_any_ai_spend(env):
    services = _services([])
    called = []
    services.generate_content = lambda **k: called.append("content") or "x"

    def boom(seeds, tokens):
        raise KeywordResearchError("quota exceeded")

    services.fetch_clusters = boom
    with pytest.raises(KeywordResearchError, match="quota"):
        _draft(env, services)
    assert called == []
    assert list(env["jobs"].iterdir()) == []


def test_ai_unavailable_stops_before_research(env):
    services = _services([])
    services.ai_available = lambda: False
    services.fetch_clusters = lambda *a: pytest.fail("research should not run")
    with pytest.raises(autobuild.AutobuildError, match="OPENAI_API_KEY"):
        _draft(env, services)


def test_ai_titles_that_never_reach_the_count_stop(env):
    services = _services([])
    services.generate_titles = lambda **k: ["Only One", "AI dup"]
    with pytest.raises(autobuild.AutobuildError, match="Needed 14 page titles"):
        _draft(env, services)


def test_short_content_and_faqs_are_warned(env):
    services = _services([])
    services.generate_content = lambda **k: "Too short."
    services.generate_faqs = lambda **k: FaqGenerationResult(
        requested=15, items=[FaqItem("Q?", "", SOURCE_GOOGLE)]
    )
    result = _draft(env, services)
    assert any("rendered words" in w for w in result.warnings)
    assert "Only 1 of 15 FAQs were generated" in result.warnings
    assert any("blank answer" in w for w in result.warnings)


def test_from_file_overrides_newest(env, tmp_path):
    other = tmp_path / "other.yaml"
    other.write_text(
        yaml.dump(_client_file(**{"* Client Name": "Acme Mixed Case"})),
        encoding="utf-8",
    )
    result = _draft(env, _services([]), from_file=other)
    assert result.source_file == other
    assert result.job["target_link_text"] == "Acme Mixed Case"


def test_find_client_dir(env):
    assert (
        autobuild.find_client_dir("united-structural-systems", env["root"])
        == env["folder"]
    )
    with pytest.raises(autobuild.AutobuildError, match="united_structural_systems"):
        autobuild.find_client_dir("United Structural", env["root"])


def test_no_diagram_file(tmp_path):
    folder = tmp_path / "acme"
    folder.mkdir()
    (folder / "a.yaml").write_text("YACSS Build Type: Listicle\n", encoding="utf-8")
    with pytest.raises(autobuild.AutobuildError, match="--from"):
        autobuild.newest_diagram_file(folder)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("774-444-2014", "(774) 444-2014"),
        ("(774) 444-2014", "(774) 444-2014"),
        ("+1 774 444 2014", "+1 774 444 2014"),
        ("", ""),
        (None, ""),
    ],
)
def test_tidy_phone(raw, expected):
    assert autobuild.tidy_phone(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            "UNITED STRUCTURAL SYSTEMS OF ILLINOIS, INC",
            "United Structural Systems Of Illinois, Inc",
        ),
        ("McDonald's Plumbing", "McDonald's Plumbing"),
        ("ACME", "Acme"),
        ("123", "123"),
    ],
)
def test_display_name(raw, expected):
    assert autobuild.display_name(raw) == expected


def test_summary_marks_ai_titles_and_faqs(env):
    result = _draft(env, _services([]))
    text = autobuild.summary(result)
    assert "[      AI] AI Title 1" in text
    assert "[AI] AI Q0?" in text
    assert "15 (10 Google, 5 AI)" in text
    assert (
        "united-structural-systems (pinned), folder commercial-foundation-repair/"
        in text
    )
    assert "Google showed no People Also Ask" not in text


def test_summary_explains_when_google_has_no_questions(env):
    services = _services([])
    services.generate_faqs = lambda **k: FaqGenerationResult(
        requested=15,
        items=[FaqItem(f"AI Q{i}?", "A.", SOURCE_AI) for i in range(15)],
        searched_phrases=[KEYWORD, f"{KEYWORD} Wheaton"],
    )
    result = _draft(env, services)
    assert result.faq_searched == [KEYWORD, f"{KEYWORD} Wheaton"]
    assert (
        "Google showed no People Also Ask questions for: "
        f"{KEYWORD}; {KEYWORD} Wheaton" in autobuild.summary(result)
    )


def test_near_duplicate_research_titles_are_skipped():
    """The research titles from the 2026-11-05 live USS run, in volume
    order. Covered-word duplicates go; distinct ones stay."""
    clusters = [
        _cluster(title, 1000 - i)
        for i, title in enumerate(
            [
                "Foundation Repair Near Me",
                "Foundation Repair Specialists",
                "Foundation Specialist",
                "Foundation Repair Companies Near Me",
                "Foundation Repair Specialists Near Me",
                "Best Foundation Repair Company Near Me",
            ]
        )
    ]
    assert autobuild.pick_research_titles(KEYWORD, clusters, 13) == [
        "Foundation Repair Specialists",
        "Foundation Repair Companies Near Me",
    ]


def test_research_titles_stop_at_needed():
    clusters = [_cluster(f"{w} Repair Work", 100) for w in TOPICS]
    assert len(autobuild.pick_research_titles(KEYWORD, clusters, 3)) == 3


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "Best Foundation Repair Companies Near Me",
            {"foundation", "repair", "company"},
        ),
        ("Foundation Specialists", {"foundation", "specialist"}),
        ("Near Me", set()),
    ],
)
def test_title_words(text, expected):
    assert autobuild.title_words(text) == expected
