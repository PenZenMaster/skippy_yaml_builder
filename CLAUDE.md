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
pytest -q
```

This project has no `ruff`/`black`/`mypy` configuration (unlike the global
CLAUDE.md's default Python gate) -- `pytest -q` is the real, complete gate
today. If linting/type-checking is ever added, update this section and the
global gate's expectations together, don't silently diverge from what's
actually enforced.

Two venvs currently exist in the repo root: `venv/` (canonical, documented
in README.md) and an undocumented `.venv/` with a different PyQt6 patch
version -- always use `venv/Scripts/python.exe` /
`venv/Scripts/pytest.exe` explicitly rather than whatever `python`/`pytest`
resolves to on PATH, until these are consolidated (see
`docs/projectStatus.md`'s "Resume From" section for that open item).

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
