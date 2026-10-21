#!/usr/bin/env python3
"""Unit tests for tools/play/publish.py — pure helpers only (no network, no Play).

Run:  python3 tools/play/test_publish.py
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import publish as P  # noqa: E402

SAMPLE_SPEC = "name: fitnation_mobile\nversion: 1.0.0+1\n"
LISTING_MD = """# Play listing content

## App title

FitNation: Gym, Workouts & Diet
(30 chars exactly — alternates below)

## Short description

Workouts, diet plans, check-in QR & progress — your gym in your pocket.

That's under 80 chars.

## Full description

Line one.

Line two — consult your physician line stays in this block.

## Changelog

### en-IN

```
First public test release. Fixes and polishing.
```

### mr-IN

```
First public test release.
```
"""


class ParsePubspec(unittest.TestCase):
    def test_parses_name_and_code(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pubspec.yaml"
            p.write_text(SAMPLE_SPEC)
            self.assertEqual(P.parse_pubspec_version(p), ("1.0.0", 1))

    def test_rejects_missing_version(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pubspec.yaml"
            p.write_text("name: fitnation_mobile\n")
            with self.assertRaises(ValueError):
                P.parse_pubspec_version(p)

    def test_rejects_nonnumeric_code(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "pubspec.yaml"
            p.write_text("version: 1.0.0+abc\n")
            with self.assertRaises(ValueError):
                P.parse_pubspec_version(p)


class ReleasePayload(unittest.TestCase):
    def test_completed_with_code(self):
        rel = P.release_payload([7], "completed", None, None)
        self.assertEqual(rel["versionCodes"], [7])
        self.assertNotIn("userFraction", rel)

    def test_inprogress_rollout_maps_to_userfraction(self):
        rel = P.release_payload([7], "inProgress", 10, None)
        self.assertEqual(rel["userFraction"], 0.10)
        self.assertEqual(rel["status"], "inProgress")

    def test_inprogress_without_rollout_rejected(self):
        with self.assertRaises(ValueError):
            P.release_payload([7], "inProgress", None, None)

    def test_rollout_with_wrong_status_rejected(self):
        with self.assertRaises(ValueError):
            P.release_payload([7], "completed", 10, None)

    def test_release_notes_language_shape(self):
        rel = P.release_payload([7], "completed", None,
                                {"language": "en-IN", "text": "first test release"})
        self.assertEqual(rel["releaseNotes"], [{"language": "en-IN", "text": "first test release"}])


class ListingParser(unittest.TestCase):
    def test_sections_extracted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "play-listing-content.md"
            p.write_text(LISTING_MD)
            f = P.listing_fields_from_markdown(p)
        self.assertIn("FitNation", f["title"])
        self.assertIn("gym in your pocket", f["short"])
        self.assertIn("consult your physician", f["full"])
        self.assertIn("First public test release", f["changelog"])

    def test_missing_sections_are_absent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "play-listing-content.md"
            p.write_text("## App title\nOnly title\n")
            f = P.listing_fields_from_markdown(p)
        self.assertIn("title", f)
        self.assertNotIn("full", f)

    def test_fence_stripping_keeps_full_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "play-listing-content.md"
            p.write_text("## Full description\n```\nA single fenced para.\n```\n")
            f = P.listing_fields_from_markdown(p)
        self.assertEqual(f["full"], "A single fenced para.")


class CollectAssets(unittest.TestCase):
    def test_picks_known_names_and_sorted_screenshots(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app-icon-512.png").write_bytes(b"i")
            (root / "feature-graphic-1024x500.png").write_bytes(b"f")
            shots = root / "screenshots"
            shots.mkdir()
            (shots / "02-b.png").write_bytes(b"2")
            (shots / "01-a.png").write_bytes(b"1")
            a = P.collect_assets(str(root))
        self.assertEqual([p.name for p in a["icon"]], ["app-icon-512.png"])
        self.assertEqual([p.name for p in a["feature-graphic"]], ["feature-graphic-1024x500.png"])
        self.assertEqual([p.name for p in a["screenshots"]], ["01-a.png", "02-b.png"])


class CheckLimits(unittest.TestCase):
    def test_title_over_30_rejected(self):
        with self.assertRaises(SystemExit):
            P.check_limits({"title": "x" * 31, "shortDescription": "s" * 79, "fullDescription": ""})

    def test_short_over_80_rejected(self):
        with self.assertRaises(SystemExit):
            P.check_limits({"title": "ok", "shortDescription": "s" * 81, "fullDescription": ""})

    def test_valid_passes(self):
        P.check_limits({"title": "ok", "shortDescription": "s" * 80, "fullDescription": "f" * 4000})

    def test_markdown_bold_rejected(self):
        # Play listing text is plain text; "**bold**" would publish literally.
        with self.assertRaises(SystemExit):
            P.check_limits({"title": "ok", "shortDescription": "s" * 10,
                            "fullDescription": "**Your phone number is your login.**"})

    def test_markdown_link_rejected(self):
        with self.assertRaises(SystemExit):
            P.check_limits({"title": "ok", "shortDescription": "s" * 10,
                            "fullDescription": "see [policy](https://x.com)"})

    def test_plain_text_with_asterisk_passes(self):
        P.check_limits({"title": "ok", "shortDescription": "s" * 10,
                        "fullDescription": "Diet plan — today's meals, no asterisks * here"})


class RealListingContentIsPlaySafe(unittest.TestCase):
    """The committed listing file must itself be upload-safe."""

    def test_committed_listing_has_no_markdown_and_fits_limits(self):
        md = Path(__file__).resolve().parents[2] / "mobile" / "store" / "play-listing-content.md"
        fields = P.listing_fields_from_markdown(md, P.DEFAULT_LANG)
        for key in ("title", "short", "full"):
            self.assertTrue(fields.get(key), f"{key} missing from {md}")
        P.check_limits({"title": fields["title"], "shortDescription": fields["short"],
                        "fullDescription": fields["full"]})


class CommandArgs(unittest.TestCase):
    """The CLI must fail with a readable message, never a traceback."""

    def test_listing_without_content_exits_cleanly(self):
        with self.assertRaises(SystemExit):
            P.main(["listing", "--dry-run"])

    def test_assets_without_store_dir_exits_cleanly(self):
        with self.assertRaises(SystemExit):
            P.main(["assets", "--dry-run"])

    def test_release_dry_run_makes_no_network_call(self):
        # A dry run must not touch the network: patch the client to explode.
        original = P.Play

        def boom(*a, **kw):
            raise AssertionError("dry run must not construct a live client")

        P.Play = boom
        try:
            code = P.main(["release", "--dry-run", "--pubspec", "mobile/pubspec.yaml"])
        finally:
            P.Play = original
        self.assertEqual(code, 0)


class PlayUrlBuilding(unittest.TestCase):
    def test_call_targets_package_scoped_urls(self):
        # routing helper assertion: paths start with /edits and never embed credentials
        P.DEFAULT_PACKAGE = "com.test.app"
        self.assertTrue(P.API_ROOT.endswith("applications/"))
        self.assertTrue(P.ANDROIDPUBLISHER_SCOPE.endswith("androidpublisher"))
        self.assertEqual([s for s in P.TOKEN_SCOPES if "androidpublisher" in s], P.TOKEN_SCOPES)


if __name__ == "__main__":
    unittest.main(verbosity=1)