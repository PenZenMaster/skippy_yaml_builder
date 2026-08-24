# Skippy YAML Builder

A desktop form for building the client-intake YAML files that drive
[rr_yacss_factory](../rr_yacss_factory)'s bulk YACSS site builds --
company info, target cities, services, FAQs, and the `YACSS *` build
mechanics fields. This file is rendered directly inside the app itself
(Help -> How to Use) as well as read here on GitHub.

## Using the app

### Basic workflow
1. Fill in the client's business info (name, phone, address, target
   cities, services).
2. Fill in the `YACSS *` fields (see below) to describe the build itself.
3. **File > Open YAML** reopens a saved client file; **Save YAML** at the
   bottom writes it out.

### YACSS Build Type changes what the other YACSS fields mean
The three build types build fundamentally different things, and several
fields' meaning changes depending on which one is selected:

- **Diagram** (a "Cloud Stack") -- a link pyramid of pages: `YACSS
  Tier0 Pages` is the money-page count (usually 1), and `YACSS Tiers
  (tier:pages, one per line)` (e.g. `1:3`, `2:3`, `3:3`) sets each
  tier's branching factor -- tiers **multiply**, they don't add (1 + 3 +
  3x3 + 3x3x3 = 40 pages for that example, not 1+3+3+3=10). This is the
  only type where a real cloud storage bucket gets auto-created, named
  from `YACSS Bucket Keyword`.
- **Listicle** and **Masspage_Silo_Local** -- ignore Tier0/Tiers
  entirely (they're not a pyramid). Neither ever creates its own
  bucket -- both publish INTO an existing Diagram build's bucket, so for
  these two types `YACSS Bucket Keyword` must instead name that existing
  build's own keyword. The field's on-screen label updates automatically
  based on which type is selected, so it always describes what it
  currently means.

### Cloud Account IDs also depend on build type
- **Diagram**: assign accounts **per tier**, in the table that appears
  (synced automatically to whatever's typed into `YACSS Tiers`) -- a
  real stack typically spreads different tiers across different cloud
  platforms (e.g. tier 1 on Vultr, tier 2 on Bunny) so the hosting
  footprint doesn't look centralized.
- **Listicle / Masspage_Silo_Local**: use the flat checklist instead --
  pick whichever account(s) host the target Diagram build's bucket.

Both the checklist and the per-tier table are populated live from the
real YACSS account on startup (the same account `rr_yacss_factory`
uses -- see "For developers" below for where the token comes from). If
that lookup fails (no token, no network), both still work manually: the
checklist just starts empty, and the "extra/manual account IDs" field
next to it is exactly for that case.

### FAQ Questions & Answers
- Type a question, press **Enter** to jump to the Answer cell, type the
  answer, press **Enter** again to open a fresh row -- built specifically
  so Enter does the right thing, unlike Qt's plain default (which
  reselects the same cell without reopening it for editing).
- **Import FAQs from CSV** expects two columns, `question,answer` (an
  optional `Question,Answer` header row is detected and skipped
  automatically). Imported rows are **appended** to whatever's already
  in the table, not a destructive replace.

### Fields with no effect yet
`Hero Image URL`, `City Page Hero Image Base URL`, and `Logo URL` are
captured but not yet consumed by any downstream build step -- there's no
established convention yet for exactly how they'd be used. Fill them in
for future use, or leave blank.

## For developers

To run, double-click `run.cmd` (or run it from a terminal) -- it creates
`venv\` if it doesn't already exist, installs/updates dependencies, and
launches the app:
```cmd
run.cmd
```

Or manually, one command at a time in an interactive shell:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

To run tests:
```cmd
venv\Scripts\activate
pip install -r requirements-dev.txt
pytest
```

See `CLAUDE.md` for this project's own conventions, and `CHANGELOG.md`
for what's shipped.
