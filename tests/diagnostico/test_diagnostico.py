"""Diagnóstico: cada verificação diz o que achou e o que fazer."""

from __future__ import annotations

from types import SimpleNamespace

import httpx

from nicx.diagnostico import verificacoes as v


def _config(modelo="qwen3.5:4b"):
    return SimpleNamespace(
        engine=SimpleNamespace(ollama=SimpleNamespace(host="")),
        intelligence=SimpleNamespace(default_model=modelo),
    )


def _ollama(versao, modelos):
    def resposta(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": versao})
        return httpx.Response(200, json={"models": [{"name": m} for m in modelos]})

    return httpx.Client(base_url="http://x", transport=httpx.MockTransport(resposta))


def test_ollama_antigo_avisa_e_modelo_ausente_falha():
    r = v.ollama(_config(), _ollama("0.40.8", ["llama3:8b"]))
    assert [(x.id, x.estado) for x in r] == [("ollama", v.AVISO), ("modelo", v.FALHA)]
    assert "0.40.14" in r[0].dica and "ollama pull qwen3.5:4b" in r[1].dica

    r = v.ollama(_config(), _ollama("0.40.18", ["qwen3.5:4b"]))
    assert [(x.id, x.estado) for x in r] == [("ollama", v.OK), ("modelo", v.OK)]


def test_ollama_fora_do_ar_e_so_aviso():
    def cai(_request):
        raise httpx.ConnectError("recusado")

    cliente = httpx.Client(base_url="http://x", transport=httpx.MockTransport(cai))
    r = v.ollama(_config(), cliente)
    assert len(r) == 1 and r[0].estado == v.AVISO


def test_memoria_microfone_e_voz():
    pouca = SimpleNamespace(
        virtual_memory=lambda: SimpleNamespace(
            available=1 * 1024**3, total=16 * 1024**3
        )
    )
    assert v.memoria_ram(pouca).estado == v.AVISO

    sem_mic = SimpleNamespace(
        query_devices=lambda kind=None: [
            {"name": "Alto-falante", "max_input_channels": 0}
        ]
    )
    assert v.microfone(sem_mic).estado == v.AVISO
    dois = [
        {"name": "Mic USB", "max_input_channels": 1},
        {"name": "Mic USB", "max_input_channels": 2},  # o mesmo, por outra API
        {"name": "Mic interno", "max_input_channels": 1},
    ]
    com_mic = SimpleNamespace(
        query_devices=lambda kind=None: {"name": "Mic USB"} if kind else dois
    )
    r = v.microfone(com_mic)
    assert r.estado == v.OK and r.mensagem.startswith("2 microfone(s)")

    so_ouvir = v.voz(lambda nome: object() if nome == "faster_whisper" else None)
    assert so_ouvir.estado == v.AVISO and "falar" in so_ouvir.mensagem


def test_atalhos_so_os_ligados():
    class G:
        def __init__(self, estado, mensagem=""):
            self.st = {"estado": estado, "mensagem": mensagem}

        def status(self):
            return self.st

    estado = SimpleNamespace(
        atalho=G("registrado"),
        ditado=G("desligado"),
        captura=G("em_uso", "outro programa"),
    )
    r = {x.id: x for x in v.atalhos(estado)}
    assert set(r) == {"atalho_atalho", "atalho_captura"}
    assert (
        r["atalho_captura"].estado == v.AVISO
        and "outro programa" in r["atalho_captura"].mensagem
    )


def test_pasta_disco_e_rodar_tudo(tmp_path, monkeypatch):
    assert v.pasta_gravavel(tmp_path / "nova").estado == v.OK
    assert v.disco(tmp_path).estado in (v.OK, v.AVISO)
    monkeypatch.setattr(v, "ollama", lambda _c: [v.Verificacao("ollama", v.OK, "ok")])
    r = v.rodar(_config(), None, tmp_path)
    ids = {x["id"] for x in r["verificacoes"]}
    assert {
        "ollama",
        "rust",
        "ram",
        "disco",
        "pasta",
        "microfone",
        "voz",
        "historico",
    } <= ids
    assert sum(r["resumo"].values()) == len(r["verificacoes"])


def test_rota(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.diagnostico import router

    monkeypatch.setattr(v, "ollama", lambda _c: [v.Verificacao("ollama", v.OK, "ok")])
    app = FastAPI()
    app.include_router(router)
    app.state.config = _config()
    r = TestClient(app).get("/v1/diagnostico")
    assert r.status_code == 200 and r.json()["verificacoes"]
