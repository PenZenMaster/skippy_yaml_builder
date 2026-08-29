## Resume From

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
