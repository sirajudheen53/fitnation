# Play store listing content — FitNation (`com.getfitwithus.app`)

**Single source of the paste-copy for Play Console → Grow → Store presence →
Main store listing.** The orchestrator pastes each block below into the
Console; the Console keeps being a human step on purpose.

Machine-readable: `tools/play/publish.py listing --listing-content` /
`tools/play/publish.py release --listing-content …` read the sections below —
keep the exact `## <section>` headers as delimited here. Char limits are
enforced by `tools/play/publish.py check_limits` (title ≤ 30, short ≤ 80,
full ≤ 4000).

## App title

FitNation: Gym, Workouts, Diet
<!-- exactly 30 chars (Play limit 30). NOTE: the older checklist line
     "FitNation — Gym, Workouts & Diet" is 32 chars and "FitNation: Gym,
     Workouts & Diet" is 31 — BOTH are rejected by the 30-char field.
     Alternates (also valid): -->
<!-- FitNation — Gym & Workouts (27) | -->
<!-- FitNation — Your Gym App (25) | -->
<!-- FitNation (9) -->

## Short description

Workouts, diet plans, check-in QR & progress — your gym in your pocket.
<!-- 65-71 chars, max 80. First 60-80 chars are what Play shows in search — keep. -->

## Full description

FitNation is the official member app of your gym. Everything your gym plans
for you — workouts, diet, classes, check-ins, progress — is now in your
pocket, exactly as your trainer left it.

**Your phone number is your login.** Open the invite link your gym sends on
WhatsApp, sign in with your mobile number and the one-time OTP that arrives
by WhatsApp/SMS. No passwords, ever.

What you get:

• **Workouts** — the plan your trainer wrote for you; log sets, weight and
  reps, tick the day done.
• **Diet plan** — today's meals in one screen, with your macros.
• **Class booking** — book a seat for a live session with one tap.
• **Check-in** — show the QR at the front desk; your visit is counted.
• **Progress** — weight and body measurements, progress photos only you can
  see, charts that show the trend line, not just the last reading.
• **Streaks & reminders** — push notifications for booked classes and
  workout nudges from your gym.
• **Trainer chat** — quick questions straight to your gym's trainer.

How access works: your gym (any partner on FitNation, e.g. Hash Fit) issues
you a membership. Your active membership is your app access — there is no
in-app purchase, and it is included in what your gym charges you. No active
membership, no app access.

Your data, your call: everything you log — body measurements, progress
photos, injuries your trainer must know about — moves only between your
phone and FitNation's servers over encrypted HTTPS. It is never sold and
never shared with advertisers. Delete individual entries in the app, or ask
your gym to remove your whole account. See our privacy policy for the full
picture: https://yougetfitwithus.com/privacy

FitNation does not provide medical advice. Before starting any workout or
diet program, please consult your physician, especially if you have a
pre-existing condition.
<!-- ~2000/4000 chars. Paste as-is (plain text survives the paste; bold
     markers paste as plain text). Update the "e.g. Hash Fit" example only if
     the pilot tenant line-up changes. -->

## Changelog
<!-- Release notes; one fenced block per language tag. en-IN is the default. -->

### en-IN

```
First public release: your gym's workouts, diet plan, class booking, QR
check-in, and progress tracking — with passwordless OTP login.
```

### mr-IN

```
```

> Keep `mr-IN` empty rather than pasting English there; only fill it when a
> real marathi copy exists (unused empty language blocks are dropped by the
> publisher tool).

## Data Safety (App content → Data safety) — exact answers

Source of truth with the reasoning per row:
`mobile/store/play-health-data-disclosure.md`. Paste-answers:

- **Health & fitness → Health profile / body measurements:** collected • not
  shared • encrypted in transit • deletable • purpose: app functionality.
- **Photos & videos → Photos** (progress photos): collected • not shared •
  encrypted in transit • deletable • purpose: app functionality.
- **Personal info → Phone number:** collected • NOT optional (account
  creation/OTP) • encrypted in transit • deletable • app functionality.
- **Personal info → Name:** collected • required • app functionality.
- **Personal info → Email (optional), App activity → logs, Device/crash
  tokens:** as in the disclosure file.
- **"Does your app collect or share any of the required data types?"** → Yes.
- **Data deletion:** account-level deletion request in-app (Profile → Delete
  account → gym-admin approval → backend hard delete) + support email URL
  once published.
- **Privacy policy URL (required, review blocker):**
  `https://yougetfitwithus.com/privacy` — Siju hosts the page before
  submission (open item; URL is asserted here and in the full description).

## Health apps declaration (App content → Health apps) — paste copy

- Does your app contain Health features? → **Yes**
- Category → **Fitness & wellness** (NOT medical/telehealth)
- Declaration text (paste into the free-form acknowledgment/notes):

> FitNation lets members of partner gyms log their own fitness progress
> (weight, height, body measurements, progress photos, workout and diet
> check-ins) and communicate with their gym. It does not diagnose, treat,
> or prevent any disease or medical condition; it does not provide medical
> advice, clinical decision support, telemedicine, or emergency care; and it
> does not access electronic health records. All health data belongs to the
> individual member, is used only to show the member their own progress and
> to give their chosen gym's trainers visibility for coaching, is protected
> in transit with TLS, and can be deleted by the member (per item, in-app)
> or by their gym administrator (account level).

## What is still human-only here

- Screenshots (8-shot list in `mobile/store/README.md`; needs a device —
  Play rejects composited/fabricated ones) — **not produced yet**.
- Privacy policy + account-deletion URLs (open items in
  `play-health-data-disclosure.md`).
- Category "Health & Fitness", target audience 18+, content-rating
  questionnaire (answer photos honestly: private to the user).
- Reviewer access notes (template in `docs/play-release-checklist.md` §7).