"""Servidores MCP do usuário: cadastro, segredos, carga real, risco, recarga e rotas."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from nicx.extensoes import mcp

FALSO = str(Path(__file__).with_name("servidor_mcp_falso.py"))


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    yield tmp_path / "home"
    for c in mcp._POOL["clients"]:
        c.close()
    mcp._POOL.update(tools=[], clients=[])
    mcp._FERRAMENTAS.clear()
    mcp._SITUACAO.clear()


def _falso(**campos) -> mcp.Servidor:
    dados = {
        "nome": "falso",
        "comando": sys.executable,
        "args": [FALSO],
        "env": {"NICX_TESTE": "segredo-123"},
    }
    dados.update(campos)
    return mcp.Servidor.de_dict(dados)


def test_validacao():
    with pytest.raises(mcp.ServidorInvalido):
        mcp.criar(_falso(nome="nome/com/barra"))
    with pytest.raises(mcp.ServidorInvalido):
        mcp.criar(_falso(comando=""))
    with pytest.raises(mcp.ServidorInvalido):
        mcp.criar(
            mcp.Servidor.de_dict({"nome": "web", "tipo": "http", "url": "ftp://x"})
        )
    with pytest.raises(mcp.ServidorInvalido):
        mcp.criar(_falso(confianca="total"))
    mcp.criar(_falso())
    with pytest.raises(mcp.ServidorInvalido):
        mcp.criar(_falso(nome="FALSO"))


def test_segredos_nao_saem_e_a_mascara_mantem_o_valor():
    s = mcp.criar(_falso(token="tok"))
    publico = mcp.publico(s)
    assert publico["env"] == {"NICX_TESTE": mcp.MASCARA}
    assert publico["token"] == mcp.MASCARA
    novo = mcp.Servidor.de_dict({**publico, "descricao": "mudou"})
    mcp.atualizar(s.id, novo)
    guardado = mcp.obter(s.id)
    assert guardado.env == {"NICX_TESTE": "segredo-123"} and guardado.token == "tok"
    assert guardado.descricao == "mudou"


def test_historico_sem_segredos():
    from nicx.historico.registro import registro

    mcp.criar(_falso())
    linhas = [a.para_dict() for a in registro().listar()]
    assert linhas[0]["tipo"] == "extensao" and "falso" in linhas[0]["titulo"]
    assert "segredo-123" not in repr(linhas)


def test_testar_liga_lista_e_desliga():
    resultado = mcp.testar(_falso())
    assert resultado["ok"], resultado
    assert {f["nome"] for f in resultado["ferramentas"]} == {
        "eco_falkyria",
        "ambiente_falkyria",
    }


def test_testar_comando_que_nao_existe():
    resultado = mcp.testar(_falso(comando="programa-que-nao-existe-nicx"))
    assert not resultado["ok"] and resultado["erro"]


def test_carregar_usa_env_e_risco_da_confianca():
    mcp.criar(_falso(confianca="sempre"))
    mcp.criar(_falso(nome="desligado", ativo=False))
    tools, clients = mcp.carregar()
    assert len(clients) == 1
    nomes = {t.spec.name: t for t in tools}
    assert set(nomes) == {"eco_falkyria", "ambiente_falkyria"}
    assert nomes["ambiente_falkyria"].execute().content == "segredo-123"
    assert mcp.risco_de("eco_falkyria") == "alto"
    assert mcp.risco_de("file_read") is None
    from nicx.historico.autonomia import risco_ferramenta

    assert risco_ferramenta("eco_falkyria") == "alto"
    estados = {v["estado"] for v in mcp.situacao().values()}
    assert estados == {"ligado", "desligado"}


def test_roteamento_conhece_as_extensoes():
    from nicx.acoes.roteamento import needs_tools

    assert not needs_tools("me fala do falkyria")
    mcp.criar(_falso())
    mcp.carregar()
    assert needs_tools("me fala do falkyria")


def test_recarregar_troca_as_ferramentas_do_agente():
    from nicx.ferramentas._stubs import ToolExecutor

    fixa = MagicMock()
    fixa.spec.name = "web_search"
    agente = SimpleNamespace(_tools=[fixa], _model="m")
    agente._executor = ToolExecutor(agente._tools)
    estado = SimpleNamespace(agent=agente, mcp_tools=[], _mcp_clients=[])
    estado._mcp_clients_lock = __import__("threading").Lock()

    s = mcp.criar(_falso())
    mcp.recarregar(estado)
    assert {t.spec.name for t in agente._tools} == {
        "web_search",
        "eco_falkyria",
        "ambiente_falkyria",
    }
    assert "eco_falkyria" in agente._executor._tools
    assert len(estado._mcp_clients) == 1

    mcp.apagar(s.id)
    mcp.recarregar(estado)
    assert [t.spec.name for t in agente._tools] == ["web_search"]
    assert estado._mcp_clients == [] and estado.mcp_tools == []


def test_rotas():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.extensoes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    dados = client.get("/v1/extensoes/mcp").json()
    assert dados["servidores"] == [] and {"filesystem", "github"} <= {
        m["chave"] for m in dados["catalogo"]
    }
    corpo = {"nome": "falso", "comando": sys.executable, "args": [FALSO]}
    corpo["env"] = {"NICX_TESTE": "x"}
    criado = client.post("/v1/extensoes/mcp", json=corpo).json()
    assert criado["env"] == {"NICX_TESTE": mcp.MASCARA}
    assert client.post("/v1/extensoes/mcp", json=corpo).status_code == 400
    teste = client.post(
        "/v1/extensoes/mcp/testar",
        json={**corpo, "env": criado["env"], "id": criado["id"]},
    ).json()
    assert teste["ok"]
    assert client.put("/v1/extensoes/mcp/x", json=corpo).status_code == 404
    assert client.delete(f"/v1/extensoes/mcp/{criado['id']}").json() == {"ok": True}
