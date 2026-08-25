# Changelog

All notable changes to this project are documented in this file. Format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.1] - 2026-08-24

### Added

- **Listicle brand placement + competitor/target URLs.** Three new
  fields -- `YACSS Brand Name`, `YACSS Brand URL`, `YACSS Brand
  Position` -- map to `ListicleJob.brand` (src/jobs/schema.ts's
  `brandPlacementSchema`), plus `YACSS Competitor URLs (one per
  line)`/`YACSS Target URLs (one per line)` for `competitor_urls`/
  `target_urls`. All five are optional and shown only for the Listicle
  build type. `brand` requires both name and url once either is
  filled in -- a partial entry warns and is omitted rather than sent
  incomplete. Verified live against rr_yacss_factory's own `parseJob()`.

## [0.3.0] - 2026-08-24

### Added

- **Export Job JSON for Listicle and Masspage_Silo_Local.** Previously
  Diagram-only; `_build_listicle_job()`/`_build_masspage_job()` now
  build real rr_yacss_factory `ListicleJob`/`MasspageJob` dicts, both
  schema-validated against `parseJob()` in a live check. Adds one new
  field, `YACSS Topic Keyword` (hidden for Diagram, shown otherwise) --
  it holds the job's real SEO subject (`job.keyword`, e.g. "best coffee
  shops in Austin"), which is a genuinely different value from `YACSS
  Bucket Keyword`. For these two types that field is relabeled "YACSS
  Target Stack Keyword" and now maps to `job.lsi_keyword` instead --
  confirmed against rr_yacss_factory's own `bucketAndDirectoryForJob()`
  (`bucket = slugify(lsi_keyword)`, `directory = slugify(keyword)`),
  correcting an earlier assumption that it mapped to `job.keyword`
  directly the way it does for Diagram/cloud_stack. Masspage reuses the
  existing `YACSS Diagram Page Titles`/`YACSS Diagram Content` fields
  (their own setup comment already anticipated this); unlike Diagram,
  masspage's page_titles has no multiplicative-total requirement, so
  the live page-titles counter now only applies to Diagram and shows a
  neutral label otherwise. `brand`/`competitor_urls`/`target_urls`
  (optional on ListicleJob) have no form field yet and are omitted.

## [0.2.0] - 2026-08-24

### Added

- **Tabbed layout + centralized button theme.** The old single-screen
  form (every field in one 4-column grid, full-width buttons) is now
  four tabs -- Client Info, Content, FAQ, YACSS Build -- keeping any
  one screen a reasonable size. Button colors are now centralized in
  `theme.py`'s `ThemeManager` (one semantic style per action: success,
  export, import, danger, secondary) instead of ad hoc per-button
  styling, adapted from the same pattern in the sibling
  `cloud-stack-generator` project. Widget identity is unchanged --
  `self.inputs`/`self.labels` and all existing save/load/export logic
  are untouched, only where each widget is placed changed.
- **Export Job JSON** (Diagram build type only) -- writes a real
  `rr_yacss_factory` job file directly, in the same shape its own
  `factory run` reads. Added the two fields a Diagram job actually
  needs that had no home in the form before now: `YACSS Diagram Page
  Titles (one per line)` and `YACSS Diagram Content`. Warns (without
  blocking) on blank required fields, a page-title count that doesn't
  match the real multiplicative total, or a tier with no cloud accounts
  assigned. FAQs ride along as YACSS's real `faq_question[]`/
  `faq_answer[]` build-field keys. Verified against a real client file
  (Overhead Door Joliet): the exported JSON was validated directly
  against `rr_yacss_factory`'s own live schema, both the expected
  rejection (missing page_titles/content) and the clean pass once
  filled in, with real cloud account IDs and a real template id.

## [0.1.0] - 2026-08-25

First versioned release -- this project had no version tracking before
today (the window title's old "v4" was a leftover UI-redesign label, not
a real version). This entry is a baseline summary of what already
existed, not a claim that all of it shipped together.

### Added

- Two-column grid-layout client-intake form (client info, target cities,
  services, FAQs, Google Maps embeds, broker fields).
- `YACSS *` build-settings section feeding `rr_yacss_factory`'s job
  files (build type, template, bucket keyword, tiers, AI platform/model,
  cloud account targeting).
- Live YACSS Template and Cloud Account dropdowns (`yacss_api.py`),
  reading the same token `rr_yacss_factory` uses -- with a manual
  fallback field so the form still works if the live lookup fails.
- FAQ Questions & Answers as a real two-column table (not question-only),
  matching YACSS's actual `faq_question[]`/`faq_answer[]` shape, with an
  Enter-key flow (type Q, Enter, type A, Enter, next row) and CSV import
  (`question,answer`, optional header, appends rather than replaces).
- Type-aware `YACSS Bucket Keyword` label (its real meaning differs
  between Diagram and Listicle/Masspage_Silo_Local) and a per-tier
  Cloud Account IDs table for Diagram builds, synced live to `YACSS
  Tiers`, replacing one global list that couldn't express a real stack's
  per-tier platform diversity.
- `run.cmd` -- creates the venv if needed, installs dependencies, and
  launches the app in one step.
- In-app Help (Help -> How to Use) rendering this project's own
  `README.md` directly, so in-app help and the GitHub readme can't drift
  apart. Real version tracking (`__version__`, shown in the window title
  and About).
- First pytest suite (offscreen/headless), now 50+ tests covering
  save/load round-tripping, the live-lookup fields, the FAQ table, and
  CSV import.

### Fixed

- `save_yaml` wrote files in the platform's locale encoding (cp1252 on
  Windows) instead of UTF-8, while `load_yaml` hardcoded UTF-8 -- any
  em dash, curly quote, or (R)/(TM) symbol (common in pasted FAQ content)
  made a saved file fail to reload at all. Found and fixed against a
  real client file.
- The FAQ table's Enter key silently overwrote the question just typed
  instead of moving to the Answer cell (Qt's default Return handling on
  a table commits the edit and reselects the same cell without reopening
  it for editing).
- `test.cmd` (the previous launcher) never actually ran `pip install` or
  `main.py` -- `venv\Scripts\activate` was invoked without `call`, which
  in batch permanently hands off control and never returns. Replaced by
  `run.cmd`.
