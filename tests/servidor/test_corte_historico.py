"""O histórico que vai ao modelo cabe no contexto e não leva respostas de erro."""

from __future__ import annotations

from nicx.servidor.models import ChatMessage
from nicx.servidor.rotas.chat import _cortar_historico


def _m(role, content, **kw):
    return ChatMessage(role=role, content=content, **kw)


def test_conversa_longa_fica_com_as_mais_novas():
    msgs = [_m("system", "regras")]
    for i in range(40):
        msgs += [_m("user", f"pergunta {i} " + "x" * 400), _m("assistant", "y" * 400)]
    msgs.append(_m("user", "a de agora"))
    cortado = _cortar_historico(msgs, 8192)
    assert cortado[0].content == "regras" and cortado[-1].content == "a de agora"
    assert sum(len(m.content) for m in cortado) < 8192 + 1000
    assert len(cortado) < len(msgs)


def test_respostas_de_erro_e_vazias_saem():
    msgs = [
        _m("user", "oi"),
        _m("assistant", "Não consegui responder: o motor caiu"),
        _m("user", "oi de novo"),
        _m("assistant", ""),
        _m("user", "e agora?"),
    ]
    assert [m.content for m in _cortar_historico(msgs, 8192)] == [
        "oi",
        "oi de novo",
        "e agora?",
    ]


def test_so_a_ultima_leva_imagem():
    msgs = [
        _m("user", "veja", images=["AAA"]),
        _m("assistant", "vi"),
        _m("user", "e esta?", images=["BBB"]),
    ]
    cortado = _cortar_historico(msgs, 8192)
    assert cortado[0].images is None and cortado[-1].images == ["BBB"]


def test_mensagem_unica_fica_igual():
    msgs = [_m("user", "oi")]
    assert _cortar_historico(msgs, 8192) == msgs
