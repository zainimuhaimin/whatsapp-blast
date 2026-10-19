# Ekstraksi & render variabel template {{nama}}.
import re

# Pola sesuai dokumen desain: {{nama_variabel}}
VARIABLE_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def extract_variables(body: str) -> list[str]:
    """Ekstrak nama variabel unik dari body template, sesuai urutan kemunculan."""
    seen: list[str] = []
    for match in VARIABLE_RE.finditer(body or ""):
        name = match.group(1)
        if name not in seen:
            seen.append(name)
    return seen


def render(body: str, values: dict[str, str | None]) -> str:
    """Ganti {{var}} dengan nilainya; variabel tanpa nilai jadi string kosong."""
    def _replace(match: re.Match) -> str:
        name = match.group(1)
        value = values.get(name)
        return "" if value is None else str(value)

    return VARIABLE_RE.sub(_replace, body or "")
