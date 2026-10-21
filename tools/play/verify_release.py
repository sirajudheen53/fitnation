#!/usr/bin/env python3
"""Read-only go/no-go check for the FitNation Play release state.

Creates an edit, READS track states + listing + images for the package, then
discards the edit (no published change). Prints a go/no-go checklist and
exits 0 (go) / 1 (no-go) so it can gate an upload step.

Usage:
  tools/play/verify_release.py                       # package default, track internal
  tools/play/verify_release.py --expect-track production
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from publish import Play, ApiError, parse_pubspec_version, DEFAULT_PACKAGE, DEFAULT_SA, DEFAULT_LANG, IMAGE_TYPES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Play track/listing state (read-only)")
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--sa-file", default=os.environ.get("PLAY_SA_JSON", DEFAULT_SA))
    parser.add_argument("--token-cmd", default=None)
    parser.add_argument("--pubspec", default="mobile/pubspec.yaml")
    parser.add_argument("--expect-track", default="internal", choices=("internal", "alpha", "beta", "production"))
    parser.add_argument("--expect-version-code", type=int, default=None,
                        help="default: the versionCode from --pubspec")
    parser.add_argument("--lang", default=DEFAULT_LANG)
    args = parser.parse_args()

    pub_name, pub_code = parse_pubspec_version(Path(args.pubspec))
    expected_code = args.expect_version_code or pub_code

    play = Play(args.package, args.sa_file, args.token_cmd)
    try:
        edit = play.edit_create(False)
    except ApiError as e:
        print(f"✗ cannot even open an edit: HTTP {e.status}: {e.body}")
        print("  ('Item not found' → app shell not created yet, or first upload not yet propagated)")
        print("NO-GO")
        return 1

    checks: list[tuple[bool | None, str]] = []   # True pass / False fail / None info
    tracks: list[dict] = []
    try:
        tracks = play.call("GET", f"/edits/{edit}/tracks").get("tracks", [])
        if not tracks:
            checks.append((False, "no tracks have any release — nothing uploaded yet"))
        matched_expect_track = False
        for track in tracks:
            for release in track.get("releases", []):
                codes = [int(c) for c in release.get("versionCodes", [])]
                status = release.get("status")
                frac = release.get("userFraction")
                line = f"{track['track']:>12}: {status} codes={codes}" + (f" rollout={frac:.0%}" if frac is not None else "")
                if track["track"] == args.expect_track:
                    matched_expect_track = True
                    if expected_code in codes:
                        checks.append((True, line))
                    else:
                        checks.append((False, line + f" — expected versionCode {expected_code} (pubspec: {pub_name}+{pub_code})"))
                    if status == "halted":
                        checks.append((False, "  release is HALTED (staged rollout stopped) — investigate before shipping"))
                else:
                    checks.append((None, line))
        if not matched_expect_track:
            checks.append((False, f"track '{args.expect_track}' has no releases at all — nothing uploaded there yet"))

        listing_ok = False
        try:
            listing = play.call("GET", f"/edits/{edit}/listings/{args.lang}")
            title = listing.get("title", "")
            short = listing.get("shortDescription", "")
            full = listing.get("fullDescription", "")
            listing_ok = bool(title and short and full)
            checks.append((listing_ok,
                           f"listing({args.lang}): title={title!r} short={len(short)} chars full={len(full)} chars"))
        except ApiError as e:
            if e.status == 404:
                checks.append((False, f"no store listing for '{args.lang}' yet — title/short/full/images all missing"))
            else:
                checks.append((False, f"HTTP {e.status}: {e.body}"))

        if listing_ok:
            required, optional = ("icon", "featureGraphic"), ("phoneScreenshots",)
            for img_type in required + optional:
                try:
                    images = play.call("GET", f"/edits/{edit}/listings/{args.lang}/{img_type}").get("images", [])
                    empty = not images
                    if empty:
                        note = "REQUIRED for review" if img_type in required else "required before review; needs a device pass (see store/README.md)"
                        checks.append((False, f"images {img_type}: 0 — {note}"))
                    else:
                        checks.append((True if img_type in required else None, f"images {img_type}: {len(images)}"))
                except ApiError as e:
                    checks.append((False, f"images {img_type}: HTTP {e.status}"))
    except ApiError as e:
        checks.append((False, f"HTTP {e.status}: {e.body}"))
    finally:
        play.edit_delete(edit)

    print(f"Play state for {args.package} (expecting {pub_name}+{pub_code} → track '{args.expect_track}')\n")
    go = True
    for ok, text in checks:
        if ok is True:
            print(f"  ✅ {text}")
        elif ok is False:
            go = False
            print(f"  ✗ {text}")
        else:
            print(f"  ⚠ {text}")
    prod_live = any(
        r.get("status") == "completed" and any(int(c) for c in r.get("versionCodes", []))
        for t in tracks for r in t.get("releases", []) if t["track"] == "production")
    if prod_live:
        print(f"\n✅ production live — store URL: https://play.google.com/store/apps/details?id={args.package}")
    else:
        print("\n  (production not live — store URL not public yet)")
    print("\nGO ✅" if go else "\nNO-GO ❌")
    return 0 if go else 1


if __name__ == "__main__":
    sys.exit(main())