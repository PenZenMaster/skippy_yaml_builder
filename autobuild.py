"""
Module/Script Name: autobuild.py
Path: E:\\projects\\skippy_yaml_builder\\autobuild.py

Description:
Drafts a complete YACSS Cloud Stack from just a client and a keyword,
without the GUI:

  venv/Scripts/python.exe autobuild.py --client "United Structural Systems"
      --keyword "commercial foundation repair"

1. Client facts come from the newest Diagram-type file in
   client_yaml/<client>/ (or --from FILE); a 10-digit phone is tidied to
   (xxx) xxx-xxxx, as the app does when opening a file.
2. The stack profile (stack_profiles/default.yaml, or --profile) supplies
   every build setting (stack_profile.apply_profile).
3. Page titles: title 1 is the keyword (the money page); the rest are the
   top unflagged keyword-research clusters by search volume, topped up by
   AI when research gives too few.
4. Spun content (AI) and 15 FAQs (Google People Also Ask, AI top-up).
5. job_export builds the job; images are size-checked (advisory).

Writes client_yaml/<client>/<job-id>.yaml (openable in the app) and
../rr_yacss_factory/jobs/<job-id>.json, then prints a summary. It never
calls rr_yacss_factory or YACSS -- nothing spends YACSS credits. If any
research/AI step fails it stops and writes nothing. The job id is
<client-folder>-<keyword>, with -02, -03... added when a job file or
manifest entry of that name already exists.

Author(s):
Rank Rocket Co (C) Copyright 2026 - All Rights Reserved

Created Date:
2026-11-05

Last Modified Date:
2026-11-05

Comments:
- v1.00 Initial implementation.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

import job_export
import stack_profile
from faq_generation import SOURCE_AI as FAQ_SOURCE_AI

ROOT = Path(__file__).resolve().parent
CLIENT_YAML_DIR = ROOT / "client_yaml"
FACTORY_DIR = ROOT.parent / "rr_yacss_factory"
FACTORY_JOBS_DIR = FACTORY_DIR / "jobs"
FACTORY_MANIFEST = FACTORY_DIR / "state" / "manifest.json"

FAQ_COUNT = 15

PAGE_TITLES_FIELD = "YACSS Diagram Page Titles (one per line)"
CONTENT_FIELD = "YACSS Diagram Content"
FAQ_FIELD = "FAQ Questions & Answers"

SOURCE_KEYWORD = "keyword"
SOURCE_RESEARCH = "research"
SOURCE_AI = "AI"


class AutobuildError(Exception):
    """Autobuild cannot continue; nothing has been written."""


# --------------------------------------------------------------------------
# External services, injectable so tests never touch the network. The
# defaults import lazily, so importing this module needs no API keys.
# --------------------------------------------------------------------------


def _default_ai_available() -> bool:
    from ai_content_generator import is_available

    return is_available()


def _default_fetch_clusters(seeds: list[str], local_tokens: set[str]) -> list[dict]:
    from keyword_research_api import fetch_clusters

    return fetch_clusters(seeds, local_tokens)


def _default_generate_titles(**kwargs: Any) -> list[str]:
    from ai_content_generator import generate_diagram_page_titles

    return generate_diagram_page_titles(**kwargs)


def _default_generate_content(**kwargs: Any) -> str:
    from ai_content_generator import generate_diagram_content

    return generate_diagram_content(**kwargs)


def _default_generate_faqs(**kwargs: Any) -> Any:
    from faq_generation import generate_faqs

    return generate_faqs(**kwargs)


def _default_check_images(items: list[tuple[str, str]]) -> list[str]:
    from image_size_check import check_image_sizes

    return check_image_sizes(items)


@dataclass
class Services:
    ai_available: Callable[[], bool] = _default_ai_available
    fetch_clusters: Callable[[list[str], set[str]], list[dict]] = (
        _default_fetch_clusters
    )
    generate_titles: Callable[..., list[str]] = _default_generate_titles
    generate_content: Callable[..., str] = _default_generate_content
    generate_faqs: Callable[..., Any] = _default_generate_faqs
    check_images: Callable[[list[tuple[str, str]]], list[str]] = _default_check_images


@dataclass
class AutobuildResult:
    job_id: str
    source_file: Path
    client_yaml_path: Path
    job_json_path: Path
    client_data: dict[str, Any]
    job: dict[str, Any]
    title_sources: list[str]
    faq_sources: list[str]
    content_words: int
    warnings: list[str] = field(default_factory=list)
    # Google searches made for People Also Ask questions.
    faq_searched: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# Small pure helpers
# --------------------------------------------------------------------------


def _norm(name: str) -> str:
    return " ".join(re.split(r"[-_\s]+", name.strip().lower())).strip()


def find_client_dir(client: str, root: Path = CLIENT_YAML_DIR) -> Path:
    """The client_yaml/<folder> whose name matches `client`, ignoring case
    and treating -, _ and spaces alike ("United Structural Systems" ->
    united_structural_systems)."""
    wanted = _norm(client)
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    for folder in folders:
        if _norm(folder.name) == wanted:
            return folder
    first_word = wanted.split(" ")[0] if wanted else ""
    close = [f.name for f in folders if first_word and first_word in _norm(f.name)]
    hint = f" Close matches: {', '.join(close)}." if close else ""
    raise AutobuildError(f"No client folder for {client!r} in {root}.{hint}")


def newest_diagram_file(client_dir: Path) -> Path:
    """The most recently modified .yaml/.yml in client_dir whose YACSS Build
    Type is Diagram."""
    candidates = sorted(
        (p for p in client_dir.iterdir() if p.suffix.lower() in (".yaml", ".yml")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        data = _read_yaml(path)
        if str(data.get(job_export.BUILD_TYPE_FIELD) or "").strip() == "Diagram":
            return path
    raise AutobuildError(
        f"No Diagram client file in {client_dir} -- use --from to name one"
    )


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise AutobuildError(f"Cannot read {path}: {e}") from e
    if not isinstance(data, dict):
        raise AutobuildError(f"{path} is not a client file (expected a mapping)")
    return data


def tidy_phone(value: Any) -> str:
    """A value with exactly 10 digits becomes (xxx) xxx-xxxx, as the app's
    phone field shows it after opening a file; anything else is unchanged."""
    text = "" if value is None else str(value)
    digits = re.sub(r"\D", "", text)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return text


def display_name(name: str) -> str:
    """An ALL-CAPS name gets capitalised words ("UNITED STRUCTURAL
    SYSTEMS OF ILLINOIS, INC" -> "United Structural Systems Of Illinois,
    Inc"); a mixed-case name is returned exactly as typed."""
    name = name.strip()
    if any(c.isalpha() for c in name) and name == name.upper():
        return " ".join(w[:1].upper() + w[1:].lower() for w in name.split(" "))
    return name


def title_case(text: str) -> str:
    """Capitalises the first letter of each word, leaving the rest alone
    (same as keyword research's own candidate titles)."""
    return " ".join(w[:1].upper() + w[1:] if w else w for w in text.split(" "))


def unique_job_id(
    base: str, jobs_dir: Path = FACTORY_JOBS_DIR, manifest: Path = FACTORY_MANIFEST
) -> str:
    """base, or base-02, base-03, ... -- the first that has neither a job
    file in jobs_dir nor an entry in rr_yacss_factory's manifest."""
    taken: set[str] = set()
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise AutobuildError(f"Cannot read factory manifest {manifest}: {e}")
        if isinstance(data, dict):
            taken.update(data)

    def free(job_id: str) -> bool:
        return job_id not in taken and not (jobs_dir / f"{job_id}.json").exists()

    if free(base):
        return base
    for n in range(2, 100):
        candidate = f"{base}-{n:02d}"
        if free(candidate):
            return candidate
    raise AutobuildError(f"No free job id for {base!r} (tried up to -99)")


def pick_research_titles(keyword: str, clusters: list[dict], needed: int) -> list[str]:
    """Up to `needed` candidate titles from the clusters, highest search
    volume first, skipping flagged ones (possible competitor brand,
    off-target location) and near-duplicates: a title is skipped when all
    its meaningful words (title_words) already appear in one title picked
    before it, the keyword included. E.g. with the keyword "commercial
    foundation repair", "Foundation Repair Near Me" is skipped, and after
    "Foundation Repair Specialists", "Foundation Specialist" is too."""
    picked = [title_words(keyword)]
    titles: list[str] = []
    for cluster in sorted(
        clusters, key=lambda c: c.get("total_search_volume", 0), reverse=True
    ):
        if len(titles) >= needed:
            break
        if cluster.get("candidate_page_title_flagged"):
            continue
        title = str(cluster.get("candidate_page_title") or "").strip()
        words = title_words(title)
        if not words or any(words <= earlier for earlier in picked):
            continue
        picked.append(words)
        titles.append(title)
    return titles


def title_words(text: str) -> set[str]:
    """A title's meaningful words: keyword research's own significant
    tokens (stopwords such as near, me, best, the dropped; a plural "s"
    dropped), plus "ies" plurals made singular so Companies = Company."""
    from keyword_research_api import significant_tokens

    return {
        token[:-2] + "y" if token.endswith("ie") else token
        for token in significant_tokens(text)
    }


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------


def draft_stack(
    client: str,
    keyword: str,
    *,
    from_file: Path | None = None,
    profile_path: Path = stack_profile.DEFAULT_PROFILE,
    client_root: Path = CLIENT_YAML_DIR,
    jobs_dir: Path = FACTORY_JOBS_DIR,
    manifest: Path = FACTORY_MANIFEST,
    services: Services | None = None,
    log: Callable[[str], None] = lambda _msg: None,
) -> AutobuildResult:
    """Runs every step and returns the drafted client data and job without
    writing anything (see write_outputs). Raises AutobuildError (or the
    research/AI module's own error) on any failure."""
    services = services or Services()
    keyword = " ".join(keyword.split())
    if not keyword:
        raise AutobuildError("A keyword is required")

    client_dir = find_client_dir(client, client_root)
    source = Path(from_file) if from_file else newest_diagram_file(client_dir)
    log(f"Client facts from {source}")
    client_data = _read_yaml(source)
    try:
        profile = stack_profile.load_profile(profile_path)
    except stack_profile.StackProfileError as e:
        raise AutobuildError(str(e)) from e

    if not services.ai_available():
        raise AutobuildError(
            "AI generation is not available -- set OPENAI_API_KEY in "
            "cloud-stack-generator's .env (../cloud-stack-generator/.env)"
        )

    data = stack_profile.apply_profile(client_data, profile, keyword)
    for phone_field in ("* Phone", "Broker Phone"):
        if phone_field in data:
            data[phone_field] = tidy_phone(data[phone_field])
    business_name = display_name(str(data.get("* Client Name") or ""))
    if (
        data.get("YACSS Text Of Target Link")
        == str(data.get("* Client Name") or "").strip()
    ):
        data["YACSS Text Of Target Link"] = business_name

    base_id = job_export.slugify(f"{client_dir.name} {keyword}")
    job_id = unique_job_id(base_id, jobs_dir, manifest)
    # Per-build fields from the old file must not leak into this stack:
    # its folder (would collide in the pinned bucket) and job id.
    data["YACSS Job ID (override)"] = job_id
    data["YACSS Stack Folder"] = ""

    tier0 = int(str(data.get("YACSS Tier0 Pages") or "0").strip() or "0")
    tiers = job_export.parse_tier_lines(
        str(data.get("YACSS Tiers (tier:pages, one per line)") or "")
    )
    needed = job_export.compute_cloud_stack_total_pages(
        tier0, [job_export.tier_page_count(p) for _, p in tiers]
    )
    if needed < 1:
        raise AutobuildError("The stack profile's tiers give 0 pages")

    category = str(data.get("* Business Category") or "").strip()
    cities = _lines(data.get("* Target Cities (one per line)"))
    services_list = _lines(data.get("* Services (one per line)"))

    # Page titles: keyword first, then research, then AI top-up.
    from keyword_research_api import local_location_tokens

    log("Keyword research (DataForSEO)...")
    clusters = services.fetch_clusters(
        [keyword], local_location_tokens(str(data.get("State") or ""), cities)
    )
    titles = [title_case(keyword)]
    sources = [SOURCE_KEYWORD]
    research = pick_research_titles(keyword, clusters, needed - 1)
    titles += research
    sources += [SOURCE_RESEARCH] * len(research)
    shortfall = needed - len(titles)
    if shortfall > 0:
        log(f"Research gave {len(research)} usable title(s); AI writes {shortfall}")
        seen = {_norm(t) for t in titles}
        ai_titles: list[str] = []
        for _attempt in range(2):
            # The AI prompt treats its first title as the money page; ask
            # for one extra and drop it, since title 1 is already set.
            generated = services.generate_titles(
                business_name=business_name,
                business_category=category,
                target_keyword=keyword,
                target_cities=cities,
                services=services_list,
                title_count=shortfall + 1,
            )
            for title in generated[1:]:
                if len(ai_titles) < shortfall and _norm(title) not in seen:
                    seen.add(_norm(title))
                    ai_titles.append(title)
            if len(ai_titles) >= shortfall:
                break
        if len(ai_titles) < shortfall:
            raise AutobuildError(
                f"Needed {needed} page titles but got only "
                f"{len(titles) + len(ai_titles)} after research and AI"
            )
        titles += ai_titles
        sources += [SOURCE_AI] * len(ai_titles)
    data[PAGE_TITLES_FIELD] = titles

    log("Writing spun content (AI)...")
    from ai_content_generator import MIN_DIAGRAM_CONTENT_WORDS, count_rendered_words

    content = services.generate_content(
        business_name=business_name,
        business_category=category,
        target_keyword=keyword,
        target_cities=cities,
        services=services_list,
        city=str(data.get("City") or ""),
        state=str(data.get("State") or ""),
    ).strip()
    if not content:
        raise AutobuildError("AI returned no content")
    data[CONTENT_FIELD] = content
    words = count_rendered_words(content)

    log(f"FAQs: People Also Ask + AI ({FAQ_COUNT})...")
    company_facts = {
        "Legal name": str(data.get("Legal / Company Name") or ""),
        "Street address": str(data.get("Street Address") or ""),
        "City": str(data.get("City") or ""),
        "State": str(data.get("State") or ""),
        "ZIP": str(data.get("ZIP") or ""),
        "Phone": str(data.get("* Phone") or ""),
        "Email": str(data.get("Email") or data.get("Contact Email Address") or ""),
        "Website": str(data.get("* Website") or ""),
    }
    faq_result = services.generate_faqs(
        seed_keyword=keyword,
        business_name=business_name,
        business_category=category,
        target_cities=cities,
        services=services_list,
        count=FAQ_COUNT,
        company_facts=company_facts,
    )
    faq_items = list(faq_result.items)
    data[FAQ_FIELD] = [{"question": i.question, "answer": i.answer} for i in faq_items]
    faq_sources = [i.source for i in faq_items]

    job, warnings = job_export.build_job(data)
    if words < MIN_DIAGRAM_CONTENT_WORDS:
        warnings.append(
            f"Content is {words} rendered words, below the {MIN_DIAGRAM_CONTENT_WORDS} minimum"
        )
    if len(faq_items) < FAQ_COUNT:
        warnings.append(f"Only {len(faq_items)} of {FAQ_COUNT} FAQs were generated")
    blank = sum(1 for i in faq_items if not i.answer)
    if blank:
        warnings.append(f"{blank} FAQ(s) have a blank answer -- fill them in the app")
    log("Checking image sizes...")
    warnings += services.check_images(job_export.image_check_items(job))

    return AutobuildResult(
        job_id=job_id,
        source_file=source,
        client_yaml_path=client_dir / f"{job_id}.yaml",
        job_json_path=jobs_dir / f"{job_id}.json",
        client_data=data,
        job=job,
        title_sources=sources,
        faq_sources=faq_sources,
        content_words=words,
        warnings=warnings,
        faq_searched=list(getattr(faq_result, "searched_phrases", []) or []),
    )


def write_outputs(result: AutobuildResult) -> None:
    """Writes the client YAML and job JSON. Refuses to overwrite either."""
    for path in (result.client_yaml_path, result.job_json_path):
        if path.exists():
            raise AutobuildError(f"{path} already exists -- not overwriting it")
    result.job_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(result.client_yaml_path, "w", encoding="utf-8", newline="") as f:
        yaml.dump(result.client_data, f, allow_unicode=True, sort_keys=False)
    with open(result.job_json_path, "w", encoding="utf-8") as f:
        json.dump([result.job], f, indent=2, ensure_ascii=False)


def summary(result: AutobuildResult) -> str:
    job = result.job
    lines = [
        f"Job id:       {result.job_id}",
        f"Client facts: {result.source_file}",
        f"Keyword:      {job.get('keyword')}",
        f"Template:     {job.get('template')}",
    ]
    if job.get("cloud_buckets"):
        bucket = next(iter(job["cloud_buckets"].values()))
        lines.append(f"Bucket:       {bucket} (pinned), folder {job.get('directory')}/")
        lines.append(f"Accounts:     {', '.join(job['cloud_buckets'])}")
    else:
        lines.append(f"Bucket:       new bucket named {job.get('keyword')}")
    lines.append(
        f"Link:         {job.get('target_link_text_before')} "
        f"[{job.get('target_link_text')}] {job.get('target_link_text_after')}"
    )
    lines.append(f"Page titles ({len(job.get('page_titles', []))}):")
    for title, source in zip(job.get("page_titles", []), result.title_sources):
        lines.append(f"  [{source:>8}] {title}")
    lines.append(f"Content:      {result.content_words} rendered words")
    ai = sum(1 for s in result.faq_sources if s == FAQ_SOURCE_AI)
    google = len(result.faq_sources) - ai
    lines.append(f"FAQs:         {len(result.faq_sources)} ({google} Google, {ai} AI)")
    if result.faq_sources and google == 0 and result.faq_searched:
        lines.append(
            "  Google showed no People Also Ask questions for: "
            + "; ".join(result.faq_searched)
        )
    for faq, source in zip(job.get("faqs", []), result.faq_sources):
        if source == FAQ_SOURCE_AI:
            lines.append(f"  [AI] {faq['question']}")
    if result.warnings:
        lines.append("WARNINGS:")
        lines += [f"  - {w}" for w in result.warnings]
    else:
        lines.append("Warnings:     none")
    lines += [
        "Wrote:",
        f"  {result.client_yaml_path}",
        f"  {result.job_json_path}",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# --submit: hand the job to rr_yacss_factory (draft + preview only)
# --------------------------------------------------------------------------

FactoryRunner = Callable[[list[str]], tuple[int, str]]

NOTHING_TO_CREATE = "Dry-run: nothing to create."


def run_factory(args: list[str]) -> tuple[int, str]:
    """Runs `npx tsx src/cli.ts <args>` in rr_yacss_factory (its current
    source, not a possibly stale build) and returns (exit code, output),
    with npm's own notice lines dropped."""
    npx = shutil.which("npx")
    if npx is None:
        raise AutobuildError(
            "npx not found -- Node.js is needed to run rr_yacss_factory"
        )
    if not FACTORY_DIR.is_dir():
        raise AutobuildError(f"rr_yacss_factory not found at {FACTORY_DIR}")
    try:
        done = subprocess.run(
            [npx, "tsx", "src/cli.ts", *args],
            cwd=FACTORY_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
    except subprocess.TimeoutExpired as e:
        raise AutobuildError(f"rr_yacss_factory timed out: {' '.join(args)}") from e
    output = "\n".join(
        line
        for line in (done.stdout + done.stderr).splitlines()
        if not line.startswith("npm notice")
    )
    return done.returncode, output


def factory_command(args: list[str]) -> str:
    """The same factory call as a command the user can run themselves."""
    quoted = " ".join(f'"{a}"' if " " in a else a for a in args)
    return f"cd {FACTORY_DIR} && npx tsx src/cli.ts {quoted}"


def other_drafted_jobs(job_id: str, manifest: Path = FACTORY_MANIFEST) -> list[str]:
    """Manifest entries other than job_id with status "drafted". The
    factory's generate step works through every drafted entry, not only
    the jobs in the file passed, so these would be generated too by a
    --confirm run."""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted(
        f"{key} (build {entry.get('build_id')})"
        for key, entry in data.items()
        if key != job_id
        and isinstance(entry, dict)
        and entry.get("status") == "drafted"
    )


def submit(
    result: AutobuildResult,
    run: FactoryRunner = run_factory,
    log: Callable[[str], None] = print,
    manifest: Path = FACTORY_MANIFEST,
) -> int:
    """Drafts the job in YACSS and previews generate/publish, never with
    --confirm: (1) stops if the job has warnings; (2) for a pinned bucket,
    runs `onboard-client` as a dry run and stops unless the bucket already
    exists on every account; (3) runs `all -f <job>` without --confirm
    (creates a real YACSS draft; generate/publish are YACSS previews only);
    (4) prints the command that finishes the build. Returns an exit code."""
    job = result.job
    job_file = f"jobs/{result.job_json_path.name}"
    all_args = ["all", "-f", job_file]

    if result.warnings:
        log("Not submitted: fix the warnings above first (in the app or the files),")
        log("then draft it with:")
        log(f"  {factory_command(all_args)}")
        return 1

    buckets = job.get("cloud_buckets") or {}
    if buckets:
        bucket = next(iter(buckets.values()))
        onboard_args = ["onboard-client", bucket, "-a", ",".join(buckets)]
        log(f"Checking bucket {bucket} on accounts {', '.join(buckets)} ...")
        code, output = run(onboard_args)
        log(output)
        if code != 0 or NOTHING_TO_CREATE not in output:
            log("Not submitted: the client bucket is missing or could not be checked")
            log("on some account. To create the missing buckets, run:")
            log(f"  {factory_command([*onboard_args, '--confirm'])}")
            log("then draft the job with:")
            log(f"  {factory_command(all_args)}")
            return 1

    log("Drafting in YACSS (no --confirm: nothing is generated or published) ...")
    code, output = run(all_args)
    log(output)
    if code != 0:
        log("The factory reported a failure (see above). The YACSS draft, if one")
        log("was created, stays tracked in the factory manifest; once fixed, re-run:")
        log(f"  {factory_command(all_args)}")
        return 1

    log("")
    log("Drafted. Review the preview above, then generate and publish with:")
    log(f"  {factory_command([*all_args, '--confirm'])}")
    others = other_drafted_jobs(result.job_id, manifest)
    if others:
        log("Note: --confirm also generates these other drafted jobs:")
        log("".join(f"  - {o}\n" for o in others).rstrip("\n"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draft a YACSS Cloud Stack job from a client and a keyword. "
        "Writes a client YAML and a rr_yacss_factory job file; never calls "
        "YACSS or the factory."
    )
    parser.add_argument(
        "--client", required=True, help='e.g. "United Structural Systems"'
    )
    parser.add_argument(
        "--keyword", required=True, help='e.g. "commercial foundation repair"'
    )
    parser.add_argument(
        "--from", dest="from_file", type=Path, help="client file to use"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=stack_profile.DEFAULT_PROFILE,
        help="stack profile",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="then draft it in YACSS through rr_yacss_factory and show the "
        "generate/publish preview (never --confirm; prints the command that "
        "finishes the build)",
    )
    args = parser.parse_args(argv)

    from ai_content_generator import AiContentError
    from keyword_research_api import KeywordResearchError

    try:
        result = draft_stack(
            args.client,
            args.keyword,
            from_file=args.from_file,
            profile_path=args.profile,
            log=lambda msg: print(msg, flush=True),
        )
        write_outputs(result)
    except (AutobuildError, AiContentError, KeywordResearchError) as e:
        print(f"Autobuild stopped, nothing written: {e}", file=sys.stderr)
        return 1
    print()
    print(summary(result))
    if not args.submit:
        return 0
    print()
    try:
        return submit(result, log=lambda msg: print(msg, flush=True))
    except AutobuildError as e:
        print(f"Submit stopped: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
