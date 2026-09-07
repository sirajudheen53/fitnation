# FBOS QA — TLS setup for api.dev.yougetfitwithus.com

One-time sequence to get the dev environment login working end to end.
Assumes the QA VM exists (see deploy/scripts/deploy-qa.sh) and DNS is manageable.

## 0. Prereqs (VM + DNS)

```bash
# Start the VM (it was down as of 2026-09-05 — connection refused)
gcloud compute instances start <VM_NAME>

# Firewall: allow 80 + 443 (skip if a rule already exists)
gcloud compute firewall-rules create fbos-qa-http-https \
    --allow=tcp:80,tcp:443 --source-ranges=0.0.0.0/0 \
    --description="FBOS QA HTTP/HTTPS"

# DNS: add an A record  api.dev.yougetfitwithus.com → 34.93.81.238
# Verify propagation before issuing the cert:
dig +short api.dev.yougetfitwithus.com
```

## 1. Env values (apply on the VM too — ~/qa/.env.qa)

```ini
ALLOWED_HOSTS=api.dev.yougetfitwithus.com,localhost,127.0.0.1,34.93.81.238
CORS_ALLOWED_ORIGINS=https://dev.yougetfitwithus.com,http://34.93.81.238,http://localhost
NEXT_PUBLIC_API_URL=https://api.dev.yougetfitwithus.com/api/v1
```

Updated in both deploy/qa/.env.qa and deploy/qa/.env.qa.example in the repo.

## 2. Start the stack with the HTTP config (current nginx.conf)

```bash
ssh <user>@34.93.81.238
cd ~/qa && docker compose -f docker-compose.qa.yml up -d
```

## 3. Issue the certificate (webroot through the running nginx)

```bash
docker run --rm \
    -v /home/$USER/qa/certbot/conf:/etc/letsencrypt \
    -v /home/$USER/qa/certbot/www:/var/www/certbot \
    certbot/certbot certonly --webroot -w /var/www/certbot \
    -d api.dev.yougetfitwithus.com \
    --email <you@yougetfitwithus.com> --agree-tos --no-eff-email
```

## 4. Swap nginx to the TLS config

In docker-compose.qa.yml, change the nginx volume mount:

```
- ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
+ ./nginx.ssl.conf:/etc/nginx/conf.d/default.conf:ro
```

Validate, then recreate:

```bash
docker compose -f docker-compose.qa.yml run --rm --no-deps nginx nginx -t
docker compose -f docker-compose.qa.yml up -d --force-recreate nginx
```

## 5. Verify

```bash
curl -sS https://api.dev.yougetfitwithus.com/api/health/
# login endpoint should answer 405 (method not allowed) on GET, not 404/timeout:
curl -sS -o /dev/null -w '%{http_code}\n' https://api.dev.yougetfitwithus.com/api/v1/users/auth/login/
```

## 5b. Seed the QA database (unified seed command)

```bash
# On the VM, after migrations (deploy-qa.sh runs migrate already):
docker compose -f docker-compose.qa.yml exec backend python manage.py seed_qa --realistic
```

Idempotent — safe to re-run. Seeds platform admin + catalogs + FitGym A/B regression
tenants + tenant-1 staff + IronHouse + full realistic data. Key logins are printed at
the end (admin@fitnation.test, owner_a/b@fitgym*.qa, owner@fitnation.test,
owner.iron@fitnation.test).

## 6. Renewal (cron on the VM host)

```
0 3 * * * cd /home/$USER/qa && docker run --rm -v /home/$USER/qa/certbot/conf:/etc/letsencrypt -v /home/$USER/qa/certbot/www:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot && docker compose -f docker-compose.qa.yml exec -T nginx nginx -s reload
```

## 7. Vercel (frontend) — needs dashboard access

1. Project → Settings → Environment Variables:
   `NEXT_PUBLIC_API_URL = https://api.dev.yougetfitwithus.com/api/v1` (Production + Preview)
2. **Redeploy** — the value is inlined at build time; saving alone changes nothing.
3. Verify: the login page bundle must no longer contain `localhost:8000`
   (check: view source → search chunk JS, or just log in).

## Notes

- `config.settings.qa` reads ALLOWED_HOSTS / CORS_ALLOWED_ORIGINS from .env.qa.
  nginx terminates TLS and sets X-Forwarded-Proto=https; qa.py already trusts it
  (SECURE_PROXY_SSL_HEADER).
- Mixed content: https://dev.yougetfitwithus.com cannot call http://34.93.81.238 —
  that's why the API needs TLS, not just the frontend.
- If you also use the VM-hosted frontend (http://34.93.81.238): compose-level
  `${NEXT_PUBLIC_API_URL}` interpolation reads the shell / a `.env` file next to
  the compose file — not `env_file`. Export the variable before `docker compose up`
  or pass `--env-file .env.qa`, and rebuild the frontend image (NEXT_PUBLIC_* is
  baked at build time).