# Skippy YAML Builder

A desktop form for building the client-intake YAML files that drive
[rr_yacss_factory](../rr_yacss_factory)'s bulk YACSS site builds --
company info, target cities, services, FAQs, and the `YACSS *` build
mechanics fields. This file is rendered directly inside the app itself
(Help -> How to Use) as well as read here on GitHub.

## Using the app

### Basic workflow
1. Fill in the client's business info (name, phone, address, target
   cities, services) on the **Client Info** and **Content** tabs.
2. Fill in the `YACSS *` fields (see below) on the **YACSS Build** tab to
   describe the build itself. For page titles specifically, prefer the
   **Keyword Research** tab (see below) over hand-brainstorming or the
   "Generate with AI" button -- it's the primary path now, backed by real
   DataForSEO search-volume data; "Generate with AI" is a fallback for
   seeds too niche/sparse for DataForSEO to return useful data on.
3. Fill in **FAQ Questions & Answers** on the **FAQ** tab if the client
   wants FAQs on the published pages.
4. **File > Open YAML** reopens a saved client file; **Save YAML** at the
   bottom writes it out. Neither dialog has a fixed default folder (it
   opens wherever your OS last remembered) -- existing client files live
   in this repo's own gitignored `client_yaml/<client-slug>/*.yaml`
   (e.g. `client_yaml/salvo_metal_works/dormers.yaml`), one folder per
   client, sometimes one file per product line/service within it. Navigate
   there yourself each time; the app won't remember or suggest it.
5. **Export Job JSON** writes a real `rr_yacss_factory` job file from the
   current form state (see "Exporting a real rr_yacss_factory job file"
   below) -- the actual input `factory run` consumes to draft/generate/
   publish the build. Saving the YAML and exporting the job JSON are two
   separate, independent steps; do both if you want the client file kept
   for later editing AND a job ready to run.
6. **File > Exit** closes the app (same as the window's own close button).

### Legal / Company Name and YACSS Listicle Display Title (both optional)
`* Client Name` drives the brand name used everywhere (page titles, target
link text, `job_id`). Two fields let a specific export diverge from it
when needed, both defaulting to `* Client Name` when left blank:
- `Legal / Company Name` (Client Info tab) -- feeds a Diagram export's
  `company.name` specifically, for a client whose legal entity name
  differs from the brand name (e.g. "Acme Plumbing & Associates LLC" vs.
  "Acme Plumbing").
- `YACSS Listicle Display Title` (YACSS Build tab) -- feeds a Listicle
  export's own `name` (its display title), for a listicle titled something
  unrelated to the client's own name (e.g. "Best Plumbers in Dallas, TX").

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
  footprint doesn't look centralized. Cloud Account IDs aren't shown
  anywhere in the YACSS dashboard itself, so each row has a **Select...**
  button opening a checkable picker of real accounts (by provider and
  name, not just a bare number) instead of requiring you to already know
  the ID -- it writes the ID(s) back into that row's text field, which
  stays directly editable too if you already know the ID or the live
  lookup below failed.
- **Listicle / Masspage_Silo_Local**: use the flat checklist instead --
  pick whichever account(s) host the target Diagram build's bucket.

Both the checklist and the per-tier table/picker are populated live from
the real YACSS account on startup (the same account `rr_yacss_factory`
uses -- see "For developers" below for where the token comes from). If
that lookup fails (no token, no network), both still work manually: the
checklist just starts empty, and the "extra/manual account IDs" field
next to it is exactly for that case.

### AI Platform, AI Model, and Tone are live dropdowns
`YACSS AI Platform` and `YACSS AI Model` are populated on startup from
the same YACSS account (AI Model re-filters to whichever platform is
currently selected). A provider not yet configured with a key on this
account still shows up in the list -- hover it to see the tooltip -- but
selecting it will fail at generation time. `YACSS Tone` is pre-filled
with the confirmed real option set (Conversational, ProfessionalWarm,
Authoritative, Empathetic, Witty, Inspirational, Persuasive, Relatable,
Educational, Urgent). All three stay editable, same as `YACSS Template`,
so an unlisted value can still be typed in and is preserved on save/load.

### Target link text (Diagram only, required)
A Diagram build's whole purpose is to build real, visible backlinks to the
client's own site -- `* Website` alone only ever produces an invisible
`<link rel="canonical">` tag, not an actual clickable citation. `YACSS
Text Before Target Link` / `YACSS Text Of Target Link` / `YACSS Text
After Target Link` are woven around `* Website` into that real anchor-text
link (e.g. before: "Visit", of: "Acme Plumbing", after: "to learn more
about emergency plumbing in Dallas" -> "Visit **Acme Plumbing** to learn
more about emergency plumbing in Dallas."). All three are required for a
Diagram export; leaving any blank produces an export warning.

### Keyword Research tab
Replaces hand-brainstormed page titles with real, volume-ranked keyword
clusters from DataForSEO Labs -- the preferred way to fill in `YACSS
Diagram Page Titles` for a Diagram build (see "Basic workflow" above).

1. Fill in `YACSS Bucket Keyword` (Diagram) or `YACSS Topic Keyword`
   (Listicle/Masspage) on the YACSS Build tab first -- that's the seed
   this tab searches from, shown live in the "Seed keyword" label. An
   optional second seed field lets you add a colloquial/industry synonym
   alongside the formal term (e.g. "portable toilet rental" AND "porta
   potty rental") -- some verticals miss a large share of real search
   volume without it.
2. **Run Research** calls DataForSEO and fills the results table:
   candidate page title, monthly search volume, a **Flagged** column, and
   sample keywords behind each cluster. Two independent flags can appear,
   shown in red rather than silently trusted or dropped -- you decide:
   - A cluster whose keywords all look like a competitor/brand name (not
     the client's own).
   - A cluster that reads as **off-target-location** -- built from the
     client's own State/Target Cities fields, since a generic seed can
     return nationwide "near \<state\>" results that aren't locally
     relevant to this client.
   - DataForSEO can genuinely return zero results for an overly
     niche/uncommon exact phrase -- if that happens you'll see an explicit
     "No results" message (not a silent empty table) suggesting a broader
     phrasing.
3. Check the rows you want (the "N / needed" counter tracks against the
   Diagram build's real multiplicative page-title total, same math as the
   page-titles field's own live counter) and click **Send Selected to
   YACSS Build Tab** to write them into `YACSS Diagram Page Titles` --
   confirms first if that field already has content.

### Content Silo tab
A separate content pipeline for the client's OWN website, unrelated to any
YACSS job type -- generates real landing-page-depth content (title, meta
description, intro, body, optional FAQs, plain prose, no spintax) for a
services/products silo: a Services/Category page linking out to individual
Service pages. This tab's own state (seed, discovered categories/services,
generated content) is NOT part of the saved client YAML -- it never
touches Save YAML/Open YAML/Export Job JSON.

1. Fill in **Silo Seed Keyword** (the silo's overall topic, e.g. "garage
   door services") and click **Find Categories** -- calls the same
   DataForSEO clustering the Keyword Research tab uses (including its
   off-target-location flagging from Client Info's State/Target Cities) to
   discover the top-level categories.
2. Check the category rows you want, then click **Find Services for
   Selected Categories** -- re-runs clustering seeded by each checked
   category's own title to discover the services within it. Re-running
   this always rebuilds the whole services table from whichever categories
   are currently checked, rather than appending -- unchecking a category
   and re-running removes its stale rows.
3. Check whichever category and/or service rows you want actual pages for,
   then click **Generate Content**. A checked category becomes its own
   silo-landing page (its content naturally references every service
   discovered under it, whether or not that service is ALSO checked for
   its own page); a checked service becomes its own leaf page. One page
   failing does not stop the rest -- every attempted page's result is
   kept, and a single combined warning names whichever ones failed.
4. **Export Silo** writes one Markdown file per successfully-generated
   page to a folder you choose: category pages at the root
   (`<category-slug>.md`), service pages nested under their own category's
   slug folder (`<category-slug>/<service-slug>.md`) -- reproducing the
   real silo structure -- plus a `_silo_structure.md` index linking
   everything. A page that failed to generate is skipped, not exported
   with blank content.

Uses the same `OPENAI_API_KEY` (`cloud-stack-generator`'s own `.env`) as
the Diagram "Generate with AI" buttons -- if that's not configured, an
"AI Not Available" warning tells you where to set it before Generate
Content will run.

### YACSS Content Generation Mode
Controls how a Diagram build's page content is generated:
- **Cheap (spun template, current default)** -- one authored
  `YACSS Diagram Content` block, spread across every page via YACSS's own
  spintax spinning. Cheap, but every page reads similarly.
- **AI-written per page (real distinct content, costs more)** -- a real,
  distinct AI-written article per page (uses `YACSS AI Platform`/`YACSS AI
  Model`). More expensive (an AI call for every page), genuinely different
  content per page. `YACSS Diagram Content` is still required either way
  -- an empty value produced zero real paragraphs even in AI mode when
  this was live-tested.

### FAQ Questions & Answers
- Type a question, press **Enter** to jump to the Answer cell, type the
  answer, press **Enter** again to open a fresh row -- built specifically
  so Enter does the right thing, unlike Qt's plain default (which
  reselects the same cell without reopening it for editing).
- **Import FAQs from CSV** expects two columns, `question,answer` (an
  optional `Question,Answer` header row is detected and skipped
  automatically). Imported rows are **appended** to whatever's already
  in the table, not a destructive replace.

### Exporting a real rr_yacss_factory job file
**Export Job JSON** writes a real `rr_yacss_factory` job file -- the same
JSON shape its own `factory run` reads, ready to draft/generate/publish
from there. It dispatches on `YACSS Build Type`, so all three build types
(Diagram -> `CloudStackJob`, Listicle -> `ListicleJob`, Masspage_Silo_Local
-> `MasspageJob`) are supported; choose a build type before exporting.
`YACSS Diagram Page Titles (one per line)` and `YACSS Diagram Content` are
shared by Diagram and Masspage_Silo_Local (the field labels don't change
name, but Masspage has no multiplicative-total requirement -- just at
least one title). For a Diagram export specifically, the page-titles count
must equal the build's real total page count (see the multiplicative math
above, not a plain sum of tier sizes) -- the field's own label updates
live as you type, e.g. "need 40, have 12", so you don't have to compute
the total by hand. If anything looks incomplete when you export (a blank
required field, a Diagram page-title count that doesn't match the real
total, a tier with no cloud accounts assigned), you'll get a warning
listing the specific issues and a chance to cancel -- exporting anyway is
still allowed, since the authoritative check is `rr_yacss_factory`'s own
job schema when the file is actually used, not anything duplicated here.
FAQ Questions & Answers are carried into a Diagram export too (YACSS has
no dedicated FAQ field, so they ride along as the real `faq_question[]`/
`faq_answer[]` build-field keys). Listicle export never includes FAQs
(`ListicleJob` has no FAQ field in the real job schema). Masspage export
currently doesn't send FAQs either, even though `MasspageJob.faqs` is a
real, already-working field on the `rr_yacss_factory` side -- this app's
Masspage export path just doesn't populate it yet.

### Hero Image URL / Content Image URL (Diagram only)
Both feed a Diagram export directly: `Hero Image URL` becomes
`CloudStackJob.hero_image_url` (a full-width banner shown below the nav,
above the page title); `Content Image URL` becomes
`CloudStackJob.content_image_url` (the stack's one supported in-content
image). Both are optional -- omit either to publish without it, same as
every build before these fields existed. Leave blank for Listicle/Masspage
builds; neither job type reads them.

### Fields with no effect yet
`City Page Hero Image Base URL` and `Logo URL` are captured but not yet
consumed by any downstream build step -- there's no established
convention yet for exactly how they'd be used. Fill them in for future
use, or leave blank.

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
