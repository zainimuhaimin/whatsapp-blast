FROM node:24-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

COPY server.js ./

# Direktori sesi (di-mount sebagai volume agar QR pairing tidak hilang saat restart)
RUN mkdir -p /app/auth_info
VOLUME /app/auth_info

EXPOSE 3001

CMD ["node", "server.js"]
