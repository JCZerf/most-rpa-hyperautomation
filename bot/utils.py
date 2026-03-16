import re


def valor_texto_para_float(texto: str) -> float:
    """Converte texto monetário BRL para float. Ex.: 'R$ 1.234,56' -> 1234.56."""
    if not texto:
        return 0.0
    limpo = re.sub(r"[^\d,.-]", "", texto)
    if not limpo:
        return 0.0
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except Exception:
        return 0.0


def formatar_brl(valor: float) -> str:
    """Formata float para moeda BRL. Ex.: 1234.56 -> 'R$ 1.234,56'."""
    bruto = f"{valor:,.2f}"
    br = bruto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {br}"
