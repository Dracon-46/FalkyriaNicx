"""Dados do modo Trabalho: analisar tabelas, gráficos, converter e comparar.

Tudo local e sem dependências novas: CSV pelo módulo ``csv``, Excel e gráficos
pelo ``openpyxl`` (o gráfico é um gráfico de verdade do Excel, editável), PDF
pelo ``pdfplumber`` e Word pelo ``python-docx``.
"""

from __future__ import annotations

import csv
import difflib
import io
import re
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

MAX_LINHAS = 100_000
OPERACOES = ("soma", "media", "contagem", "maximo", "minimo")


class ErroDados(RuntimeError):
    """Falha explicada ao modelo."""


# ------------------------------------------------------------------ valores


def numero(valor: Any) -> Optional[float]:
    """Número de uma célula: 42, '3.5', '1.234,56', 'R$ 45,90', '12%'; senão None."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    if not isinstance(valor, str):
        return None
    t = valor.strip().replace(" ", " ")
    t = re.sub(r"^(R\$|US\$|\$|€|£)\s*", "", t).rstrip("%").strip()
    negativo = t.startswith("(") and t.endswith(")")
    t = t.strip("()").replace(" ", "")
    if re.fullmatch(r"-?\d+", t):
        n = float(t)
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+,\d+", t):
        n = float(t.replace(".", "").replace(",", "."))
    elif re.fullmatch(r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+\.\d+", t):
        n = float(t.replace(",", ""))
    else:
        return None
    return -n if negativo else n


def data(valor: Any) -> Optional[date]:
    """Data de uma célula: datetime, '25/11/2026', '2026-11-25', '25-11-2026'."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if not isinstance(valor, str):
        return None
    t = valor.strip()[:19]
    for formato in (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(t if "T" in formato else t[:10], formato).date()
        except ValueError:
            continue
    return None


def _celula(valor: Any) -> Any:
    """Valor para gravar no Excel: números e datas viram números e datas."""
    if isinstance(valor, str):
        n = numero(valor)
        if n is not None and not (
            len(valor.strip()) > 1
            and valor.strip()[0] == "0"
            and valor.strip()[1].isdigit()
        ):
            return (
                int(n)
                if n.is_integer() and "," not in valor and "." not in valor
                else n
            )
        d = data(valor) if re.search(r"\d{1,4}[/-]\d{1,2}[/-]\d{2,4}", valor) else None
        if d:
            return d
    return valor


def _fmt(n: float) -> str:
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ tabelas


def ler_tabela(p: Path, aba: str = "") -> tuple[list[str], list[list[Any]]]:
    """Cabeçalho e linhas de um CSV/TSV ou de uma aba do Excel."""
    ext = p.suffix.lower()
    if ext in (".csv", ".tsv", ".txt"):
        bruto = p.read_bytes()
        for cod in ("utf-8-sig", "cp1252"):
            try:
                texto = bruto.decode(cod)
                break
            except UnicodeDecodeError:
                continue
        else:
            texto = bruto.decode("utf-8", errors="replace")
        try:
            dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=",;\t|")
        except csv.Error:
            dialeto = csv.excel_tab if ext == ".tsv" else csv.excel
        linhas = [
            r
            for r in csv.reader(io.StringIO(texto), dialeto)
            if any(c.strip() for c in r)
        ]
    elif ext in (".xlsx", ".xlsm"):
        import openpyxl

        livro = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
        try:
            if aba:
                if aba not in livro.sheetnames:
                    raise ErroDados(
                        f"a planilha não tem a aba '{aba}' "
                        f"(tem: {', '.join(livro.sheetnames)})"
                    )
                folha = livro[aba]
            else:
                folha = livro.worksheets[0]
            linhas = []
            for linha in folha.iter_rows(values_only=True):
                if any(v not in (None, "") for v in linha):
                    linhas.append(list(linha))
                if len(linhas) > MAX_LINHAS:
                    break
        finally:
            livro.close()
    else:
        raise ErroDados("para analisar, use uma tabela .csv, .tsv ou .xlsx")
    if not linhas:
        raise ErroDados("a tabela está vazia")
    cabecalho = [
        str(c).strip() if c not in (None, "") else f"coluna {i + 1}"
        for i, c in enumerate(linhas[0])
    ]
    corpo = [
        list(r) + [None] * (len(cabecalho) - len(r)) for r in linhas[1 : MAX_LINHAS + 1]
    ]
    return cabecalho, corpo


def _coluna(cabecalho: list[str], nome: str) -> int:
    alvo = nome.strip().lower()
    for i, c in enumerate(cabecalho):
        if c.lower() == alvo:
            return i
    for i, c in enumerate(cabecalho):
        if alvo and alvo in c.lower():
            return i
    raise ErroDados(f"não achei a coluna '{nome}' (colunas: {', '.join(cabecalho)})")


def analisar(
    cabecalho: list[str],
    linhas: list[list[Any]],
    *,
    agrupar_por: str = "",
    valor: str = "",
    operacao: str = "soma",
    por_mes: bool = False,
) -> str:
    """Resumo da tabela; com ``agrupar_por``, a conta por grupo (ou por mês)."""
    operacao = (operacao or "soma").lower().replace("é", "e").replace("á", "a")
    if operacao not in OPERACOES:
        raise ErroDados(f"operação desconhecida: use {', '.join(OPERACOES)}")
    partes = [f"{len(linhas)} linhas, {len(cabecalho)} colunas."]
    for i, nome in enumerate(cabecalho):
        valores = [r[i] for r in linhas if r[i] not in (None, "")]
        nums = [n for n in (numero(v) for v in valores) if n is not None]
        datas = [d for d in (data(v) for v in valores) if d]
        if valores and len(nums) >= 0.8 * len(valores):
            partes.append(
                f"- {nome}: números; soma {_fmt(sum(nums))}, "
                f"média {_fmt(sum(nums) / len(nums))}, "
                f"mín {_fmt(min(nums))}, máx {_fmt(max(nums))}"
            )
        elif valores and len(datas) >= 0.8 * len(valores):
            partes.append(
                f"- {nome}: datas de {min(datas):%d/%m/%Y} a {max(datas):%d/%m/%Y}"
            )
        else:
            distintos = list(OrderedDict.fromkeys(str(v) for v in valores))
            amostra = ", ".join(distintos[:6]) + ("…" if len(distintos) > 6 else "")
            partes.append(
                f"- {nome}: texto; {len(distintos)} valores diferentes ({amostra})"
            )
    if not agrupar_por:
        return "\n".join(partes)

    g = _coluna(cabecalho, agrupar_por)
    v = _coluna(cabecalho, valor) if valor else None
    if v is None and operacao != "contagem":
        raise ErroDados("diga a coluna de valor (ou use a operação 'contagem')")
    grupos: "OrderedDict[str, list[float]]" = OrderedDict()
    ignoradas = 0
    for r in linhas:
        chave_bruta = r[g]
        if por_mes:
            d = data(chave_bruta)
            if not d:
                ignoradas += 1
                continue
            chave = f"{d:%Y-%m}"
        else:
            chave = "" if chave_bruta is None else str(chave_bruta).strip()
        if v is None:
            grupos.setdefault(chave, []).append(1.0)
            continue
        n = numero(r[v])
        if n is None:
            ignoradas += 1
            continue
        grupos.setdefault(chave, []).append(n)
    if por_mes:
        grupos = OrderedDict(sorted(grupos.items()))
    conta = {
        "soma": sum,
        "media": lambda xs: sum(xs) / len(xs),
        "contagem": len,
        "maximo": max,
        "minimo": min,
    }[operacao]
    titulo_valor = cabecalho[v] if v is not None else "linhas"
    partes.append("")
    partes.append(
        f"{operacao} de {titulo_valor} por {cabecalho[g]}{' (mês)' if por_mes else ''}:"
    )
    partes.append(f"{cabecalho[g]}\t{operacao} {titulo_valor}")
    for chave, xs in list(grupos.items())[:200]:
        resultado = conta(xs)
        partes.append(
            f"{chave or '(vazio)'}\t"
            f"{_fmt(resultado) if operacao != 'contagem' else resultado}"
        )
    if len(grupos) > 200:
        partes.append(f"… (+{len(grupos) - 200} grupos)")
    if ignoradas:
        partes.append(
            f"({ignoradas} linha(s) ignorada(s): "
            f"sem número{' ou data' if por_mes else ''})"
        )
    return "\n".join(partes)


# ------------------------------------------------------------------ gráfico


TIPOS_GRAFICO = ("barras", "colunas", "linhas", "pizza")


def grafico_xlsx(
    p: Path, linhas: list, *, tipo: str = "colunas", titulo: str = ""
) -> int:
    """Grava a tabela e um gráfico do Excel numa aba 'Gráfico' (cria ou atualiza).

    ``linhas``: a primeira é o cabeçalho; a 1ª coluna são os rótulos e as outras,
    as séries. Devolve quantas linhas de dados entraram.
    """
    import openpyxl
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.styles import Font

    tipo = (tipo or "colunas").lower()
    if tipo not in TIPOS_GRAFICO:
        raise ErroDados(f"tipo de gráfico: use {', '.join(TIPOS_GRAFICO)}")
    if not isinstance(linhas, list) or len(linhas) < 2:
        raise ErroDados("mande o cabeçalho e pelo menos uma linha de dados")
    tabela = [r if isinstance(r, list) else [r] for r in linhas]
    largura = max(len(r) for r in tabela)
    if largura < 2:
        raise ErroDados("cada linha precisa do rótulo e de pelo menos um valor")
    tabela = [r + [None] * (largura - len(r)) for r in tabela]

    if p.exists():
        livro = openpyxl.load_workbook(str(p))
        nome = "Gráfico"
        i = 2
        while nome in livro.sheetnames:
            nome = f"Gráfico {i}"
            i += 1
        folha = livro.create_sheet(nome)
    else:
        livro = openpyxl.Workbook()
        folha = livro.active
        folha.title = "Gráfico"
    for n, r in enumerate(tabela):
        if n == 0:
            folha.append([str(c) if c is not None else "" for c in r])
            for c in folha[1]:
                c.font = Font(bold=True)
        else:
            folha.append(
                [r[0]] + [numero(c) if numero(c) is not None else c for c in r[1:]]
            )
    linhas_dados = len(tabela) - 1
    if tipo == "pizza":
        grafico = PieChart()
        largura = 2
    elif tipo == "linhas":
        grafico = LineChart()
    else:
        grafico = BarChart()
        grafico.type = "bar" if tipo == "barras" else "col"
    grafico.title = titulo or None
    valores = Reference(
        folha, min_col=2, max_col=largura, min_row=1, max_row=linhas_dados + 1
    )
    rotulos = Reference(folha, min_col=1, min_row=2, max_row=linhas_dados + 1)
    grafico.add_data(valores, titles_from_data=True)
    grafico.set_categories(rotulos)
    grafico.width, grafico.height = 18, 9
    folha.add_chart(grafico, f"{chr(ord('A') + min(largura, 20) + 1)}2")
    p.parent.mkdir(parents=True, exist_ok=True)
    livro.save(str(p))
    return linhas_dados


# ----------------------------------------------------------------- converter


CONVERSOES = {
    ".csv": {".xlsx"},
    ".tsv": {".xlsx"},
    ".xlsx": {".csv"},
    ".docx": {".txt", ".md"},
    ".pdf": {".txt", ".md", ".xlsx"},
    ".txt": {".docx"},
    ".md": {".docx"},
    ".json": {".xlsx", ".csv"},
}


def _tabelas_do_pdf(p: Path) -> list[list[list[Any]]]:
    import pdfplumber

    tabelas = []
    with pdfplumber.open(str(p)) as pdf:
        for pagina in pdf.pages[:50]:
            for t in pagina.extract_tables() or []:
                limpa = [
                    [(c or "").strip() for c in linha]
                    for linha in t
                    if any(c for c in linha)
                ]
                if len(limpa) >= 2:
                    tabelas.append(limpa)
    return tabelas


def _json_em_tabela(p: Path) -> list[list[Any]]:
    import json

    try:
        dados = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ErroDados(f"JSON inválido: {exc}") from exc
    if isinstance(dados, dict):
        lista = next((v for v in dados.values() if isinstance(v, list)), [dados])
    else:
        lista = dados
    if (
        not isinstance(lista, list)
        or not lista
        or not all(isinstance(x, dict) for x in lista)
    ):
        raise ErroDados("o JSON precisa ser uma lista de objetos para virar tabela")
    colunas = list(OrderedDict.fromkeys(k for x in lista for k in x))
    return [colunas] + [
        [
            x.get(c)
            if not isinstance(x.get(c), (dict, list))
            else json.dumps(x.get(c), ensure_ascii=False)
            for c in colunas
        ]
        for x in lista
    ]


def _gravar_xlsx(destino: Path, abas: list[tuple[str, list[list[Any]]]]) -> int:
    import openpyxl
    from openpyxl.styles import Font

    livro = openpyxl.Workbook()
    livro.remove(livro.active)
    total = 0
    for nome, linhas in abas:
        folha = livro.create_sheet(nome[:31])
        for n, r in enumerate(linhas):
            folha.append([_celula(c) for c in r])
            if n == 0:
                for c in folha[1]:
                    c.font = Font(bold=True)
            total += 1
    destino.parent.mkdir(parents=True, exist_ok=True)
    livro.save(str(destino))
    return total


def converter(origem: Path, destino: Path, texto_de: Any) -> str:
    """Converte *origem* em *destino* pelas extensões.

    ``texto_de(p)`` lê qualquer arquivo como texto.
    """
    de, para = origem.suffix.lower(), destino.suffix.lower()
    if para not in CONVERSOES.get(de, set()):
        possiveis = ", ".join(
            f"{a}→{'/'.join(sorted(b))}" for a, b in CONVERSOES.items()
        )
        raise ErroDados(
            f"não sei converter {de or 'sem extensão'} em {para} (sei: {possiveis})"
        )
    if para == ".xlsx":
        if de == ".pdf":
            tabelas = _tabelas_do_pdf(origem)
            if not tabelas:
                raise ErroDados(
                    "não achei tabelas nesse PDF (se for escaneado, não há texto)"
                )
            n = _gravar_xlsx(
                destino, [(f"Tabela {i + 1}", t) for i, t in enumerate(tabelas)]
            )
            return f"{len(tabelas)} tabela(s), {n} linhas"
        if de == ".json":
            linhas = _json_em_tabela(origem)
        else:
            cab, corpo = ler_tabela(origem)
            linhas = [cab] + corpo
        n = _gravar_xlsx(destino, [(origem.stem or "Dados", linhas)])
        return f"{n} linhas"
    if para == ".csv":
        if de == ".json":
            linhas = _json_em_tabela(origem)
        else:
            cab, corpo = ler_tabela(origem)
            linhas = [cab] + corpo
        saida = io.StringIO()
        escritor = csv.writer(saida, delimiter=";", lineterminator="\n")
        for r in linhas:
            escritor.writerow(
                [
                    ""
                    if c is None
                    else (f"{c:%d/%m/%Y}" if isinstance(c, (date, datetime)) else c)
                    for c in r
                ]
            )
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(
            saida.getvalue().encode("utf-8-sig")
        )  # o Excel abre com acentos
        return f"{len(linhas)} linhas (separador ;)"
    if para in (".txt", ".md"):
        texto = texto_de(origem)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(texto.encode("utf-8"))
        return f"{len(texto)} caracteres"
    if para == ".docx":
        import docx

        d = docx.Document()
        for linha in texto_de(origem).splitlines():
            limpa = linha.rstrip()
            if limpa.startswith("### "):
                d.add_heading(limpa[4:], level=3)
            elif limpa.startswith("## "):
                d.add_heading(limpa[3:], level=2)
            elif limpa.startswith("# "):
                d.add_heading(limpa[2:], level=1)
            elif limpa.lstrip().startswith(("- ", "* ")):
                d.add_paragraph(limpa.lstrip()[2:], style="List Bullet")
            elif limpa.strip():
                d.add_paragraph(limpa)
        destino.parent.mkdir(parents=True, exist_ok=True)
        d.save(str(destino))
        return "documento Word criado"
    raise ErroDados("conversão não suportada")  # pragma: no cover


# ----------------------------------------------------------------- comparar


def comparar(
    texto_a: str, texto_b: str, nome_a: str, nome_b: str, limite: int = 6000
) -> str:
    """O que mudou de A para B, linha a linha (+ entrou, - saiu)."""
    a = [linha.rstrip() for linha in texto_a.splitlines()]
    b = [linha.rstrip() for linha in texto_b.splitlines()]
    if a == b:
        return "Os dois têm o mesmo conteúdo."
    diff = list(
        difflib.unified_diff(a, b, fromfile=nome_a, tofile=nome_b, lineterm="", n=1)
    )
    entrou = sum(1 for d in diff if d.startswith("+") and not d.startswith("+++"))
    saiu = sum(1 for d in diff if d.startswith("-") and not d.startswith("---"))
    semelhanca = difflib.SequenceMatcher(None, texto_a, texto_b).ratio()
    corpo = "\n".join(diff[2:])
    if len(corpo) > limite:
        corpo = corpo[:limite] + "\n… (mais diferenças)"
    return (
        f"{nome_a} → {nome_b}: {entrou} linha(s) entraram, {saiu} saíram; "
        f"{semelhanca:.0%} parecidos.\n"
        f"(+ = só em {nome_b}, - = só em {nome_a})\n{corpo}"
    )


__all__ = [
    "CONVERSOES",
    "ErroDados",
    "analisar",
    "comparar",
    "converter",
    "data",
    "grafico_xlsx",
    "ler_tabela",
    "numero",
]
