"""Pacotes: os prontos, prévia e permissões, instalar, atualizar, remover e exportar."""

from __future__ import annotations

import json
import sys

import pytest

from nicx.assistentes import armazenamento as assistentes
from nicx.extensoes import habilidades, mcp, pacotes, pacotes_prontos
from nicx.rotinas import armazenamento as rotinas


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(habilidades, "pasta", lambda: tmp_path / "home" / "skills")
    return tmp_path / "home"


def _importado(**extra) -> dict:
    dados = {
        "formato": 1,
        "id": "meu-pacote",
        "nome": "Meu pacote",
        "assistentes": [
            {"nome": "Ajudante", "instrucoes": "Ajude.", "ferramentas": ["*"]}
        ],
        "rotinas": [],
        "habilidades": [
            {
                "nome": "dica",
                "titulo": "Dica",
                "descricao": "Dá dicas.",
                "instrucoes": "Dê dicas.",
            }
        ],
        "mcp": [
            {
                "nome": "falso",
                "comando": sys.executable,
                "args": ["-c", "pass"],
                "env": {"CHAVE": ""},
            }
        ],
    }
    dados.update(extra)
    return dados


@pytest.mark.parametrize("idioma", ["pt-BR", "en", "fr"])
def test_prontos_sao_validos(idioma):
    lista = pacotes_prontos.prontos(idioma)
    assert {p["id"] for p in lista} == set(pacotes_prontos.IDS)
    for p in lista:
        previa = pacotes.previa(pacotes.ler(json.dumps(p)))
        assert previa["problemas"] == [], (p["id"], previa["problemas"])
        assert previa["permissoes"]["comandos"] == []  # prontos não rodam programas
        assert previa["itens"]["assistentes"] and previa["itens"]["habilidades"]


def test_instalar_pronto_atualizar_e_remover():
    pacote = pacotes_prontos.pronto("professor", "pt-BR")
    resultado = pacotes.instalar(pacote)
    assert resultado["pulados"] == []
    nomes = {a.nome for a in assistentes.listar()}
    assert nomes == {"Planejador de aulas", "Corretor de redações"}
    assert {r.nome for r in rotinas.listar()} == {"Hora de corrigir"}
    origem = {h.nome: h.origem for h in habilidades.listar()}
    assert origem == {
        "plano-de-aula": "pacote:professor",
        "rubrica-de-avaliacao": "pacote:professor",
    }
    pacotes.instalar(pacote)  # de novo: atualiza, sem duplicar
    assert len(assistentes.listar()) == 2 and len(habilidades.listar()) == 2
    assert pacotes.previa(pacote)["instalado"]
    assert pacotes.desinstalar("professor")
    assert assistentes.listar() == [] and rotinas.listar() == []
    assert habilidades.listar() == [] and pacotes.instalados() == []
    assert not pacotes.desinstalar("professor")


def test_nome_repetido_ganha_numero():
    from nicx.assistentes.modelo import Assistente

    assistentes.criar(Assistente(nome="Tutor de estudos", instrucoes="Meu."))
    pacotes.instalar(pacotes_prontos.pronto("estudante", "pt-BR"))
    assert {a.nome for a in assistentes.listar()} == {
        "Tutor de estudos",
        "Tutor de estudos 2",
    }
    pacotes.desinstalar("estudante")
    assert [a.nome for a in assistentes.listar()] == ["Tutor de estudos"]  # o seu fica


def test_mcp_so_entra_se_marcar_e_desligado_sem_segredo():
    pacote = pacotes.ler(json.dumps(_importado()))
    previa = pacotes.previa(pacote)
    assert previa["permissoes"]["comandos"] == [f"{sys.executable} -c pass"]
    assert previa["permissoes"]["segredos"] == ["CHAVE"]
    assert previa["permissoes"]["todas_as_ferramentas"]
    resultado = pacotes.instalar(pacote)
    assert mcp.listar() == [] and any("não marcado" in p for p in resultado["pulados"])
    pacotes.instalar(pacote, com_mcp=True)
    (servidor,) = mcp.listar()
    assert servidor.pacote == "meu-pacote" and not servidor.ativo
    pacotes.desinstalar("meu-pacote")
    assert mcp.listar() == []


@pytest.mark.parametrize("pedida", ["livre", "sempre"])
def test_pacote_nao_escolhe_a_confianca_do_servidor(pedida):
    dados = _importado()
    dados["mcp"][0]["confianca"] = pedida
    pacote = pacotes.ler(json.dumps(dados))
    assert pacotes.previa(pacote)["permissoes"]["mcp_confirma"] is True
    pacotes.instalar(pacote, com_mcp=True)
    (servidor,) = mcp.listar()
    assert servidor.confianca == "perguntar"


def test_backup_do_usuario_volta_com_a_confianca_que_ele_tinha():
    dados = _importado()
    dados["mcp"][0]["confianca"] = "livre"
    pacote = pacotes.ler(json.dumps(dados))
    pacotes.instalar(pacote, com_mcp=True, pular_existentes=True)
    (servidor,) = mcp.listar()
    assert servidor.confianca == "livre"


@pytest.mark.parametrize(
    "texto",
    [
        "não é json",
        json.dumps({"formato": 2, "id": "x", "nome": "X"}),
        json.dumps({"formato": 1, "id": "Com Espaço", "nome": "X"}),
        json.dumps({"formato": 1, "id": "x", "nome": ""}),
        json.dumps({"formato": 1, "id": "x", "nome": "X", "rotinas": "nada"}),
    ],
)
def test_ler_recusa(texto):
    with pytest.raises(pacotes.PacoteInvalido):
        pacotes.ler(texto)


def test_previa_mostra_itens_com_problema():
    ruim = _importado(
        rotinas=[{"nome": "Desligar", "passos": [{"kind": "power", "op": "off"}]}]
    )
    problemas = pacotes.previa(pacotes.ler(json.dumps(ruim)))["problemas"]
    assert any("não permitidos" in p for p in problemas)
    resultado = pacotes.instalar(pacotes.ler(json.dumps(ruim)))
    assert rotinas.listar() == [] and any("Desligar" in p for p in resultado["pulados"])


def test_exportar_sem_segredos_e_reinstalar():
    pacotes.instalar(pacotes_prontos.pronto("escritorio", "pt-BR"))
    s = mcp.criar(
        mcp.Servidor.de_dict(
            {"nome": "gh", "comando": "npx", "args": ["x"], "env": {"TOKEN": "segredo"}}
        )
    )
    s_http = mcp.criar(
        mcp.Servidor.de_dict(
            {"nome": "web", "tipo": "http", "url": "https://x.y", "token": "t"}
        )
    )
    a = assistentes.listar()[0]
    exportado = pacotes.exportar(
        "meu-escritorio",
        "Meu escritório",
        assistentes_ids=[a.id],
        habilidades_nomes=["ata-de-reuniao"],
        mcp_ids=[s.id, s_http.id],
    )
    texto = json.dumps(exportado, ensure_ascii=False)
    assert "segredo" not in texto and '"t"' not in texto
    pacotes.desinstalar("escritorio")
    for servidor in mcp.listar():
        mcp.apagar(servidor.id)
    lido = pacotes.ler(texto)
    pacotes.instalar(lido, com_mcp=True)
    assert [x.nome for x in assistentes.listar()] == [a.nome]
    assert habilidades.obter("ata-de-reuniao") is not None
    assert {x.nome: x.ativo for x in mcp.listar()} == {"gh": False, "web": False}
    with pytest.raises(pacotes.PacoteInvalido):
        pacotes.exportar("vazio", "Vazio")


def test_rotas():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.extensoes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    dados = client.get("/v1/extensoes/pacotes", params={"idioma": "en"}).json()
    assert {p["id"] for p in dados["prontos"]} == set(pacotes_prontos.IDS)
    assert dados["instalados"] == []
    feito = client.post(
        "/v1/extensoes/pacotes/instalar", json={"pronto": "programador"}
    )
    assert feito.status_code == 200 and feito.json()["instalado"]["id"] == "programador"
    assert (
        client.post("/v1/extensoes/pacotes/instalar", json={"pronto": "x"}).status_code
        == 404
    )
    conteudo = json.dumps(_importado())
    previa = client.post(
        "/v1/extensoes/pacotes/previa", json={"conteudo": conteudo}
    ).json()
    assert previa["permissoes"]["segredos"] == ["CHAVE"]
    resposta = client.post("/v1/extensoes/pacotes/previa", json={"conteudo": "{}"})
    assert resposta.status_code == 400
    corpo = {"id": "x", "nome": "X", "habilidades": ["revisao-de-codigo"]}
    exportado = client.post("/v1/extensoes/pacotes/exportar", json=corpo).json()
    assert exportado["habilidades"][0]["nome"] == "revisao-de-codigo"
    assert client.delete("/v1/extensoes/pacotes/programador").json() == {"ok": True}
    assert client.delete("/v1/extensoes/pacotes/programador").status_code == 404
