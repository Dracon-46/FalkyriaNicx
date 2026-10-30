"""Pedidos atendidos na hora (7 idiomas) e o "continue de onde parei"."""

from __future__ import annotations

import json

import pytest

from nicx.contexto.montagem import FIM, INICIO, sem_contexto, tem_contexto
from nicx.projetos import servico, textos
from nicx.projetos.deteccao import SinalJanela


def envelhecer(loja, projeto_id, iso="2000-01-01T00:00:00"):
    """Põe a última atividade no passado (``tocar`` só avança no tempo)."""
    dados = json.loads(loja.caminho.read_text(encoding="utf-8"))
    for item in dados["projetos"]:
        if item["id"] == projeto_id:
            item["ultima_atividade"] = iso
    loja.caminho.write_text(json.dumps(dados), encoding="utf-8")


def _r(frase, idioma=None, **kw):
    preparo = servico.preparar(frase, idioma=idioma, **kw)
    assert preparo is not None, frase
    return preparo


def test_sem_projetos(loja):
    assert "ainda não tem projetos" in _r("quais meus projetos?").resposta
    assert "não há projetos" in _r("continue de onde parei").resposta


def test_criar_listar_ver_e_anotar(loja):
    assert _r("cria o projeto Lumen").resposta == 'Projeto "Lumen" criado.'
    assert _r("cria o projeto lumen").resposta == 'O projeto "Lumen" já existe.'
    resposta = _r("adiciona pendência no projeto Lumen: comprar o domínio").resposta
    assert resposta == "Pendência adicionada ao projeto Lumen: comprar o domínio."
    resposta = _r("adiciona pendência no projeto Lumen revisar textos").resposta
    assert resposta == "Pendência adicionada ao projeto Lumen: revisar textos."
    resposta = _r("anota no projeto lumen que decidimos usar Postgres").resposta
    assert resposta == "Anotado no projeto Lumen: Usar Postgres."
    resposta = _r("atualiza o estado do projeto Lumen: API pronta").resposta
    assert "API pronta" in resposta

    assert _r("quais meus projetos?").resposta == (
        "Seus projetos: Lumen (2 pendências)."
    )
    ver = _r("como está o projeto Lumen?").resposta
    assert "Estado: API pronta." in ver
    assert "Última decisão: Usar Postgres." in ver
    assert "comprar o domínio" in ver
    assert "Última atividade: agora há pouco." in ver

    assert _r("o que falta no projeto Lumen?").resposta.startswith(
        "No projeto Lumen falta: "
    )
    concluida = _r("conclui a pendência comprar dominio do projeto Lumen").resposta
    assert concluida == "Pendência concluída no projeto Lumen: comprar o domínio."
    # Sem dizer o projeto: acha a pendência em qualquer um.
    assert "revisar textos" in _r("marca a tarefa revisar textos como feita").resposta
    assert _r("o que falta no projeto Lumen?").resposta == (
        "No projeto Lumen não há pendências abertas."
    )
    assert _r("arquiva o projeto Lumen").resposta == "Projeto Lumen arquivado."
    assert "ainda não tem projetos" in _r("meus projetos").resposta


def test_pendencia_com_nome_grudado(loja):
    loja.criar("Nicx Site")
    loja.criar("Nicx")
    resposta = _r("adiciona pendência no projeto nicx site trocar a foto").resposta
    assert resposta == "Pendência adicionada ao projeto Nicx Site: trocar a foto."


def test_nao_achei_lista_os_projetos(loja):
    loja.criar("Lumen")
    resposta = _r("o que falta no projeto Ascend?").resposta
    assert resposta == 'Não achei o projeto "Ascend". Seus projetos: Lumen.'


def test_pergunta_sobre_outro_tipo_de_projeto_vai_para_o_modelo(loja):
    loja.criar("Lumen")
    assert servico.preparar("como está o projeto de lei da reforma?") is None
    assert servico.preparar("marca a tarefa de casa como feita") is None


@pytest.mark.parametrize(
    ("idioma", "frase", "esperado"),
    [
        ("en", "create project Lumen", 'Project "Lumen" created.'),
        ("es", "crea el proyecto Lumen", 'Proyecto "Lumen" creado.'),
        ("fr", "crée le projet Lumen", "Projet « Lumen » créé."),
        ("zh", "create project Lumen", "已创建项目“Lumen”。"),
        ("hi", "create project Lumen", 'प्रोजेक्ट "Lumen" बना दिया।'),
        ("ar", "create project Lumen", 'تم إنشاء المشروع "Lumen".'),
    ],
)
def test_respostas_no_idioma(loja, idioma, frase, esperado):
    assert _r(frase, idioma).resposta == esperado


def test_textos_tem_as_mesmas_chaves_nos_7_idiomas():
    chaves = textos.chaves()
    base = chaves["pt-BR"]
    assert set(chaves) == {"pt-BR", "en", "es", "fr", "zh", "hi", "ar"}
    for codigo, tabela in chaves.items():
        assert tabela == base, codigo


def test_criar_na_pasta(loja, tmp_path):
    pasta = tmp_path / "site"
    pasta.mkdir()
    resposta = _r(f"cria o projeto Site na pasta {pasta}").resposta
    assert resposta == f'Projeto "Site" criado. Pasta: {pasta}.'
    assert loja.buscar("Site").pastas == [str(pasta)]
    resposta = _r("cria o projeto Outro na pasta C:\\nao\\existe\\mesmo").resposta
    assert "Não achei a pasta" in resposta
    assert loja.buscar("Outro").pastas == []


def test_criar_usa_a_pasta_aberta_no_vscode(loja, tmp_path, monkeypatch):
    from nicx.projetos import deteccao

    pasta = tmp_path / "Lumen"
    pasta.mkdir()
    monkeypatch.setattr(deteccao, "pasta_do_vscode", lambda nome: str(pasta))
    sinal = SinalJanela(arquivo="app.py", pasta_aberta="Lumen")
    _r("cria o projeto Lumen", sinal=sinal)
    assert loja.buscar("Lumen").pastas == [str(pasta)]


def test_continuar_monta_resumo_do_mais_recente(loja, monkeypatch):
    from nicx.projetos import continuar

    monkeypatch.setattr(continuar, "coletar", lambda projeto: continuar.Sinais())
    velho = loja.criar("Ascend")
    novo = loja.criar("Lumen")
    envelhecer(loja, velho.id)
    loja.atualizar_estado(novo.id, "Falta a tela de login")
    loja.adicionar_pendencia(novo.id, "Revisar textos legais")

    preparo = _r("continue de onde parei")
    assert preparo.resposta is None
    assert preparo.projeto_id == novo.id
    bloco = preparo.resumo
    assert tem_contexto(bloco)
    assert 'fonte="projeto" projeto="Lumen"' in bloco
    assert "Estado: Falta a tela de login" in bloco
    assert "- Revisar textos legais" in bloco
    assert bloco.index("Revisar") < bloco.index(FIM)
    assert bloco.rstrip().endswith(continuar.AVISO)
    # O pedido sai limpo para memória e rastros.
    assert sem_contexto("continue de onde parei" + bloco) == "continue de onde parei"
    assert bloco.count(INICIO) == 1


def test_continuar_prefere_o_projeto_da_janela(loja, monkeypatch, tmp_path):
    from nicx.projetos import continuar

    monkeypatch.setattr(continuar, "coletar", lambda projeto: continuar.Sinais())
    pasta = tmp_path / "ascend"
    pasta.mkdir()
    ascend = loja.criar("Ascend", pastas=[str(pasta)])
    loja.criar("Lumen")  # mais recente
    sinal = SinalJanela(caminho=str(pasta / "src" / "main.py"), arquivo="main.py")
    assert _r("o que eu estava fazendo?", sinal=sinal).projeto_id == ascend.id
    # Pelo nome, vale o nome.
    assert _r("continua o projeto Lumen", sinal=sinal).projeto_id != ascend.id


def test_mencao_marca_atividade(loja):
    a = loja.criar("Lumen")
    envelhecer(loja, a.id)
    antes = loja.obter(a.id).ultima_atividade
    loja.criar("Ascend")
    assert servico.preparar("estou mexendo no projeto Lumen hoje") is None
    assert loja.obter(a.id).ultima_atividade > antes
