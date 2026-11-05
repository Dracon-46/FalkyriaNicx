"""Imagem anexada no chat chega ao modelo; o que não serve volta com o motivo."""

from __future__ import annotations

import base64
import io
from unittest.mock import MagicMock

import pytest

pytest.importorskip("fastapi")
from PIL import Image  # noqa: E402

from nicx.visao import modelo  # noqa: E402


def _png(lado=(1200, 900)) -> str:
    saida = io.BytesIO()
    Image.new("RGB", lado, (20, 120, 200)).save(saida, "PNG")
    return base64.b64encode(saida.getvalue()).decode()


def _client():
    from fastapi.testclient import TestClient

    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.app import create_app

    cfg = NicxConfig()
    cfg.analytics.enabled = False
    cfg.traces.enabled = False
    cfg.security.enabled = False
    cfg.agent.context_from_memory = False
    engine = MagicMock()
    engine.engine_id = "mock"
    engine.is_cloud = False
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "Um quadrado azul.",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    memory = MagicMock()
    memory.list_facts.return_value = []
    app = create_app(engine, "m", config=cfg, memory_service=memory)
    return TestClient(app), engine


def _pedir(client, frase, imagens):
    corpo = {
        "model": "m",
        "messages": [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "Olá!"},
            {"role": "user", "content": frase, "images": imagens},
        ],
    }
    return client.post("/v1/chat/completions", json=corpo)


def test_imagem_anexada_vai_reduzida_ao_modelo(monkeypatch):
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: True)
    client, engine = _client()
    resposta = _pedir(client, "o que é isso?", [_png()])
    assert resposta.status_code == 200
    assert resposta.json()["choices"][0]["message"]["content"] == "Um quadrado azul."
    ultima = engine.generate.call_args.args[0][-1]
    (enviada,) = ultima.images
    img = Image.open(io.BytesIO(base64.b64decode(enviada)))
    assert max(img.size) == 640
    # Caminho direto: sem a lista de ferramentas.
    assert not engine.generate.call_args.kwargs.get("tools")


def test_com_imagem_nao_le_a_tela(monkeypatch):
    from nicx.contexto import servico

    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: True)
    chamado = []
    monkeypatch.setattr(servico, "preparar", lambda *a, **k: chamado.append(1))
    client, _ = _client()
    assert _pedir(client, "descreve essa imagem", [_png()]).status_code == 200
    assert chamado == []


def test_imagem_que_nao_abre_volta_400(monkeypatch):
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: True)
    client, engine = _client()
    lixo = base64.b64encode(b"nao sou imagem").decode()
    resposta = _pedir(client, "o que é isso?", [lixo])
    assert resposta.status_code == 400
    assert "abrir" in resposta.json()["detail"]
    engine.generate.assert_not_called()


def test_modelo_sem_visao_avisa(monkeypatch):
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: False)
    client, engine = _client()
    resposta = _pedir(client, "o que é isso?", [_png()])
    assert "não enxerga imagens" in resposta.json()["choices"][0]["message"]["content"]
    engine.generate.assert_not_called()
