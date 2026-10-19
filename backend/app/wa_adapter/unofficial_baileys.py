"""
Adapter non-resmi: Baileys sidecar (self-hosted, gratis, untuk testing).

Backend memanggil REST API sidecar Node.js (lihat ../baileys/server.js):
  POST {BAILEYS_API_URL}/send-text  {to, text}  header x-api-key

Pairing dilakukan dengan scan QR di {BAILEYS_API_URL}/qr (satu kali;
sesi tersimpan di volume sidecar).

PERINGATAN: jalur tidak resmi (protokol WhatsApp Web) — jangan pakai
nomor WA utama/pribadi, gunakan nomor testing khusus (risiko banned).
"""
import logging
import uuid

import httpx

from app.core.config import settings
from app.wa_adapter.base import WaProviderAdapter

log = logging.getLogger(__name__)


class UnofficialWhatsAppAdapter(WaProviderAdapter):
    @property
    def name(self) -> str:
        return "unofficial"

    def is_configured(self) -> bool:
        return bool(settings.BAILEYS_API_URL)

    def _dry_run(self, phone: str) -> dict:
        log.warning(
            "DRY-RUN Baileys: BAILEYS_API_URL kosong, pesan ke %s TIDAK dikirim", phone
        )
        return {"provider_message_id": f"dry-run-{uuid.uuid4().hex[:12]}", "dry_run": True}

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if settings.BAILEYS_API_KEY:
            headers["x-api-key"] = settings.BAILEYS_API_KEY
        return headers

    def send_text(self, phone: str, text: str) -> dict:
        if not self.is_configured():
            return self._dry_run(phone)
        url = settings.BAILEYS_API_URL.rstrip("/") + "/send-text"
        # trust_env=False: traffic ke sidecar internal tidak boleh lewat proxy env
        with httpx.Client(timeout=60, trust_env=False) as client:
            resp = client.post(
                url, headers=self._headers(), json={"to": phone, "text": text}
            )
        if resp.status_code == 409:
            # Sidecar belum terhubung (belum scan QR) -> raise agar worker
            # menandai failed + retry, bukan silent success.
            raise RuntimeError(
                "Baileys belum terhubung — buka menu 'Koneksi WA' di aplikasi "
                "lalu scan QR dengan nomor testing khusus"
            )
        resp.raise_for_status()
        data = resp.json()
        return {"provider_message_id": data.get("message_id"), "raw": data}

    def send_template(
        self, phone: str, template_name: str, language: str, named_params: dict
    ) -> dict:
        """
        Baileys tidak memakai konsep template Meta; template di sini berarti
        body teks bebas. Worker me-render body lebih dulu lalu memanggil
        send_text, jadi method ini hanya fallback defensif.
        """
        from app.services import renderer

        text = renderer.render(template_name, named_params or {})
        return self.send_text(phone, text)
