"""Validasi & normalisasi nomor telepon format E.164."""
import re

try:
    import phonenumbers

    _HAS_PHONENUMBERS = True
except ImportError:  # pragma: no cover
    _HAS_PHONENUMBERS = False

_E164_RE = re.compile(r"^\+?[1-9]\d{7,14}$")


def normalize_phone(raw: str) -> str:
    """
    Normalisasi nomor ke digit E.164 tanpa '+' (mis. '6281234567890').
    Contoh input yang diterima: '+62 812-3456-7890', '081234567890' -> '6281234567890'.
    Raise ValueError bila format tidak valid.
    """
    if not raw or not isinstance(raw, str):
        raise ValueError("nomor telepon wajib diisi")
    cleaned = re.sub(r"[\s\-().]", "", raw.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    # Awalan 0 lokal (mis. 08xx) -> asumsikan Indonesia (62)
    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]
    if not cleaned.isdigit():
        raise ValueError("nomor telepon hanya boleh berisi digit (dan awalan +)")
    if not _E164_RE.match(cleaned):
        raise ValueError("format nomor tidak valid (E.164: 8-15 digit, tanpa awalan 0)")
    if _HAS_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse("+" + cleaned, None)
            if not phonenumbers.is_possible_number(parsed):
                raise ValueError("nomor telepon tidak memungkinkan (cek kembali digitnya)")
        except Exception as exc:
            raise ValueError(f"nomor telepon tidak valid: {exc}") from exc
    return cleaned
