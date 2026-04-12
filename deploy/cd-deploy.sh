#!/usr/bin/env bash
# deploy/cd-deploy.sh — Exécuté par le runner GitHub Actions sur server13
# Le runner a déjà fait `git checkout` dans son workspace.

set -euo pipefail

APP_DIR="/home/stelwey/apps/palimpsest"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"

echo "══════════════════════════════════════════════════════"
echo "  Palimpsest — CD deploy depuis le runner GitHub"
echo "  Source  : $GITHUB_WORKSPACE"
echo "  App dir : $APP_DIR"
echo "══════════════════════════════════════════════════════"

# ── 1. Synchroniser le code du workspace runner → app dir ─────────────────
echo ""
echo "[1/3] Synchronisation du code..."
rsync -az --delete \
  --exclude ".git" \
  --exclude ".DS_Store" \
  --exclude "__pycache__" \
  --exclude "*.py[cod]" \
  --exclude ".env" \
  --exclude "config.yaml" \
  --exclude "output/" \
  --exclude ".cache/" \
  --exclude "uploads/" \
  "$GITHUB_WORKSPACE/" \
  "$APP_DIR/"
echo "  ✓"

# ── 2. Build Docker ────────────────────────────────────────────────────────
echo ""
echo "[2/3] Build Docker..."
cd "$APP_DIR"
docker compose build
echo "  ✓"

# ── 3. Restart (config.yaml + output intacts via bind mount) ───────────────
echo ""
echo "[3/3] Démarrage du conteneur..."
docker compose up -d
echo "  ✓"

echo ""
echo "  Déploiement terminé."
