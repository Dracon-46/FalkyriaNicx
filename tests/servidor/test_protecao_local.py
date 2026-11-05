"""Sites abertos no navegador não usam a API local (DNS rebinding e CSRF)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.servidor.protecao_local import ProtecaoLocal


def _cliente(checar_host: bool = True) -> TestClient:
    app = FastAPI()

    @app.get("/v1/dados")
    def dados():
        return {"ok": True}

    @app.post("/v1/acao")
    def acao():
        return {"feito": True}

    @app.post("/webhooks/twilio")
    def webhook():
        return {"recebido": True}

    app.add_middleware(
        ProtecaoLocal, origens=["http://localhost:5173"], checar_host=checar_host
    )
    return TestClient(app)


def test_cli_e_app_do_proprio_pc_passam():
    c = _cliente()
    assert c.get("/v1/dados", headers={"host": "127.0.0.1:8765"}).status_code == 200
    assert c.post("/v1/acao").status_code == 200  # sem Origin: CLI, lançador
    mesma = {"host": "127.0.0.1:8765", "origin": "http://127.0.0.1:8765"}
    assert c.post("/v1/acao", headers=mesma).status_code == 200
    dev = {"host": "127.0.0.1:8000", "origin": "http://localhost:5173"}
    assert c.post("/v1/acao", headers=dev).status_code == 200


def test_dns_rebinding_barrado_pelo_host():
    c = _cliente()
    r = c.get("/v1/dados", headers={"host": "ataque.exemplo.com:8765"})
    assert r.status_code == 403 and "endereço" in r.json()["detail"]


def test_csrf_de_outro_site_barrado():
    c = _cliente()
    for origem in ("https://site-malicioso.com", "null", "http://127.0.0.1:9999"):
        r = c.post("/v1/acao", headers={"host": "127.0.0.1:8765", "origin": origem})
        assert r.status_code == 403, origem
    sem_origem = {"host": "127.0.0.1:8765", "sec-fetch-site": "cross-site"}
    assert c.post("/v1/acao", headers=sem_origem).status_code == 403


def test_leitura_de_outro_site_fica_com_o_cors():
    # GET de outra origem passa aqui; quem impede o site de LER é o CORS.
    c = _cliente()
    r = c.get(
        "/v1/dados", headers={"host": "127.0.0.1:8765", "origin": "https://x.com"}
    )
    assert r.status_code == 200


def test_webhooks_ficam_livres():
    c = _cliente()
    r = c.post("/webhooks/twilio", headers={"host": "abc.trycloudflare.com"})
    assert r.status_code == 200


def test_servidor_aberto_para_a_rede_nao_confere_host():
    c = _cliente(checar_host=False)
    assert c.get("/v1/dados", headers={"host": "192.168.0.10:8000"}).status_code == 200
    r = c.post(
        "/v1/acao", headers={"host": "192.168.0.10:8000", "origin": "https://x.com"}
    )
    assert r.status_code == 403
