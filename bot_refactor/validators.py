import re
from typing import Tuple, Literal

ConsultaTipo = Literal["cpf", "nis", "nome"]


def _digito_verificador_cpf(digits: str) -> Tuple[int, int]:
    """Calcula os dois dígitos verificadores de um CPF a partir dos 9 primeiros dígitos."""
    soma1 = sum(int(d) * peso for d, peso in zip(digits[:9], range(10, 1, -1)))
    dv1 = (soma1 * 10) % 11
    if dv1 == 10:
        dv1 = 0

    soma2 = sum(int(d) * peso for d, peso in zip(digits[:9] + str(dv1), range(11, 1, -1)))
    dv2 = (soma2 * 10) % 11
    if dv2 == 10:
        dv2 = 0

    return dv1, dv2


def _valida_cpf(numero: str) -> bool:
    if len(numero) != 11 or len(set(numero)) == 1:
        return False
    dv1, dv2 = _digito_verificador_cpf(numero)
    return numero[-2:] == f"{dv1}{dv2}"


def _valida_nis(numero: str) -> bool:
    """Valida PIS/PASEP/NIS com algoritmo de peso 3,2,9,8,7,6,5,4,3,2."""
    if len(numero) != 11 or len(set(numero)) == 1:
        return False
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(numero[:10], pesos))
    resto = soma % 11
    digito = 11 - resto
    if digito in (10, 11):
        digito = 0
    return int(numero[-1]) == digito


def classificar_consulta(valor: str) -> Tuple[bool, ConsultaTipo | None, str, str]:
    """
    Classifica e valida a string de consulta.
    Retorna: (valido, tipo, valor_normalizado, motivo_erro)
    """
    if valor is None:
        return False, None, "", "Consulta ausente"

    valor_str = str(valor).strip()
    if not valor_str:
        return False, None, "", "Consulta vazia"

    valor_digitos = re.sub(r"\D", "", valor_str)
    somente_digitos = valor_str.isdigit()
    tem_letras = bool(re.search(r"[A-Za-zÀ-ÿ]", valor_str))

    # Caso misto letras+digitos é inválido
    if somente_digitos and tem_letras:
        return False, None, valor_str, "Consulta mista (letras e dígitos) não é permitida"

    # Permite CPF/NIS com pontuação e valida em cima da versão normalizada.
    if valor_digitos and not tem_letras:
        if len(valor_digitos) != 11:
            return False, None, valor_digitos, "Número deve ter 11 dígitos para CPF/NIS"
        if _valida_cpf(valor_digitos):
            return True, "cpf", valor_digitos, ""
        if _valida_nis(valor_digitos):
            return True, "nis", valor_digitos, ""
        return False, None, valor_digitos, "Dígitos inválidos para CPF/NIS"

    if tem_letras:
        # Nome: letras, espaços, ponto, hífen e apóstrofos/acentos simples
        if re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'´`^~çÇ.\-\s]{1,}", valor_str):
            return True, "nome", valor_str, ""
        return False, None, valor_str, "Nome inválido (somente letras/espacos/pontuação simples)"

    # Qualquer outro caso cai como inválido
    return False, None, valor_str, "Formato de consulta inválido"


def mascarar_identificador(valor: str) -> str:
    if not valor:
        return "***"
    if len(valor) <= 6:
        return "***"
    return f"{valor[:3]}***{valor[-3:]}"
