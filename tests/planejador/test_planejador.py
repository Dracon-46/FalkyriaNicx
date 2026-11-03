"""Planejador: prazos, frases, etapas do modelo, datas, lembretes, progresso, reajuste e rotas."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nicx.acoes import confirmacao, lembretes
from nicx.planejador import pedidos, servico
from nicx.planejador.prazo import interpretar
from nicx.planejador.servico import Etapa, PlanoErro
from nicx.projetos.armazenamento import Projetos

HOJE = date(2026, 11, 3)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "home"))
    confirmacao.drop()
    yield tmp_path / "home"


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("ate dezembro", date(2026, 12, 31)),
        ("ate 15/12", date(2026, 12, 15)),
        ("ate 15 de dezembro", date(2026, 12, 15)),
        ("em 3 meses", HOJE + timedelta(days=90)),
        ("daqui a duas semanas", HOJE + timedelta(days=14)),
        ("ate o fim do ano", date(2026, 12, 31)),
        ("ate marco", date(2027, 3, 31)),
        ("by december 15", date(2026, 12, 15)),
        ("in 6 weeks", HOJE + timedelta(days=42)),
        ("hasta diciembre", date(2026, 12, 31)),
        ("dans 6 semaines", HOJE + timedelta(days=42)),
        ("ate o show", None),
    ],
)
def test_prazo(texto, esperado):
    assert interpretar(texto, HOJE) == esperado


def test_frases_de_plano():
    p = pedidos.detectar(
        "Nicx, monta um plano para aprender Inglês até dezembro", "pt-BR", HOJE
    )
    assert p.objetivo == "aprender Inglês" and p.prazo == date(2026, 12, 31)
    assert (
        pedidos.detectar(
            "make a plan to learn Python by December 15", "en", HOJE
        ).objetivo
        == "learn Python"
    )
    assert pedidos.detectar("quero ir até a praia", "pt-BR", HOJE) is None
    assert pedidos.detectar("qual o plano para hoje", "pt-BR", HOJE) is None


def test_ler_etapas_tolera_texto_em_volta():
    resposta = (
        "<think>pensando</think>Claro!\n"
        '[{"texto": "Revisar gramática", "minutos": 120, "depende_de": []},'
        '{"texto": "Conversar", "minutes": "90", "depends_on": [0, 5]},'
        ' "Prova final"]\nBoa sorte!'
    )
    etapas = servico.ler_etapas(resposta)
    assert [e.texto for e in etapas] == [
        "Revisar gramática",
        "Conversar",
        "Prova final",
    ]
    assert etapas[1].minutos == 90 and etapas[1].depende_de == [0]
    with pytest.raises(PlanoErro):
        servico.ler_etapas("não sei")


def test_distribuir_proporcional_e_dentro_do_prazo():
    datas = servico.distribuir([60, 60, 120], HOJE, HOJE + timedelta(days=40))
    assert datas == [
        HOJE + timedelta(days=10),
        HOJE + timedelta(days=20),
        HOJE + timedelta(days=40),
    ]
    assert servico.distribuir([30], HOJE, HOJE) == [HOJE]


def _plano(dias=30):
    etapas = [Etapa("Base", 60), Etapa("Prática", 120, [0]), Etapa("Prova", 60, [1])]
    return servico.criar_plano(
        "Aprender inglês", date.today() + timedelta(days=dias), etapas
    )


def test_cria_plano_com_datas_dependencias_e_lembretes():
    projeto = _plano()
    etapas = projeto.pendencias
    assert projeto.prazo and len(etapas) == 3
    assert etapas[1].depende_de == [etapas[0].id] and etapas[2].depende_de == [
        etapas[1].id
    ]
    assert [e.prazo for e in etapas] == sorted(e.prazo for e in etapas)
    assert len(lembretes.pending()) == 3 and all(e.lembrete_id for e in etapas)
    from nicx.historico.registro import registro

    assert (
        len(registro().listar(tipos=["lembrete"])) == 1
    )  # uma linha para os 3 lembretes


def test_concluir_etapa_cancela_o_lembrete_e_conta_no_progresso():
    projeto = _plano()
    primeira = projeto.pendencias[0]
    Projetos().concluir_pendencia(projeto.id, primeira.id)
    assert primeira.lembrete_id not in {r.id for r in lembretes.pending()}
    info = servico.progresso(Projetos().obter(projeto.id))
    assert info["feitas"] == 1 and info["total"] == 3 and info["percentual"] == 25
    assert info["proxima"]["texto"] == "Prática"


def test_reajustar_redistribui_e_troca_lembretes():
    projeto = _plano()
    antigos = {r.id for r in lembretes.pending()}
    novo = date.today() + timedelta(days=60)
    reajustado = servico.reajustar(projeto.id, novo)
    assert reajustado.prazo == novo.isoformat()
    assert reajustado.pendencias[-1].prazo == novo.isoformat()
    assert (
        not antigos & {r.id for r in lembretes.pending()}
        and len(lembretes.pending()) == 3
    )
    with pytest.raises(PlanoErro):
        servico.reajustar(projeto.id, date.today())


def test_atrasadas_e_ritmo():
    projeto = _plano()
    info = servico.progresso(
        Projetos().obter(projeto.id), hoje=date.today() + timedelta(days=31)
    )
    assert len(info["atrasadas"]) == 3 and info["no_ritmo"] is False


class _Motor:
    is_cloud = False

    def __init__(self, conteudo):
        self.conteudo, self.pedidos = conteudo, []

    def generate(self, mensagens, **kw):
        self.pedidos.append(mensagens[0].content)
        return {"content": self.conteudo}


def test_propor_usa_o_modelo_e_valida_prazo():
    motor = _Motor(json.dumps([{"texto": "Estudar", "minutos": 30}]))
    etapas = servico.propor(
        "Aprender", date.today() + timedelta(days=10), "pt-BR", motor, "qwen"
    )
    assert [e.texto for e in etapas] == ["Estudar"] and "Aprender" in motor.pedidos[0]
    with pytest.raises(PlanoErro):
        servico.propor("Aprender", date.today(), "pt-BR", motor, "qwen")


@pytest.fixture
def client():
    from nicx.servidor.rotas.planejador import router

    app = FastAPI()
    app.include_router(router)
    app.state.engine = _Motor(
        json.dumps(
            [{"texto": "Ler", "minutos": 60}, {"texto": "Resumir", "minutos": 60}]
        )
    )
    app.state.model = "qwen3.5:4b"
    return TestClient(app)


def test_rotas(client):
    prazo = (date.today() + timedelta(days=20)).isoformat()
    proposta = client.post(
        "/v1/planejador/propor", json={"objetivo": "Ler um livro", "prazo": prazo}
    ).json()
    assert [e["texto"] for e in proposta["etapas"]] == ["Ler", "Resumir"]
    criado = client.post(
        "/v1/planejador",
        json={"objetivo": "Ler um livro", "prazo": prazo, "etapas": proposta["etapas"]},
    ).json()
    pid = criado["projeto"]["id"]
    assert criado["progresso"]["total"] == 2
    assert client.get(f"/v1/planejador/{pid}").json()["percentual"] == 0
    novo = (date.today() + timedelta(days=40)).isoformat()
    assert (
        client.post(f"/v1/planejador/{pid}/reajustar", json={"prazo": novo}).json()[
            "prazo"
        ]
        == novo
    )
    assert client.get("/v1/planejador/inexistente").status_code == 404
    assert (
        client.post("/v1/planejador/prazo", json={"texto": "até dezembro"})
        .json()["prazo"]
        .endswith("12-31")
    )


def test_textos_com_as_mesmas_chaves():
    from nicx.planejador import textos

    chaves = textos.chaves()
    assert all(c == chaves["pt-BR"] for c in chaves.values())
