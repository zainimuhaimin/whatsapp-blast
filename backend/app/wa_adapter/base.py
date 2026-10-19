"""
Interface abstrak provider WhatsApp.

Seluruh kode bisnis hanya bicara ke interface ini; campaign memilih
implementasi via kolom `campaigns.provider` ('official' | 'unofficial').

ATURAN TEGAS: adapter TIDAK PERNAH mengirim pesan sungguhan tanpa
kredensial terkonfigurasi — bila kredensial kosong, adapter berjalan
dalam mode dry_run (log warning, tanpa request HTTP).
"""
import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class WaProviderAdapter(ABC):
    """Kontrak pengiriman pesan WhatsApp."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nama provider: 'official' | 'unofficial'."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """True bila kredensial lengkap dan siap kirim sungguhan."""
        ...

    @abstractmethod
    def send_text(self, phone: str, text: str) -> dict:
        """
        Kirim teks bebas. Return dict minimal berisi 'provider_message_id'
        (dan 'dry_run': True bila mode dry-run).
        """
        ...

    @abstractmethod
    def send_template(
        self, phone: str, template_name: str, language: str, named_params: dict
    ) -> dict:
        """
        Kirim template dengan parameter BERNAMA (NAMED).
        Return dict minimal berisi 'provider_message_id'.
        """
        ...


def get_adapter(provider: str):
    """Factory: pilih adapter sesuai campaigns.provider."""
    from app.wa_adapter.official_whatsapp import OfficialWhatsAppAdapter
    from app.wa_adapter.unofficial_baileys import UnofficialWhatsAppAdapter

    if provider == "unofficial":
        return UnofficialWhatsAppAdapter()
    return OfficialWhatsAppAdapter()
