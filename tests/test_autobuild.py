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
    # AI asked for its money-page title (dropped) plus 2 spares beyond the 3.
    assert calls["title_calls"][0]["title_count"] == 6
    assert job["page_titles"][11:] == ["AI Title 1", "AI Title 2", "AI Title 3"]

    assert job["template"] == "gardinbus-001"
    assert job["directory"] == "commercial-foundation-repair"
    assert set(job["cloud_buckets"].values()) == {"united-structural-systems"}
    assert job["target_link_text"] == "United Structural Systems Of Illinois, Inc"
    # {service} comes from the client website's page: /foundation-repair/.
    assert job["target_link_text_after"] == "to learn more about foundation repair."
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


def test_landing_url_overrides_the_backlink_target(env):
    calls = {}
    url = "https://uss.example/basement-and-crawlspace-waterproofing/"
    result = _draft(env, _services([], calls), landing_url=f"  {url} ")

    assert result.job["landing_url"] == url
    assert result.client_data["* Website"] == url
    # FAQ answers may only use facts on file; the website fact follows too.
    assert calls["faqs"]["company_facts"]["Website"] == url
    # The client file itself keeps its own website.
    saved = yaml.safe_load(env["diagram"].read_text(encoding="utf-8"))
    assert saved["* Website"] == "https://uss.example/foundation-repair/"


def test_landing_url_defaults_to_the_client_website(env):
    result = _draft(env, _services([]))
    assert result.job["landing_url"] == "https://uss.example/foundation-repair/"


@pytest.mark.parametrize(
    "bad", ["uss.example/page", "ftp://uss.example/x", "https://", ""]
)
def test_landing_url_must_be_a_full_http_url(env, bad):
    with pytest.raises(autobuild.AutobuildError, match="landing-url"):
        _draft(env, _services([]), landing_url=bad)


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
    # "...Near Me" titles are skipped outright since 2026-11-06.
    assert autobuild.pick_research_titles(KEYWORD, clusters, 13) == [
        "Foundation Repair Specialists",
    ]


def test_cost_and_near_me_research_titles_are_skipped():
    """Research titles from the 2026-11-06 USS batch the content cannot
    deliver on (it may not state prices)."""
    titles = [
        "Underpinning Cost",
        "How Much Is Underpinning For A Trailer",
        "Helical Piers Price",
        "Foundation Repair Contractors Near Me",
        "Crawl Space Inspection",
    ]
    clusters = [_cluster(t, 1000 - i) for i, t in enumerate(titles)]
    assert autobuild.pick_research_titles("underpinning", clusters, 13) == [
        "Crawl Space Inspection"
    ]


def test_ai_titles_with_claims_are_dropped_and_topped_up(env):
    calls = {}
    services = _services([], calls)
    batches = iter(
        [
            ["money page", "Geneva's Leading Solution", "Plain Title One"]
            + ["Barrington's Premier Repair", "Affordable Waterproofing"],
            ["money page"] + [f"Plain Title {i}" for i in range(2, 20)],
        ]
    )
    services.generate_titles = lambda **k: next(batches)
    result = _draft(env, services)
    titles = result.job["page_titles"]
    assert len(titles) == 14
    assert not any(
        word in t for t in titles for word in ("Leading", "Premier", "Affordable")
    )
    assert "Plain Title One" in titles


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://uss.example/foundation-repair/", "foundation repair"),
        (
            "https://uss.example/basement-and-crawlspace-waterproofing/",
            "basement and crawlspace waterproofing",
        ),
        ("https://uss.example/services/helical_piers.html?x=1", "helical piers"),
        ("https://uss.example/", "fallback"),
        ("https://uss.example", "fallback"),
    ],
)
def test_link_topic_from_url(url, expected):
    assert autobuild.link_topic_from_url(url, "fallback") == expected


def test_link_sentence_names_the_landing_page_topic(env):
    result = _draft(
        env,
        _services([]),
        landing_url="https://uss.example/resistance-and-micro-pile-installation/",
    )
    assert result.job["target_link_text_after"] == (
        "to learn more about resistance and micro pile installation."
    )


def test_link_topic_override(env):
    result = _draft(env, _services([]), link_topic="  underpinning  ")
    assert result.job["target_link_text_after"] == "to learn more about underpinning."


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


# --------------------------------------------------------------------------
# --submit (factory runner faked; nothing reaches YACSS)
# --------------------------------------------------------------------------

ONBOARD_OK = "cloud (account 25398): exists -- already exists\n" + (
    autobuild.NOTHING_TO_CREATE
)


def _runner(responses):
    calls = []

    def run(args):
        calls.append(args)
        return responses[args[0]]

    return run, calls


def _log():
    lines = []
    return lines, lines.append


def test_submit_checks_bucket_then_drafts_without_confirm(env, tmp_path):
    result = _draft(env, _services([]))
    run, calls = _runner(
        {"onboard-client": (0, ONBOARD_OK), "all": (0, "created: 1, failed: 0")}
    )
    lines, log = _log()
    manifest = tmp_path / "m.json"
    manifest.write_text("{}", encoding="utf-8")

    assert autobuild.submit(result, run=run, log=log, manifest=manifest) == 0
    accounts = ",".join(result.job["cloud_buckets"])
    assert calls == [
        ["onboard-client", "united-structural-systems", "-a", accounts],
        ["all", "-f", f"jobs/{result.job_id}.json"],
    ]
    assert not any("--confirm" in arg for call in calls for arg in call)
    text = "\n".join(lines)
    assert f"src/cli.ts all -f jobs/{result.job_id}.json --confirm" in text
    assert "also generates" not in text


def test_submit_stops_on_warnings_without_calling_the_factory(env):
    services = _services([])
    services.generate_content = lambda **k: "Too short."
    result = _draft(env, services)
    run, calls = _runner({})
    lines, log = _log()

    assert autobuild.submit(result, run=run, log=log) == 1
    assert calls == []
    assert any("fix the warnings" in line for line in lines)


def test_submit_stops_when_bucket_is_missing(env):
    result = _draft(env, _services([]))
    missing = "aws (account 11883): create -- would create\nDry-run (no --confirm passed): 1 account(s) would be changed."
    run, calls = _runner({"onboard-client": (0, missing)})
    lines, log = _log()

    assert autobuild.submit(result, run=run, log=log) == 1
    assert [c[0] for c in calls] == ["onboard-client"]
    assert any(
        "united-structural-systems -a" in line and "--confirm" in line for line in lines
    )


def test_submit_reports_a_factory_failure(env, tmp_path):
    result = _draft(env, _services([]))
    run, _calls = _runner(
        {"onboard-client": (0, ONBOARD_OK), "all": (1, "[failed] ... 422")}
    )
    lines, log = _log()
    assert autobuild.submit(result, run=run, log=log, manifest=tmp_path / "x") == 1
    assert not any(".json --confirm" in line for line in lines)


def test_submit_skips_bucket_check_for_unpinned_job(env, tmp_path):
    result = _draft(env, _services([]))
    del result.job["cloud_buckets"]
    run, calls = _runner({"all": (0, "ok")})
    _lines, log = _log()
    assert autobuild.submit(result, run=run, log=log, manifest=tmp_path / "x") == 0
    assert [c[0] for c in calls] == ["all"]


def test_submit_lists_other_drafted_jobs(env, tmp_path):
    result = _draft(env, _services([]))
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            {
                result.job_id: {"status": "drafted", "build_id": "1"},
                "other-job": {"status": "drafted", "build_id": "2"},
                "done-job": {"status": "published", "build_id": "3"},
            }
        ),
        encoding="utf-8",
    )
    run, _calls = _runner({"onboard-client": (0, ONBOARD_OK), "all": (0, "ok")})
    lines, log = _log()
    autobuild.submit(result, run=run, log=log, manifest=manifest)
    text = "\n".join(lines)
    assert "also generates these other drafted jobs" in text
    assert "other-job (build 2)" in text
    assert "done-job" not in text


def test_batch_position_gives_each_stack_its_own_images(env, tmp_path):
    # 14 pages (house profile) and 30 client images: stack 0 gets images
    # 1-14, stack 1 gets 15-28, and both client YAMLs keep the full list.
    urls = [f"https://uss.example/img-{i}.jpg" for i in range(1, 31)]
    source = tmp_path / "with-images.yaml"
    source.write_text(
        yaml.dump(_client_file(**{"Content Image URLs (one per line)": urls})),
        encoding="utf-8",
    )

    first = _draft(env, _services(), from_file=source)
    second = _draft(env, _services(), from_file=source, batch_position=1)

    assert first.job["content_image_urls"] == urls[0:14]
    assert second.job["content_image_urls"] == urls[14:28]
    assert first.client_data["Content Image URLs (one per line)"] == urls
    assert not any("never be used" in w for w in second.warnings)


def test_batch_position_option_reaches_draft_stack(monkeypatch):
    seen = {}

    def fake_draft(*args, **kwargs):
        seen.update(kwargs)
        raise autobuild.AutobuildError("stop here")

    monkeypatch.setattr(autobuild, "draft_stack", fake_draft)

    code = autobuild.main(["--client", "x", "--keyword", "y", "--batch-position", "3"])

    assert code == 1
    assert seen["batch_position"] == 3
