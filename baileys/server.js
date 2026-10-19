/**
 * Baileys sidecar untuk tool blast WA (jalur non-resmi / gratis).
 *
 * Mengendalikan satu nomor WhatsApp via protokol WhatsApp Web (Baileys).
 * Diekspos sebagai REST API sederhana untuk backend Python:
 *
 *   GET  /health            -> { ok: true }
 *   GET  /status            -> { connected, qr_available, phone, uptime_seconds }
 *   GET  /qr                -> halaman HTML berisi QR untuk pairing (auto-refresh)
 *   POST /send-text         -> { to, text }  => { message_id } | 409 { error: 'not_connected' }
 *   POST /logout             -> logout + hapus sesi (perlu scan QR ulang)
 *
 * Auth: bila env BAILEYS_API_KEY diisi, endpoint POST wajib header `x-api-key`.
 * Sesi tersimpan di ./auth_info (mount sebagai volume agar tidak hilang saat restart).
 *
 * PERINGATAN: jalur tidak resmi — pakai nomor testing khusus, JANGAN nomor utama.
 */
'use strict';

const express = require('express');
const QRCode = require('qrcode');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const PORT = parseInt(process.env.PORT || '3001', 10);
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, 'auth_info');
const API_KEY = process.env.BAILEYS_API_KEY || '';

const log = pino({ level: process.env.LOG_LEVEL || 'info' });

let sock = null;
let connected = false;
let myPhone = null;
let currentQR = null;
let startedAt = Date.now();

function toJid(phone) {
  const digits = String(phone || '').replace(/\D/g, '');
  if (!digits) throw new Error('nomor tujuan kosong');
  return `${digits}@s.whatsapp.net`;
}

async function clearAuthDir() {
  try {
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  } catch (e) {
    log.warn({ err: e }, 'gagal membersihkan auth dir');
  }
}

async function connect() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }));

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger: pino({ level: 'silent' }),
      browser: ['WA-Blast', 'Chrome', '1.0'],
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;
      if (qr) {
        currentQR = qr;
        log.info('QR tersedia — buka GET /qr untuk scan');
      }
      if (connection === 'close') {
        connected = false;
        myPhone = null;
        const code = lastDisconnect?.error?.output?.statusCode;
        log.warn({ code }, 'koneksi tertutup');
        if (code === DisconnectReason.loggedOut) {
          log.warn('ter-logout — sesi dihapus, perlu scan QR ulang');
          try { await sock.logout().catch(() => {}); } catch (_) {}
          await clearAuthDir();
          currentQR = null;
        }
        setTimeout(connect, 5000);
      } else if (connection === 'open') {
        connected = true;
        currentQR = null;
        myPhone = sock.user ? String(sock.user.id).split(':')[0] : null;
        log.info({ phone: myPhone }, 'terhubung ke WhatsApp');
      }
    });
  } catch (err) {
    log.error({ err }, 'gagal inisialisasi socket, coba lagi 10 dtk');
    setTimeout(connect, 10000);
  }
}

// ---------- Express ----------

const app = express();
app.use(express.json({ limit: '256kb' }));

function requireKey(req, res, next) {
  if (!API_KEY) return next();
  if (req.headers['x-api-key'] === API_KEY) return next();
  return res.status(401).json({ error: 'unauthorized' });
}

app.get('/health', (req, res) => res.json({ ok: true }));

app.get('/status', (req, res) => {
  res.json({
    connected,
    qr_available: !!currentQR,
    phone: myPhone,
    uptime_seconds: Math.floor((Date.now() - startedAt) / 1000),
  });
});

app.get('/qr', async (req, res) => {
  if (connected) {
    return res.send('<h2>Sudah terhubung' + (myPhone ? ' sebagai ' + myPhone : '') + '. Tidak perlu scan QR.</h2>');
  }
  if (!currentQR) {
    return res.send('<h2>QR belum tersedia — tunggu beberapa detik lalu refresh.</h2><script>setTimeout(()=>location.reload(),5000)</script>');
  }
  try {
    const dataUrl = await QRCode.toDataURL(currentQR, { width: 320, margin: 1 });
    res.send(
      '<!doctype html><html><head><meta charset="utf-8"><title>Pairing WhatsApp</title></head>' +
      '<body style="font-family:sans-serif;text-align:center">' +
      '<h2>Scan QR dengan WhatsApp di HP testing</h2>' +
      '<p>WhatsApp &gt; Perangkat Tertaut &gt; Tautkan Perangkat</p>' +
      '<img src="' + dataUrl + '" style="border:1px solid #ccc"/>' +
      '<p>QR refresh otomatis tiap 20 detik.</p>' +
      '<script>setTimeout(()=>location.reload(),20000)</script>' +
      '</body></html>'
    );
  } catch (e) {
    res.status(500).send('gagal membuat QR: ' + e.message);
  }
});

app.post('/send-text', requireKey, async (req, res) => {
  const { to, text } = req.body || {};
  if (!to || !text) return res.status(400).json({ error: 'to dan text wajib diisi' });
  if (!connected || !sock) return res.status(409).json({ error: 'not_connected', detail: 'sidecar belum terhubung — scan QR dulu di /qr' });
  try {
    const sent = await sock.sendMessage(toJid(to), { text: String(text) });
    const messageId = sent && sent.key ? sent.key.id : null;
    return res.json({ message_id: messageId });
  } catch (err) {
    log.error({ err }, 'gagal kirim pesan');
    return res.status(502).json({ error: 'send_failed', detail: String(err && err.message || err) });
  }
});

app.post('/logout', requireKey, async (req, res) => {
  try { if (sock) await sock.logout().catch(() => {}); } catch (_) {}
  connected = false;
  myPhone = null;
  currentQR = null;
  await clearAuthDir();
  res.json({ ok: true, detail: 'logout — scan QR ulang di /qr untuk pairing kembali' });
  setTimeout(connect, 2000);
});

app.listen(PORT, () => {
  log.info(`baileys sidecar listen di port ${PORT} (auth dir: ${AUTH_DIR})`);
  connect();
});
