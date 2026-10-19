"""
Service ekstraksi variabel via Google Gemini.

Bila GEMINI_API_KEY tidak dikonfigurasi -> fallback graceful:
kembalikan mapping kosong + ai_available=False (TIDAK error).
"""
import json
import logging
import re

from app.core.config import settings

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Kamu adalah ekstraktor data untuk tool pengiriman pesan WhatsApp. "
    "Tugasmu: dari teks bebas yang diberikan user, ekstrak HANYA nilai untuk "
    "daftar variabel berikut: {variables}. "
    "Aturan:\n"
    "1. Kembalikan JSON MURNI dengan format {{\"nama_variabel\": \"nilai\"}}, tanpa teks lain, tanpa markdown.\n"
    "2. Jika nilai sebuah variabel tidak ditemukan di teks, isi dengan string kosong \"\".\n"
    "3. JANGAN mengarang nilai yang tidak ada di teks user.\n"
    "4. Jangan mengekstrak data personal penerima (nama penerima dsb) — hanya variabel yang diminta."
)


def extract_variable_values(
    input_text: str, variables: list[str]
) -> tuple[dict[str, str], bool]:
    """
    Ekstrak nilai variabel dari teks bebas user.
    Return: (mapping {variabel: value}, ai_available).
    """
    if not settings.GEMINI_API_KEY:
        log.info("GEMINI_API_KEY kosong -> ai-extract fallback tanpa AI")
        return {}, False
    try:
        import google.generativeai as genai
    except ImportError:
        log.warning("package google-generativeai tidak terinstall -> fallback tanpa AI")
        return {}, False

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=_SYSTEM_PROMPT.format(variables=", ".join(variables)),
        )
        response = model.generate_content(input_text)
        text = (response.text or "").strip()
        # Bersihkan fence markdown bila ada
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
        data = json.loads(text)
        values = {
            var: str(data.get(var, "") or "")
            for var in variables
            if isinstance(data, dict)
        }
        return values, True
    except Exception as exc:  # AI gagal -> graceful, bukan error fatal
        log.warning("Gemini extract gagal (%s) -> fallback mapping kosong", exc)
        return {}, False
