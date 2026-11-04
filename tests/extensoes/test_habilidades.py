"""Habilidades do usuário: criar, ligar/desligar, apagar, importar .zip e o chat."""

from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

import pytest

from nicx.extensoes import habilidades as hab


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    (tmp_path / "home").mkdir()
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(hab, "pasta", lambda: tmp_path / "home" / "skills")
    return tmp_path / "home"


def _ata():
    return hab.salvar(
        "Ata de reunião",
        "Use quando pedirem a ata ou o resumo de uma reunião.",
        "Liste participantes, decisões e próximos passos com responsável e prazo.",
    )


def _zip(arquivos: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for nome, texto in arquivos.items():
            z.writestr(nome, texto)
    return buffer.getvalue()


SKILL = "---\nname: {nome}\ndescription: {desc}\n---\n\nFaça assim.\n"


def test_criar_listar_e_editar():
    h = _ata()
    assert h.nome == "ata-de-reuniao" and h.titulo == "Ata de reunião"
    assert h.editavel and h.ativa and "decisões" in h.instrucoes
    with pytest.raises(hab.HabilidadeInvalida):
        _ata()  # mesmo nome
    hab.salvar(
        "Ata de reunião", "Outra descrição.", "Novo texto.", h.nome, substituir=True
    )
    assert hab.obter(h.nome).instrucoes.strip() == "Novo texto."
    assert [x.nome for x in hab.listar()] == ["ata-de-reuniao"]


@pytest.mark.parametrize(
    ("titulo", "descricao", "instrucoes"),
    [("!!!", "d", "i"), ("Ok", "", "i"), ("Ok", "d", " ")],
)
def test_validacao(titulo, descricao, instrucoes):
    with pytest.raises(hab.HabilidadeInvalida):
        hab.salvar(titulo, descricao, instrucoes)


def test_desligar_e_apagar():
    h = _ata()
    hab.ligar(h.nome, False)
    assert not hab.obter(h.nome).ativa and hab.nomes_ativos() == []
    hab.ligar(h.nome, True)
    assert hab.nomes_ativos() == [h.nome]
    assert hab.apagar(h.nome) and hab.listar() == []
    assert not hab.apagar(h.nome)
    with pytest.raises(KeyError):
        hab.ligar("nao-existe", True)


def test_importar_zip_sem_scripts(home):
    dados = _zip(
        {
            "pacote/planilha/SKILL.md": SKILL.format(
                nome="planilha", desc="Monta planilhas."
            ),
            "pacote/planilha/scripts/roda.py": "print('não deve vir')",
            "pacote/planilha/references/guia.md": "guia",
        }
    )
    (resultado,) = hab.importar_zip(dados)
    assert resultado["ok"] and resultado["nome"] == "planilha"
    h = hab.obter("planilha")
    assert h is not None and h.origem == "importadas"
    assert not (h.pasta / "scripts").exists()


def test_importar_zip_perigoso_pede_confirmacao():
    texto = (
        "---\nname: limpa\ndescription: Limpa coisas.\n"
        "required_capabilities: [shell:execute]\n---\n\nRode comandos.\n"
    )
    (resultado,) = hab.importar_zip(_zip({"limpa/SKILL.md": texto}))
    assert not resultado["ok"] and resultado["pede_confirmacao"]
    assert hab.obter("limpa") is None
    (resultado,) = hab.importar_zip(_zip({"limpa/SKILL.md": texto}), True)
    assert resultado["ok"] and hab.obter("limpa").perigosas == ("shell:execute",)


@pytest.mark.parametrize(
    "arquivos",
    [
        {"../fora/SKILL.md": SKILL.format(nome="x", desc="y")},
        {"nada.txt": "sem skill"},
    ],
)
def test_zip_recusado(arquivos):
    with pytest.raises(hab.HabilidadeInvalida):
        hab.importar_zip(_zip(arquivos))
    with pytest.raises(hab.HabilidadeInvalida):
        hab.importar_zip(b"isto nao e zip")


def test_github_so_aceita_repositorio():
    with pytest.raises(hab.HabilidadeInvalida):
        hab.importar_github("https://exemplo.com/x")


def test_liga_no_agente_e_vira_ferramenta():
    from unittest.mock import MagicMock

    from nicx.ferramentas._stubs import ToolExecutor

    fixa = MagicMock()
    fixa.spec.name = "web_search"
    agente = SimpleNamespace(_tools=[fixa], _bus=None)
    agente._executor = ToolExecutor(agente._tools)
    h = _ata()
    assert hab.ligar_no_agente(agente) == 1
    nomes = {t.spec.name for t in agente._tools}
    assert nomes == {"web_search", f"skill_{h.nome}"}
    ferramenta = next(t for t in agente._tools if t.spec.name.startswith("skill_"))
    assert "decisões" in ferramenta.execute(task="ata de hoje").content
    hab.ligar(h.nome, False)
    assert hab.ligar_no_agente(agente) == 0
    assert [t.spec.name for t in agente._tools] == ["web_search"]
    assert list(agente._executor._tools) == ["web_search"]


def test_roteamento_conhece_a_habilidade():
    from nicx.acoes.roteamento import needs_tools

    frase = "quero uma receita culinaria de bolo"
    assert not needs_tools(frase)
    hab.salvar("Receita culinária", "Receitas passo a passo.", "Liste ingredientes.")
    assert needs_tools(frase)


def test_rotas():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from nicx.servidor.rotas.extensoes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    assert client.get("/v1/extensoes/habilidades").json()["habilidades"] == []
    corpo = {
        "titulo": "Ata",
        "descricao": "Para atas.",
        "instrucoes": "Liste decisões.",
    }
    criada = client.post("/v1/extensoes/habilidades", json=corpo).json()
    assert criada["nome"] == "ata" and criada["editavel"]
    assert client.post("/v1/extensoes/habilidades", json=corpo).status_code == 400
    corpo["instrucoes"] = "Outra."
    assert client.put("/v1/extensoes/habilidades/ata", json=corpo).status_code == 200
    resposta = client.put("/v1/extensoes/habilidades/ata/ativa", json={"ativa": False})
    assert resposta.json() == {"nome": "ata", "ativa": False}
    enviado = client.post(
        "/v1/extensoes/habilidades/importar",
        files={
            "arquivo": (
                "h.zip",
                _zip({"z/SKILL.md": SKILL.format(nome="zeta", desc="Z.")}),
            )
        },
    ).json()
    assert enviado["resultados"][0]["ok"]
    resposta = client.put("/v1/extensoes/habilidades/zeta", json=corpo)
    assert resposta.status_code == 400  # importada: não se edita pela tela
    assert client.post("/v1/extensoes/habilidades/recarregar").json() == {"ligadas": 0}
    assert client.delete("/v1/extensoes/habilidades/ata").json() == {"ok": True}
    assert client.delete("/v1/extensoes/habilidades/ata").status_code == 404
