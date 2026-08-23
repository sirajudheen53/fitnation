#!/usr/bin/env bash
#
# deploy-qa.sh — Build and deploy the FBOS QA stack to a single GCP VM.
#
# Strategy for a single VM (no registry needed):
#   1. Build the QA images locally
#   2. Save them to a tarball and scp to the VM
#   3. Load images + docker compose up -d on the VM
#   4. Run Django migrations
#   5. Health-check the stack
#
# Usage:
#   ./deploy/scripts/deploy-qa.sh <VM_IP> [SSH_USER]
#   SSH_USER defaults to your GCP username (gcloud config or $USER).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
QA_DIR="$REPO_ROOT/deploy/qa"
TAG="qa"

IP="${1:?Usage: deploy-qa.sh <VM_IP> [SSH_USER]}"
SSH_USER="${2:-$USER}"
SSH_TARGET="${SSH_USER}@${IP}"

COMPOSE_FILE="$QA_DIR/docker-compose.qa.yml"
ENV_FILE="$QA_DIR/.env.qa"
IMAGE_TAR="/tmp/fboston-qa-images.tar"

# ── Preflight ───────────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Missing $ENV_FILE"
    echo "   Copy: cp $QA_DIR/.env.qa.example $ENV_FILE"
    echo "   Then set real secrets (SECRET_KEY, POSTGRES_PASSWORD)."
    exit 1
fi
if ! command -v docker >/dev/null; then
    echo "❌ Docker not found locally."
    exit 1
fi

echo "→ Deploying QA stack to $SSH_TARGET"
echo "→ Compose file: $COMPOSE_FILE"

# ── 1. Build images locally ─────────────────────────────────────────────
echo "→ Building backend image (${TAG}-backend)..."
docker build -t "qa-backend:latest" -f "$QA_DIR/Dockerfile.backend" "$REPO_ROOT/backend"

echo "→ Building frontend image (${TAG}-frontend)..."
docker build \
    --build-arg NEXT_PUBLIC_API_URL="$(grep -E '^NEXT_PUBLIC_API_URL=' "$ENV_FILE" | cut -d= -f2-)" \
    -t "qa-frontend:latest" \
    -f "$QA_DIR/Dockerfile.frontend" \
    "$REPO_ROOT/frontend"

# ── 2. Save + scp images ────────────────────────────────────────────────
echo "→ Saving images to $IMAGE_TAR ..."
docker save qa-backend:latest qa-frontend:latest -o "$IMAGE_TAR"

echo "→ Uploading to VM..."
scp "$IMAGE_TAR" "${SSH_TARGET}:/tmp/qa-images.tar"
scp -r "$QA_DIR" "${SSH_TARGET}:~/qa"
scp "$ENV_FILE" "${SSH_TARGET}:~/qa/.env.qa"

# ── 3. Load + compose up on the VM ──────────────────────────────────────
echo "→ Loading images + starting stack on VM..."
ssh "$SSH_TARGET" 'bash -s' <<'EOF'
set -euo pipefail
cd ~/qa
echo "   - Loading images..."
docker load -i /tmp/qa-images
echo "   - Starting stack (docker compose up -d)..."
docker compose -f docker-compose.qa.yml up -d --build
EOF

# ── 4. Run migrations ───────────────────────────────────────────────────
echo "→ Running Django migrations..."
ssh "$SSH_TARGET" 'cd ~/qa && docker compose -f docker-compose.qa.yml exec backend python manage.py migrate --noinput'

# ── 5. Health check ─────────────────────────────────────────────────────
echo "→ Waiting for services to be healthy..."
sleep 20
echo "   Docker ps:"
ssh "$SSH_TARGET" 'cd ~/qa && docker compose -f docker-compose.qa.yml ps'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy complete. Verify:"
echo "  ─ Health:      curl -s https://qa.fitnation.app/api/health/"
echo "  ─ Frontend:    https://qa.fitnation.app"
echo "  ─ Logs:        ssh ${SSH_TARGET} \"cd ~/qa && docker compose -f docker-compose.qa.yml logs -f\""
echo "  ─ Down:        ssh ${SSH_TARGET} \"cd ~/qa && docker compose -f docker-compose.qa.yml down\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
