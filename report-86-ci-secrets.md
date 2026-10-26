# Report — #86: CI deploy workflows wipe manually-wired Cloud Run secrets

P1, prod gate. Every deploy through `deploy-dev.yml` / `deploy-prod.yml` passed a
FULL-REPLACE `--set-secrets` list containing only the 4 base secrets, so each run
wiped any secret wired to the Cloud Run service outside the workflow. Real damage:
2026-10-25 dev lost `META_SYSTEM_TOKEN` + `META_WABA_ID` (WhatsApp gate, rev
00116-bbx → re-wired manually as 00125-rsl); later CI deploys wiped them again —
by 2026-10-26 the dev service was back to base-4 only, and `FIREBASE_CREDENTIALS`
(wired to PROD rev 00020-pbg + DEV rev 00124-frd for Firebase login) had been
wiped off dev too. The next unpatched prod deploy would have regressed Firebase
login to 503.

## Root cause

`gcloud run deploy --set-secrets` (and `--set-env-vars`) replace the service's
**entire** secret/env map with what's on the command line. The workflows listed
only `DATABASE_URL / SECRET_KEY / SENDGRID_API_KEY / DEFAULT_FROM_EMAIL`
(prod: `PROD_DATABASE_URL / PROD_SECRET_KEY / …`), so anything wired manually
disappeared on every deploy. Confirmed live: the dev service template just before
this fix carried exactly the 4 env vars + 4 secret refs and nothing else.

## What changed (workflow-only, config-in-code)

**`.github/workflows/deploy-prod.yml`** (Deploy to Cloud Run (prod) step)

- `--set-secrets` appends `FIREBASE_CREDENTIALS=FIREBASE_CREDENTIALS:latest`
  (5 secrets total).
- The `^|^` custom-delimiter quoting on `--set-env-vars` is untouched (no commas
  inside secret mappings; CORS commas still protected by the delimiter).

**`.github/workflows/deploy-dev.yml`** (Deploy to Cloud Run step)

- `--set-secrets` appends `FIREBASE_CREDENTIALS=FIREBASE_CREDENTIALS:latest` +
  `META_SYSTEM_TOKEN=META_SYSTEM_TOKEN:latest` (6 secrets total).
- `--set-env-vars` appends `META_WABA_ID=1542497557602795` so the WhatsApp WABA
  id validated 2026-10-25 vs getfitwithus survives deploys (same FULL-REPLACE
  mechanics — it must live in the declared list).

Both deploy steps carry a comment stating the constraint: these flags are
full-replace, so any secret/env var the service needs must be added to the
workflow list or the deploy wipes it.

## Incident during this fix (fb210bd, self-inflicted, caught + fixed same hour)

The first attempt put the new explanatory comment lines **inside the shell line
continuation** of the deploy command:

```
--allow-unauthenticated \
# --set-env-vars/--set-secrets are FULL-REPLACE ...
--set-env-vars "..." \
```

Bash ends the logical command at a `#` comment line, so `gcloud run deploy` ran
with **no** `--set-env-vars`/`--set-secrets` (exit 127 on the orphaned
`--set-env-vars` "command"). The created revision (dev 00129-7qp) inherited the
service's current template — which was already the wiped base-4 state, so dev
ended up serving the same (still-wiped) config, no *new* regression. The same
pattern sat in `deploy-prod.yml`, where a tag deploy would have gone out with
**no secrets at all** (prod DB gone) — never triggered; fixed in 9bc05fc before
any prod run. Fix: comments moved above the command, outside the continuations;
lesson recorded — never interleave `#` lines with `\` continuations in workflow
run blocks.

## Optional hardening (brief item 4) — skipped, deliberately

- **Additive semantics**: there is no `--add-secrets`-style flag; it would need
  read-current-config → merge → apply logic in the workflow, a real deploy-
  behavior change the brief said to avoid ("do NOT break the deploy").
- **Fail-the-run pinned-secrets check**: adds a new failure mode to a P1 prod
  gate for a problem the append already eliminates. Revisit if manual wiring
  becomes routine (a `gcloud run services describe` + grep step would do it).

## Verification

- YAML: `yaml.safe_load` passes on both files.
- **Shell semantics (the check that matters here):** both deploy run blocks
  executed under `bash -e` with a stubbed `gcloud` — each yields exactly ONE
  deploy invocation; dev carries 6 `=`-pairs in `--set-secrets` and
  `META_WABA_ID=1542497557602795` inside `--set-env-vars`; prod carries 5 pairs
  with the `^|^` env block intact (CORS commas survive as data).
- **Live (dev, run 40356188850 for 9bc05fc):** Deploy-Dev green end-to-end;
  revision `fitnation-backend-00130-q68` serving 100% with 6 secret refs —
  `DATABASE_URL, SECRET_KEY, SENDGRID_API_KEY, DEFAULT_FROM_EMAIL,
  FIREBASE_CREDENTIALS, META_SYSTEM_TOKEN` — and 5 env vars including
  `META_WABA_ID`; `GET /api/health/` → HTTP 200.
- **Prod**: not deployed by this change (tag/manual only); the patched workflow
  is verified by the stubbed-shell run above and will carry `FIREBASE_CREDENTIALS`
  on the next tag deploy. Worth eyeballing the revision config after the next
  prod release.
- No app code, settings, or other workflow touched.
- Both secrets pre-exist in Secret Manager (`FIREBASE_CREDENTIALS`,
  `META_SYSTEM_TOKEN`), confirmed by the deploy resolving `:latest` cleanly.

## Commits

- `fb210bd` fix(ci): stop deploy workflows wiping manually-wired Cloud Run secrets (#86)
- `9bc05fc` fix(ci): move FULL-REPLACE comment out of shell continuation (#86)

Both pushed to `origin/develop`.
