"""Tests for stack_profile: loading the house profile and merging it over a
client file so job_export can build a Cloud Stack from client + keyword."""

import pytest

import job_export
import stack_profile


def _client():
    """Client facts plus some stale build settings an older file carries."""
    return {
        "* Client Name": "Acme Plumbing",
        "* Phone": "(214) 555-0100",
        "Email": "info@acmeplumbing.example",
        "* Website": "https://acmeplumbing.example",
        "Street Address": "123 Main St",
        "City": "Dallas",
        "State": "TX",
        "ZIP": "75201",
        "YACSS Pinned Bucket": "acme-plumbing",
        "YACSS AI Model": "gpt-3.5-turbo",
        "YACSS Tone": "Persuasive",
        "YACSS Bucket Keyword": "old keyword",
    }


def test_default_profile_loads_and_has_house_settings():
    profile = stack_profile.load_profile()
    assert profile["YACSS Build Type"] == "Diagram"
    assert profile["YACSS Template"] == "gardinbus-001"
    assert job_export.parse_tier_lines(
        profile["YACSS Tiers (tier:pages, one per line)"]
    ) == [(1, "1"), (2, "6"), (3, "1")]
    assert [
        r["cloud_account_ids"] for r in profile["YACSS Diagram Tier Cloud Account IDs"]
    ] == ["25398", "27504,25701,14308,11884,11883", "25701"]


def test_profile_wins_and_client_facts_stay():
    merged = stack_profile.apply_profile(
        _client(), stack_profile.load_profile(), "commercial foundation repair"
    )
    assert merged["YACSS AI Model"] == "gpt-5"
    assert merged["YACSS Tone"] == "ProfessionalWarm"
    assert merged["YACSS Bucket Keyword"] == "commercial foundation repair"
    assert merged["* Phone"] == "(214) 555-0100"
    assert merged["YACSS Pinned Bucket"] == "acme-plumbing"
    assert merged["YACSS Text Of Target Link"] == "Acme Plumbing"
    assert (
        merged["YACSS Text After Target Link"]
        == "to learn more about commercial foundation repair."
    )


def test_apply_profile_does_not_change_client_data():
    client = _client()
    stack_profile.apply_profile(client, stack_profile.load_profile(), "x")
    assert client == _client()


def test_merged_data_builds_a_14_page_pinned_stack():
    merged = stack_profile.apply_profile(
        _client(), stack_profile.load_profile(), "commercial foundation repair"
    )
    merged["YACSS Diagram Page Titles (one per line)"] = [
        f"Title {i}" for i in range(1, 15)
    ]
    merged["YACSS Diagram Content"] = "Some content."
    job, warnings = job_export.build_job(merged)
    assert warnings == []
    assert job["template"] == "gardinbus-001"
    assert [t["pages"] for t in job["tiers"]] == [1, 6, 1]
    assert job["directory"] == "commercial-foundation-repair"
    assert set(job["cloud_buckets"]) == {
        "25398",
        "27504",
        "25701",
        "14308",
        "11884",
        "11883",
    }
    assert "content_mode" not in job


def test_blank_keyword_is_rejected():
    with pytest.raises(ValueError, match="keyword"):
        stack_profile.apply_profile(_client(), {}, "  ")


def test_profile_may_not_set_client_fields(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("YACSS Template: x\n'* Client Name': Someone\n", encoding="utf-8")
    with pytest.raises(stack_profile.StackProfileError, match="Client Name"):
        stack_profile.load_profile(path)


def test_missing_or_malformed_profile(tmp_path):
    with pytest.raises(stack_profile.StackProfileError, match="Cannot read"):
        stack_profile.load_profile(tmp_path / "nope.yaml")
    path = tmp_path / "list.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(stack_profile.StackProfileError, match="mapping"):
        stack_profile.load_profile(path)


def test_other_braces_are_left_alone():
    merged = stack_profile.apply_profile(
        _client(), {"YACSS Text After Target Link": "{a|b} {keyword}"}, "kw"
    )
    assert merged["YACSS Text After Target Link"] == "{a|b} kw"
