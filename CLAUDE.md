# skippy_yaml_builder — project instructions

This file is scoped to `skippy_yaml_builder`. It supplements (does not
replace) the user's global `CLAUDE.md`; that file's mission contract,
quality gates, and override-directive syntax all apply here unchanged.

## What this project is

A PyQt6 desktop app (`main.py`) for authoring client-intake YAML files
used to drive real-world SEO deliverables for Rank Rocket Co clients --
target cities, services, company info, FAQ content, city embed codes, and
the YACSS build-mechanics fields (`YACSS *`) that feed the sibling
`rr_yacss_factory` CLI's job files. Client YAML files live under
`client_yaml/<client-slug>/` and are gitignored (client data, not source).
No web UI, no server -- a single-window desktop form + YAML read/write.

`yacss_api.py` gives the form live, read-only YACSS API lookups (current
templates, current cloud accounts) to populate two dropdowns instead of
free-text guessing -- it assumes `rr_yacss_factory` is a sibling directory
(`../rr_yacss_factory/.env`) and reads that project's own
`YACSS_API_TOKEN` rather than needing a second copy of the token. If that
sibling layout ever changes, update `RR_YACSS_FACTORY_ENV` in
`yacss_api.py` to match.

## Quality gate

```bash
venv/Scripts/ruff.exe check --fix . && venv/Scripts/black.exe . && venv/Scripts/mypy.exe . && venv/Scripts/pytest.exe -q
```

This matches the global CLAUDE.md's default Python gate. Configuration
lives in `pyproject.toml` (added 2026-09-25); the tools are in
`requirements-dev.txt`. Scope is deliberately conservative -- if you want
to widen it, change `pyproject.toml` and this section together rather than
letting them diverge:

- **ruff**: `E4`, `E7`, `E9`, `F`, `I` only (correctness + import sorting).
  Style-opinion rules (`E501`, `SIM`, `RUF`, `BLE`) are not enforced.
- **black**: defaults (88 cols). Skips everything in `.gitignore`.
- **mypy**: default strictness, `ignore_missing_imports = true`; bodies of
  unannotated functions are not checked. Excludes `venv/`, `source/`,
  `build/`, `dist/`, `client_yaml/`.
- **pytest**: unchanged.

`ruff --fix` and `black` rewrite files -- run them before committing, not
after, so the commit contains the formatted result.

Only one venv exists in the repo root: `venv/` (canonical, documented in
README.md). An undocumented second `.venv/` briefly existed with a stale
PyQt6 patch version and was deleted 2026-09-13 -- always use
`venv/Scripts/python.exe` / `venv/Scripts/pytest.exe` explicitly rather
than whatever `python`/`pytest` resolves to on PATH, and don't recreate a
second venv at the repo root.

## Project Start / Checkpoint / Shutdown

Same trigger phrases and fallback protocol as the global `CLAUDE.md`
Section 4, scoped to this repo:

- **"Project start"**: read `docs/projectStatus.md`'s "Resume From"
  section + the latest file in `docs/archive/checkpoints/`, then summarize
  last wins -> remaining work -> today's plan.
- **"Checkpoint now" / "Prepare for rollover"**: write
  `docs/archive/checkpoints/CheckPoint-YYYY-MM-DD_HHMM.md`, update
  `docs/projectStatus.md`'s "Resume From" section, commit
  (`chore(checkpoint): YYYY-MM-DD_HHMM - <short summary>`).
- **"Project shutdown"**: run the checkpoint protocol above, then push to
  `origin/main` (`github.com/PenZenMaster/skippy_yaml_builder`), then
  confirm branch/commit state and list 3 bullets for next session.

## Code decisions require the user's permission

Never make a code decision on the user's behalf. Whenever there is more
than one reasonable way to implement something, stop before editing and
present the options with `AskUserQuestion`, then wait for the user's
selection. This covers design and approach choices (data source, algorithm,
where logic lives), behavior on failure or edge cases, scope (what is and
isn't included), new dependencies, and any change to existing behavior or
public shape (field names, YAML/JSON output, UI layout).

For each option, state:

- **What it does**: one or two sentences, concrete.
- **Expected result**: what the user will see or get, including
  trade-offs, risks, and what it leaves unhandled.

Lead with a recommended option (marked "(Recommended)") and say why, but
do not act on it until the user selects. Do not bundle a decision into a
larger patch and announce it afterwards, and do not treat an earlier
approval of one option as approval of a different one.

This does not apply to choices that are mechanical and have a single
right answer (matching the surrounding code's style, fixing a typo,
following an explicit instruction the user already gave). If unsure whether
something is a decision, treat it as one and ask.

## Notes specific to this codebase

- `main.py` has no versioned file header (predates that global CLAUDE.md
  convention being applied here) -- don't retrofit one just to match the
  convention; do add one to genuinely new files (e.g. `yacss_api.py`
  already follows it).
- `self.inputs` is the generic widget-per-field dict that `save_yaml`/
  `load_yaml` iterate automatically; a field needs a manual save/load
  branch (like `city_data`, `cloud_account_list`, `faq_table`) only when
  its shape isn't a plain string, a `\n`-per-line list, or a `QComboBox`
  selection -- prefer fitting a new field into the generic dict over adding
  another special case.
- `conftest.py`'s `no_live_yacss_lookup` fixture stubs `main.fetch_templates`/
  `main.fetch_cloud_accounts` to `[]` for every test by default, since
  `YAMLForm()` calls the live YACSS API on construction -- a test that
  needs to exercise real live-population behavior should override this
  fixture's monkeypatch locally, not remove the fixture.
