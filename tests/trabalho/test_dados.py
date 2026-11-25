"""Ferramentas de dados do modo Trabalho: analisar, gráfico, converter, comparar."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from nicx.trabalho import dados, ferramentas, modelo
from nicx.trabalho.modelo import Tarefa


@pytest.fixture
def pasta(tmp_path) -> Path:
    p = tmp_path / "dados"
    p.mkdir()
    (p / "gastos.csv").write_bytes(
        (
            "Data;Loja;Categoria;Valor\n"
            "03/11/2026;Padaria;Comida;R$ 45,90\n"
            "05/11/2026;Mercado;Comida;312,40\n"
            "10/11/2026;Farmácia;Saúde;87,15\n"
            "02/12/2026;Mercado;Comida;1.200,00\n"
            "05/12/2026;Posto;Transporte;\n"
        ).encode("utf-8")
    )
    return p


def _f(pasta: Path) -> tuple[Tarefa, ferramentas.Ferramentas]:
    t = Tarefa(id=modelo.novo_id(), pasta=str(pasta), pedido="dados")
    return t, ferramentas.Ferramentas(t, lambda _x: True, lambda: modelo.salvar(t))


def test_numeros_e_datas_do_jeito_brasileiro():
    assert dados.numero("R$ 1.234,56") == 1234.56
    assert dados.numero("1,234.56") == 1234.56
    assert dados.numero("(10,00)") == -10.0
    assert dados.numero("12%") == 12.0
    assert dados.numero("abc") is None and dados.numero(True) is None
    assert dados.data("25/11/2026") == date(2026, 11, 25)
    assert dados.data("2026-11-25T10:00:00") == date(2026, 11, 25)
    assert dados.data("ontem") is None


def test_analisar_resumo_e_agrupado_por_mes(pasta):
    _t, f = _f(pasta)
    ok, texto = f.executar("analisar_dados", {"caminho": "gastos.csv"})
    assert ok, texto
    assert "5 linhas, 4 colunas." in texto
    assert "Valor: números; soma 1.645,45" in texto
    assert "Data: datas de 03/11/2026 a 05/12/2026" in texto

    ok, texto = f.executar(
        "analisar_dados",
        {
            "caminho": "gastos.csv",
            "agrupar_por": "data",
            "valor": "valor",
            "por_mes": True,
        },
    )
    assert ok, texto
    assert "2026-11\t445,45" in texto and "2026-12\t1.200,00" in texto
    assert "1 linha(s) ignorada(s)" in texto  # o Posto sem valor

    ok, texto = f.executar(
        "analisar_dados",
        {"caminho": "gastos.csv", "agrupar_por": "Categoria", "operacao": "contagem"},
    )
    assert "Comida\t3" in texto and "Saúde\t1" in texto
    ok, texto = f.executar(
        "analisar_dados", {"caminho": "gastos.csv", "agrupar_por": "Nada"}
    )
    assert not ok and "não achei a coluna" in texto


def test_grafico_do_excel_e_desfazer(pasta):
    import openpyxl

    t, f = _f(pasta)
    linhas = [["Mês", "Gastos"], ["2026-11", "445,45"], ["2026-12", 1200]]
    ok, texto = f.executar(
        "criar_grafico",
        {"caminho": "graficos.xlsx", "linhas": linhas, "tipo": "colunas"},
    )
    assert ok, texto
    livro = openpyxl.load_workbook(pasta / "graficos.xlsx")
    folha = livro["Gráfico"]
    assert len(folha._charts) == 1
    assert [c.value for c in folha["B"]][1:] == [445.45, 1200]
    # Segunda vez na mesma planilha: aba nova, cópia guardada para o desfazer.
    ok, _ = f.executar(
        "criar_grafico", {"caminho": "graficos.xlsx", "linhas": linhas, "tipo": "pizza"}
    )
    assert ok and openpyxl.load_workbook(pasta / "graficos.xlsx").sheetnames == [
        "Gráfico",
        "Gráfico 2",
    ]
    ferramentas.desfazer(t)
    assert not (pasta / "graficos.xlsx").exists()
    assert not f.executar("criar_grafico", {"caminho": "g.xlsx", "linhas": [["só"]]})[0]


def test_converter_csv_xlsx_csv_e_docx(pasta):
    import openpyxl

    _t, f = _f(pasta)
    ok, texto = f.executar(
        "converter", {"origem": "gastos.csv", "destino": "gastos.xlsx"}
    )
    assert ok, texto
    folha = openpyxl.load_workbook(pasta / "gastos.xlsx").active
    linha = [c.value for c in folha[2]]
    assert linha[1:] == ["Padaria", "Comida", 45.9]
    assert linha[0].date() == date(2026, 11, 3)

    ok, texto = f.executar(
        "converter", {"origem": "gastos.xlsx", "destino": "copia.csv"}
    )
    assert ok, texto
    csv_texto = (pasta / "copia.csv").read_bytes().decode("utf-8-sig")
    assert csv_texto.splitlines()[1] == "03/11/2026;Padaria;Comida;45.9"

    (pasta / "notas.md").write_bytes("# Título\n- item\ntexto".encode())
    assert f.executar("converter", {"origem": "notas.md", "destino": "notas.docx"})[0]
    ok, lido = f.executar("ler_arquivo", {"caminho": "notas.docx"})
    assert "Título" in lido and "item" in lido

    (pasta / "lista.json").write_bytes(b'[{"a": 1, "b": "x"}, {"a": 2, "c": [1]}]')
    assert f.executar("converter", {"origem": "lista.json", "destino": "lista.csv"})[0]
    assert (pasta / "lista.csv").read_bytes().decode("utf-8-sig").splitlines() == [
        "a;b;c",
        "1;x;",
        "2;;[1]",
    ]
    ok, texto = f.executar("converter", {"origem": "gastos.csv", "destino": "x.pdf"})
    assert not ok and "não sei converter" in texto


def test_comparar(pasta):
    _t, f = _f(pasta)
    (pasta / "v1.txt").write_bytes(
        "Cláusula 1: prazo de 30 dias\nCláusula 2: multa 2%\n".encode()
    )
    (pasta / "v2.txt").write_bytes(
        "Cláusula 1: prazo de 45 dias\nCláusula 2: multa 2%\n".encode()
    )
    ok, texto = f.executar("comparar", {"a": "v1.txt", "b": "v2.txt"})
    assert ok, texto
    assert "1 linha(s) entraram, 1 saíram" in texto
    assert (
        "-Cláusula 1: prazo de 30 dias" in texto
        and "+Cláusula 1: prazo de 45 dias" in texto
    )
    ok, texto = f.executar("comparar", {"a": "v1.txt", "b": "v1.txt"})
    assert texto == "Os dois têm o mesmo conteúdo."
