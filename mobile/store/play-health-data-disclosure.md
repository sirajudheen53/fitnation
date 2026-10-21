# Play Data Safety / Health apps disclosure — FitNation (com.getfitwithus.app)

Standing source of truth for Play Console → App content → Data safety and
→ **Health apps** declaration. Update this file whenever a release adds a new
data category. Values below reflect scope at release **1.0.0+1**.

## What the app actually stores (evidence: mobile/lib feature models)

| Data category | Concrete fields | Where |
|---|---|---|
| Health & fitness — Health profile | height, weight, fitness goals, gym membership context (`BodyMeasurement`, `FitnessGoal`, customer profile) | `lib/features/progress`, `lib/features/onboarding` |
| Health & fitness — Body measurements | weight (kg), height (cm), measurement history entries with timestamps | `lib/features/progress/data/models` |
| Health & fitness — Progress photos | user-taken body-progress photos attached to measurement/progress records | `lib/features/progress/.../progress_photos_screen.dart` |
| Identity | name, phone number (OTP auth), e-mail | `lib/features/access` |
| App activity | workout/diet check-ins, bookings, chat messages with the customer's gym | respective feature dirs |
| Device / other | FCM push token, app settings cache (Hive) | `lib/features/*/services` |

## Data safety questionnaire (Play Console form)

For every category above:

- **Collected?** Yes. **Purpose:** app functionality / personalization (display the
  customer's own profile, progress history, gym programs). **Not used for advertising.**
- **Shared with third parties?** No. Data is exchanged only with FitNation's
  servers over encrypted HTTPS and, for the customer's own gym, with the
  gym's authorized staff dashboards (same FitNation backend, tenant-scoped).
  No ad networks, no analytics-identity sharing, no data brokers.
- **Transmitted off the device?** Yes — to the customer's own
  FitNation-hosted backend only.
- **Encrypted in transit?** Yes — TLS 1.2+ HTTPS (Dio with certificate
  validation on; no plaintext fallback in release builds).
- **Stored on device?** Minimal offline cache (Hive) of the customer's own
  profile/preferences and in-flight uploads; can be cleared via system storage
  settings or by logging out.
- **Data deletion:**
  - Progress photos and individual measurements: deletable in-app
    (Progress → edit/delete record) — the record and its photo are removed
    from the backend.
  - Whole account / health profile: the customer's gym admin deletes the
    customer account (verified staff action), OR the customer writes to
    the support contact published in Play Console support email / in-app
    support screen. Play's account-deletion requirement is met through the
    in-app deletion request path → gym-admin approval → backend hard delete.
- **Optional collection:** progress photos and body measurements are
  entirely opt-in (customer creates them to track progress); the app works
  without them.

## Health apps declaration (Play Console → App content → Health apps)

FitNation is a **fitness, not telehealth/medical** app, and must be declared
in the "Fitness & wellness" category, NOT in any of the restricted
"Health services / clinical decision" categories. Use this wording:

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

## Play Console copy/paste checklist (when filling the forms)

1. Data type: **Health & fitness → Health profile** + **Health & fitness →
   Body measurements** (and **Photos & videos → Photos** for progress
   photos). Set each: collected, not shared, TLS-encrypted in transit,
   deletable, purpose = app functionality.
2. Health apps: declare **Fitness / wellness, personal progress tracking
   only**; answer "No" to all clinical/telemedicine declarations.
3. Account deletion URL: in-app path + support email (add final URL once
   the support inbox is live — orchestrator decision).

## Open items the product owner must confirm before submission

- Support/deletion e-mail address that will be published on the listing.
- Whether gym staff visibility of member data should be surfaced more
  explicitly in the first-build privacy policy text (Play policy requires
  the privacy policy URL to list this sharing honestly — it IS the same
  company backend, but state it plainly).
- Privacy policy URL (required on the listing) — does not exist yet.