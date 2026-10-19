FROM node:24-alpine

# git WAJIB ada: npm butuh git untuk dependency Baileys via git URL
# (libsignal-node dari github.com/whiskeysockets) — tanpa ini build
# gagal dengan "npm error syscall spawn git / ENOENT".
RUN apk add --no-cache git

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

COPY server.js ./

# Direktori sesi (di-mount sebagai volume agar QR pairing tidak hilang saat restart)
RUN mkdir -p /app/auth_info
VOLUME /app/auth_info

EXPOSE 3001

CMD ["node", "server.js"]
