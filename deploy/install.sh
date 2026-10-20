#!/usr/bin/env bash
# ============================================================
#  WA Blast — Installer produksi (Ubuntu 22.04 / 24.04, root)
# ============================================================
#  Menyiapkan stack WA Blast di VPS:
#    1. Install Docker (bila belum ada)
#    2. Membuat rahasia (JWT secret, password Postgres) secara acak
#    3. Menulis backend/.env (login AKTIF untuk deployment publik)
#    4. Mode akses (dipilih saat install):
#       a. Tailscale (DIREKOMENDASIKAN) — aplikasi hanya bisa dibuka dari
#          perangkat di jaringan Tailscale Anda; port web di-bind ke IP
#          Tailscale VPS saja, publik tidak bisa menyentuhnya sama sekali.
#       b. Whitelist IP publik — firewall hanya mengizinkan IP Anda
#          membuka port web (IP dinamis perlu update manual).
#    5. Build & menjalankan stack (docker-compose + override produksi)
#
#  Cara pakai (di server, sebagai root):
#    git clone https://github.com/zainimuhaimin/whatsapp-blast.git
#    cd whatsapp-blast
#    bash deploy/install.sh
#
#  Script interaktif: Anda akan ditanya mode akses, username/password
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
echo "--- Mode akses aplikasi ---"
echo "  1) Tailscale (disarankan) — aplikasi hanya terbuka untuk perangkat"
echo "     di jaringan Tailscale Anda. IP publik berubah / CGNAT tidak masalah."
echo "  2) Whitelist IP publik — port web hanya untuk satu IP publik Anda."
read -r -p "Pilih [1/2, default 1]: " ACCESS_MODE
ACCESS_MODE="${ACCESS_MODE:-1}"
[ "$ACCESS_MODE" = "1" ] || [ "$ACCESS_MODE" = "2" ] || die "Pilih 1 atau 2."

WHITELIST_IP=""
if [ "$ACCESS_MODE" = "2" ]; then
  echo
  echo "--- Whitelist IP ---"
  echo "Hanya IP ini yang boleh membuka aplikasi. Cek IP publik Anda dari"
  echo "perangkat/jaringan yang akan dipakai akses (mis. WiFi rumah) lewat:"
  echo "  https://ifconfig.me   atau   https://whatismyip.com"
  read -r -p "IP publik Anda (IPv4): " WHITELIST_IP
  echo "$WHITELIST_IP" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || die "Format IP tidak valid: $WHITELIST_IP"
fi

echo
echo "--- Akun admin aplikasi ---"
read -r -p "Username admin [admin]: " ADMIN_USER
ADMIN_USER="${ADMIN_USER:-admin}"
read -r -s -p "Password admin (min. 10 karakter): " ADMIN_PASS; echo
[ ${#ADMIN_PASS} -ge 10 ] || die "Password terlalu pendek (min. 10 karakter)."

echo
echo "--- Opsional ---"
read -r -p "Google Gemini API key (Enter untuk lewati, isi nanti di menu Pengaturan): " GEMINI_KEY

# ---------- 3. Tailscale (mode 1) ----------
FRONTEND_BIND_IP="0.0.0.0"
TS_IP=""
if [ "$ACCESS_MODE" = "1" ]; then
  echo
  echo "--- Tailscale ---"
  if ! command -v tailscale >/dev/null 2>&1; then
    echo "Menginstall Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    info "Tailscale terinstall."
  fi
  systemctl enable --now tailscaled >/dev/null 2>&1 || true
  echo
  echo "Tailscale perlu dihubungkan ke akun Anda. Jalankan login berikut"
  echo "dan buka link yang muncul di browser Anda (satu kali saja):"
  echo
  tailscale up --hostname wablast
  TS_IP="$(tailscale ip -4 | head -1)"
  [ -n "$TS_IP" ] || die "Gagal membaca IP Tailscale VPS."
  FRONTEND_BIND_IP="$TS_IP"
  info "VPS terhubung ke Tailscale dengan IP $TS_IP."
  echo "Catatan: di HP/laptop Anda install aplikasi Tailscale & login dengan"
  echo "akun yang SAMA agar bisa membuka aplikasi nanti."
fi

# ---------- 4. Rahasia & .env ----------
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
ACCESS_MODE=$ACCESS_MODE
WHITELIST_IP=$WHITELIST_IP
FRONTEND_BIND_IP=$FRONTEND_BIND_IP
TS_IP=$TS_IP
EOF
chmod 600 .env

# ---------- 5. Firewall ----------
echo
echo "--- Firewall ---"
if ! command -v ufw >/dev/null 2>&1; then
  apt-get update -qq && apt-get install -y -qq ufw >/dev/null
fi
# SSH selalu diizinkan agar tidak terkunci keluar.
ufw allow 22/tcp >/dev/null
if [ "$ACCESS_MODE" = "1" ]; then
  # Mode Tailscale: port web di-bind ke IP Tailscale VPS (di compose), jadi
  # publik sudah tertutup secara inheren. Firewall cukup default-deny.
  info "Mode Tailscale: port web di-bind ke IP Tailscale $TS_IP — publik tertutup."
else
  # Mode whitelist IP: port Docker diforward via NAT sehingga aturan INPUT
  # biasa tidak menangkapnya — pakai aturan 'route' (rantai FORWARD).
  ufw route allow from "$WHITELIST_IP" to any port 80 proto tcp >/dev/null
  ufw route allow from "$WHITELIST_IP" to any port 443 proto tcp >/dev/null
  info "Firewall aktif: port 80/443 hanya dari $WHITELIST_IP."
fi
ufw --force enable >/dev/null

# ---------- 6. Build & jalankan ----------
echo
echo "--- Build & run (bisa beberapa menit) ---"
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

echo
echo "============================================================"
info "Deployment selesai."
echo " Login         : $ADMIN_USER (password yang baru Anda set)"
if [ "$ACCESS_MODE" = "1" ]; then
  echo " Buka aplikasi : http://$TS_IP/"
  echo "                 (dari HP/laptop yang sudah login Tailscale"
  echo "                  dengan akun yang sama; atau lewat nama MagicDNS"
  echo "                  wablast di admin console Tailscale)"
  echo " Undang orang  : admin console Tailscale -> Machines -> wablast"
  echo "                 -> Share (orang itu hanya bisa akses VPS ini)"
else
  SERVER_IP="$(curl -s --max-time 5 ifconfig.me || echo '<IP-SERVER>')"
  echo " Buka aplikasi : http://$SERVER_IP/"
  echo " Whitelist IP  : $WHITELIST_IP (port 80/443)"
  echo " IP ganti      : bash deploy/update-whitelist.sh <IP-baru>"
fi
echo
echo " Perintah berguna:"
echo "   Log     : docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api"
echo "   Update  : git pull && bash deploy/update.sh"
echo "============================================================"
