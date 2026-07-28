"""Vínculo de fondo objetivo → prioridad estratégica (pilar del roadmap).

Función pura y determinista que infiere a qué pilar del roadmap pertenece un
objetivo mensual, votando primero por coincidencia de KPIs y, si no hay señal,
cayendo a solapamiento de palabras significativas del texto.
"""
import re
import unicodedata

# Stopwords españolas básicas: no aportan señal de tema.
_STOPWORDS = {
    "de", "la", "el", "los", "las", "para", "con", "que", "una", "del",
    "por", "en", "y", "a", "su", "sus", "este", "esta",
}


def _norm(s: str | None) -> str:
    """Normaliza: minúsculas, sin acentos, sin puntuación, espacios colapsados."""
    if not s:
        return ""
    # Quita acentos vía descomposición NFKD y descarta marcas de combinación.
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Reemplaza cualquier cosa que no sea alfanumérico por espacio.
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _kpi_labels_of_pilar(pilar: dict) -> list[str]:
    """Labels normalizados de los KPIs de un pilar (tolerante a formas raras)."""
    out: list[str] = []
    for kpi in (pilar.get("kpis") or []):
        if isinstance(kpi, dict):
            label = kpi.get("label")
        else:
            label = kpi
        norm = _norm(label if isinstance(label, str) else None)
        if norm:
            out.append(norm)
    return out


def _labels_match(a: str, b: str) -> bool:
    """Igualdad normalizada, o que uno contenga al otro con len>=4."""
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 4 and a in b:
        return True
    if len(b) >= 4 and b in a:
        return True
    return False


def _significant_words(texto: str | None) -> set[str]:
    """Palabras normalizadas de len>=4 que no son stopwords."""
    words = _norm(texto).split()
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS}


def infer_pilar_index(
    kpi_refs: list[str] | None,
    texto: str | None,
    pilares: list[dict] | None,
) -> int | None:
    """Infiere el índice del pilar (en `pilares`) al que pertenece un objetivo.

    1) Voto por KPI: cada kpi_ref que empate con algún KPI de un pilar suma un
       voto a ese pilar. Gana el más votado (desempate: índice más bajo).
    2) Fallback por texto: si no hubo votos, solapamiento de palabras
       significativas entre `texto` y (nombre+objetivo+estrategias) del pilar.
       Devuelve el de mayor solapamiento solo si score >= 2; si no, None.

    Devuelve None ante None / listas vacías / pilares vacíos.
    """
    if not pilares or not isinstance(pilares, list):
        return None

    # --- Paso 1: voto por KPI ---
    if kpi_refs:
        norm_refs = [_norm(r) for r in kpi_refs if isinstance(r, str) and _norm(r)]
        votos: dict[int, int] = {}
        for ref in norm_refs:
            for idx, pilar in enumerate(pilares):
                if not isinstance(pilar, dict):
                    continue
                if any(_labels_match(ref, lbl) for lbl in _kpi_labels_of_pilar(pilar)):
                    votos[idx] = votos.get(idx, 0) + 1
        if votos:
            # Máximo de votos; desempate por índice más bajo.
            best = min(votos.items(), key=lambda kv: (-kv[1], kv[0]))
            return best[0]

    # --- Paso 2: fallback por texto ---
    obj_words = _significant_words(texto)
    if not obj_words:
        return None

    best_idx: int | None = None
    best_score = 0
    for idx, pilar in enumerate(pilares):
        if not isinstance(pilar, dict):
            continue
        partes = [pilar.get("nombre") or "", pilar.get("objetivo") or ""]
        estrategias = pilar.get("estrategias") or []
        if isinstance(estrategias, list):
            partes.extend(str(e) for e in estrategias)
        pilar_words = _significant_words(" ".join(partes))
        score = len(obj_words & pilar_words)
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_score >= 2:
        return best_idx
    return None
