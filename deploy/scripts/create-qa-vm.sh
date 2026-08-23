#!/usr/bin/env bash
#
# create-qa-vm.sh — Provision a single GCP VM for the FBOS QA environment.
#
# Creates:
#   - e2-small VM (Ubuntu 22.04) with 30GB disk
#   - Firewall rules for ports 80, 443, 22
#   - Installs Docker + Docker Compose plugin
#   - Prints VM IP + next steps
#
# Prereqs: gcloud CLI authenticated, a GCP project + zone configured.
#
# Usage:
#   ./deploy/scripts/create-qa-vm.sh [PROJECT_ID] [ZONE]
#   Defaults: PROJECT_ID from `gcloud config get-value project`
#             ZONE=asia-south1-a (Mumbai, near IST team)

set -euo pipefail

# ── Config ───────────────────────────────────────────────────────────────
PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null)}"
ZONE="${2:-asia-south1-a}"
VM_NAME="fitnation-qa"
MACHINE_TYPE="e2-small"
IMAGE_FAMILY="ubuntu-2204-lts"
IMAGE_PROJECT="ubuntu-os-cloud"
BOOT_DISK_SIZE="30GB"
TAG="qa"

if [[ -z "$PROJECT_ID" ]]; then
    echo "❌ No GCP project set. Set one:"
    echo "   gcloud config set project YOUR_PROJECT_ID"
    echo "   or pass it as the first argument."
    exit 1
fi

echo "→ Using project: $PROJECT_ID"
echo "→ Zone:          $ZONE"
echo "→ VM:            $MACHINE_TYPE (${IMAGE_FAMILY}, ${BOOT_DISK_SIZE})"

# ── 1. Create firewall rules (idempotent) ────────────────────────────────
create_firewall() {
    local name="$1" ports="$2"
    if gcloud compute firewall-rules describe "$name" --project "$PROJECT_ID" >/dev/null 2>&1; then
        echo "→ Firewall rule $name already exists, skipping."
    else
        echo "→ Creating firewall rule $name (ports $ports)..."
        gcloud compute firewall-rules create "$name" \
            --project "$PROJECT_ID" \
            --direction=INGRESS \
            --priority=1000 \
            --network=default \
            --action=ALLOW \
            --rules="tcp:${ports}" \
            --target-tags="$TAG"
    fi
}

create_firewall "allow-${TAG}-http"  "80"
create_firewall "allow-${TAG}-https" "443"
create_firewall "allow-${TAG}-ssh"   "22"

# ── 2. Create the VM ─────────────────────────────────────────────────────
echo "→ Creating VM '$VM_NAME'..."
gcloud compute instances create "$VM_NAME" \
    --project "$PROJECT_ID" \
    --zone "$ZONE" \
    --machine-type "$MACHINE_TYPE" \
    --image-family "$IMAGE_FAMILY" \
    --image-project "$IMAGE_PROJECT" \
    --boot-disk-size "$BOOT_DISK_SIZE" \
    --boot-disk-type pd-balanced \
    --tags "$TAG" \
    --metadata startup-script='#!/bin/bash
set -e
# Docker + Compose plugin (Ubuntu 22.04)
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
usermod -aG docker $(whoami)
echo "startup-script: Docker + Compose installed" > /var/log/qa-bootstrap.log
'

echo "✅ VM created."

# ── 3. Wait for external IP ──────────────────────────────────────────────
echo "→ Waiting for external IP..."
for _ in $(seq 1 20); do
    IP=$(gcloud compute instances describe "$VM_NAME" \
        --project "$PROJECT_ID" --zone "$ZONE" \
        --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || true)
    if [[ -n "$IP" ]]; then break; fi
    sleep 3
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  QA VM ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Project : $PROJECT_ID"
echo "  VM      : $VM_NAME ($ZONE)"
echo "  IP      : ${IP:-<pending — check via gcloud compute instances describe>}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Wait ~2 min for Docker to install (startup script)."
echo "     SSH: gcloud compute ssh $VM_NAME --zone $ZONE"
echo "     Check: cat /var/log/startup.log && docker --version"
echo "  2. Copy deploy files to the VM:"
echo "     scp -r deploy/qa ${IP}:/home/<user>/qa"
echo "  3. Fill secrets:"
echo "     cp .env.qa.example .env.qa && edit values"
echo "  4. Deploy:"
echo "     ./deploy/scripts/deploy-qa.sh  (or run compose on the VM)"
echo "  5. Point DNS: A record  qa.fitnation.app  →  $IP"
echo "  6. Obtain TLS cert (after DNS propagates):"
echo "     docker compose -f deploy/qa/docker-compose.qa.yml exec nginx certbot certonly ..."
