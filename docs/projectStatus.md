## Resume From

Checkpoint: `docs/archive/checkpoints/CheckPoint-2026-08-24_1001.md`
Last session: 2026-08-24
Branch: main | Latest commit: `35f1edd` | Split the "one per line" text
fields (Target Cities, Services, Social/Citation URLs, FAQ Questions)
into real YAML lists at save time (load still accepts the older
flat-string format for backward compat); fixed a white-on-white text bug
in Services and other `QTextEdit` fields caused by no widget ever having
an explicit color/background set, so Windows dark mode could leave text
invisible even though the underlying YAML data was correct; added the
project's first real pytest suite (`tests/test_save_load_roundtrip.py`,
now 10 tests, headless offscreen QApplication) covering save/load
round-tripping, since the project previously had no test framework at
all; and converted the `YACSS Build Type` free-text field to a
`QComboBox` dropdown (blank / Diagram / Listicle / Masspage_Silo_Local)
with case-insensitive load matching for legacy values. All four commits
pushed to origin/main.

NEXT SESSION (top 3):
1. Run a real United Structural Systems batch through rr_yacss_factory
   using data authored via this form's YACSS section -- still the actual
   end-to-end test this integration was built for, still not done. Check
   rr_yacss_factory against the now-list-shaped export fields and the new
   YACSS Build Type dropdown values.
2. Consider consolidating the two venvs present in the repo root (`venv/`
   canonical/documented vs `.venv/` undocumented, different PyQt6 patch
   version) to avoid future confusion.
3. rr_yacss_factory has since added a third job type (`masspage`, Silo
   "AI Website" sites) with its own build-mechanics needs (Silo sub-mode,
   page-title list, AI platform) not yet represented in this form's YACSS
   section -- revisit once/if that job type becomes a real target. Now
   that YACSS Build Type is a closed dropdown, adding it as a fourth
   option is a one-line change plus a pytest case.

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
