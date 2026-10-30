"""Ferramenta ``projetos``, sugestões da memória e o contrato ``resumo_do_dia``."""

from __future__ import annotations

import json
from datetime import date

from nicx.projetos import resumo_do_dia
from nicx.projetos.ferramenta import ProjectsTool
from nicx.projetos.memoria import sugerir_da_conversa


def _run(**params):
    return ProjectsTool().execute(**params)


# --- Ferramenta -------------------------------------------------------------


def test_ferramenta_curta_e_carregada_com_as_outras():
    import nicx.ferramentas  # noqa: F401  (importa a ferramenta junto)
    from nicx.seguranca.capabilities import canonical_tool_capabilities

    assert canonical_tool_capabilities(ProjectsTool()) == ["tool:invoke"]
    spec = ProjectsTool().spec
    assert spec.name == "projetos"
    assert len(json.dumps(spec.parameters)) + len(spec.description) < 600
    assert spec.parameters["properties"]["acao"]["enum"] == [
        "listar",
        "ver",
        "criar",
        "atualizar_estado",
        "decisao",
        "pendencia",
        "concluir_pendencia",
    ]


def test_ferramenta_fluxo_completo(loja):
    assert _run(acao="listar").content == "Nenhum projeto ainda."
    assert _run(acao="criar", projeto="Lumen", texto="Dados públicos").success
    assert not _run(acao="criar", projeto="lumen").success
    assert _run(acao="atualizar_estado", projeto="lumen", texto="API pronta").success
    assert _run(acao="decisao", projeto="Lumen", texto="Usar Postgres").success
    assert _run(acao="pendencia", projeto="Lumen", texto="Comprar domínio").success
    ver = _run(acao="ver", projeto="Lumen").content
    assert "Objetivo: Dados públicos" in ver
    assert "Estado: API pronta" in ver
    assert "Decisão" in ver and "Usar Postgres" in ver
    assert "Pendência: Comprar domínio" in ver
    assert "1 pendência(s)" in _run(acao="listar").content
    feita = _run(acao="concluir_pendencia", projeto="Lumen", texto="comprar dominio")
    assert feita.success and "Comprar domínio" in feita.content
    errada = _run(acao="concluir_pendencia", projeto="Lumen", texto="outra coisa")
    assert not errada.success


def test_ferramenta_erros(loja):
    assert not _run(acao="apagar_tudo").success
    sem = _run(acao="ver", projeto="Ascend")
    assert not sem.success and "não encontrado" in sem.content
    loja.criar("Lumen")
    assert not _run(acao="decisao", projeto="Lumen", texto="").success
    # Sem nome: o projeto mais recente.
    assert "Projeto Lumen" in _run(acao="ver").content


def test_roteamento_manda_ferramentas_quando_fala_de_projeto():
    from nicx.acoes.roteamento import needs_tools

    assert needs_tools("terminei a tela de login do projeto Lumen, anota aí")
    assert needs_tools("vamos continuar de onde parei?")
    assert needs_tools("what's pending in my project?")
    assert not needs_tools("me conta uma piada")


# --- Memória -----------------------------------------------------------------


def test_memoria_anota_decisao_e_pendencia_com_confianca(loja):
    p = loja.criar("Lumen")
    assert sugerir_da_conversa(
        "No projeto Lumen decidimos usar Postgres em vez de SQLite."
    ) == ("decisao", "Lumen", "Usar Postgres em vez de SQLite")
    # Repetida não entra de novo.
    assert (
        sugerir_da_conversa("no projeto Lumen decidimos usar Postgres em vez de SQLite")
        is None
    )
    assert sugerir_da_conversa(
        "Hoje mexi no projeto Lumen e ainda falta revisar os textos legais"
    ) == ("pendencia", "Lumen", "Revisar os textos legais")
    lido = loja.obter(p.id)
    assert lido.decisoes[-1].origem == "auto"
    assert lido.abertas[-1].origem == "auto"


def test_memoria_nao_inventa(loja):
    loja.criar("Lumen")
    # Pergunta, projeto que não existe, sem marcador, sem "projeto".
    assert sugerir_da_conversa("No projeto Lumen decidimos usar Postgres?") is None
    assert sugerir_da_conversa("No projeto Ascend decidimos usar Postgres") is None
    assert sugerir_da_conversa("O projeto Lumen está indo bem") is None
    assert sugerir_da_conversa("No Lumen decidimos usar Postgres") is None
    assert [p.nome for p in loja.listar()] == ["Lumen"]  # nunca cria projeto
    assert loja.buscar("Lumen").decisoes == []


def test_memoria_sem_arquivo_nao_faz_nada(home):
    assert sugerir_da_conversa("No projeto Lumen decidimos usar Postgres") is None
    assert not (home / "projetos.json").exists()


def test_servico_de_memoria_chama_o_gancho():
    from unittest.mock import MagicMock

    from nicx.memoria.service import MemoryService

    extractor = MagicMock()
    extractor.extract.return_value = []
    vistos = []
    svc = MemoryService(MagicMock(), extractor, project_hook=vistos.append)
    svc._process(("no projeto Lumen decidimos X", "ok"))
    assert vistos == ["no projeto Lumen decidimos X"]

    def quebra(texto):
        raise RuntimeError("falhou")

    svc = MemoryService(MagicMock(), extractor, project_hook=quebra)
    svc._process(("oi", ""))  # não levanta
    assert extractor.extract.call_count == 2


# --- resumo_do_dia ------------------------------------------------------------


def test_resumo_do_dia_sem_projetos(home):
    assert resumo_do_dia(date(2026, 10, 30)) == {
        "atualizados": [],
        "concluidas": [],
        "pendentes": [],
    }


def test_resumo_do_dia_contrato(loja):
    dados = {
        "versao": 1,
        "projetos": [
            {
                "id": "a",
                "nome": "Lumen",
                "criado_em": "2026-10-01T10:00:00",
                "ultima_atividade": "2026-10-30T18:00:00",
                "dias_ativos": ["2026-10-29", "2026-10-30"],
                "pendencias": [
                    {
                        "id": "p1",
                        "texto": "Comprar domínio",
                        "feita": True,
                        "criada_em": "2026-10-20T10:00:00",
                        "feita_em": "2026-10-30T11:00:00",
                    },
                    {
                        "id": "p2",
                        "texto": "Revisar textos",
                        "criada_em": "2026-10-29T10:00:00",
                    },
                ],
            },
            {
                "id": "b",
                "nome": "Ascend",
                "criado_em": "2026-09-01T10:00:00",
                "ultima_atividade": "2026-10-29T09:00:00",
                "dias_ativos": ["2026-10-29"],
                "pendencias": [
                    {
                        "id": f"q{i}",
                        "texto": f"Tarefa {i}",
                        "criada_em": f"2026-10-{10 + i}T10:00:00",
                    }
                    for i in range(12)
                ],
            },
            {
                "id": "c",
                "nome": "Velho",
                "arquivado": True,
                "criado_em": "2026-01-01T10:00:00",
                "ultima_atividade": "2026-10-30T08:00:00",
                "pendencias": [
                    {
                        "id": "z",
                        "texto": "Esquecida",
                        "criada_em": "2026-10-30T07:00:00",
                    }
                ],
            },
        ],
    }
    loja.caminho.write_text(json.dumps(dados), encoding="utf-8")

    hoje = resumo_do_dia(date(2026, 10, 30))
    assert set(hoje) == {"atualizados", "concluidas", "pendentes"}
    assert hoje["atualizados"] == ["Lumen", "Velho"]
    assert hoje["concluidas"] == [("Lumen", "Comprar domínio")]
    pendentes = hoje["pendentes"]
    assert len(pendentes) == 10
    assert all(isinstance(item, tuple) and len(item) == 2 for item in pendentes)
    assert pendentes[0] == ("Lumen", "Revisar textos")  # a mais recente
    assert pendentes[1] == ("Ascend", "Tarefa 11")
    assert ("Velho", "Esquecida") not in pendentes  # arquivado fica de fora

    ontem = resumo_do_dia(date(2026, 10, 29))
    assert ontem["atualizados"] == ["Lumen", "Ascend"]
    assert ontem["concluidas"] == []
