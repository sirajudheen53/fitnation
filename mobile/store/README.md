# Play listing assets — FitNation (com.getfitwithus.app)

Map of every asset in this directory to its Play Console slot. Console path →
Grow → Store presence → Main store listing (unless noted).

| Play Console slot | Requirement | Asset in this repo |
|---|---|---|
| App icon | 512×512 PNG, opaque, full square (Play masks it) | `app-icon-512.png` |
| Feature graphic | 1024×500 PNG, no text near edges | `feature-graphic-1024x500.png` |
| Phone screenshots | 2–8 PNGs, min 320px, max 3840px, 9:16-ish | **NOT PRODUCED** — see "Screenshots" below |
| App category / tags | Fitness | — (Console choice) |

Regenerate the listing art with the committed script (brand palette in
`lib/core/theme/app_theme.dart`: primary `#6C13E2`, dark `#4B0E9F`,
light `#9D54F0`, mint `#00E5A0`):

```bash
cd mobile && python3 store/generate_store_assets.py
```

The same brand mark is also wired into the launcher itself:
`android/app/src/main/res/mipmap-*/ic_launcher.png` (legacy) and
`mipmap-*/ic_launcher_{foreground,background,mono}.png` +
`mipmap-anydpi-v26/ic_launcher.xml` (adaptive + Android 13 themed icon).

## Screenshots — status: NOT AVAILABLE (be explicit)

**No real screenshots were produced because this release machine has no
Android device or emulator. Play rejects fabricated/composited images and the
project rule forbids faking them.** The upload step (orchestrator) therefore
needs a device pass first.

### Precise shot list (capture on an API 33+ phone, 1080×2400; enable USB
debug → `flutter install --release` first)

All shots: light theme, onboarding data REAL or seeded demo tenant (never
another person's data), status bar clean (airplane mode, full battery).

| # | Screen (route) | State to show | What it sells |
|---|---|---|---|
| 1 | Splash/gym-code entry (deep-link or manual gym code) | tenant-loaded dashboard empty state | "Join my gym in ten seconds" |
| 2 | Dashboard (home) | populated widgets: today's class, streak, quick actions | daily operating screen |
| 3 | Bookings | session list with an upcoming class + CTA | one-tap class booking |
| 4 | Workout tracking | active workout screen with sets logged | logger UX |
| 5 | Progress | progress chart (fl_chart) + latest measurement row | visible results |
| 6 | Progress photos | photo grid with a couple of seeded photos | body-progress story |
| 7 | Diet plan | today's meal cards | nutrition guidance |
| 8 | Chat with trainer | one friendly exchange with the gym's trainer | human support |

Capture: `adb shell screencap -p /sdcard/s.png && adb pull /sdcard/s.png
store/screenshots/01-gym-code.png` (increment naming `0N-<route>.png` to match
this table; Play slots: screenshots 1–3 of the phone set are auto-chosen in
upload order — put 2, 5, 6 first if only three are used).

## Assets still needed from humans (not machine generatable)

- Real screenshots (the 8 above) — needs device + seeded demo tenant.
- Privacy policy URL + account-deletion URL (see
  `play-health-data-disclosure.md` open items).
- The Console paste itself (the copy is ready in
  `play-listing-content.md`; the paste stays a human step — or use
  `tools/play/publish.py listing --listing-content mobile/store/play-listing-content.md`).

## Marketing copy — DONE ✅

App name, short description, full description and changelog are written and
length-checked in `play-listing-content.md`:

| Field | Value | Limit |
|---|---|---|
| Title | `FitNation: Gym, Workouts, Diet` | 30 / 30 |
| Short description | `Workouts, diet plans, check-in QR & progress — your gym in your pocket.` | 71 / 80 |
| Full description | 1811 chars, plain text (no markdown) | 1811 / 4000 |

Play listing text is **plain text** — the Console does not render markdown, so
`**bold**` would be published literally. `tools/play/publish.py` refuses to
upload a listing containing markdown markers.