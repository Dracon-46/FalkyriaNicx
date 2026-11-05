"""Atualizações: arquivo de versões assinado, download conferido, instalar por cima."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from nicx.atualizacao import manifesto, servico
from nicx.extensoes import assinatura


@pytest.fixture(autouse=True)
def casa(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    (tmp_path / "home").mkdir()
    with servico._LOCK:
        servico._DOWNLOAD.update(
            baixando=False, progresso=0.0, erro=None, arquivo=None, versao=None
        )
    monkeypatch.setattr(servico, "versao_atual", lambda: "0.2.1")
    return tmp_path


@pytest.fixture
def chave(tmp_path, monkeypatch):
    pasta = tmp_path / "chave"
    ident, publica = assinatura.gerar_chave(pasta)
    monkeypatch.setitem(assinatura.CHAVES_CONFIAVEIS, ident, publica)
    return pasta


def _instalador(tmp_path, conteudo=b"MZ instalador de teste " * 100):
    arq = tmp_path / "NicxSetup.exe"
    arq.write_bytes(conteudo)
    return arq


def _assinado(tmp_path, chave, versao="0.2.2", **mudar):
    conteudo = manifesto.montar(
        versao, _instalador(tmp_path), publicado_em="2026-11-06"
    )
    conteudo.update(mudar)
    return manifesto.assinar(conteudo, chave)


def _cliente(rotas: dict[str, bytes | int]):
    pedidos: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(str(request.url))
        resposta = rotas.get(str(request.url), 404)
        if isinstance(resposta, int):
            return httpx.Response(resposta)
        return httpx.Response(200, content=resposta)

    cliente = httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    cliente.pedidos = pedidos  # type: ignore[attr-defined]
    return cliente


# ------------------------------------------------------------------ manifesto


def test_manifesto_assinado_confere(tmp_path, chave):
    lido = manifesto.ler(_assinado(tmp_path, chave))
    assert lido["versao"] == "0.2.2"
    win = lido["windows"]
    assert win["url"] == f"{manifesto.PREFIXO_DOWNLOAD}v0.2.2/NicxSetup.exe"
    assert (
        win["sha256"] == hashlib.sha256(_instalador(tmp_path).read_bytes()).hexdigest()
    )
    assert lido["novidades"][0]["versao"] == "0.2.1"


def test_manifesto_mexido_e_recusado(tmp_path, chave):
    assinado = _assinado(tmp_path, chave)
    conteudo = json.loads(assinado["conteudo"])
    conteudo["windows"]["sha256"] = "0" * 64
    mexido = dict(assinado, conteudo=assinatura.canonico(conteudo))
    with pytest.raises(manifesto.ManifestoInvalido, match="assinatura"):
        manifesto.ler(mexido)
    # Mesmo recalculando o sha256 do texto, a assinatura não bate.
    mexido["sha256"] = assinatura.impressao(mexido["conteudo"])
    with pytest.raises(manifesto.ManifestoInvalido, match="assinatura"):
        manifesto.ler(mexido)


def test_pacote_da_loja_nao_passa_por_atualizacao(chave):
    pacote = manifesto.assinar({"formato": 1, "id": "x", "nome": "X"}, chave)
    with pytest.raises(
        manifesto.ManifestoInvalido, match="não é um arquivo de versões"
    ):
        manifesto.ler(pacote)


def test_instalador_fora_das_releases_e_recusado(tmp_path, chave):
    win = manifesto.montar("0.2.2", _instalador(tmp_path))["windows"]
    win["url"] = "https://exemplo.com/NicxSetup.exe"
    with pytest.raises(manifesto.ManifestoInvalido, match="instalador"):
        manifesto.ler(_assinado(tmp_path, chave, windows=win))


def test_chave_desconhecida_e_recusada(tmp_path):
    outra = tmp_path / "outra"
    assinatura.gerar_chave(outra)  # não está entre as confiáveis
    conteudo = manifesto.montar("0.2.2", _instalador(tmp_path))
    with pytest.raises(manifesto.ManifestoInvalido, match="não conhece"):
        manifesto.ler(manifesto.assinar(conteudo, outra))


@pytest.mark.parametrize(
    ("nova", "atual", "esperado"),
    [
        ("0.2.2", "0.2.1", True),
        ("0.10.0", "0.9.9", True),
        ("0.2.1", "0.2.1", False),
        ("0.2.0", "0.2.1", False),
        ("0.2.2", "0.2.2.dev3+g1234", False),
        ("0.2.3", "0.2.2.dev3+g1234", True),
    ],
)
def test_mais_nova(nova, atual, esperado):
    assert manifesto.mais_nova(nova, atual) is esperado


# ------------------------------------------------------------------- serviço


def test_procurar_acha_versao_nova_e_guarda(tmp_path, chave):
    corpo = json.dumps(_assinado(tmp_path, chave)).encode()
    cliente = _cliente({manifesto.URL_PADRAO: corpo})
    estado = servico.verificar(cliente=cliente)
    assert estado["ha_nova"] and estado["ultima"]["versao"] == "0.2.2"
    assert estado["erro"] is None and estado["verificado_em"]
    # Guardado e conferido de novo ao ler.
    assert servico.estado()["ha_nova"]


def test_sem_internet_nao_quebra(tmp_path):
    def falha(request):
        raise httpx.ConnectError("sem rede")

    cliente = httpx.Client(transport=httpx.MockTransport(falha))
    estado = servico.verificar(cliente=cliente)
    assert estado["ha_nova"] is False and "conexão" in estado["erro"]


def test_arquivo_de_versoes_falso_nao_vira_atualizacao(tmp_path, chave):
    assinado = _assinado(tmp_path, chave)
    assinado["assinatura"] = assinado["assinatura"][::-1]
    cliente = _cliente({manifesto.URL_PADRAO: json.dumps(assinado).encode()})
    estado = servico.verificar(cliente=cliente)
    assert estado["ha_nova"] is False and "assinatura" in estado["erro"]


def test_baixar_confere_e_instalar_abre_o_instalador(tmp_path, chave, monkeypatch):
    monkeypatch.setattr(servico, "instalacao", lambda: "windows")
    assinado = _assinado(tmp_path, chave)
    win = json.loads(assinado["conteudo"])["windows"]
    cliente = _cliente(
        {
            manifesto.URL_PADRAO: json.dumps(assinado).encode(),
            win["url"]: _instalador(tmp_path).read_bytes(),
        }
    )
    servico.verificar(cliente=cliente)
    estado = servico.baixar(esperar=True, cliente=cliente)
    estado = servico.estado()
    assert estado["pronto_para_instalar"] and estado["progresso"] == 1.0
    aberto = {}
    resultado = servico.instalar(abrir=lambda exe, log: aberto.update(exe=exe, log=log))
    assert resultado == {"ok": True, "versao": "0.2.2"}
    assert aberto["exe"].name == "NicxSetup-0.2.2.exe"
    assert aberto["exe"].parent == servico.pasta_downloads()


def test_instalador_diferente_do_assinado_nao_instala(tmp_path, chave, monkeypatch):
    monkeypatch.setattr(servico, "instalacao", lambda: "windows")
    assinado = _assinado(tmp_path, chave)
    win = json.loads(assinado["conteudo"])["windows"]
    falso = b"X" * win["tamanho"]
    cliente = _cliente(
        {manifesto.URL_PADRAO: json.dumps(assinado).encode(), win["url"]: falso}
    )
    servico.verificar(cliente=cliente)
    servico.baixar(esperar=True, cliente=cliente)
    estado = servico.estado()
    assert not estado["pronto_para_instalar"]
    assert "não é o que a Falkyria publicou" in estado["erro_download"]
    assert not list(servico.pasta_downloads().glob("*.exe"))
    with pytest.raises(servico.AtualizacaoErro, match="baixe"):
        servico.instalar(abrir=lambda *a: None)


def test_instalador_trocado_depois_do_download_nao_abre(tmp_path, chave, monkeypatch):
    monkeypatch.setattr(servico, "instalacao", lambda: "windows")
    assinado = _assinado(tmp_path, chave)
    win = json.loads(assinado["conteudo"])["windows"]
    cliente = _cliente(
        {
            manifesto.URL_PADRAO: json.dumps(assinado).encode(),
            win["url"]: _instalador(tmp_path).read_bytes(),
        }
    )
    servico.verificar(cliente=cliente)
    servico.baixar(esperar=True, cliente=cliente)
    baixado = next(servico.pasta_downloads().glob("*.exe"))
    baixado.write_bytes(b"outro programa")
    with pytest.raises(servico.AtualizacaoErro, match="mudou"):
        servico.instalar(abrir=lambda *a: pytest.fail("não podia abrir"))


def test_fora_do_instalador_do_windows_nao_baixa(tmp_path, chave, monkeypatch):
    monkeypatch.setattr(servico, "instalacao", lambda: "git")
    cliente = _cliente(
        {manifesto.URL_PADRAO: json.dumps(_assinado(tmp_path, chave)).encode()}
    )
    estado = servico.verificar(cliente=cliente)
    assert estado["ha_nova"] and estado["pode_instalar"] is False
    assert estado["comando_git"] == "nicx self-update"
    with pytest.raises(servico.AtualizacaoErro):
        servico.baixar()


def test_sem_versao_nova_nao_baixa(tmp_path, chave, monkeypatch):
    monkeypatch.setattr(servico, "instalacao", lambda: "windows")
    cliente = _cliente(
        {
            manifesto.URL_PADRAO: json.dumps(
                _assinado(tmp_path, chave, versao="0.2.1")
            ).encode()
        }
    )
    assert servico.verificar(cliente=cliente)["ha_nova"] is False
    with pytest.raises(servico.AtualizacaoErro, match="não há versão nova"):
        servico.baixar()


def test_verificacao_diaria_desligada_nos_testes(monkeypatch):
    monkeypatch.setenv("NICX_NO_UPDATE_CHECK", "1")
    servico.ligar_verificacao_diaria()
    assert servico._THREAD is None or not servico._THREAD.is_alive()


def test_precisa_verificar_uma_vez_por_dia(tmp_path):
    import time

    assert servico._precisa_verificar(time.time())
    servico._guardar({"verificado_em": "2026-11-05T10:00:00+00:00"})
    from datetime import datetime

    base = datetime.fromisoformat("2026-11-05T10:00:00+00:00").timestamp()
    assert not servico._precisa_verificar(base + 3600)
    assert servico._precisa_verificar(base + 25 * 3600)


# -------------------------------------------------------------------- rotas


def test_rotas(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.nucleo.config import NicxConfig
    from nicx.servidor.rotas.atualizacao import router

    caminho = tmp_path / "home" / "config.toml"
    caminho.write_text('[engine]\ndefault = "ollama"\n', encoding="utf-8")
    cfg = NicxConfig()
    cfg._config_path = caminho
    app = FastAPI()
    app.include_router(router)
    app.state.config = cfg
    http = TestClient(app)
    estado = http.get("/v1/atualizacao").json()
    assert estado["versao_atual"] == "0.2.1" and estado["automatica"] is True
    assert estado["novidades"][0]["versao"]  # as que vieram com o Nicx
    desligado = http.put("/v1/atualizacao/config", json={"automatica": False}).json()
    assert desligado["automatica"] is False
    assert "automatica = false" in caminho.read_text(encoding="utf-8")
    assert (
        http.put("/v1/atualizacao/config", json={"automatica": "sim"}).status_code
        == 422
    )
    assert http.post("/v1/atualizacao/instalar").status_code == 409
