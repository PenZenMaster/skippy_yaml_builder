## Resume From

Checkpoint: `docs/archive/checkpoints/CheckPoint-2026-08-24_0913.md`
Last session: 2026-08-24
Branch: main | Latest commit: `016670c` | Split the "one per line" text
fields (Target Cities, Services, Social/Citation URLs, FAQ Questions)
into real YAML lists at save time (load still accepts the older
flat-string format for backward compat); fixed a white-on-white text bug
in Services and other `QTextEdit` fields caused by no widget ever having
an explicit color/background set, so Windows dark mode could leave text
invisible even though the underlying YAML data was correct; and added
the project's first real pytest suite (`tests/test_save_load_roundtrip.py`,
6 tests, headless offscreen QApplication) covering save/load
round-tripping, since the project previously had no test framework at
all. Both commits pushed to origin/main.

NEXT SESSION (top 3):
1. Run a real United Structural Systems batch through rr_yacss_factory
   using data authored via this form's YACSS section -- still the actual
   end-to-end test this integration was built for, still not done. Check
   rr_yacss_factory against the now-list-shaped export fields.
2. Consider consolidating the two venvs present in the repo root (`venv/`
   canonical/documented vs `.venv/` undocumented, different PyQt6 patch
   version) to avoid future confusion.
3. rr_yacss_factory has since added a third job type (`masspage`, Silo
   "AI Website" sites) with its own build-mechanics needs (Silo sub-mode,
   page-title list, AI platform) not yet represented in this form's YACSS
   section -- revisit once/if that job type becomes a real target.

Session 2026-08-24: split one-per-line fields into YAML lists, fixed
white-on-white QTextEdit text, added pytest suite. See the checkpoint
file above for full technical detail.

Session 2026-08-21 (part 1): added the YACSS build-settings section. See
`docs/archive/checkpoints/CheckPoint-2026-08-21_1304.md` for full
technical detail.
