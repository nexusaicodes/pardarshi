#!/usr/bin/env bash
set -euo pipefail

# Install Docker
apt-get update
apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
systemctl enable --now docker

# Clone repo
git clone https://github.com/nexusaicodes/pardarshi.git /opt/pardarshi

# Build and start
cd /opt/pardarshi
docker compose up -d --build

echo "Done. App running on port 80."
