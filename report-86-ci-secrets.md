# Report — #86: CI deploy workflows wipe manually-wired Cloud Run secrets

P1, prod gate. Every deploy through `deploy-dev.yml` / `deploy-prod.yml` passed a
FULL-REPLACE `--set-secrets` list containing only the 4 base secrets, so each run
wiped any secret wired to the Cloud Run service outside the workflow. Real damage:
2026-10-25 dev lost `META_SYSTEM_TOKEN` + `META_WABA_ID` (WhatsApp gate, rev
00116-bbx → re-wired manually as 00125-rsl); 2026-10-26 `FIREBASE_CREDENTIALS`
was wired on PROD (rev 00020-pbg) + DEV (rev 00124-frd) for Firebase login — the
next unpatched deploy would have regressed Firebase login to 503 in prod.

## Root cause

`gcloud run deploy --set-secrets` (and `--set-env-vars`) replace the service's
**entire** secret/env map with what's on the command line. The workflows listed
only `DATABASE_URL / SECRET_KEY / SENDGRID_API_KEY / DEFAULT_FROM_EMAIL`
(prod: `PROD_DATABASE_URL / PROD_SECRET_KEY / …`), so anything wired manually —
`FIREBASE_CREDENTIALS`, `META_SYSTEM_TOKEN` — disappeared on every deploy.

## What changed (workflow-only, config-in-code)

**`.github/workflows/deploy-prod.yml`** (Deploy to Cloud Run (prod) step)

- `--set-secrets` appends `FIREBASE_CREDENTIALS=FIREBASE_CREDENTIALS:latest`
  (6 secrets total).
- The `^|^` custom-delimiter quoting on `--set-env-vars` is untouched (that's
  env vars, not secrets; no commas inside secret mappings).

**`.github/workflows/deploy-dev.yml`** (Deploy to Cloud Run step)

- `--set-secrets` appends `FIREBASE_CREDENTIALS=FIREBASE_CREDENTIALS:latest` +
  `META_SYSTEM_TOKEN=META_SYSTEM_TOKEN:latest` (6 secrets total).
- `--set-env-vars` appends `META_WABA_ID=1542497557602795` so the WhatsApp WABA
  id validated 2026-10-25 vs getfitwithus survives deploys (same FULL-REPLACE
  mechanics — it must live in the declared list).

Both deploy steps now carry a comment stating the constraint: these flags are
full-replace, so any secret/env var the service needs must be added to the
workflow list or the deploy wipes it. That's the durable fix for the next person
who wires a secret by hand — wire it here too.

## Optional hardening (brief item 4) — skipped, deliberately

- **Additive semantics**: there is no `--add-secrets`-style flag; it would need
  read-current-config → merge → apply logic in the workflow, a real deploy-
  behavior change the brief said to avoid ("do NOT break the deploy").
- **Fail-the-run pinned-secrets check**: adds a new failure mode to a P1 prod
  gate for a problem the append already eliminates. Revisit if manual wiring
  becomes routine (a `gcloud run services describe` + grep step would do it).

## Verification

- `python3 -c "import yaml; yaml.safe_load(...)"` passes on both files.
- Eyeball (actionlint-style): line continuations intact, `${{ }}` expressions
  untouched, no commas inside the secret mappings, prod `^|^` block unchanged.
- No app code, settings, or other workflow touched — deploy behavior beyond the
  append is identical.
- Both secrets pre-exist in Secret Manager (`FIREBASE_CREDENTIALS`,
  `META_SYSTEM_TOKEN`), so the first patched deploy resolves `:latest` cleanly.
- Live verification after the next Deploy-Dev/Deploy-Prod run: revision env
  should show all 6 secrets + `META_WABA_ID` (check via Cloud Run console or
  `gcloud run services describe --format yaml`).
