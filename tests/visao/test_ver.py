"""Ver a imagem: pedidos, captura (janela e área de transferência), checagem
do modelo e a imagem chegando ao motor pela rota do chat."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nicx.contexto import janela, pedidos, servico
from nicx.contexto.montagem import Captura, bloco
from nicx.visao import modelo, ocr

PNG = "iVBORw0KGgo="  # só o começo de um PNG: o motor é simulado


@pytest.mark.parametrize(
    ("frase", "fonte"),
    [
        ("descreve essa imagem", pedidos.JANELA),
        ("o que você vê na tela?", pedidos.JANELA),
        ("explica esse gráfico", pedidos.JANELA),
        ("descreve a imagem que eu copiei", pedidos.AREA),
        ("o que tem na foto copiada?", pedidos.AREA),
        ("describe this picture", pedidos.JANELA),
        ("what do you see?", pedidos.JANELA),
        ("¿qué ves?", pedidos.JANELA),
        ("décris cette image", pedidos.JANELA),
    ],
)
def test_pedidos_de_ver(frase, fonte):
    pedido = pedidos.detectar(frase)
    assert pedido is not None and pedido.ver and pedido.fonte == fonte


@pytest.mark.parametrize(
    "frase",
    [
        "lê o texto da imagem que eu copiei",
        "o que está escrito nessa imagem",
        "resume essa página",
        "lê a tela",
    ],
)
def test_so_texto_nao_usa_visao(frase):
    pedido = pedidos.detectar(frase)
    assert pedido is not None and not pedido.ver


@pytest.mark.parametrize("frase", ["tira uma foto minha amanhã", "manda a foto"])
def test_nao_e_pedido(frase):
    assert pedidos.detectar(frase) is None


# ------------------------------------------------------------------- captura
@pytest.fixture
def windows(monkeypatch):
    monkeypatch.setattr(servico.sys, "platform", "win32")
    monkeypatch.setattr(janela, "sensivel", lambda _i: False)
    info = janela.InfoJanela(hwnd=7, titulo="vendas.png - Fotos", processo="photos.exe")
    monkeypatch.setattr(janela, "janela_de_fora", lambda: info)
    return info


def test_imagem_da_janela(windows, monkeypatch):
    vistos = []

    def ver(hwnd, idioma, lado):
        vistos.append((hwnd, lado))
        return ocr.Leitura(True, texto="Vendas 2026", imagem=PNG)

    monkeypatch.setattr(servico, "_ver_janela", ver)
    preparo = servico.preparar("descreve essa imagem", config=None)
    assert preparo.captura.imagens == (PNG,) and preparo.captura.fonte == "tela"
    assert preparo.captura.texto == "Vendas 2026" and vistos == [(7, 640)]
    assert 'imagem="anexada' in bloco(preparo.captura, 1000)


def test_imagem_copiada(windows, monkeypatch):
    monkeypatch.setattr(
        servico, "_ver_area", lambda idioma, lado: ocr.Leitura(True, imagem=PNG)
    )
    preparo = servico.preparar("descreve a imagem que eu copiei", config=None)
    assert preparo.captura.fonte == "imagem_copiada" and preparo.captura.texto == ""


def test_sem_imagem_cai_no_texto(windows, monkeypatch):
    monkeypatch.setattr(
        servico, "_ver_janela", lambda *a: ocr.Leitura(False, motivo="minimizada")
    )
    texto = servico.Preparo(pedidos.JANELA, captura=Captura("texto", "documento"))
    monkeypatch.setattr(servico, "capturar_janela", lambda *a, **k: texto)
    preparo = servico.preparar("descreve essa imagem", config=None)
    assert preparo.captura.fonte == "documento" and preparo.captura.imagens == ()


def test_janela_sensivel_sem_imagem(windows, monkeypatch):
    monkeypatch.setattr(janela, "sensivel", lambda _i: True)
    monkeypatch.setattr(servico, "_ver_janela", lambda *a: pytest.fail("não captura"))
    preparo = servico.preparar("descreve essa imagem", config=None)
    assert preparo.captura is None and preparo.resposta


def test_ver_imagens_desligado(windows, monkeypatch):
    from nicx.nucleo.config import NicxConfig

    cfg = NicxConfig()
    cfg.contexto.ver_imagens = False
    monkeypatch.setattr(servico, "_ver_janela", lambda *a: pytest.fail("desligado"))
    monkeypatch.setattr(
        servico,
        "capturar_janela",
        lambda *a, **k: servico.Preparo(pedidos.JANELA, captura=Captura("x", "tela")),
    )
    assert servico.preparar("descreve essa imagem", config=cfg).captura.imagens == ()


# -------------------------------------------------------------------- modelo
def test_enxerga(monkeypatch):
    import httpx

    modelo._CACHE.clear()
    chamadas = []

    def post(url, json, timeout):
        chamadas.append(json["model"])
        resposta = MagicMock()
        resposta.json.return_value = {"capabilities": ["completion", "vision"]}
        return resposta

    monkeypatch.setattr(httpx, "post", post)
    assert modelo.enxerga("qwen3.5:4b") and modelo.enxerga("qwen3.5:4b")
    assert chamadas == ["qwen3.5:4b"]  # guardado

    cfg = MagicMock()
    cfg.engine.default = "llamacpp"
    assert not modelo.enxerga("qwen3.5:4b", cfg)


def test_enxerga_com_ollama_desligado(monkeypatch):
    import httpx

    modelo._CACHE.clear()

    def falha(*a, **k):
        raise httpx.ConnectError("recusado")

    monkeypatch.setattr(httpx, "post", falha)
    assert not modelo.enxerga("qwen3.5:4b") and modelo._CACHE == {}


# ---------------------------------------------------------------------- rota
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
    engine.health.return_value = True
    engine.list_models.return_value = ["m"]
    engine.generate.return_value = {
        "content": "Um gráfico de barras.",
        "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        "model": "m",
        "finish_reason": "stop",
    }
    memory = MagicMock()
    memory.list_facts.return_value = []
    app = create_app(engine, "m", config=cfg, memory_service=memory)
    return TestClient(app), engine, memory


def _com_imagem(monkeypatch, texto=""):
    captura = Captura(texto, "tela", {"app": "Fotos"}, imagens=(PNG,))
    monkeypatch.setattr(
        servico,
        "preparar",
        lambda *a, **k: servico.Preparo(pedidos.JANELA, captura=captura),
    )


def _pedir(client, frase="descreve essa imagem"):
    corpo = {"model": "m", "messages": [{"role": "user", "content": frase}]}
    return client.post("/v1/chat/completions", json=corpo).json()


def test_rota_manda_a_imagem_ao_modelo(monkeypatch):
    _com_imagem(monkeypatch, "Vendas 2026")
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: True)
    client, engine, memory = _client()
    assert _pedir(client)["choices"][0]["message"]["content"] == "Um gráfico de barras."
    ultima = engine.generate.call_args.args[0][-1]
    assert ultima.images == [PNG] and "Vendas 2026" in ultima.content
    memory.store.assert_not_called()  # a imagem e o pedido ficam fora da memória


def test_rota_modelo_sem_visao_fica_com_o_texto(monkeypatch):
    _com_imagem(monkeypatch, "Vendas 2026")
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: False)
    client, engine, _ = _client()
    _pedir(client)
    ultima = engine.generate.call_args.args[0][-1]
    assert not ultima.images and "Vendas 2026" in ultima.content


def test_rota_modelo_sem_visao_e_sem_texto(monkeypatch):
    _com_imagem(monkeypatch)
    monkeypatch.setattr(modelo, "enxerga", lambda m, c=None: False)
    client, engine, _ = _client()
    resposta = _pedir(client)["choices"][0]["message"]["content"]
    assert "não enxerga imagens" in resposta
    engine.generate.assert_not_called()
