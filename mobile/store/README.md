# Play listing assets — FitNation (com.getfitwithus.app)

Map of every asset in this directory to its Play Console slot. Console path →
Grow → Store presence → Main store listing (unless noted).

| Play Console slot | Requirement | Asset in this repo |
|---|---|---|
| App icon | 512×512 PNG, opaque, full square (Play masks it) | `app-icon-512.png` |
| Feature graphic | 1024×500 PNG, no text near edges | `feature-graphic-1024x500.png` |
| Phone screenshots | 2–8 PNGs, min 320px, max 3840px, 9:16-ish | `screenshots/01-dashboard.png` … `04-qr-checkin.png` — rendered from the real app UI |
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

## Screenshots — DONE (rendered from the real app UI)

The four phone screenshots are **widget captures of the real app screens** (actual
Flutter widgets, the app's `AppTheme.light`, the app's Inter font via
`google_fonts`) pumped with realistic demo member data ("Raman Kumar @ Hash Fit",
Hypertrophy PPL plan, Lean Cut diet, 6-day streak, QR check-in) through the
flutter test framework — not fabricated marketing art. No device needed.

| # | File | Screen |
|---|---|---|
| 1 | `screenshots/01-dashboard.png` | Dashboard (greeting, quick actions, AI features, today's workout/diet) |
| 2 | `screenshots/02-workouts.png` | Workouts — plan header + workout days |
| 3 | `screenshots/03-diet-plan.png` | Diet plan — plan header + meal days |
| 4 | `screenshots/04-qr-checkin.png` | Enrollment QR (gym check-in) |

All are exactly 1080×1920 RGB (Play phone-screenshot requirement). The capture
renders at logical 540×960 @ dpr 2.0 (the xhdpi 1080p phone profile; narrower
360/432dp widths overflow the plan-header meta rows in the real screens).

Regenerate (from `mobile/`):

```bash
flutter test test/store/screenshot_capture_test.dart
```

The test writes the PNGs, then flatten + verify them with PIL (Play rejects
transparent PNGs):

```bash
python3 - <<'EOF'
from PIL import Image
import os
d = 'store/screenshots'
names = ['01-dashboard.png', '02-workouts.png', '03-diet-plan.png', '04-qr-checkin.png']
for n in names:
    p = os.path.join(d, n)
    img = Image.open(p)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGBA')
        base = Image.new('RGB', img.size, (248, 247, 250))
        base.paste(img, mask=img.split()[-1])
        img = base
    else:
        img = img.convert('RGB')
    img.save(p)
    img2 = Image.open(p); img2.load()
    assert img2.size == (1080, 1920) and img2.mode == 'RGB', (n, img2.size, img2.mode)
    assert os.path.getsize(p) > 30_000, (n, 'too small / blank')
    print(n, img2.size, img2.mode, os.path.getsize(p), 'bytes OK')
EOF
```

Note: the Inter TTF fixtures under `test/store/fonts/` are SIL OFL 1.1
(redistribution permitted) and are hash-verified against the google_fonts
package data, so the capture runs fully offline.

### Optional: higher-fidelity shots on a real device (API 33+ phone,
### 1080×2400; enable USB debug → `flutter install --release` first)

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

- ~~Real screenshots~~ — DONE for the Play minimum (4 widget captures above);
  device shots of the remaining flows (bookings, progress charts, chat) remain
  a nice-to-have.
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