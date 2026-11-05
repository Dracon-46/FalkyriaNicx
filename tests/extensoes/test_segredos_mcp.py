"""Chave escrita no comando ou no endereço de um servidor MCP não sai no pacote."""

from __future__ import annotations

import json
import sys

import pytest

from nicx.extensoes import mcp, pacotes, segredos_mcp


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path))
    return tmp_path


@pytest.mark.parametrize(
    ("args", "esperado"),
    [
        (["--api-key=abc123", "--port=8080"], ["--api-key=", "--port=8080"]),
        (["--token", "abc123", "server.js"], ["--token", "", "server.js"]),
        (["-e", "GITHUB_TOKEN=ghp_x", "img"], ["-e", "GITHUB_TOKEN=", "img"]),
        (["sk-abcdefghijklmnop"], [""]),
        (["ghp_abcdefghijklmnop1234"], [""]),
        # Não são segredos: ficam como estão.
        (["--author", "Ana", "--keyboard=br"], ["--author", "Ana", "--keyboard=br"]),
        (["--no-auth", "server.py"], ["--no-auth", "server.py"]),
        (
            ["-y", "@modelcontextprotocol/server-filesystem", "C:/docs"],
            ["-y", "@modelcontextprotocol/server-filesystem", "C:/docs"],
        ),
        (["--token", "--verbose"], ["--token", "--verbose"]),
    ],
)
def test_limpar_args(args, esperado):
    assert segredos_mcp.limpar_args(args) == esperado


@pytest.mark.parametrize(
    ("url", "esperado"),
    [
        ("https://api.exemplo.com/mcp", "https://api.exemplo.com/mcp"),
        ("https://u:senha@api.exemplo.com/mcp", "https://api.exemplo.com/mcp"),
        (
            "https://api.exemplo.com/mcp?api_key=abc&region=br",
            "https://api.exemplo.com/mcp?api_key=&region=br",
        ),
    ],
)
def test_limpar_url(url, esperado):
    assert segredos_mcp.limpar_url(url) == esperado


def test_faltando_diz_o_que_preencher():
    args = segredos_mcp.limpar_args(
        ["--api-key=abc", "--token", "x", "sk-abcdefghijklmnop"]
    )
    assert segredos_mcp.faltando(args) == ["--api-key", "--token", "argumento 4"]
    assert segredos_mcp.faltando(["--port=1"]) == []
    url = segredos_mcp.limpar_url("https://h/mcp?token=abc")
    assert segredos_mcp.faltando([], url) == ["token"]


def test_exportar_nao_leva_chave_dos_argumentos_nem_do_endereco():
    local = mcp.criar(
        mcp.Servidor.de_dict(
            {
                "nome": "local",
                "comando": sys.executable,
                "args": ["-c", "pass", "--api-key=segredo123"],
            }
        )
    )
    remoto = mcp.criar(
        mcp.Servidor.de_dict(
            {"nome": "remoto", "url": "https://ana:senha@h.exemplo/mcp?key=segredo456"}
        )
    )
    pacote = pacotes.exportar("meu", "Meu", mcp_ids=[local.id, remoto.id])
    texto = json.dumps(pacote)
    assert "segredo123" not in texto
    assert "segredo456" not in texto
    assert "senha" not in texto
    previa = pacotes.previa(pacotes.ler(texto))
    assert "--api-key" in previa["permissoes"]["segredos"]
    assert "key" in previa["permissoes"]["segredos"]


def test_servidor_com_chave_em_branco_entra_desligado():
    dados = {
        "formato": 1,
        "id": "com-chave",
        "nome": "Com chave",
        "mcp": [
            {
                "nome": "local",
                "comando": sys.executable,
                "args": ["-c", "pass", "--token="],
            }
        ],
    }
    pacotes.instalar(pacotes.ler(json.dumps(dados)), com_mcp=True)
    (servidor,) = mcp.listar()
    assert servidor.ativo is False


def test_previa_nao_mostra_a_chave_de_um_pacote_recebido():
    dados = {
        "formato": 1,
        "id": "recebido",
        "nome": "Recebido",
        "mcp": [
            {
                "nome": "local",
                "comando": sys.executable,
                "args": ["--api-key=vazou123"],
            }
        ],
    }
    previa = pacotes.previa(pacotes.ler(json.dumps(dados)))
    assert "vazou123" not in json.dumps(previa["permissoes"])
