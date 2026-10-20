#!/usr/bin/env bash
# ============================================================
#  WA Blast — Installer produksi (Ubuntu 22.04 / 24.04, root)
# ============================================================
#  Menyiapkan stack WA Blast di VPS:
#    1. Install Docker (bila belum ada)
#    2. Membuat rahasia (JWT secret, password Postgres) secara acak
#    3. Menulis backend/.env (login AKTIF untuk deployment publik)
#    4. Mengatur firewall (ufw): port web HANYA dari IP whitelist Anda
#    5. Build & menjalankan stack (docker-compose + override produksi)
#
#  Cara pakai (di server, sebagai root):
#    git clone https://github.com/zainimuhaimin/whatsapp-blast.git
#    cd whatsapp-blast
#    bash deploy/install.sh
#
#  Script interaktif: Anda akan ditanya IP whitelist, username/password
#  admin, dan (opsional) API key Gemini. Tidak ada kredensial yang
#  dikirim ke mana pun — semua tersimpan lokal di file .env server.
# ============================================================
set -euo pipefail

RED='\033[0;31m'; GRN='\033[0;32m'; YEL='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GRN}[ok]${NC} $*"; }
warn()  { echo -e "${YEL}[!]${NC} $*"; }
die()   { echo -e "${RED}[x]${NC} $*" >&2; exit 1; }

[ "$(id -u)" = "0" ] || die "Jalankan sebagai root (sudo bash deploy/install.sh)."
cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"
[ -f "docker-compose.yml" ] || die "docker-compose.yml tidak ditemukan — jalankan dari clone repo whatsapp-blast."

echo "============================================================"
echo " WA Blast — Installer Produksi"
echo " Direktori: $ROOT_DIR"
echo "============================================================"

# ---------- 1. Docker ----------
if ! command -v docker >/dev/null 2>&1; then
  echo "Menginstall Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
  info "Docker terinstall."
else
  info "Docker sudah ada: $(docker --version)"
fi
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin tidak tersedia."

# ---------- 2. Input pengguna ----------
echo
echo "--- Whitelist IP ---"
echo "Hanya IP ini yang boleh membuka aplikasi. Cek IP publik Anda dari"
echo "perangkat/jaringan yang akan dipakai akses (mis. WiFi rumah) lewat:"
echo "  https://ifconfig.me   atau   https://whatismyip.com"
read -r -p "IP publik Anda (IPv4): " WHITELIST_IP
echo "$WHITELIST_IP" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || die "Format IP tidak valid: $WHITELIST_IP"

echo
echo "--- Akun admin aplikasi ---"
read -r -p "Username admin [admin]: " ADMIN_USER
ADMIN_USER="${ADMIN_USER:-admin}"
read -r -s -p "Password admin (min. 10 karakter): " ADMIN_PASS; echo
[ ${#ADMIN_PASS} -ge 10 ] || die "Password terlalu pendek (min. 10 karakter)."

echo
echo "--- Opsional ---"
read -r -p "Google Gemini API key (Enter untuk lewati, isi nanti di menu Pengaturan): " GEMINI_KEY

# ---------- 3. Rahasia & .env ----------
if [ -f backend/.env ] && grep -q "^JWT_SECRET=" backend/.env 2>/dev/null; then
  warn "backend/.env sudah ada — rahasia lama dipertahankan."
  JWT_SECRET=$(grep "^JWT_SECRET=" backend/.env | cut -d= -f2-)
  PG_PASS=$(grep "^POSTGRES_PASSWORD=" backend/.env | cut -d= -f2- || true)
  [ -n "${PG_PASS:-}" ] || PG_PASS="$(openssl rand -hex 24)"
else
  JWT_SECRET="$(openssl rand -hex 32)"
  PG_PASS="$(openssl rand -hex 24)"
fi
BAILEYS_KEY="$(openssl rand -hex 24)"

cat > backend/.env <<EOF
# Dibuat oleh deploy/install.sh — JANGAN commit file ini.
JWT_SECRET=$JWT_SECRET
POSTGRES_PASSWORD=$PG_PASS
ADMIN_USERNAME=$ADMIN_USER
ADMIN_PASSWORD=$ADMIN_PASS
AUTH_DISABLED=false
GEMINI_API_KEY=$GEMINI_KEY
BAILEYS_API_KEY=$BAILEYS_KEY
EOF
chmod 600 backend/.env
export POSTGRES_PASSWORD="$PG_PASS"
info "backend/.env dibuat (login AKTIF, rahasia acak)."

# Simpan juga untuk compose agar run berikutnya konsisten.
cat > .env <<EOF
POSTGRES_PASSWORD=$PG_PASS
WHITELIST_IP=$WHITELIST_IP
EOF
chmod 600 .env

# ---------- 4. Firewall (whitelist IP) ----------
echo
echo "--- Firewall ---"
if ! command -v ufw >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq ufw >/dev/null
fi
# SSH selalu diizinkan dari mana saja agar tidak terkunci keluar.
# (Batasi SSH ke IP Anda setelah yakin login SSH dari IP itu berhasil:
#   ufw delete allow 22/tcp && ufw allow from $WHITELIST_IP to any port 22 proto tcp)
ufw allow 22/tcp >/dev/null
ufw allow from "$WHITELIST_IP" to any port 80 proto tcp >/dev/null
ufw allow from "$WHITELIST_IP" to any port 443 proto tcp >/dev/null
ufw --force enable >/dev/null
info "Firewall aktif: port 80/443 hanya dari $WHITELIST_IP."

# ---------- 5. Build & jalankan ----------
echo
echo "--- Build & run (bisa beberapa menit) ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo
echo "============================================================"
info "Deployment selesai."
SERVER_IP="$(curl -s --max-time 5 ifconfig.me || echo '<IP-SERVER>')"
echo " Buka aplikasi : http://$SERVER_IP/"
echo " Login         : $ADMIN_USER (password yang baru Anda set)"
echo " Whitelist IP  : $WHITELIST_IP (port 80/443)"
echo
echo " Perintah berguna:"
echo "   Log     : docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api"
echo "   Update  : git pull && bash deploy/update.sh"
echo "   IP ganti: bash deploy/update-whitelist.sh <IP-baru>"
echo "============================================================"
