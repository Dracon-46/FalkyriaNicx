"""Armazenamento dos projetos: operações, concorrência e arquivo estragado."""

from __future__ import annotations

import json
import threading

import pytest

from nicx.projetos import busca
from nicx.projetos.armazenamento import (
    ProjetoErro,
    ProjetoJaExiste,
    ProjetoNaoEncontrado,
    Projetos,
)


def test_cria_e_le_de_volta(loja, home):
    projeto = loja.criar(
        "Site Novo", objetivo="Lançar o site", pastas=["C:\\dev\\site\\"]
    )
    assert loja.caminho == home / "projetos.json"
    dados = json.loads(loja.caminho.read_text(encoding="utf-8"))
    assert dados["versao"] == 1
    lido = Projetos().obter(projeto.id)
    assert lido is not None
    assert lido.nome == "Site Novo"
    assert lido.objetivo == "Lançar o site"
    assert lido.pastas == ["C:\\dev\\site"]
    assert lido.dias_ativos == [lido.criado_em[:10]]


def test_nome_repetido_e_vazio(loja):
    loja.criar("Lumen")
    with pytest.raises(ProjetoJaExiste):
        loja.criar("lúmen")
    with pytest.raises(ProjetoErro):
        loja.criar("  ")


def test_renomear_arquivar_estado(loja):
    a = loja.criar("Lumen")
    loja.criar("Ascend")
    with pytest.raises(ProjetoJaExiste):
        loja.renomear(a.id, "ascend")
    assert loja.renomear(a.id, "Lumen 2").nome == "Lumen 2"
    loja.atualizar_estado(a.id, "API pronta, falta a tela")
    loja.arquivar(a.id)
    assert [p.nome for p in loja.listar()] == ["Ascend"]
    arquivado = loja.obter(a.id)
    assert arquivado.arquivado and arquivado.estado == "API pronta, falta a tela"
    # Arquivado não bloqueia o nome.
    assert loja.criar("Lumen 2").id != a.id


def test_decisoes_e_pendencias(loja):
    p = loja.criar("Lumen")
    loja.registrar_decisao(p.id, "Usar Postgres")
    pend = loja.adicionar_pendencia(p.id, "Comprar o domínio")
    # Repetida não duplica.
    assert loja.adicionar_pendencia(p.id, "comprar o dominio").id == pend.id
    loja.adicionar_pendencia(p.id, "Revisar textos legais")
    feita = loja.concluir_pendencia(p.id, "comprar dominio")
    assert feita is not None and feita.id == pend.id and feita.feita_em
    assert loja.concluir_pendencia(p.id, "algo que não existe") is None
    lido = loja.obter(p.id)
    assert [d.texto for d in lido.decisoes] == ["Usar Postgres"]
    assert [x.texto for x in lido.abertas] == ["Revisar textos legais"]
    # Reabrir pelo id.
    assert loja.concluir_pendencia(p.id, pend.id, feita=False).feita is False


def test_anexar_pasta_e_arquivo_sem_repetir(loja):
    p = loja.criar("Lumen")
    loja.anexar_pasta(p.id, "C:\\dev\\lumen")
    loja.anexar_pasta(p.id, "c:\\dev\\lumen\\")
    loja.anexar_arquivo(p.id, "C:\\dev\\lumen\\README.md")
    lido = loja.obter(p.id)
    assert len(lido.pastas) == 1
    assert lido.arquivos == ["C:\\dev\\lumen\\README.md"]


def test_projeto_inexistente(loja):
    with pytest.raises(ProjetoNaoEncontrado):
        loja.registrar_decisao("nao-existe", "x")
    assert loja.tocar("nao-existe") is None


def test_concorrencia_entre_lojas_nao_perde_gravacoes(home):
    """Duas "instâncias" (como servidor e terminal) gravando ao mesmo tempo."""
    p = Projetos().criar("Lumen")
    erros: list[BaseException] = []

    def gravar(n: int) -> None:
        loja = Projetos()  # instância própria: só a trava entre processos protege
        try:
            for i in range(10):
                loja.adicionar_pendencia(p.id, f"tarefa {n}-{i}")
        except BaseException as exc:  # pragma: no cover - só se falhar
            erros.append(exc)

    threads = [threading.Thread(target=gravar, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not erros
    assert len(Projetos().obter(p.id).pendencias) == 40


def test_projeto_estragado_e_pulado_os_outros_ficam(loja):
    bom = loja.criar("Lumen")
    dados = json.loads(loja.caminho.read_text(encoding="utf-8"))
    dados["projetos"].append({"nome": "", "id": ""})  # sem nome: ilegível
    dados["projetos"].append("lixo")
    loja.caminho.write_text(json.dumps(dados), encoding="utf-8")
    assert [p.id for p in loja.listar()] == [bom.id]


def test_arquivo_corrompido_volta_do_backup(loja):
    a = loja.criar("Lumen")
    loja.criar("Ascend")  # a gravação anterior (só Lumen) vai para o .bak
    loja.registrar_decisao(a.id, "Usar Postgres")  # .bak = Lumen + Ascend
    loja.caminho.write_text('{"versao": 1, "projetos": [{"nome": "Lu', encoding="utf-8")
    nomes = sorted(p.nome for p in loja.listar())
    assert nomes == ["Ascend", "Lumen"]
    # A próxima gravação guarda o estragado antes de cobrir.
    loja.criar("Novo")
    corrompido = loja.caminho.with_name("projetos.json.corrompido")
    assert corrompido.read_text(encoding="utf-8").startswith('{"versao": 1')
    assert sorted(p.nome for p in loja.listar()) == ["Ascend", "Lumen", "Novo"]


def test_arquivo_ruim_sem_backup_nao_explode(loja):
    loja.caminho.write_text("não é json", encoding="utf-8")
    assert loja.listar() == []
    loja.criar("Lumen")
    assert [p.nome for p in loja.listar()] == ["Lumen"]
    assert loja.caminho.with_name("projetos.json.corrompido").exists()


def test_lista_do_mais_recente(loja):
    a = loja.criar("Lumen")
    b = loja.criar("Ascend")
    loja.tocar(a.id, "2099-01-01T10:00:00")
    assert [p.id for p in loja.listar()] == [a.id, b.id]
    assert loja.mais_recente().id == a.id


@pytest.mark.parametrize(
    ("consulta", "esperado"),
    [
        ("Nicx Site", "Nicx Site"),
        ("nicx site", "Nicx Site"),
        ("NicxSite", "Nicx Site"),
        ("nicx-site", "Nicx Site"),
        ("site", "Nicx Site"),
        ("lúmen", "Lumen"),
        ("lum", "Lumen"),
        ("o projeto lumen", "Lumen"),
        ("aether", "AetherTable"),
        ("nicx", "Nicx"),
    ],
)
def test_busca_tolerante(loja, consulta, esperado):
    for nome in ("Nicx Site", "Lumen", "AetherTable", "Nicx"):
        loja.criar(nome)
    assert loja.buscar(consulta).nome == esperado


def test_busca_sem_nada_parecido(loja):
    loja.criar("Lumen")
    assert loja.buscar("Ascend") is None
    assert busca.pontuar("", "Lumen") == 0
