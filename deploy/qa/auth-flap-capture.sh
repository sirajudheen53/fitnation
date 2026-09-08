#!/usr/bin/env bash
# auth-flap-capture.sh — one-shot snapshot of everything that matters during an
# auth-flap window (403 "Invalid credentials" with the DB row verified correct).
#
# Usage (ON THE QA VM, the moment a failure is observed):
#   bash ~/fitnation/deploy/qa/auth-flap-capture.sh [email] [password]
#
# Captures simultaneously (≤3s): container/port-80 bindings, nginx upstream
# resolution, a live login probe, and the DB row — the simultaneous state the
# SM asked for. Safe to run repeatedly; no writes.

EMAIL="${1:-owner@fitnation.test}"
# Credentials are never hardcoded (public repo): pass the password as arg 2
# or export QA_TEST_PASSWORD. Note: a password containing '"' or '\\' will
# break the JSON probe payload in step [5].
PW="${2:-${QA_TEST_PASSWORD:-}}"
if [ -z "$PW" ]; then
  echo "error: no password — pass it as arg 2 or export QA_TEST_PASSWORD" >&2
  exit 1
fi
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ) / $(TZ=Asia/Kolkata date +%H:%M:%S) IST"

echo "════ AUTH-FLAP CAPTURE — $STAMP ════"

echo "── [1] ALL containers + port bindings (killed/running) ──"
sudo docker ps -a --format "{{.Names}} | {{.Image}} | {{.Status}} | {{.Ports}}"

echo "── [2] compose stacks (duplicates would show here) ──"
sudo docker compose ls 2>/dev/null

echo "── [3] backend container IP(s) on its networks + nginx's view ──"
sudo docker inspect qa-backend --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}={{$v.IPAddress}} {{end}}'

echo "── [4] nginx's CURRENT resolution of 'backend' (port-80 path) ──"
sudo docker exec qa-nginx getent hosts backend || echo "nginx cannot resolve backend!"

echo "── [5] live login probe through nginx (the failing path) ──"
curl -s -m 10 -X POST http://localhost/api/v1/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}" \
  -o /tmp/flap-login.json -w "login HTTP %{http_code}\n"
head -c 200 /tmp/flap-login.json; echo

echo "── [6] DB row at the SAME moment (ground truth) ──"
EMAIL_ESC="${EMAIL//\'/\'\'}"
sudo docker exec qa-db psql -U fitnation -d fitnation_qa -tAc \
  "select email, is_active, is_email_verified, left(password,7) || ' iter=' || split_part(password,'$',2) as algo, updated_at, last_login from users where email='$EMAIL_ESC';"

echo "── [7] gunicorn workers alive in qa-backend ──"
sudo docker exec qa-backend sh -c 'count=0; for p in /proc/[0-9]*/cmdline; do grep -q gunicorn "$p" 2>/dev/null && count=$((count+1)); done; echo "gunicorn processes: $count"'

echo "════ capture end ════"