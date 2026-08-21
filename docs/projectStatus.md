## Resume From

Checkpoint: `docs/archive/checkpoints/CheckPoint-2026-08-21_1304.md`
Last session: 2026-08-21
Branch: main | Latest commit: `c6779f2` | Added a `"YACSS "`-prefixed
build-settings section (11 fields) to `main.py`'s form, so
`client_profile.yaml` can carry the build mechanics the sibling
`rr_yacss_factory` project needs (template, cloud account targeting,
tiers, AI generation settings, bucket keyword), alongside this tool's
existing client-profile fields. Wrapped the form in a `QScrollArea` since
the new fields no longer fit the fixed window height. Verified via an
offscreen smoke test (compiles, launches, save/load roundtrip matches the
real current YAML format) -- not yet exercised against a real
end-to-end rr_yacss_factory batch run.

NEXT SESSION (top 3):
1. Run a real United Structural Systems batch through rr_yacss_factory
   using data authored via this form's new YACSS section -- the actual
   end-to-end test this integration was built for, not yet done.
2. rr_yacss_factory has since added a third job type (`masspage`, Silo
   "AI Website" sites) with its own build-mechanics needs (Silo sub-mode,
   page-title list, AI platform) not yet represented in this form's YACSS
   section -- revisit once/if that job type becomes a real target.
3. Consider whether the "one per line" fields (Target Cities, Services,
   Social/Citation URLs, FAQ Questions) should be split into real YAML
   lists at save time instead of left as raw multi-line strings -- current
   behavior matches this tool's existing on-disk format, unchanged this
   session, but downstream consumers must split on newlines themselves.

Session 2026-08-21 (part 1): added the YACSS build-settings section. See
the checkpoint file above for full technical detail.
