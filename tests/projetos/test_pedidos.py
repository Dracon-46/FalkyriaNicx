"""Frases de projeto em português, inglês, espanhol e francês."""

from __future__ import annotations

import pytest

from nicx.projetos import pedidos as p
from nicx.projetos.pedidos import Pedido, detectar


@pytest.mark.parametrize(
    ("frase", "esperado"),
    [
        # Português
        (
            "Cria o projeto Site Novo na pasta C:\\dev\\site",
            Pedido(p.CRIAR, nome="Site Novo", pasta="C:\\dev\\site"),
        ),
        ("Nicx, cria um novo projeto chamado Lumen", Pedido(p.CRIAR, nome="Lumen")),
        ("quais são os meus projetos?", Pedido(p.LISTAR)),
        ("meus projetos", Pedido(p.LISTAR)),
        ("Como está o projeto Lumen?", Pedido(p.VER, nome="Lumen")),
        ("como tá meu projeto?", Pedido(p.VER)),
        ("O que falta no projeto Lumen?", Pedido(p.FALTA, nome="Lumen")),
        ("quais as pendências do projeto Lumen", Pedido(p.FALTA, nome="Lumen")),
        (
            "anota no projeto Lumen que decidimos usar Postgres",
            Pedido(p.DECISAO, nome="Lumen", texto="Usar Postgres"),
        ),
        (
            "Decisão no projeto Lumen: usar Postgres às 15:30",
            Pedido(p.DECISAO, nome="Lumen", texto="Usar Postgres às 15:30"),
        ),
        (
            "no projeto Lumen decidimos trocar o logo",
            Pedido(p.DECISAO, nome="Lumen", texto="Trocar o logo"),
        ),
        (
            "adiciona pendência no projeto Lumen: comprar o domínio",
            Pedido(p.PENDENCIA, nome="Lumen", texto="comprar o domínio"),
        ),
        (
            "adiciona a pendência comprar o domínio no projeto Lumen",
            Pedido(p.PENDENCIA, nome="Lumen", texto="comprar o domínio"),
        ),
        (
            "adiciona pendência no projeto Lumen comprar o domínio",
            Pedido(p.PENDENCIA, nome="Lumen comprar o domínio", junto=True),
        ),
        (
            "conclui a pendência comprar o domínio do projeto Lumen",
            Pedido(p.CONCLUIR, nome="Lumen", texto="comprar o domínio"),
        ),
        (
            "marca a tarefa revisar textos como feita",
            Pedido(p.CONCLUIR, texto="revisar textos"),
        ),
        (
            "atualiza o estado do projeto Lumen: API pronta",
            Pedido(p.ESTADO, nome="Lumen", texto="API pronta"),
        ),
        ("arquiva o projeto Lumen", Pedido(p.ARQUIVAR, nome="Lumen")),
        (
            "renomeia o projeto Lumen para Lumen Dados",
            Pedido(p.RENOMEAR, nome="Lumen", novo_nome="Lumen Dados"),
        ),
        ("continue de onde parei", Pedido(p.CONTINUAR)),
        ("Nicx, continua de onde eu parei", Pedido(p.CONTINUAR)),
        ("o que eu estava fazendo?", Pedido(p.CONTINUAR)),
        ("onde eu parei no projeto Lumen?", Pedido(p.CONTINUAR, nome="Lumen")),
        ("continua o projeto Lumen", Pedido(p.CONTINUAR, nome="Lumen")),
        ("vamos continuar", Pedido(p.CONTINUAR)),
        # English
        (
            "create project Site in folder C:\\dev\\site",
            Pedido(p.CRIAR, nome="Site", pasta="C:\\dev\\site"),
        ),
        ("what are my projects?", Pedido(p.LISTAR)),
        ("How is project Lumen going?", Pedido(p.VER, nome="Lumen")),
        ("what's left in project Lumen?", Pedido(p.FALTA, nome="Lumen")),
        (
            "note in project Lumen that we decided to use Postgres",
            Pedido(p.DECISAO, nome="Lumen", texto="Use Postgres"),
        ),
        (
            "add task buy the domain to project Lumen",
            Pedido(p.PENDENCIA, nome="Lumen", texto="buy the domain"),
        ),
        (
            "add a task to project Lumen: buy the domain",
            Pedido(p.PENDENCIA, nome="Lumen", texto="buy the domain"),
        ),
        (
            "mark task buy the domain as done in project Lumen",
            Pedido(p.CONCLUIR, nome="Lumen", texto="buy the domain"),
        ),
        ("archive project Lumen", Pedido(p.ARQUIVAR, nome="Lumen")),
        ("pick up where I left off", Pedido(p.CONTINUAR)),
        ("What was I doing?", Pedido(p.CONTINUAR)),
        # Español
        ("crea el proyecto Lumen", Pedido(p.CRIAR, nome="Lumen")),
        ("¿cuáles son mis proyectos?", Pedido(p.LISTAR)),
        ("¿Cómo va el proyecto Lumen?", Pedido(p.VER, nome="Lumen")),
        ("¿qué falta en el proyecto Lumen?", Pedido(p.FALTA, nome="Lumen")),
        (
            "añade la tarea comprar el dominio al proyecto Lumen",
            Pedido(p.PENDENCIA, nome="Lumen", texto="comprar el dominio"),
        ),
        ("continúa donde lo dejé", Pedido(p.CONTINUAR)),
        ("¿qué estaba haciendo?", Pedido(p.CONTINUAR)),
        # Français
        ("crée le projet Lumen", Pedido(p.CRIAR, nome="Lumen")),
        ("quels sont mes projets ?", Pedido(p.LISTAR)),
        ("Où en est le projet Lumen ?", Pedido(p.VER, nome="Lumen")),
        (
            "qu'est-ce qui reste dans le projet Lumen ?",
            Pedido(p.FALTA, nome="Lumen"),
        ),
        (
            "ajoute la tâche acheter le domaine au projet Lumen",
            Pedido(p.PENDENCIA, nome="Lumen", texto="acheter le domaine"),
        ),
        ("reprends où j'en étais", Pedido(p.CONTINUAR)),
        ("qu'est-ce que je faisais ?", Pedido(p.CONTINUAR)),
    ],
)
def test_frases(frase, esperado):
    assert detectar(frase) == esperado


@pytest.mark.parametrize(
    "frase",
    [
        "Nicx, que horas são?",
        "me explica o que é um projeto de lei",
        "continua",
        "aumenta o volume",
        "anota comprar pão",
        "how do I start a project in Python?",
        "",
    ],
)
def test_nao_e_pedido_de_projeto(frase):
    assert detectar(frase) is None


def test_vamos_continuar_so_no_comeco():
    assert detectar("vamos continuar", primeira=True) == Pedido(p.CONTINUAR)
    assert detectar("vamos continuar", primeira=False) is None
    assert detectar("let's continue", primeira=False) is None
    # Com "de onde parei" vale sempre.
    assert detectar("vamos continuar de onde paramos", primeira=False) == Pedido(
        p.CONTINUAR
    )


def test_frase_da_pagina_em_chines_hindi_arabe():
    assert detectar("从上次停下的地方继续：Lumen") == Pedido(p.CONTINUAR, nome="Lumen")
    assert detectar("أكمل من حيث توقفت: Lumen") == Pedido(p.CONTINUAR, nome="Lumen")
    assert detectar("जहाँ छोड़ा था वहीं से जारी रखें: Lumen") == Pedido(
        p.CONTINUAR, nome="Lumen"
    )


def test_menciona_projeto():
    assert p.menciona_projeto("estou mexendo no projeto Lumen")
    assert p.menciona_projeto("the Lumen project")
    assert not p.menciona_projeto("bom dia")


def test_frase_do_botao_da_pagina_em_todos_os_idiomas():
    """O botão "Continuar de onde parei" manda ``continuePrompt`` ao chat."""
    import json
    from pathlib import Path

    locales = Path(__file__).parents[2] / "frontend" / "src" / "i18n" / "locales"
    arquivos = sorted(locales.glob("*/projects.json"))
    assert len(arquivos) == 7
    for arquivo in arquivos:
        frase = json.loads(arquivo.read_text(encoding="utf-8"))["continuePrompt"]
        pedido = detectar(frase.replace("{{name}}", "Nicx Site"), primeira=False)
        assert pedido == Pedido(p.CONTINUAR, nome="Nicx Site"), arquivo.parent.name
