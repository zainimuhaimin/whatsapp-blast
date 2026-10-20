#!/usr/bin/env bash
# ============================================================
#  WA Blast — update whitelist IP (mis. IP rumah Anda berubah)
#  Pakai: bash deploy/update-whitelist.sh 203.0.113.45
# ============================================================
set -euo pipefail
[ "$(id -u)" = "0" ] || { echo "[x] Jalankan sebagai root."; exit 1; }
NEW_IP="${1:?Pakai: bash deploy/update-whitelist.sh <IP-baru>}"
echo "$NEW_IP" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || { echo "[x] Format IP tidak valid."; exit 1; }

cd "$(dirname "$0")/.."
OLD_IP="$(grep '^WHITELIST_IP=' .env 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$OLD_IP" ]; then
  ufw delete allow from "$OLD_IP" to any port 80 proto tcp >/dev/null 2>&1 || true
  ufw delete allow from "$OLD_IP" to any port 443 proto tcp >/dev/null 2>&1 || true
fi
ufw allow from "$NEW_IP" to any port 80 proto tcp >/dev/null
ufw allow from "$NEW_IP" to any port 443 proto tcp >/dev/null
sed -i "s/^WHITELIST_IP=.*/WHITELIST_IP=$NEW_IP/" .env
echo "[ok] Whitelist diupdate: ${OLD_IP:-<kosong>} -> $NEW_IP"
