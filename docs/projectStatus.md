## Resume From

Checkpoint: `docs/archive/checkpoints/CheckPoint-2026-10-08_1822.md`
Last session: 2026-10-08 (catch-up only, no code changes)
Branch: main | Version: 1.3.0 (no git tag yet)

**2026-10-08**: status caught up. Two releases from 2026-09-27 had no
checkpoint: **v1.2.0** (`03cb3eb`, Diagram export auto-hyphenates `YACSS
Bucket Keyword` into the job `keyword`) and **v1.3.0** (`b746125`, Diagram
Content paragraphs wrapped in `<p>` on export). 266/266 tests. **Next:**
live-verify FAQ generation (v1.1.0) plus the v1.2.0/v1.3.0 exports on a
real factory run.

**2026-09-26 (afternoon, part 2)**: FAQ generation refactored and
released as **v1.1.0** (`72b7a61`, `5bd0c62`). Fixes made-up client
info (answers grounded in the form's facts), too-few FAQs (expanded PAA
+ city-variant searches + labelled AI-suggested top-up) and zero/blank
output (hyphenated bucket keyword cleaned into a real search phrase;
JSON answers with blank-only retries). New `faq_generation.py`. 264/264
tests, pushed. **Next: run it once on a real client** -- everything is
mock-tested only; check the count is reached and answers stay factual.
Cost per click is higher (up to 4 SERP + 4 OpenAI calls). Detail in the
checkpoint.

**2026-09-26 (afternoon)**: released **v1.0.0** (`c384ddf`; no change to the YAML or
job-file shape) after shipping the **bucket-keyword check** (`94709aa`):
Diagram exports now warn (advisory, still exportable) when `YACSS Bucket
Keyword` has anything other than lowercase letters, digits and hyphens --
closes the long-carried underscore/bucket-creation Known Issue. Existing
Diagram keywords with spaces will now warn on export. The user also
confirmed the 750-word AI Diagram Content check and the v0.10.0 image
fields on real client work. The recurring `venv\Scripts\activate.bat`
text was VS Code's Python extension auto-activating terminals; disabled
via a user-level VS Code setting. Stale launch-codes file and a dead
permission entry removed (`50e054d`). 231/231 tests, pushed. **Next:**
Content Silo real-client validation; optionally tag `v1.0.0`. Detail in
the checkpoint.

**2026-09-25 (afternoon, part 2)**: Diagram Content "Generate with AI" now
produces at least **750 rendered words** (spintax counted at each group's
shortest option; up to 3 attempts, longest kept; 6,000-token floor; live
word counter in the preview dialog) -- `f76324e`. The AI Model dropdown
needed no change: it is already filled from YACSS's live `/ai-models`
(7 OpenAI models), and the user chose to keep it mirroring YACSS. New
`CLAUDE.md` rule: present options with expected results and wait for the
user's selection before any code decision. 227/227 tests, pushed. **Next:
verify a real Generate with AI run reaches 750 words.** Detail in the
checkpoint.

**2026-09-25 (afternoon)**: QA gate is now `ruff check --fix . && black . &&
mypy . && pytest -q` (config in `pyproject.toml`, tools in
`requirements-dev.txt`). Fixed 6 mypy errors, applied a mechanical
black/ruff pass (`9abb77c`, listed in `.git-blame-ignore-revs`). All green,
217/217 tests. No behavior change. Detail in the checkpoint.

**2026-09-25 (morning)**: no code changes. The v0.10.0 per-page image list
was used for real in the factory (SARC job D); see
`CheckPoint-2026-09-25_0900.md`.

**2026-09-23**: v0.10.0 -- **"Content Image URLs (one per line)"** field
(exports `content_image_urls`, warns on the `Content Image URL` combination
and on more images than pages), **`Logo URL` now exports** as
`logo_image_url` (existing client files with one filled in will start
uploading it), and an **export-time 400KB image size check**
(`image_size_check.py`, advisory, checks hero/logo/per-page images).
v0.9.1's Job ID confirm prompt (`7eb2a27`) had also been committed without
a checkpoint. 217/217 tests. Full detail in
`docs/archive/checkpoints/CheckPoint-2026-09-23_1632.md`.

**2026-09-14**: v0.8.0's PAA-driven FAQs and Select All checkboxes passed
manual QA. Also found and committed a separate, already-complete v0.9.0
feature set present on disk (uncommitted) at session start -- **"YACSS
Job ID (override)"** (avoids silently overwriting `rr_yacss_factory`'s
manifest entry when rebuilding the same client) and a fix making "Google
Maps Embed Code" actually export (`extra_fields.mymapsurl`, previously
silently dropped). Full suite 193/193 passing (185 at session start).
Full detail in `docs/archive/checkpoints/CheckPoint-2026-09-14_0851.md`.

**2026-09-13**: Consolidated the two-venv issue -- deleted the stale,
undocumented `.venv/` (older PyQt6 patch version) so only the canonical
`venv/` (documented in README.md, matches `run.cmd`) remains at the repo
root. Project `CLAUDE.md` updated to drop the now-resolved caveat. Then
shipped v0.8.0: **"Generate FAQs from People Also Ask"** on the FAQ tab
(real Google PAA questions via a new `keyword_research_api.
fetch_people_also_ask`, DataForSEO's SERP API, answered per-question by a
new `ai_content_generator.generate_faq_answers`, capped at 10 per click)
and a **Select All / Deselect All** checkbox above each of the three
generated-results tables (Keyword Research + both Content Silo tables).
Full suite 185/185 passing (163 at session start). Full detail in
`docs/archive/checkpoints/CheckPoint-2026-09-13_1233.md`.

**2026-09-06**: v0.6.0 (File > Exit, FAQ 50/50 columns, two new optional
name fields fixing a real company.name/listicle.name gap, a real
phone-mask load bug fixed via live testing, README rewritten as a current
manual) then v0.7.0 (new "Content Silo" tab -- a Category -> Service
content pipeline for a client's own website, independent of any YACSS job
type; two-pass DataForSEO clustering, real landing-page-depth AI content
per page, Markdown export reproducing the real silo folder structure).
Full suite 163/163 passing. Survived and recovered from a serious
multi-agent incident mid-session (see the checkpoint's Known Issues #1)
-- no lasting damage, new working practices adopted for subagent use
going forward. This project's own checkpoint docs had gone stale since
2026-08-29 (intervening sessions were documented from the sibling
`rr_yacss_factory` side instead) -- caught back up as of this entry. Full
detail in `docs/archive/checkpoints/CheckPoint-2026-09-06_1250.md`.

**Next session**: real client use of the Content Silo tab to validate
output quality; consider the deferred direct-WordPress-publish fast-follow
(RankRocket MCP tools confirmed available); keep this file current going
forward rather than defaulting back to `rr_yacss_factory`-only checkpoints.

---

Previous session (2026-08-29, shutdown), preserved for reference:

Checkpoint: `docs/archive/checkpoints/CheckPoint-2026-08-29_1533.md`
Last session: 2026-08-29
Branch: main | Version: 0.4.0 (not yet pushed)

**PROJECT SHUTDOWN 2026-08-29**: called from the sibling `rr_yacss_factory`
session after three real platform bugs were found and blocked on external
YACSS support -- pause new work here too until support responds to the
three drafted tickets (see that project's checkpoint for detail).

This session: reviewed and cleanly split pre-existing uncommitted WIP (a
complete AI-generation feature, `075e63c`) from two real fixes (column
widths + duplicate-tier-number validator, `bf59f2f`), then added three
new required anchor-text backlink fields (`266ff52`) after a live
`rr_yacss_factory` build proved `landing_url` alone never produces a real
citation backlink -- confirmed live from the sibling project that the fix
is correct but currently inert due to a YACSS-side bug (ticket drafted,
not yet submitted). Full detail in
`docs/archive/checkpoints/CheckPoint-2026-08-29_1533.md`.

`pytest -q`: 114/114 green. Four local commits ahead of `origin/main`,
not pushed (shutdown protocol).

---

Previous session (2026-08-26), preserved for reference:

Built out Salvo Metal Works' full client YAML config set (general +
8 product categories), then converted `YACSS AI Platform`/`YACSS AI
Model`/`YACSS Tone` from free-text to live dropdowns and gave each
Diagram tier a named cloud-account picker instead of requiring a raw
numeric ID. A real live test of that Salvo Metal Works build in the
sibling `rr_yacss_factory` repo then surfaced a genuine math bug in this
project's own `_compute_cloud_stack_total_pages` (never multiplied by
`tier0_pages`, only ever tested at `tier0_pages=1` where that's
invisible) -- fixed here too, mirroring the TypeScript fix. Full test
suite 90/90 (was 81 at session start). See
`docs/archive/checkpoints/CheckPoint-2026-08-26_1930.md` for full detail.

**KNOWN ISSUE carried into next session**: no validation warns about
bucket-unsafe characters (e.g. underscores) in `YACSS Bucket Keyword` --
cost three live `generate` attempts in `rr_yacss_factory` to diagnose by
hand this session. Worth a real check before the next client batch.

NEXT SESSION (top 3, per the user's own stated plan): the user wants to
**batch up several more clients**, two Diagram builds/month each,
publishing to **Google Cloud Storage** specifically (the one provider
with zero issues in the Salvo Metal Works publish, out of 8 total -- see
`rr_yacss_factory`'s own checkpoint for why).
1. Find a faster path to building a new client's YAML config set than
   fully hand-authoring FAQs/content per category the way Salvo Metal
   Works was done.
2. Consider defaulting the Diagram tier cloud-account picker toward
   GCS/Azure/the one working Backblaze account for new clients, given 5
   of 8 providers failed with opaque errors on the most recent real
   publish.
3. Fix the bucket-keyword validation Known Issue above before or during
   that batch.

Session 2026-08-24 (part 2): converted YACSS Build Type to a dropdown
selector. See `docs/archive/checkpoints/CheckPoint-2026-08-24_1001.md`
for full technical detail.

Session 2026-08-24 (part 1): split one-per-line fields into YAML lists,
fixed white-on-white QTextEdit text, added pytest suite. See
`docs/archive/checkpoints/CheckPoint-2026-08-24_0913.md` for full
technical detail.

Session 2026-08-21 (part 1): added the YACSS build-settings section. See
`docs/archive/checkpoints/CheckPoint-2026-08-21_1304.md` for full
technical detail.
