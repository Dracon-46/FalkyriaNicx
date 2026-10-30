"""Frases sobre a tela: área de transferência, janela e "onde eu tô?"."""

from __future__ import annotations

import pytest

from nicx.acoes.roteamento import needs_other_tools, needs_tools
from nicx.contexto.pedidos import AREA, JANELA, ONDE, detectar


@pytest.mark.parametrize(
    "frase",
    [
        # pt
        "resume o que eu copiei",
        "Nicx, traduz o que eu copiei pra inglês",
        "corrige o texto copiado",
        "responde o que eu copiei",
        "explica o que tá na área de transferência",
        # en
        "summarize what I copied",
        "translate what I just copied into Spanish",
        "fix the copied text",
        # es
        "resume lo que copié",
        "traduce el texto copiado",
        "explica lo que hay en el portapapeles",
        # fr
        "résume ce que j'ai copié",
        "corrige le texte copié",
        "lis le presse-papiers",
    ],
)
def test_area_de_transferencia(frase):
    pedido = detectar(frase)
    assert pedido is not None and pedido.fonte == AREA


@pytest.mark.parametrize(
    "frase",
    [
        "explica isso aqui",
        "o que é esse erro?",
        "resume essa página",
        "resume esse documento",
        "corrige esse código",
        "o que eu selecionei quer dizer o quê?",
        "explain this page",
        "what does this error mean?",
        "summarize this document",
        "explica esto de aquí",
        "¿qué es este error?",
        "resume esta página",
        "explique cette page",
        "c'est quoi cette erreur ?",
        "résume ce document",
    ],
)
def test_janela(frase):
    pedido = detectar(frase)
    assert pedido is not None and pedido.fonte == JANELA


@pytest.mark.parametrize(
    "frase",
    ["onde eu tô?", "onde estou", "Nicx, onde eu estou?", "where am I?",
     "¿dónde estoy?", "où suis-je ?", "em que app eu tô?"],
)  # fmt: skip
def test_onde(frase):
    pedido = detectar(frase)
    assert pedido is not None and pedido.fonte == ONDE


@pytest.mark.parametrize(
    "frase",
    [
        "qual a capital da França?",
        "copie o arquivo pra pasta de downloads",
        "aumenta o volume",
        "e aí, tudo bem?",
        "resume essa conversa",
        "onde eu estou errando na vida",
        "what is the weather like",
        "esta semana tem feriado?",
    ],
)
def test_conversa_comum_nao_e_pedido(frase):
    assert detectar(frase) is None


def test_isso_sozinho_so_na_primeira_mensagem():
    assert detectar("traduz isso pra inglês", primeira=True).fonte == JANELA
    assert detectar("translate this", primeira=True).fonte == JANELA
    # No meio da conversa, "isso" costuma ser a resposta anterior do Nicx.
    assert detectar("traduz isso pra inglês", primeira=False) is None
    assert detectar("explica isso", primeira=False) is None
    # Referências claras valem sempre.
    assert detectar("explica isso aqui", primeira=False).fonte == JANELA
    assert detectar("resume o que eu copiei", primeira=False).fonte == AREA


def test_mensagem_que_ja_traz_o_texto():
    assert detectar("traduz isso: hello world, how are you today?") is None
    assert detectar("explica isso aqui:\nTypeError: x is undefined") is None
    # "o que eu copiei" é sempre a área de transferência.
    assert detectar("resume o que eu copiei: tá meio longo").fonte == AREA


def test_resto_sem_a_referencia_para_o_roteamento():
    assert detectar("resume esse documento").resto == "resume"
    assert "copiei" not in detectar("anota o que eu copiei").resto


def test_roteamento_de_ferramentas():
    for frase in ("o que eu copiei?", "explica isso aqui", "explain this page",
                  "résume ce que j'ai copié", "lee el portapapeles"):  # fmt: skip
        assert needs_tools(frase), frase
    assert not needs_tools("me conta uma piada")
    # Com o texto já anexado, só pedidos com outra ação precisam de ferramenta.
    assert not needs_other_tools(detectar("resume esse documento").resto)
    assert needs_other_tools(detectar("anota o que eu copiei").resto)
