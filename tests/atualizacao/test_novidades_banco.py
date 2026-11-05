"""Novidades vêm da tabela nicx_novidades e vão assinadas no arquivo de versões."""

from __future__ import annotations

import json

import httpx
import pytest
from click.testing import CliRunner

from nicx.atualizacao import banco, manifesto
from nicx.extensoes import assinatura
from nicx.nucleo.config import NicxConfig


def _config():
    cfg = NicxConfig()
    cfg.analytics.host = "https://banco.exemplo"
    cfg.analytics.key = "chave-publica"
    return cfg


def _cliente(linhas, status=200):
    pedidos = []

    def handler(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        return httpx.Response(status, json=linhas)

    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    cliente.pedidos = pedidos  # type: ignore[attr-defined]
    return cliente


LINHAS = [
    {"versao": "0.2.0", "data": "2026-11-04", "titulo": "B", "itens": ["b"]},
    {"versao": "0.10.0", "data": "2026-12-01", "titulo": "C", "itens": ["c", " "]},
    {"versao": "0.2.1", "data": "2026-11-05", "titulo": "A", "itens": ["a"]},
    {"versao": "lixo", "titulo": "X", "itens": ["x"]},
]


def test_busca_so_o_publicado_e_ordena_por_versao():
    cliente = _cliente(LINHAS)
    novidades = banco.buscar(_config(), cliente=cliente)
    assert [n["versao"] for n in novidades] == ["0.10.0", "0.2.1", "0.2.0"]
    assert novidades[0]["itens"] == ["c"]  # item em branco fica de fora
    pedido = cliente.pedidos[0]
    assert pedido.url.path == "/rest/v1/nicx_novidades"
    assert pedido.url.params["publicado"] == "eq.true"
    assert pedido.headers["apikey"] == "chave-publica"


def test_banco_fora_do_ar_avisa():
    with pytest.raises(banco.NovidadesIndisponiveis):
        banco.buscar(_config(), cliente=_cliente({"message": "x"}, status=500))


def test_sem_destino_avisa():
    cfg = NicxConfig()
    cfg.analytics.host = ""
    with pytest.raises(banco.NovidadesIndisponiveis, match="Supabase"):
        banco.buscar(cfg)


@pytest.fixture
def chave(tmp_path, monkeypatch):
    pasta = tmp_path / "chave"
    ident, publica = assinatura.gerar_chave(pasta)
    monkeypatch.setitem(assinatura.CHAVES_CONFIAVEIS, ident, publica)
    monkeypatch.setattr(assinatura, "pasta_da_chave", lambda: pasta)
    return pasta


def _rodar(args, instalador):
    from nicx.comandos.instalacao.atualizacao import atualizacao

    return CliRunner().invoke(atualizacao, ["assinar", str(instalador), *args])


def test_assinar_usa_as_novidades_do_banco(tmp_path, chave, monkeypatch):
    instalador = tmp_path / "NicxSetup.exe"
    instalador.write_bytes(b"MZ" * 100)
    lista = banco_ordenado()
    monkeypatch.setattr(banco, "buscar", lambda *a, **k: lista)
    resultado = _rodar(["--versao", "0.10.0"], instalador)
    assert resultado.exit_code == 0, resultado.output
    assinado = json.loads(
        (tmp_path / "nicx-atualizacao.json").read_text(encoding="utf-8")
    )
    conteudo = manifesto.ler(assinado)
    assert conteudo["novidades"][0] == {
        "versao": "0.10.0",
        "data": "2026-12-01",
        "titulo": "C",
        "itens": ["c"],
    }


def banco_ordenado():
    return banco.buscar(_config(), cliente=_cliente(LINHAS))


def test_assinar_recusa_versao_sem_novidades_no_banco(tmp_path, chave, monkeypatch):
    instalador = tmp_path / "NicxSetup.exe"
    instalador.write_bytes(b"MZ" * 100)
    lista = banco_ordenado()
    monkeypatch.setattr(banco, "buscar", lambda *a, **k: lista)
    resultado = _rodar(["--versao", "0.11.0"], instalador)
    assert resultado.exit_code == 1
    assert "nicx_novidades" in resultado.output
    assert not (tmp_path / "nicx-atualizacao.json").exists()


def test_assinar_sem_banco_usa_a_lista_do_app(tmp_path, chave):
    from nicx.atualizacao.novidades import NOVIDADES

    instalador = tmp_path / "NicxSetup.exe"
    instalador.write_bytes(b"MZ" * 100)
    resultado = _rodar(["--versao", NOVIDADES[0]["versao"], "--sem-banco"], instalador)
    assert resultado.exit_code == 0, resultado.output
