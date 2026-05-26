# Launch checklist

Single source of truth for going from "code exists" to "users can buy and use it". Linear order — finish each section before the next. Allow ~3 hours total for someone who's never wired Stripe/Supabase/Netlify together before, ~45 minutes if you've done it before.

## 0. Pre-flight

- [ ] You have admin on `aidxn` GitHub account
- [ ] You have admin on `aidenthomasgodbywood@gmail.com` Netlify Builds team
- [ ] You own the `aidxn.com` domain
- [ ] You have a Stripe account (sole trader OK)
- [ ] You can receive email on `support@aidxn.com` (alias or mailbox)

## 1. Generate the license keypair (once, ever)

```bash
cd ~/Desktop/00\ -\ Aidxn/PS5-MIDI-Bridge
.venv/bin/python scripts/generate_license.py keygen
```

This writes:
- `scripts/private_key.pem` — **NEVER commit this**. Move to a password manager.
- `scripts/public_key.pem` — embed into the app.

Then:

```bash
# Paste the public key bytes into src/gamepad_midi_bridge/license.py
# Replace the PUBLIC_KEY_PEM placeholder block.
$EDITOR src/gamepad_midi_bridge/license.py

# Base64-encode the private key for the Netlify env var (next step)
base64 -i scripts/private_key.pem | pbcopy
```

Verify the round-trip works locally:

```bash
.venv/bin/python scripts/generate_license.py sign --email test@example.com > /tmp/test.license
.venv/bin/python -c "
from gamepad_midi_bridge.license import activate_from_string, is_pro
with open('/tmp/test.license') as f:
    s = activate_from_string(f.read())
print('is_pro:', is_pro(), 'email:', s.email, 'reason:', s.reason)
"
```

Should print `is_pro: True`.

Commit the public-key change:

```bash
git add src/gamepad_midi_bridge/license.py
git commit -m "Embed production Ed25519 public key for license verification"
git push
```

## 2. Stripe (15 min)

1. Stripe Dashboard → Products → Create product "Universal Controller MIDI Pro" → one-time payment, currency = AUD or USD as you prefer, $49.
2. Copy the **price ID** (`price_...`) — used by the webhook to sanity-check that incoming sessions are for this product.
3. Stripe Dashboard → Settings → Tax → enable **Stripe Tax**. Add your ABN.
4. Stripe Dashboard → Payment Links → New → pick the Pro product. In **"After payment"**, choose "Don't show confirmation page" and set the custom URL to:
   `https://store.aidxn.com/success?session_id={CHECKOUT_SESSION_ID}`
   Copy the resulting `https://buy.stripe.com/...` URL.
5. Paste the Payment Link URL into the four `https://buy.stripe.com/...` strings in `src/pages/index.astro` + `src/components/Nav.astro` (already wired for the V1 link).
6. Stripe Dashboard → Developers → API keys → copy the **live secret key** (`sk_live_...`).
7. Stripe Dashboard → Developers → Webhooks → Add endpoint → URL = `https://store.aidxn.com/api/stripe-webhook` → event = `checkout.session.completed` → copy the **signing secret** (`whsec_...`).

## 3. Resend (5 min)

1. Sign up at resend.com.
2. Add `aidxn.com` as a domain — add the SPF + DKIM records to Netlify DNS when prompted.
3. Verify the domain (DNS propagation usually 2-10 minutes).
4. API Keys → Create → copy the key (`re_...`).

## 4. Supabase (10 min)

1. supabase.com → New project → name `gamepad-midi-bridge`, region closest to your customers (AU East = Sydney for Aussie + APAC).
2. Once provisioned, Project Settings → API → copy:
   - **Project URL**
   - **anon (public) key**
   - **service_role (secret) key** — never expose this to browser code.
3. SQL Editor → run both migrations in order:
   - `supabase/migrations/20260526120000_marketplace.sql`
   - `supabase/migrations/20260526130000_telemetry.sql`

## 5. Netlify env vars (5 min)

Open https://app.netlify.com/projects/gamepad-midi-bridge-store → Site settings → Environment variables → add each:

| Key | Value source |
|---|---|
| `LICENSE_PRIV_KEY_V1` | base64'd `scripts/private_key.pem` from step 1 |
| `STRIPE_API_KEY` | `sk_live_...` from step 2.6 |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from step 2.7 |
| `STRIPE_PRICE_ID` | `price_...` from step 2.2 (defensive sanity check, optional but recommended) |
| `RESEND_API_KEY` | `re_...` from step 3.4 |
| `RECOVERY_EMAIL_FROM` | e.g. `noreply@aidxn.com` |
| `SUPABASE_URL` | from step 4.2 |
| `SUPABASE_ANON_KEY` | from step 4.2 |
| `SUPABASE_SERVICE_ROLE_KEY` | from step 4.2 |
| `ADMIN_TOKEN` | a long random string (`openssl rand -hex 32`) |

Save. Trigger a redeploy from the Deploys tab.

## 6. Swap the placeholder Stripe URL (5 min)

In `PS5-MIDI-Bridge-Store/src/pages/index.astro`, replace **4 occurrences** of:

```
https://buy.stripe.com/PLACEHOLDER
```

with the URL you copied in step 2.4.

```bash
cd ~/Desktop/00\ -\ Aidxn/PS5-MIDI-Bridge-Store
git add . && git commit -m "Wire production Stripe Checkout link" && git push
```

Netlify auto-deploys.

## 7. Wire DNS (5 min, propagation 5-30 min)

On the `aidxn.com` DNS zone (Netlify DNS or your registrar):

| Type | Name | Value |
|---|---|---|
| `CNAME` | `store` | `gamepad-midi-bridge-store.netlify.app` |
| (whatever Resend asked for in step 3.2) | … | … |

Then in Netlify → Domain management → Add custom domain → `store.aidxn.com`. Wait for cert issuance (Netlify does Let's Encrypt automatically).

## 8. Seed the marketplace (1 min)

```bash
cd ~/Desktop/00\ -\ Aidxn/PS5-MIDI-Bridge-Store
SUPABASE_URL='https://...' SUPABASE_SERVICE_ROLE_KEY='eyJ...' \
    python scripts/load_seed_presets.py
```

Refresh `store.aidxn.com/marketplace` — should show 8 presets.

## 9. Build + tag the first release (10 min)

```bash
cd ~/Desktop/00\ -\ Aidxn/PS5-MIDI-Bridge
# Bump version if needed
$EDITOR src/gamepad_midi_bridge/__init__.py
git add . && git commit -m "Bump to v0.1.0"
git tag v0.1.0 && git push origin v0.1.0
```

GitHub Actions builds zips for mac/win/linux and attaches them to a GitHub Release at `https://github.com/aidenwood/gamepad-midi-bridge/releases/tag/v0.1.0`. The store landing page auto-detects them via the `latest-release.json.ts` endpoint and points the Download button at the right asset.

## 10. End-to-end smoke test

- Visit `store.aidxn.com` → click "Buy Pro $49" → use a Stripe test card (`4242 4242 4242 4242`, any future expiry, any CVC) — or your own card if you're confident.
- Within 10 seconds, you should receive a license email at the address you used. The body contains the license blob.
- Download the free `.app` → install → About → "Enter license key" → paste the blob.
- "Pro unlocked" dialog. All Pro panels' lock overlays disappear.

## 11. Marketing (post-launch, ~2 hours)

- [ ] Record the 90-second demo video per `docs/video-script-90s.md`
- [ ] Upload to YouTube, copy the embed ID
- [ ] Replace `PLACEHOLDER_VIDEO_ID` in `src/pages/index.astro` (1 occurrence)
- [ ] Tweet from `@aidxndesign` with a 60-second cutdown
- [ ] Post in Resolume + Ableton forums (community-friendly, not spam)
- [ ] Submit to producthunt.com
- [ ] Email beta testers (you can pre-seed a list via the in-app marketplace authors who opt in)

## Rollback

If something explodes between step 9 and step 11, you can:
- Pause new Stripe checkouts — Dashboard → Products → archive the Pro product
- Revert the Netlify deploy — Deploys tab → previous deploy → Publish
- Rotate license signing key — generate a new keypair, update app `PUBLIC_KEY_PEM`, bump `keyVersion` in `LICENSE_PRIV_KEY_V2`, ship app update

## You're done

Total wall-clock from this checklist: ~3 hours including DNS propagation.
