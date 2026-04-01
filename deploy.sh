#!/usr/bin/env bash
set -euo pipefail

# Required environment variables:
# - DROPLET_IP (e.g. 203.0.113.10)
# Optional:
# - DEPLOY_USER (default: root)
# - REMOTE_APP_DIR (default: /opt/freebies)
# - REPO_URL (default: https://github.com/rajaththaliyadath/freebies.git)
# - BRANCH (default: main)

DROPLET_IP="${DROPLET_IP:-}"
DEPLOY_USER="${DEPLOY_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/freebies}"
REPO_URL="${REPO_URL:-https://github.com/rajaththaliyadath/freebies.git}"
BRANCH="${BRANCH:-main}"

if [[ -z "${DROPLET_IP}" ]]; then
  echo "Missing DROPLET_IP. Example:"
  echo "  DROPLET_IP=203.0.113.10 ./deploy.sh"
  exit 1
fi

SSH_TARGET="${DEPLOY_USER}@${DROPLET_IP}"

ssh -o StrictHostKeyChecking=accept-new "${SSH_TARGET}" "bash -s" <<EOF
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg lsb-release git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    \$(. /etc/os-release && echo \$VERSION_CODENAME) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

mkdir -p "${REMOTE_APP_DIR}"
if [[ ! -d "${REMOTE_APP_DIR}/.git" ]]; then
  git clone "${REPO_URL}" "${REMOTE_APP_DIR}"
fi

cd "${REMOTE_APP_DIR}"
git fetch origin
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"

mkdir -p data
docker compose up -d --build
EOF

echo "Deployment completed on ${SSH_TARGET}."
