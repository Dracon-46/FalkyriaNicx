# ruff: noqa: E501  (padrões de frase: uma regex por linha fica mais legível)
"""Calculadora em linguagem natural, sem modelo (~instantâneo).

Porcentagens ("15% de 230", "230 com 15% de desconto", "30 é quantos por cento
de 120"), contas ("quanto é 3 x 45,90", "calcula (2+3)*4"), dividir a conta
("dividir 350 entre 4 pessoas") e datas ("quantos dias faltam para 25/12",
"que dia cai daqui a 45 dias", "quantos dias entre 01/03 e 15/04").

Só frases inteiras que batem com os padrões viram cálculo; o resto segue para
o modelo. As contas são feitas aqui, com ``ast`` restrito (números e + - * / ^
e parênteses), nunca com ``eval``.
"""

from __future__ import annotations

import ast
import operator
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

_NUM = r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:[.,]\d+)?"
_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}  # fmt: skip
_DIAS_SEMANA = (
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
)
_MESES_NOME = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[?!]+", " ", t)
    t = t.replace("×", "*").replace("÷", "/")
    return " ".join(t.split()).strip(" .")


def numero(texto: str) -> float:
    t = texto.strip()
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?", t):
        return float(t.replace(".", "").replace(",", "."))
    return float(t.replace(",", "."))


def formatar(n: float, casas: Optional[int] = None) -> str:
    """1234.5 -> '1.234,50'; inteiros sem casas."""
    if casas is None:
        casas = 0 if abs(n - round(n)) < 1e-9 else 2
    texto = f"{n:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ contas

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _avaliar(no: ast.AST) -> float:
    if isinstance(no, ast.Expression):
        return _avaliar(no.body)
    if isinstance(no, ast.Constant) and isinstance(no.value, (int, float)):
        return float(no.value)
    if isinstance(no, ast.BinOp) and type(no.op) in _OPS:
        a, b = _avaliar(no.left), _avaliar(no.right)
        if isinstance(no.op, ast.Pow) and (abs(b) > 100 or abs(a) > 1e6):
            raise ValueError("potência grande demais")
        return _OPS[type(no.op)](a, b)
    if isinstance(no, ast.UnaryOp) and type(no.op) in _OPS:
        return _OPS[type(no.op)](_avaliar(no.operand))
    raise ValueError("expressão não permitida")


def _expressao(t: str) -> Optional[float]:
    """'3 x 45,90', '1200 dividido por 12', '(2+3)*4' -> número (ou None)."""
    e = t
    for antes, depois in (
        (r"\bdividido por\b", "/"),
        (r"\belevado a\b", "**"),
        (r"\bvezes\b", "*"),
        (r"\bmais\b", "+"),
        (r"\bmenos\b", "-"),
        (r"(?<=\d)\s*x\s*(?=[\d(])", "*"),
        (r"\^", "**"),
    ):
        e = re.sub(antes, depois, e)
    e = re.sub(_NUM, lambda m: repr(numero(m.group(0))), e)
    if not re.fullmatch(r"[\d\s.+\-*/()e]+", e) or not re.search(
        r"[+\-*/]", e.strip("-")
    ):
        return None
    try:
        return _avaliar(ast.parse(e, mode="eval"))
    except (SyntaxError, ValueError, ZeroDivisionError, OverflowError, RecursionError):
        return None


# ------------------------------------------------------------------- datas


def _data(t: str, hoje: date) -> Optional[date]:
    """'25/12', '25/12/2027', '25 de dezembro', 'natal', 'ano novo'."""
    t = t.strip()
    if t in ("natal", "o natal"):
        alvo = date(hoje.year, 12, 25)
        return alvo if alvo >= hoje else date(hoje.year + 1, 12, 25)
    if t in ("ano novo", "o ano novo", "reveillon", "o reveillon"):
        return date(hoje.year + 1, 1, 1)
    m = re.fullmatch(r"(?:o dia |dia )?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if m:
        dia, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.fullmatch(
            r"(?:o dia |dia )?(\d{1,2}) de (" + "|".join(_MESES) + r")(?: de (\d{4}))?",
            t,
        )
        if not m:
            return None
        dia, mes, ano = int(m.group(1)), _MESES[m.group(2)], m.group(3)
    try:
        if ano:
            a = int(ano)
            return date(a + 2000 if a < 100 else a, mes, dia)
        alvo = date(hoje.year, mes, dia)
        return alvo if alvo >= hoje else date(hoje.year + 1, mes, dia)
    except ValueError:
        return None


def _dia_por_extenso(d: date) -> str:
    return f"{_DIAS_SEMANA[d.weekday()]}, {d.day} de {_MESES_NOME[d.month - 1]} de {d.year}"


def _unidade_em_dias(n: int, unidade: str) -> int:
    if unidade.startswith("semana"):
        return n * 7
    if unidade.startswith(("mes", "meses")):
        return n * 30
    return n


# ----------------------------------------------------------------- parser

_PREFIXO = r"(?:(?:me )?(?:diz|diga|fala) )?(?:quanto (?:e|da|fica|sai|seria)|calcul[ae](?: pra mim| para mim)?|qual (?:e )?o resultado de|qual (?:e )?)?\s*"


def responder(texto: str, agora: Optional[datetime] = None) -> Optional[str]:
    """A resposta pronta, ou None se a frase não é um cálculo."""
    t = _normalizar(texto)
    if not t or len(t) > 160 or not re.search(r"\d|natal|ano novo|reveillon", t):
        return None
    hoje = (agora or datetime.now()).date()
    n = _NUM

    # --- porcentagem de um valor: "15% de 230", "quanto e 15 por cento de 230"
    m = re.fullmatch(
        _PREFIXO + rf"({n})\s*(?:%|por cento) (?:de|do|da|sobre) (?:r\$ ?)?({n})", t
    )
    if m:
        p, v = numero(m.group(1)), numero(m.group(2))
        return f"{formatar(p)}% de {formatar(v)} é {formatar(v * p / 100)}."

    # --- desconto / aumento
    valor_desconto = None
    m = re.fullmatch(
        _PREFIXO
        + rf"(?:r\$ ?)?({n}) (?:com|menos) ({n})\s*(?:%|por cento)(?: de desconto)?",
        t,
    )
    if m:
        valor_desconto = (numero(m.group(1)), numero(m.group(2)))
    m = re.fullmatch(
        _PREFIXO
        + rf"(?:um )?desconto de ({n})\s*(?:%|por cento) (?:em|no|na|sobre) (?:r\$ ?)?({n})",
        t,
    )
    if m:
        valor_desconto = (numero(m.group(2)), numero(m.group(1)))
    if valor_desconto:
        v, p = valor_desconto
        desconto = v * p / 100
        return (
            f"{formatar(v)} com {formatar(p)}% de desconto fica {formatar(v - desconto)} "
            f"(desconto de {formatar(desconto)})."
        )
    m = re.fullmatch(
        _PREFIXO
        + rf"(?:r\$ ?)?({n}) (?:mais|com aumento de|com acrescimo de|\+) ({n})\s*(?:%|por cento)",
        t,
    )
    if m:
        v, p = numero(m.group(1)), numero(m.group(2))
        aumento = v * p / 100
        return f"{formatar(v)} mais {formatar(p)}% fica {formatar(v + aumento)} (aumento de {formatar(aumento)})."

    # --- que porcentagem: "30 e quantos por cento de 120", "quanto por cento e 30 de 120"
    m = re.fullmatch(rf"({n}) e quantos (?:%|por cento) de ({n})", t) or re.fullmatch(
        rf"quantos? (?:%|por cento) (?:e|sao) ({n}) de ({n})", t
    )
    if m:
        parte, total = numero(m.group(1)), numero(m.group(2))
        if total == 0:
            return None
        return f"{formatar(parte)} é {formatar(parte / total * 100, 1).rstrip('0').rstrip(',')}% de {formatar(total)}."

    # --- dividir a conta
    m = re.fullmatch(
        rf"(?:dividir|divide|divida|rachar|racha) (?:a conta de |uma conta de )?(?:r\$ ?)?({n}) (?:entre|por|para|pra) ({n}) (?:pessoas|amigos|pessoa)",
        t,
    )
    if m:
        total, pessoas = numero(m.group(1)), numero(m.group(2))
        if pessoas <= 0:
            return None
        return f"{formatar(total)} dividido por {formatar(pessoas)} dá {formatar(total / pessoas, 2)} para cada um."

    # --- quantos dias faltam
    m = re.fullmatch(
        r"(?:quantos dias (?:faltam|falta) (?:para|pra|pro|ate)|em quantos dias (?:e|cai)) (.+)",
        t,
    )
    if m:
        alvo = _data(m.group(1), hoje)
        if alvo:
            dias = (alvo - hoje).days
            if dias == 0:
                return f"É hoje: {_dia_por_extenso(alvo)}."
            return f"Faltam {dias} dia{'s' if dias != 1 else ''} para {_dia_por_extenso(alvo)}."
    # --- dias entre duas datas
    m = re.fullmatch(
        r"quantos dias (?:tem |ha |sao )?(?:entre|de) (.+?) (?:e|ate|a) (.+)", t
    )
    if m:
        a, b = _data(m.group(1), hoje), _data(m.group(2), hoje)
        if a and b:
            if b < a and not re.search(r"\d{4}", m.group(2)):
                b = date(b.year + 1, b.month, b.day)
            return f"São {abs((b - a).days)} dias entre {a:%d/%m/%Y} e {b:%d/%m/%Y}."
    # --- daqui a N dias / há N dias
    m = re.fullmatch(
        r"(?:que dia (?:cai|vai ser|sera|foi|era|e)|qual (?:e |era |foi )?a data) (daqui a|daqui|em|ha|faz) (\d+) (dias?|semanas?|mes|meses)(?: atras)?",
        t,
    )
    if m:
        quantos = _unidade_em_dias(int(m.group(2)), m.group(3))
        passado = m.group(1) in ("ha", "faz") or t.endswith("atras")
        alvo = (
            hoje - timedelta(days=quantos)
            if passado
            else hoje + timedelta(days=quantos)
        )
        return f"{'Foi' if passado else 'Vai ser'} {_dia_por_extenso(alvo)}."

    # --- conta comum: "quanto e 3 x 45,90", "calcula (2+3)*4", "12*7"
    m = re.fullmatch(_PREFIXO + r"(.+)", t)
    expr = m.group(1) if m else t
    if not re.search(
        r"[a-z]", re.sub(r"\b(?:vezes|mais|menos|dividido por|elevado a|x)\b", "", expr)
    ):
        resultado = _expressao(expr)
        if resultado is not None:
            if not (m and t != expr) and not re.search(
                r"[+\-*/x^]|vezes|mais|menos|dividido", expr
            ):
                return None
            return f"Dá {formatar(resultado) if abs(resultado) < 1e15 else f'{resultado:.6g}'}."
    return None


def parse(texto: str):
    """Action('calc') com a resposta em ``target``, ou None."""
    resposta = responder(texto)
    if resposta is None:
        return None
    from nicx.acoes.intencoes import Action

    return Action("calc", target=resposta)


__all__ = ["formatar", "numero", "parse", "responder"]
