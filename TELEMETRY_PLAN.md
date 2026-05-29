# Telemetry default — decision needed

**Status:** ✅ **Decision locked: Option C — opt-IN default with a prominent onboarding wizard prompt.** · decided 2026-05-29 · author Aiden + Claude (store-side session)

**No marketing changes required.** Skip the Option B section below.

This file captures a deliberate decision that hasn't been executed yet because the
trade-off touches both the desktop app **and** the store's marketing copy. When you
get to it, read this whole file first — there are 14 marketing surfaces tied to the
current "No telemetry" promise that need to flip in sync with any code change.

---

## Background

The store has a `telemetry_events` table (applied via migration
`20260526130000_telemetry.sql` in the store repo) with three pre-built views
(`v_daily_active_installs`, `v_connector_install_rate`, `v_onboarding_funnel`)
feeding the admin dashboard at `/admin/dashboard`. The table is empty — the
desktop app doesn't emit events yet. RLS is service-role-only by design.

The schema captures **anonymous** events:
- `event` — string name (`app_launched`, `connector_installed`, `onboarding_step_N_complete`, etc.)
- `app_version`, `os`, `os_version`
- `extras` — JSONB payload (`{ "connector": "ableton" }`)
- `received_at_hour` — timestamp **bucketed to the hour**, not the exact second
- No user id, no machine id, no IP, no PII

Currently every public-facing surface promises **"no telemetry"** — comparison
table tick mark, pricing section footnote, FAQ, privacy page, drip emails, and
~10 blog-post CTAs. Aiden's product positioning is "indie-friendly, privacy-positive."

---

## The decision

Aiden asked to default telemetry **ON** with an opt-out in settings.

After flagging the marketing-vs-data trade-off, three options were on the table:

### A. Keep telemetry OFF (status quo)
- Marketing stays untouched and honest
- Zero data on which features get used / where onboarding drops off
- Same posture as Obsidian, NetNewsWire, BBEdit

### B. Opt-OUT default + rewrite the marketing
- ~14 marketing surfaces need to flip from "no telemetry" → "anonymous opt-out telemetry"
- Comparison-table row vs Camelot Pro flips — Camelot loses its weakness on this row
- Privacy page needs a section explaining what's collected + how to disable
- 20-30% higher data capture vs opt-in
- Some privacy-sensitive buyers will bounce — niche but real

### C. Opt-IN default with a prominent prompt in the onboarding wizard ← **CHOSEN**
- First-launch wizard shows a screen: *"Help us prioritise features — share anonymous version + connector use? (Recommended)"* with the recommended button focus-defaulted
- Marketing copy stays "opt-in" — still true, no edits needed across the 14 surfaces
- Realistic opt-in rate when the prompt is well-designed: **60–80%**
- Privacy pillar preserved, almost as much data as B

---

## Implementation guide

### Common to all three options

Whichever option lands, these have to be true before shipping:

1. **A POST endpoint exists** in the store repo at `src/pages/api/telemetry.json.ts`
   that accepts a small batch of events from the desktop app and writes to
   `telemetry_events` via the service-role client. Rate-limit by IP (or just
   cap to 100/min per IP using Netlify edge — see existing `preset-upload`
   for the rate-limiting pattern). Validate: `event` length < 80 chars,
   `app_version` matches semver regex, `extras` JSON < 2 KB.
2. **The desktop app has a `TelemetryClient`** at
   `src/gamepad_midi_bridge/telemetry.py` that:
   - Buffers events in memory (max 100 per flush, dropped FIFO if full)
   - Flushes every 15 minutes OR on graceful shutdown
   - POSTs to `https://midi.aidxn.com/api/telemetry.json` with a 3s timeout
   - Silent-fails — telemetry is never allowed to break the app
   - Reads the user's preference from `config["telemetry"]["enabled"]`
3. **A settings UI** in the app at `src/gamepad_midi_bridge/ui/settings_tab.py`
   with a checkbox: **"Share anonymous usage data"** + a short description
   explaining what's collected. Toggling it persists to `config.toml` immediately.
4. **A privacy page link** in the settings UI pointing at the store's
   `/privacy#telemetry` anchor.

### Option A (status quo) — nothing to do

Don't ship a telemetry emitter at all. Delete the table + views in a cleanup
migration. Move on.

### Option B (opt-out) extras

In the desktop app:
- Default `config["telemetry"]["enabled"]` to `True` in
  `src/gamepad_midi_bridge/config.py` (or wherever defaults live)
- During the onboarding wizard, show a non-blocking notice screen:
  *"This app shares anonymous version + feature-use metrics by default. You can disable this anytime in Settings → Privacy."* — single OK button
- The wizard MUST mention this; burying it loses the "informed" legal cover under AU Privacy Act 1988 and EU GDPR (even though the data is anonymous, opt-out collection without disclosure can still be argued in bad faith)

In the store repo (every change is a one-liner copy edit unless noted):
- `src/pages/privacy.astro:28` — replace the "transmits no telemetry" paragraph with the new opt-out wording (see `notes/telemetry-copy.md` for the canonical wording, or write it during the change)
- `src/components/sections/PricingSection.astro:97` — drop "No telemetry" from the footnote, or replace with "Anonymous opt-out telemetry"
- `src/components/sections/FAQVideoSection.astro:17` — rewrite the answer
- `src/components/sections/ComparisonSection.astro:45` — flip the row from `us: true` to `us: false`, OR rephrase the row label
- `src/layouts/BlogPost.astro:545` — update the inline "no telemetry" CTA
- `src/lib/emails.ts` — three remarketing templates mention "no telemetry"; update
- `src/pages/docs/concepts/marketplace.astro:91` — rewrite
- 10 blog posts under `src/pages/blog/` mention "no telemetry" in CTAs — sweep them with sed
- `public/llms.txt` — update the privacy line under Legal
- `src/data/releases.ts` v1.0.0 entry says "telemetry is opt-in, off by default" — rewrite for accuracy
- `src/pages/docs/advanced/pro-vs-free.astro` if it mentions telemetry

`grep -rn "telemetry" src/ public/` should hit every surface — there are about 14 last time I counted. Don't miss any.

### Option C (prominent opt-in) extras

In the desktop app:
- Default `config["telemetry"]["enabled"]` stays `False`
- During the onboarding wizard, show a dedicated step (NOT a checkbox buried elsewhere):
  - Title: **"Help us build what gets used."**
  - Body: *"Anonymous version + connector-use metrics. No personal data, no usage tracking, no fingerprinting. Hour-bucketed, not per-event timestamps."*
  - Two buttons side-by-side: **"Share anonymously" (default focus, teal)** and **"No thanks"** (outlined)
  - One-line disclaimer link: *"See what we collect →"* opens `/privacy#telemetry`
- A 30-day re-prompt is fine if they declined first time AND haven't seen v1.2+ yet (gentle nudge, not nagware)

In the store repo: **nothing changes**. Marketing copy stays accurate.

---

## Privacy / legal sanity check

Whichever option ships, these constraints are non-negotiable:

- **No PII ever** — no user ID, no email, no machine UUID, no IP, no MAC address. If the app
  emits anything PII-shaped, scrub it before write. Anonymity is the whole pitch.
- **Hour-bucketed timestamps** — `received_at_hour` is on purpose. Don't add per-second
  precision later "because it'd be nice for funnels." Once you have per-second
  timestamps + version + OS + connector list, you have a fingerprint.
- **Server-side scrubbing** — even if the client sends extras, the API endpoint
  drops any field starting with `_` and rejects payloads > 2 KB.
- **EU + AU customers** — opt-out is legal under both jurisdictions IF the data
  is genuinely anonymous AND disclosed prominently AND has a one-click off
  switch. Don't paint yourself into a corner by collecting anything that could
  be argued as personal information later.

---

## Acceptance criteria for "this work is done"

- [ ] Decision (A/B/C) locked in writing
- [ ] Desktop app emits events in line with the chosen option, with a working settings toggle
- [ ] Settings toggle persists across app launches
- [ ] `POST /api/telemetry.json` exists, rate-limited, validates payload size + shape
- [ ] Admin dashboard at `/admin/dashboard` actually shows real data after a day of use
- [ ] If option B: every "no telemetry" mention swept across the 14 surfaces (grep clean)
- [ ] Privacy page has a dedicated `#telemetry` section regardless of option
- [ ] This file is deleted

---

## Why this exists as a separate doc

Aiden asked to flip the default ON during the store-side launch sprint, when
the marketing was already locked in around "no telemetry." Rather than
make the change in haste and have to undo it (or worse, ship a marketing lie),
this doc captures the decision context + the implementation map so future-you
(or future-Claude) can finish the work cleanly when telemetry actually
becomes useful — which is post-launch, when you have enough users for the
data to be meaningful.

Until then: empty table, no emitter, marketing stays "no telemetry."
