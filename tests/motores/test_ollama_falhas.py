"""Falhas do Ollama não podem virar resposta vazia (PCs dos amigos, 2026-11-04).

O Ollama manda erros *dentro* do stream (HTTP 200 + ``{"error": ...}``); antes o
Nicx ignorava a linha e a tela ficava em branco. Quando o modelo cai na placa
de vídeo, o Nicx tenta de novo só no processador.
"""

from __future__ import annotations

import json

import httpx
import pytest

from nicx.motores import ollama
from nicx.motores._base import EngineRequestError
from nicx.motores.ollama import OllamaEngine
from nicx.nucleo.types import Message, Role

CRASH = "llama runner process has terminated: exit status 0xc0000409"


@pytest.fixture(autouse=True)
def volta_para_gpu(monkeypatch):
    monkeypatch.setattr(ollama, "_SO_CPU", False)


def _engine(respostas):
    """Cada pedido recebe a próxima resposta: linhas NDJSON ou (status, corpo)."""
    pedidos: list[dict] = []
    fila = list(respostas)

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(json.loads(request.content))
        atual = fila.pop(0)
        if isinstance(atual, tuple):
            return httpx.Response(atual[0], text=atual[1])
        return httpx.Response(200, content="\n".join(json.dumps(x) for x in atual))

    engine = OllamaEngine(host="http://localhost:11434")
    engine._async_transport = httpx.MockTransport(handler)
    return engine, pedidos


async def _texto(engine) -> str:
    partes = [
        t
        async for t in engine.stream([Message(role=Role.USER, content="oi")], model="m")
    ]
    return "".join(partes)


@pytest.mark.asyncio
async def test_erro_no_meio_do_stream_aparece():
    engine, _ = _engine([[{"error": "model failed to load, this may be a bug"}]])
    with pytest.raises(EngineRequestError, match="Ollama\\) falhou"):
        await _texto(engine)


@pytest.mark.asyncio
async def test_motor_caiu_na_gpu_tenta_no_processador():
    engine, pedidos = _engine(
        [
            [{"error": CRASH}],
            [{"message": {"content": "Oi!"}, "done": False}, {"done": True}],
        ]
    )
    assert await _texto(engine) == "Oi!"
    assert "num_gpu" not in pedidos[0]["options"]
    assert pedidos[1]["options"]["num_gpu"] == 0
    assert ollama._SO_CPU  # e os próximos pedidos já vão no processador
    engine2, pedidos2 = _engine([[{"message": {"content": "ok"}, "done": True}]])
    await _texto(engine2)
    assert pedidos2[0]["options"]["num_gpu"] == 0


@pytest.mark.asyncio
async def test_motor_caiu_com_http_500_tambem():
    engine, pedidos = _engine(
        [
            (500, json.dumps({"error": CRASH})),
            [{"message": {"content": "Oi"}, "done": True}],
        ]
    )
    assert await _texto(engine) == "Oi"
    assert pedidos[1]["options"]["num_gpu"] == 0


@pytest.mark.asyncio
async def test_caiu_de_novo_no_processador_mostra_o_erro():
    engine, _ = _engine([[{"error": CRASH}], [{"error": CRASH}]])
    with pytest.raises(EngineRequestError, match="exit status"):
        await _texto(engine)


@pytest.mark.asyncio
async def test_resposta_vazia_vira_aviso():
    engine, _ = _engine([[{"message": {"content": ""}, "done": True}]])
    with pytest.raises(EngineRequestError, match="sem escrever nada"):
        await _texto(engine)


@pytest.mark.asyncio
async def test_stream_full_tambem_tenta_no_processador():
    engine, pedidos = _engine(
        [[{"error": CRASH}], [{"message": {"content": "Oi"}, "done": True}]]
    )
    partes = [
        c
        async for c in engine.stream_full(
            [Message(role=Role.USER, content="oi")], model="m"
        )
    ]
    assert any(c.content == "Oi" for c in partes)
    assert pedidos[1]["options"]["num_gpu"] == 0


def test_generate_tenta_no_processador(monkeypatch):
    pedidos: list[dict] = []
    respostas = [
        httpx.Response(500, text=json.dumps({"error": CRASH})),
        httpx.Response(200, json={"message": {"content": "Oi"}, "done": True}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(json.loads(request.content))
        return respostas.pop(0)

    engine = OllamaEngine(host="http://localhost:11434")
    engine._client = httpx.Client(
        base_url="http://localhost:11434", transport=httpx.MockTransport(handler)
    )
    resultado = engine.generate([Message(role=Role.USER, content="oi")], model="m")
    assert resultado["content"] == "Oi"
    assert pedidos[1]["options"]["num_gpu"] == 0
