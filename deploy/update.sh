#!/usr/bin/env bash
# ============================================================
#  WA Blast — update kode aplikasi (pull + rebuild)
#  Jalankan dari root repo di server, sebagai root.
# ============================================================
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f ".env" ] || { echo "[x] .env tidak ada — jalankan deploy/install.sh dulu."; exit 1; }
set -a; . ./.env; set +a   # muat POSTGRES_PASSWORD dkk.
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
echo "[ok] Update selesai. Cek versi backend di footer sidebar aplikasi."
