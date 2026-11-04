"""Loja: assinatura Ed25519, conferência no app, catálogo, instalação e o CLI."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
from click.testing import CliRunner

from nicx.extensoes import assinatura, habilidades, loja, pacotes, pacotes_prontos


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(habilidades, "pasta", lambda: tmp_path / "home" / "skills")
    monkeypatch.setattr(assinatura, "pasta_da_chave", lambda: tmp_path / "chave")
    return tmp_path


@pytest.fixture
def chave(monkeypatch):
    ident, publica = assinatura.gerar_chave()
    monkeypatch.setitem(assinatura.CHAVES_CONFIAVEIS, ident, publica)
    return ident


def _pacote(versao="1.0.0") -> dict:
    p = pacotes_prontos.pronto("estudante", "pt-BR")
    p = {k: v for k, v in p.items() if k != "pronto"}
    return {**p, "id": "estudo-loja", "nome": "Estudo da loja", "versao": versao}


def test_assinar_e_verificar(chave):
    assinado = assinatura.assinar(_pacote())
    assert assinado["chave"] == chave and assinado["id"] == "estudo-loja"
    assinatura.verificar(
        assinado["conteudo"], assinado["sha256"], assinado["assinatura"], chave
    )
    adulterado = assinado["conteudo"].replace("Tutor", "Golpe")
    with pytest.raises(assinatura.AssinaturaInvalida, match="diferente"):
        assinatura.verificar(
            adulterado, assinado["sha256"], assinado["assinatura"], chave
        )
    falso_sha = assinatura.impressao(adulterado)
    with pytest.raises(assinatura.AssinaturaInvalida, match="não confere"):
        assinatura.verificar(adulterado, falso_sha, assinado["assinatura"], chave)
    with pytest.raises(assinatura.AssinaturaInvalida, match="não conhece"):
        assinatura.verificar(
            assinado["conteudo"], assinado["sha256"], assinado["assinatura"], "0" * 16
        )


def test_chave_nao_sobrescreve(chave):
    with pytest.raises(FileExistsError):
        assinatura.gerar_chave()


def test_chave_da_falkyria_no_app():
    from nicx.extensoes.loja_chaves import CHAVES_CONFIAVEIS

    assert CHAVES_CONFIAVEIS and all(len(k) == 16 for k in CHAVES_CONFIAVEIS)


class _Supabase:
    """Responde como o PostgREST do Supabase, com uma versão assinada."""

    def __init__(self, assinado: dict, publicado_versao: str = "1.0.0"):
        self.assinado = assinado
        self.versao = publicado_versao
        self.contados: list[str] = []

    def get(self, url, params=None, **_k):
        resposta = MagicMock(status_code=200)
        if url.endswith("/nicx_loja_pacotes"):
            item = {
                "id": "estudo-loja",
                "nome": "Estudo da loja",
                "descricao": "",
                "autor": "Falkyria",
                "categoria": "educacao",
                "versao": self.versao,
                "downloads": 3,
                "atualizado_em": "2026-11-04T10:00:00Z",
            }
            if "id" in (params or {}) and params["id"] != "eq.estudo-loja":
                resposta.json.return_value = []
            else:
                resposta.json.return_value = [item]
        else:
            linha = {
                k: self.assinado[k]
                for k in ("conteudo", "sha256", "assinatura", "chave")
            }
            ok = params.get("versao") == f"eq.{self.assinado['versao']}"
            resposta.json.return_value = [linha] if ok else []
        return resposta

    def post(self, url, json=None, **_k):
        self.contados.append(json["p_id"])
        return MagicMock(status_code=204)


@pytest.fixture
def supabase(chave, monkeypatch):
    falso = _Supabase(assinatura.assinar(_pacote()))
    monkeypatch.setattr(httpx, "get", falso.get)
    monkeypatch.setattr(httpx, "post", falso.post)
    return falso


def test_catalogo_e_instalar(supabase):
    (item,) = loja.catalogo()
    assert item["id"] == "estudo-loja" and not item["atualizacao"]
    previa = loja.previa("estudo-loja")
    assert previa["verificado"] and previa["itens"]["assistentes"] == [
        "Tutor de estudos"
    ]
    loja.instalar("estudo-loja")
    assert supabase.contados == ["estudo-loja"]
    (registro,) = pacotes.instalados()
    assert registro["loja"] and registro["versao"] == "1.0.0" and not registro["pronto"]
    supabase.versao = "1.1.0"  # saiu versão nova no catálogo
    assert loja.catalogo()[0]["atualizacao"]


def test_conteudo_adulterado_no_banco_e_recusado(supabase):
    supabase.assinado = {
        **supabase.assinado,
        "conteudo": supabase.assinado["conteudo"][:-1],
    }
    with pytest.raises(loja.LojaErro, match="recusado"):
        loja.instalar("estudo-loja")
    assert pacotes.instalados() == []


def test_pacote_trocado_e_recusado(chave, monkeypatch):
    outro = assinatura.assinar({**_pacote(), "id": "outro"})
    falso = _Supabase({**outro, "versao": "1.0.0"})
    monkeypatch.setattr(httpx, "get", falso.get)
    with pytest.raises(loja.LojaErro, match="não é o anunciado"):
        loja.baixar("estudo-loja")


def test_sem_rede(monkeypatch):
    def falha(*_a, **_k):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "get", falha)
    with pytest.raises(loja.LojaErro, match="sem conexão"):
        loja.catalogo()


def test_cli_assinar_e_verificar(chave, tmp_path):
    from nicx.comandos.recursos.loja import loja as grupo

    arquivo = tmp_path / "estudo.nicx.json"
    arquivo.write_text(json.dumps(_pacote(), ensure_ascii=False), encoding="utf-8")
    saida = CliRunner().invoke(grupo, ["assinar", str(arquivo)])
    assert saida.exit_code == 0, saida.output
    assinado = tmp_path / "estudo-loja-1.0.0.assinado.json"
    dados = json.loads(assinado.read_text(encoding="utf-8"))
    assert dados["permissoes"]["comandos"] == [] and dados["chave"] == chave
    assert CliRunner().invoke(grupo, ["verificar", str(assinado)]).exit_code == 0
    dados["conteudo"] += " "
    assinado.write_text(json.dumps(dados), encoding="utf-8")
    assert CliRunner().invoke(grupo, ["verificar", str(assinado)]).exit_code == 1


def test_cli_recusa_pacote_com_problema(chave, tmp_path):
    from nicx.comandos.recursos.loja import loja as grupo

    ruim = {
        **_pacote(),
        "rotinas": [{"nome": "Desligar", "passos": [{"kind": "power"}]}],
    }
    arquivo = tmp_path / "ruim.json"
    arquivo.write_text(json.dumps(ruim), encoding="utf-8")
    saida = CliRunner().invoke(grupo, ["assinar", str(arquivo)])
    assert saida.exit_code == 1 and "problema" in saida.output


def test_rotas(supabase):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.extensoes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/v1/extensoes/loja").json()["pacotes"][0]["id"] == "estudo-loja"
    assert client.get("/v1/extensoes/loja/estudo-loja").json()["verificado"]
    assert client.get("/v1/extensoes/loja/nao-existe").status_code == 502
    feito = client.post("/v1/extensoes/loja/estudo-loja/instalar", json={})
    assert feito.status_code == 200 and feito.json()["instalado"]["loja"]
