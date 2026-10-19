"""
Adapter resmi: Meta WhatsApp Cloud API.

POST https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}/messages
header Authorization: Bearer {WA_ACCESS_TOKEN}
Template memakai parameter NAMED (parameter_format NAMED di Meta).
"""
import logging
import uuid

import httpx

from app.core.config import settings
from app.wa_adapter.base import WaProviderAdapter

log = logging.getLogger(__name__)
_GRAPH_VERSION = "v21.0"


class OfficialWhatsAppAdapter(WaProviderAdapter):
    @property
    def name(self) -> str:
        return "official"

    def is_configured(self) -> bool:
        return bool(settings.WA_PHONE_NUMBER_ID and settings.WA_ACCESS_TOKEN)

    def _dry_run(self, phone: str, kind: str) -> dict:
        log.warning(
            "DRY-RUN official WhatsApp: kredensial kosong, pesan %s ke %s TIDAK dikirim",
            kind, phone,
        )
        return {"provider_message_id": f"dry-run-{uuid.uuid4().hex[:12]}", "dry_run": True}

    def _post(self, payload: dict) -> dict:
        url = f"https://graph.facebook.com/{_GRAPH_VERSION}/{settings.WA_PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}"}
        with httpx.Client(timeout=30) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        messages = data.get("messages") or []
        return {"provider_message_id": messages[0].get("id") if messages else None,
                "raw": data}

    def send_text(self, phone: str, text: str) -> dict:
        if not self.is_configured():
            return self._dry_run(phone, "text")
        return self._post({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": text},
        })

    def send_template(
        self, phone: str, template_name: str, language: str, named_params: dict
    ) -> dict:
        if not self.is_configured():
            return self._dry_run(phone, f"template '{template_name}'")
        parameters = [
            {"type": "text", "parameter_name": name, "text": str(value)}
            for name, value in (named_params or {}).items()
        ]
        return self._post({
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language or "id"},
                "components": [
                    {"type": "body", "parameters": parameters}
                ] if parameters else [],
            },
        })
