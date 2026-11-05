"""Fechar o stream (botão Parar, aba fechada) para a thread do agente."""

from __future__ import annotations

import asyncio
import threading
import time
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")

from nicx.cerebro.agentes._stubs import AgentResult  # noqa: E402
from nicx.nucleo import cancelamento  # noqa: E402
from nicx.nucleo.events import EventBus  # noqa: E402
from nicx.servidor.models import ChatCompletionRequest  # noqa: E402
from nicx.servidor.pontes.stream import AgentStreamBridge  # noqa: E402


def test_fechar_o_stream_para_o_agente():
    viu_o_pedido = threading.Event()
    parou = threading.Event()

    def run_lento(texto, context=None):
        viu_o_pedido.set()
        # Um agente "pensando" (como o modelo na CPU): confere o Parar.
        for _ in range(500):
            try:
                cancelamento.verificar()
            except cancelamento.Cancelado:
                parou.set()
                raise
            time.sleep(0.01)
        return AgentResult(content="tarde demais")

    agent = MagicMock()
    agent._model = "m"
    agent.run.side_effect = run_lento
    request = ChatCompletionRequest(
        model="m", messages=[{"role": "user", "content": "oi"}], stream=True
    )
    bridge = AgentStreamBridge(agent, EventBus(), "m", request)

    async def comeca_e_desiste():
        gerador = bridge.stream()
        primeiro = await gerador.__anext__()  # papel "assistant"
        assert primeiro.startswith("data: ")
        await asyncio.to_thread(viu_o_pedido.wait, 5)
        await gerador.aclose()  # o navegador parou
        return await asyncio.to_thread(parou.wait, 5)

    assert asyncio.run(comeca_e_desiste()) is True


def test_resposta_completa_nao_cancela():
    visto: list[bool] = []

    def run_rapido(texto, context=None):
        visto.append(cancelamento.atual() is not None)
        return AgentResult(content="pronto")

    agent = MagicMock()
    agent._model = "m"
    agent.run.side_effect = run_rapido
    request = ChatCompletionRequest(
        model="m", messages=[{"role": "user", "content": "oi"}], stream=True
    )
    bridge = AgentStreamBridge(agent, EventBus(), "m", request)

    async def tudo():
        return [e async for e in bridge.stream()]

    eventos = asyncio.run(tudo())
    assert visto == [True]  # a thread enxerga o Cancelamento do pedido
    assert eventos[-1] == "data: [DONE]\n\n"
    assert cancelamento.atual() is None  # não vaza para fora do pedido
