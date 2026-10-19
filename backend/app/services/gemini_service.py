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

_SYSTEM_PROMPT_TEMPLATE = (
    "Kamu adalah ekstraktor data untuk tool pengiriman pesan WhatsApp. "
    "User memiliki TEMPLATE pesan berikut (variabel ditulis {{{{nama_variabel}}}}):\n"
    "---\n{template_body}\n---\n"
    "Tugasmu: dari teks bebas yang diberikan user, ekstrak HANYA nilai untuk "
    "daftar variabel berikut: {variables}. "
    "Gunakan TEMPLATE di atas sebagai konteks untuk memahami maksud tiap variabel — "
    "teks di sekitar sebuah variabel menjelaskan apa arti variabel itu "
    "(misalnya kalimat sebelum {{{{diskon}}}} menunjukkan itu besaran diskon, "
    "kalimat sebelum {{{{link}}}} menunjukkan itu tautan/URL). "
    "Aturan:\n"
    "1. Kembalikan JSON MURNI dengan format {{\"nama_variabel\": \"nilai\"}}, tanpa teks lain, tanpa markdown.\n"
    "2. Jika nilai sebuah variabel tidak ditemukan di teks, isi dengan string kosong \"\".\n"
    "3. JANGAN mengarang nilai yang tidak ada di teks user.\n"
    "4. Jangan mengekstrak data personal penerima (nama penerima dsb) — hanya variabel yang diminta."
)

_SYSTEM_PROMPT_NOVARS = (
    "Kamu adalah ekstraktor data untuk tool pengiriman pesan WhatsApp. "
    "Tugasmu: dari teks bebas yang diberikan user, ekstrak HANYA nilai untuk "
    "daftar variabel berikut: {variables}. "
    "Aturan:\n"
    "1. Kembalikan JSON MURNI dengan format {{\"nama_variabel\": \"nilai\"}}, tanpa teks lain, tanpa markdown.\n"
    "2. Jika nilai sebuah variabel tidak ditemukan di teks, isi dengan string kosong \"\".\n"
    "3. JANGAN mengarang nilai yang tidak ada di teks user.\n"
    "4. Jangan mengekstrak data personal penerima (nama penerima dsb) — hanya variabel yang diminta."
)

# Batas panjang template yang dikirim sebagai konteks (hemat token)
_MAX_TEMPLATE_CONTEXT_CHARS = 2000


def _build_system_prompt(variables: list[str], template_body: str | None) -> str:
    """Susun system prompt; sertakan body template sebagai konteks bila ada."""
    body = (template_body or "").strip()
    if body:
        if len(body) > _MAX_TEMPLATE_CONTEXT_CHARS:
            body = body[:_MAX_TEMPLATE_CONTEXT_CHARS] + "…"
        return _SYSTEM_PROMPT_TEMPLATE.format(
            template_body=body, variables=", ".join(variables)
        )
    return _SYSTEM_PROMPT_NOVARS.format(variables=", ".join(variables))


def extract_variable_values(
    input_text: str, variables: list[str], template_body: str | None = None
) -> tuple[dict[str, str], bool]:
    """
    Ekstrak nilai variabel dari teks bebas user.
    template_body (opsional): body template pesan, dikirim sebagai konteks
    agar LLM memahami maksud tiap variabel.
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
            system_instruction=_build_system_prompt(variables, template_body),
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
