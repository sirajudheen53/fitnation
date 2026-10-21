#!/usr/bin/env python3
"""Publish the FitNation Android app to Google Play via a service account.

Covers the androidpublisher v3 edit workflow used for `com.getfitwithus.app`
(upload AAB → set track → update listing → upload images → commit), all inside
one edit so every command is atomic (commit publishes, abort discards).

Design ground rules:
- stdlib + google-auth only (no request libs).
- Reads the access token from the service account file (google-auth JWT
  exchange at call time) — the file is NEVER copied into the repo and the
  token is never printed. Errors print status + response body only.
- Idempotent: every command re-creates the same desired state, listings are
  overwritten, existing listing images are replaced after a wipe.
- `--dry-run` makes no network calls at all and prints what would happen.

Examples:
  # read-only: what do the tracks look like right now?
  tools/play/publish.py tracks
  tools/play/publish.py tracks --package com.getfitwithus.app

  # full release: AAB → internal track (+notes) + listing + assets, one edit
  tools/play/publish.py release \
    --aab mobile/build/app/outputs/bundle/release/app-release.aab \
    --track internal --status completed \
    --changelog mobile/store/changelog-en-IN.txt \
    --listing-content mobile/store/play-listing-content.md \
    --store-dir mobile/store --dry-run      # then drop --dry-run

  # listing text / assets only
  tools/play/publish.py listing --listing-content mobile/store/play-listing-content.md
  tools/play/publish.py assets --store-dir mobile/store
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ANDROIDPUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
API_ROOT = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/"
UPLOAD_ROOT = "https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/"
DEFAULT_PACKAGE = "com.getfitwithus.app"
DEFAULT_SA = os.path.join(os.path.expanduser("~"), ".play-cred", "fb-sa.json")
DEFAULT_LANG = "en-IN"
VALID_TRACKS = ("internal", "alpha", "beta", "production")
TOKEN_SCOPES = [ANDROIDPUBLISHER_SCOPE]
IMAGE_TYPES = {"icon": "icon", "feature-graphic": "featureGraphic", "screenshots": "phoneScreenshots"}


class ApiError(RuntimeError):
    def __init__(self, status: int, body: str, what: str):
        self.status, self.body, self.what = status, body, what
        super().__init__(f"{what} failed: HTTP {status}: {trim(body)}")


def trim(body: str, n: int = 600) -> str:
    body = re.sub(r"\s+", " ", body or "")
    return body[:n]


def parse_pubspec_version(pubspec: Path) -> tuple[str, int]:
    """`version: 1.0.0+1` → ("1.0.0", 1)."""
    for line in pubspec.read_text().splitlines():
        if not re.match(r"^version:", line):
            continue
        value = line.split(":", 1)[1].strip()
        name, _, code = value.partition("+")
        if name and code.isdigit():
            return name, int(code)
        raise ValueError(f"{pubspec}: cannot parse 'MAJOR.MINOR.PATCH+CODE' from {line!r}")
    raise ValueError(f"{pubspec}: no 'version:' line")


def listing_fields_from_markdown(md_path: Path, lang: str = DEFAULT_LANG) -> dict:
    """Parse mobile/store/play-listing-content.md (its own fenced format).

    Sections it reads: `## App title` (+ `<!-- <lang> -->` alternates),
    `## Short description`, `## Full description`, `## Changelog` (one fenced
    block per `### <lang>`). Returns {"title", "full", "short", "changelog"}.
    """
    text = md_path.read_text()
    out: dict[str, str] = {}
    for section, key in (("App title", "title"), ("Short description", "short"),
                         ("Full description", "full"), ("Changelog", "changelog")):
        m = re.search(rf"^## {section}\b.*?\n(.*?)(?=^## |\Z)", text, re.S | re.M)
        if not m:
            continue
        body = m.group(1)
        if key == "changelog":
            m2 = re.search(rf"^### {re.escape(lang)}\b.*?\n(```.*?\n)(.*?)(?=```)", body, re.S | re.M)
            if m2:
                out[key] = m2.group(2).strip()
            continue
        body = re.sub(r"^```.*?\n(.*?)```\s*$", r"\1", body, flags=re.S | re.M)
        body = re.sub(r"^<!--.*?-->\s*$", "", body, flags=re.S | re.M)
        # first non-empty plain-text line, keeping multi-line full descriptions intact
        lines = [ln for ln in body.splitlines() if ln.strip()]
        if lines:
            out[key] = "\n".join(lines).strip()
    return out


# ── Play API client ─────────────────────────────────────────────────────────
class Play:
    def __init__(self, package: str, sa_file: str, token_cmd: str | None):
        self.package = package
        self.sa_file = sa_file
        self.token_cmd = token_cmd
        self._token: str | None = None

    def token(self) -> str:
        if self.token_cmd:
            proc = subprocess.run(self.token_cmd, shell=True, capture_output=True, text=True, check=True)
            tok = (proc.stdout or "").strip().splitlines()
            if not tok:
                raise RuntimeError("token command produced no output")
            self._token = tok[0]
        elif os.environ.get("PLAY_ACCESS_TOKEN"):
            self._token = os.environ["PLAY_ACCESS_TOKEN"]
        else:
            self._token = _token_from_sa(self.sa_file)
        return self._token

    def call(self, method: str, path: str, payload=None, body_data=None, content_type="application/json", timeout=420, upload: bool = False) -> dict:
        # Binary media uploads (AAB, images) must go through Google's /upload/
        # endpoint; the plain JSON API rejects raw binary payloads with HTTP 400.
        root = UPLOAD_ROOT if upload else API_ROOT
        url = f"{root}{self.package}{path}"
        headers = {"Authorization": f"Bearer {self.token()}"}
        body = None
        if payload is not None:
            headers["Content-Type"] = content_type
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        elif payload is None and body_data is not None:
            headers["Content-Type"] = content_type
            body = body_data
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as e:
            raise ApiError(e.code, e.read().decode(), f"{method} {path}")

    # edit lifecycle (all changes go in one edit → atomic commit or discard)
    def edit_create(self, dry: bool) -> str:
        if dry:
            return "<dry-run-edit-id>"
        return self.call("POST", "/edits", payload={})["id"]

    def edit_delete(self, edit_id: str):
        if edit_id != "<dry-run-edit-id>":
            self.call("DELETE", f"/edits/{edit_id}")

    def list_tracks(self) -> dict:
        e = self.edit_create(False)
        try:
            return self.call("GET", f"/edits/{e}/tracks")
        finally:
            self.edit_delete(e)   # read-only: discard the empty edit


def _token_from_sa(sa_file: str) -> str:
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError as e:
        sys.exit("google-auth is required: `python3 -m pip install google-auth` "
                 "(or activate backend/.venv). Original error: " + str(e))
    if not os.path.isfile(sa_file):
        sys.exit(f"service-account JSON not found at {sa_file} (--sa-file / PLAY_SA_JSON)")
    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=TOKEN_SCOPES)
    creds.refresh(Request())
    return creds.token


# ── desired-state builders ──────────────────────────────────────────────────
def release_payload(version_codes: list[int], status: str, rollout: float | None, notes: dict | None) -> dict:
    release: dict = {"status": status}
    if rollout is not None and status == "inProgress":
        release["userFraction"] = rollout / 100.0
    if status == "inProgress" and not rollout:
        raise ValueError("--status inProgress requires --rollout PCT")
    if status != "inProgress" and rollout is not None and rollout != 100:
        raise ValueError("--rollout only meaningful with --status inProgress (or omit)")
    release["versionCodes"] = [int(v) for v in version_codes]   # Play wants JSON numbers
    if notes:
        release["releaseNotes"] = [{"language": notes["language"], "text": notes["text"]}]
    return release


def collect_assets(store_dir: str) -> dict[str, list[Path]]:
    """Expected layout (all optional, per present files):
    mobile/store/app-icon-512.png              → icon
    mobile/store/feature-graphic-1024x500.png  → featureGraphic
    mobile/store/screenshots/*.png             → phoneScreenshots (upload order = slot order)
    """
    root = Path(store_dir)
    assets: dict[str, list[Path]] = {}
    icon = root / "app-icon-512.png"
    feature = root / "feature-graphic-1024x500.png"
    if icon.exists():
        assets["icon"] = [icon]
    if feature.exists():
        assets["feature-graphic"] = [feature]
    shots = sorted((root / "screenshots").glob("*.png"))
    if shots:
        assets["screenshots"] = shots
    return assets


# ── commands ────────────────────────────────────────────────────────────────
def cmd_tracks(args) -> int:
    play = Play(args.package, args.sa_file, args.token_cmd)
    if args.dry_run:
        print("dry-run: would create edit → GET /tracks → DELETE edit (no network)")
        return 0
    data = play.list_tracks()
    versions = {}
    pubspec = args.pubspec
    if os.path.isfile(pubspec):
        pub = parse_pubspec_version(Path(pubspec))
        versions = {"name": pub[0], "code": pub[1]}
    for track in data.get("tracks", []):
        for release in track.get("releases", []):
            print(f"{track['track']:>12}: status={release.get('status')} "
                  f"codes={release.get('versionCodes')} "
                  f"rollout={release.get('userFraction', '*') if release.get('status') == 'inProgress' else '-'}")
    if versions:
        print(f"pubspec     : versionCode {versions['code']} (v{versions['name']})")
    return 0


def cmd_release(args) -> int:
    md = Path(args.listing_content) if args.listing_content else None
    fields = listing_fields_from_markdown(md, args.lang) if md else {}
    if args.changelog:
        fields["changelog"] = Path(args.changelog).read_text().strip()
    assets = collect_assets(args.store_dir) if args.store_dir else {}

    name, code = parse_pubspec_version(Path(args.pubspec))
    if args.aab and not os.path.isfile(args.aab):
        sys.exit(f"AAB not found: {args.aab}")

    release = release_payload([code], args.status, args.rollout,
                              {"language": args.lang, "text": fields["changelog"]} if fields.get("changelog") else None)

    print(f"plan ({'DRY RUN' if args.dry_run else 'LIVE'}): package={args.package} track={args.track}")
    print(f"  aab: {args.aab or '(none — listing/assets only)'} "
          f"→ versionCode {code} v{name}")
    print(f"  track release: status={args.status} rollout={args.rollout if args.status == 'inProgress' else '-'} "
          f"codes=[{code}] changelog={'yes' if fields.get('changelog') else 'no'}")
    for key, paths in assets.items():
        for p in paths:
            print(f"  asset {IMAGE_TYPES[key]}> {p.name} ({p.stat().st_size} bytes)")
    if fields.get("title") and fields.get("short") and fields.get("full"):
        print(f"  listing ({args.lang}): title={fields['title']!r} short={fields['short']!r} "
              f"full={len(fields['full'])} chars")
        check_limits({"title": fields["title"], "shortDescription": fields["short"],
                      "fullDescription": fields["full"]})

    if args.dry_run:
        print("dry-run: would create edit → (upload bundle) → (put track) → (put listing) → "
              "(wipe+upload images) → ':commit'. No network calls made.")
        return 0

    play = Play(args.package, args.sa_file, args.token_cmd)
    edit = play.edit_create(False)
    try:
        if args.aab:
            print("uploading AAB …")
            resp = play.call("POST", f"/edits/{edit}/bundles?uploadType=media",
                             payload=Path(args.aab).read_bytes(),
                             content_type="application/octet-stream", timeout=1200, upload=True)
            uploaded = int(resp["versionCode"])
            print(f"↳ uploaded; Play versionCode={uploaded}")
            if uploaded != code:
                print(f"⚠ Play saw versionCode {uploaded}, pubspec {code} — continuing with Play's value")
            release = release_payload([uploaded], args.status, args.rollout,
                                      {"language": args.lang, "text": fields["changelog"]} if fields.get("changelog") else None)
        if fields:
            missing = [k for k in ("title", "short", "full") if not fields.get(k)]
            if missing:
                sys.exit(f"listing content is incomplete ({', '.join(missing)} missing) — refusing "
                         f"to publish a partial listing for {args.lang}")
            listing = {"language": args.lang, "title": fields["title"],
                       "shortDescription": fields["short"], "fullDescription": fields["full"]}
            play.call("PUT", f"/edits/{edit}/listings/{args.lang}", payload=listing)
        if assets and args.wipe_images:
            for img_type in assets:
                play.call("DELETE", f"/edits/{edit}/listings/{args.lang}/{IMAGE_TYPES[img_type]}")
        for img_type, paths in assets.items():
            for p in paths:
                ctype = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                play.call("POST", f"/edits/{edit}/listings/{args.lang}/{IMAGE_TYPES[img_type]}",
                          payload=p.read_bytes(), content_type=ctype, timeout=300, upload=True)
        play.call("PUT", f"/edits/{edit}/tracks/{args.track}", payload={"releases": [release]})
        play.call("POST", f"/edits/{edit}:commit", payload={})
        print(f"✅ committed edit {edit}: track {args.track} now points at versionCode "
              f"[{code}], status {args.status}")
        return 0
    except ApiError as e:
        print(f"discarding failed edit {edit} (nothing was published)", file=sys.stderr)
        print(f"play call failed ({e.what}): HTTP {e.status}: {trim(e.body)}", file=sys.stderr)
        if e.status == 401:
            print("401: access token rejected — the SA credential may lack androidpublisher access to this app", file=sys.stderr)
        if e.status == 404:
            print("404 'Item not found': the Play app shell (package name) may not exist yet, "
                  "OR the first AAB upload has not propagated from this SA yet (can take hours for brand-new apps)", file=sys.stderr)
        if "changesNotSentForReview" in e.body:
            print("hint: commit was refused because this edit has pending changes that require review — re-run "
                  "is identical (idempotent); Play asks for a review on first edits", file=sys.stderr)
        return 1
    finally:
        pass


def cmd_listing(args) -> int:
    """Upsert main-store listing text for --lang (title/short/full) in one edit."""
    if not args.listing_content:
        sys.exit("listing needs --listing-content "
                 "(e.g. --listing-content mobile/store/play-listing-content.md)")
    fields = listing_fields_from_markdown(Path(args.listing_content), args.lang)
    missing = [k for k in ("title", "short", "full") if not fields.get(k)]
    if missing:
        sys.exit(f"missing in {args.listing_content}: {', '.join(missing)} — see the file's section format")
    listing = {"language": args.lang, "title": fields["title"].strip(),
               "shortDescription": fields["short"].strip(),
               "fullDescription": fields["full"].strip()}
    check_limits(listing)
    print(f"plan ({'DRY RUN' if args.dry_run else 'LIVE'}): listing {args.lang} "
          f"title={listing['title']!r} ({len(listing['title'])}/30 chars) short="
          f"({len(listing['shortDescription'])}/80 chars) full="
          f"({len(listing['fullDescription'])}/4000 chars)")
    if args.dry_run:
        print("dry-run: create edit → PUT /listings/%s → ':commit'" % args.lang)
        return 0
    play = Play(args.package, args.sa_file, args.token_cmd)
    edit = play.edit_create(False)
    try:
        play.call("PUT", f"/edits/{edit}/listings/{args.lang}", payload=listing)
        play.call("POST", f"/edits/{edit}:commit", payload={})
        print(f"✅ committed edit {edit}: listing updated")
        return 0
    except ApiError as e:
        print(f"discarding failed edit {edit} (nothing was published)", file=sys.stderr)
        if e.status == 404:
            print("404 'Item not found': Play app shell may not exist yet (see "
                  "docs/play-release-checklist.md §0.1)", file=sys.stderr)
        return 1


def cmd_assets(args) -> int:
    """Replace listing images for --lang (icon / featureGraphic / phoneScreenshots)."""
    assets = collect_assets(args.store_dir)
    if not assets:
        sys.exit(f"no store assets found under {args.store_dir} "
                 "(app-icon-512.png / feature-graphic-1024x500.png / screenshots/*.png)")
    print(f"plan ({'DRY RUN' if args.dry_run else 'LIVE'}): assets {args.lang}")
    for key, paths in assets.items():
        for p in paths:
            print(f"  {IMAGE_TYPES[key]}> {p.name} ({p.stat().st_size} bytes)")
    if args.dry_run:
        print("dry-run: create edit → wipe+POST images per type → ':commit'")
        return 0
    play = Play(args.package, args.sa_file, args.token_cmd)
    edit = play.edit_create(False)
    try:
        for img_type in assets:
            play.call("DELETE", f"/edits/{edit}/listings/{args.lang}/{IMAGE_TYPES[img_type]}")
        for img_type, paths in assets.items():
            for p in paths:
                ctype = "image/jpeg" if p.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                play.call("POST", f"/edits/{edit}/listings/{args.lang}/{IMAGE_TYPES[img_type]}",
                          payload=p.read_bytes(), content_type=ctype, timeout=300, upload=True)
        play.call("POST", f"/edits/{edit}:commit", payload={})
        print(f"✅ committed edit {edit}: {sum(len(v) for v in assets.values())} image(s) replaced")
        return 0
    except ApiError as e:
        print(f"discarding failed edit {edit} (nothing was published)", file=sys.stderr)
        if e.status == 404:
            print("404 'Item not found': Play app shell may not exist yet (see "
                  "docs/play-release-checklist.md §0.1)", file=sys.stderr)
        return 1


def check_limits(listing: dict) -> None:
    limits = {"title": 30, "shortDescription": 80, "fullDescription": 4000}
    for key, cap in limits.items():
        if len(listing[key]) > cap:
            sys.exit(f"Play {key} limit is {cap} chars; got {len(listing[key])} (fix the listing content file)")
    check_plain_text(listing)


# Play listing fields are PLAIN TEXT — the Console renders them verbatim and
# does not interpret markdown. "**bold**" would be published as literal
# asterisks. Catch that here rather than after the paste.
MARKDOWN_MARKERS = (("**", "bold"), ("\n#", "heading"), ("](", "markdown link"))


def check_plain_text(listing: dict) -> None:
    for key in ("title", "shortDescription", "fullDescription"):
        text = listing.get(key) or ""
        for marker, label in MARKDOWN_MARKERS:
            if marker in text:
                sys.exit(
                    f"Play {key} contains markdown ({label}: {marker!r}). Play listing text is "
                    "plain text — it would be published literally. Rewrite the phrase in "
                    "mobile/store/play-listing-content.md without markdown markers."
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="publish.py", description=__doc__.splitlines()[1])
    parser.add_argument("--package", default=DEFAULT_PACKAGE)
    parser.add_argument("--sa-file", default=os.environ.get("PLAY_SA_JSON", DEFAULT_SA))
    parser.add_argument("--token-cmd", default=None,
                        help="shell command that prints an access token (overrides --sa-file)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("tracks", help="report current track/release state (read-only)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pubspec", default="mobile/pubspec.yaml")

    p = sub.add_parser("release", help="AAB + track + listing + assets in ONE atomic edit")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pubspec", default="mobile/pubspec.yaml")
    p.add_argument("--aab")
    p.add_argument("--track", default="internal", choices=VALID_TRACKS)
    p.add_argument("--status", default="completed", choices=("draft", "inProgress", "halted", "completed"))
    p.add_argument("--rollout", type=float, default=None, help="user fraction %% (with --status inProgress)")
    p.add_argument("--changelog", help="file with release-notes text (→ track releaseNotes)")
    p.add_argument("--listing-content", help="play-listing-content.md → title/short/full + changelog")
    p.add_argument("--store-dir", help="store assets dir (icon/feature-graphic/screenshots)")
    p.add_argument("--lang", default=DEFAULT_LANG)
    p.add_argument("--no-wipe-images", dest="wipe_images", action="store_false", default=True)

    p = sub.add_parser("listing", help="update main-store listing text")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pubspec", default="mobile/pubspec.yaml")
    p.add_argument("--listing-content")
    p.add_argument("--lang", default=DEFAULT_LANG)

    p = sub.add_parser("assets", help="replace main-store listing images")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--pubspec", default="mobile/pubspec.yaml")
    p.add_argument("--store-dir", required=True)
    p.add_argument("--lang", default=DEFAULT_LANG)

    args = parser.parse_args(argv)
    return {"tracks": cmd_tracks, "release": cmd_release,
            "listing": cmd_listing, "assets": cmd_assets}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())