"""Parar a resposta corta a geração do Ollama, não só a tela.

Num pedido do app (com :mod:`nicx.nucleo.cancelamento`), o ``generate`` pede em
partes e confere o Parar a cada uma; sair fecha a conexão e o Ollama para.
Fora disso (terminal, rotinas) o pedido continua o simples de sempre.
"""

from __future__ import annotations

import json

import httpx
import pytest

from nicx.motores import ollama
from nicx.motores.ollama import OllamaEngine
from nicx.nucleo import cancelamento
from nicx.nucleo.types import Message, Role

MSGS = [Message(role=Role.USER, content="oi")]


@pytest.fixture(autouse=True)
def volta_para_gpu(monkeypatch):
    monkeypatch.setattr(ollama, "_SO_CPU", False)


class _Partes(httpx.SyncByteStream):
    """Corpo em partes; ``depois_da_primeira`` roda quando a 1ª sai."""

    def __init__(self, linhas, depois_da_primeira=None):
        self.linhas = linhas
        self.depois = depois_da_primeira
        self.fechado = False
        self.enviadas = 0

    def __iter__(self):
        for i, linha in enumerate(self.linhas):
            self.enviadas += 1
            yield (json.dumps(linha) + "\n").encode()
            if i == 0 and self.depois:
                self.depois()

    def close(self):
        self.fechado = True


def _engine(corpo_ou_resposta):
    pedidos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(json.loads(request.content))
        if isinstance(corpo_ou_resposta, httpx.Response):
            return corpo_ou_resposta
        return httpx.Response(200, stream=corpo_ou_resposta)

    engine = OllamaEngine(host="http://localhost:11434")
    engine._client = httpx.Client(
        base_url="http://localhost:11434", transport=httpx.MockTransport(handler)
    )
    return engine, pedidos


PARTES = [
    {"message": {"role": "assistant", "content": "Olá"}, "done": False},
    {"message": {"role": "assistant", "content": ", tudo bem?"}, "done": False},
    {
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "model": "m",
        "prompt_eval_count": 12,
        "eval_count": 5,
        "prompt_eval_duration": 1_000_000_000,
    },
]


def test_sem_cancelamento_o_pedido_e_o_simples():
    resposta = httpx.Response(
        200,
        json={"message": {"content": "oi!"}, "prompt_eval_count": 3, "eval_count": 2},
    )
    engine, pedidos = _engine(resposta)
    resultado = engine.generate(MSGS, model="m")
    assert resultado["content"] == "oi!"
    assert pedidos[0]["stream"] is False


def test_em_partes_junta_igual_ao_pedido_simples():
    engine, pedidos = _engine(_Partes(PARTES))
    marca = cancelamento.ATUAL.set(cancelamento.Cancelamento())
    try:
        resultado = engine.generate(MSGS, model="m")
    finally:
        cancelamento.ATUAL.reset(marca)
    assert pedidos[0]["stream"] is True
    assert resultado["content"] == "Olá, tudo bem?"
    assert resultado["usage"]["completion_tokens"] == 5
    assert resultado["ttft"] == 1.0


def test_ferramentas_chegam_em_partes():
    chamada = {"function": {"name": "hora", "arguments": {"fuso": "BR"}}}
    partes = [
        {"message": {"role": "assistant", "content": "", "tool_calls": [chamada]}},
        {"message": {"role": "assistant", "content": ""}, "done": True},
    ]
    engine, _ = _engine(_Partes(partes))
    marca = cancelamento.ATUAL.set(cancelamento.Cancelamento())
    try:
        resultado = engine.generate(MSGS, model="m", tools=[{"type": "function"}])
    finally:
        cancelamento.ATUAL.reset(marca)
    (tc,) = resultado["tool_calls"]
    assert tc["name"] == "hora" and json.loads(tc["arguments"]) == {"fuso": "BR"}


def test_parar_no_meio_fecha_a_conexao():
    parar = cancelamento.Cancelamento()
    corpo = _Partes(PARTES * 50, depois_da_primeira=parar.cancelar)
    engine, _ = _engine(corpo)
    marca = cancelamento.ATUAL.set(parar)
    try:
        with pytest.raises(cancelamento.Cancelado):
            engine.generate(MSGS, model="m")
    finally:
        cancelamento.ATUAL.reset(marca)
    assert corpo.fechado
    assert corpo.enviadas < 5  # não leu a resposta inteira


def test_ja_parado_nem_pede():
    parar = cancelamento.Cancelamento()
    parar.cancelar()
    engine, pedidos = _engine(_Partes(PARTES))
    marca = cancelamento.ATUAL.set(parar)
    try:
        with pytest.raises(cancelamento.Cancelado):
            engine.generate(MSGS, model="m")
    finally:
        cancelamento.ATUAL.reset(marca)
    assert pedidos == []


def test_queda_da_placa_em_partes_tenta_na_cpu():
    crash = "llama runner process has terminated: exit status 0xc0000409"
    respostas = [_Partes([{"error": crash}]), _Partes(PARTES)]
    pedidos: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(json.loads(request.content))
        return httpx.Response(200, stream=respostas.pop(0))

    engine = OllamaEngine(host="http://localhost:11434")
    engine._client = httpx.Client(
        base_url="http://localhost:11434", transport=httpx.MockTransport(handler)
    )
    marca = cancelamento.ATUAL.set(cancelamento.Cancelamento())
    try:
        resultado = engine.generate(MSGS, model="m")
    finally:
        cancelamento.ATUAL.reset(marca)
    assert resultado["content"] == "Olá, tudo bem?"
    assert pedidos[1]["options"]["num_gpu"] == 0


def test_registro_aponta_para_o_motor():
    """O motor registrado como "ollama" é a classe (já apontou para uma função)."""
    import nicx.motores  # noqa: F401 - registra os motores
    from nicx.nucleo.registry import EngineRegistry

    assert EngineRegistry.get("ollama") is OllamaEngine
