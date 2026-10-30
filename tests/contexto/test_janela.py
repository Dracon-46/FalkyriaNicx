"""Janela de fora do Nicx, arquivo no título e janelas sensíveis."""

from __future__ import annotations

import os
import struct
import zipfile

import pytest

from nicx.contexto import arquivo_aberto, janela
from nicx.contexto.janela import ArquivoNoTitulo, InfoJanela


def _info(titulo, processo="app.exe", pid=1234, classe="Janela"):
    return InfoJanela(hwnd=10, titulo=titulo, processo=processo, pid=pid, classe=classe)


# ---------------------------------------------------------------------------
# Quem conta como janela de fora
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "info",
    [
        _info("Nicx", "msedge.exe"),
        _info("Nicx - Microsoft Edge", "msedge.exe"),
        _info("Nicx", "python.exe"),  # janela flutuante do mascote
        _info("Nicx", "nicx.exe"),
        _info("Qualquer", "app.exe", pid=os.getpid()),
    ],
)
def test_janelas_do_nicx_ficam_de_fora(info):
    assert janela.do_nicx(info)
    assert not janela.de_fora(info)


@pytest.mark.parametrize(
    "info",
    [
        _info("", "explorer.exe", classe="Shell_TrayWnd"),
        _info("Barra", "explorer.exe", classe="Shell_TrayWnd"),
        _info("Pesquisar", "searchhost.exe"),
        _info("Program Manager", "explorer.exe", classe="Progman"),
    ],
)
def test_barra_de_tarefas_e_menu_iniciar_ficam_de_fora(info):
    assert not janela.de_fora(info)


def test_janela_comum_conta():
    assert janela.de_fora(
        _info("chat.py - FalkyriaNicx - Visual Studio Code", "code.exe")
    )


@pytest.mark.parametrize(
    "info",
    [
        _info("Banco de senhas - KeePass", "keepass.exe"),
        _info("Cofre", "1password.exe"),
        _info("Bitwarden", "bitwarden.exe"),
        _info("Alterar senha - Google Chrome", "chrome.exe"),
        _info("Sign in - Password - Microsoft Edge", "msedge.exe"),
        _info("Itaú - Internet Banking - Google Chrome", "chrome.exe"),
        _info("Nubank - Microsoft Edge", "msedge.exe"),
        _info("Segurança do Windows", "credentialuibroker.exe"),
    ],
)
def test_janelas_de_senha_e_banco_sao_sensiveis(info):
    assert janela.sensivel(info)


@pytest.mark.parametrize(
    "info",
    [
        _info("chat.py - FalkyriaNicx - Visual Studio Code", "code.exe"),
        _info("Banco de dados - DBeaver", "dbeaver.exe"),
        _info("Caixa de entrada - Outlook", "olk.exe"),
    ],
)
def test_janelas_comuns_nao_sao_sensiveis(info):
    assert not janela.sensivel(info)


# ---------------------------------------------------------------------------
# Arquivo no título e nome do app
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("titulo", "processo", "nome", "projeto", "extensoes"),
    [
        ("● chat.py - FalkyriaNicx - Visual Studio Code", "code.exe", "chat.py",
         "FalkyriaNicx", ()),
        ("*notas.txt - Bloco de Notas", "notepad.exe", "notas.txt", "", ()),
        ("Relatório.docx - Word", "winword.exe", "Relatório.docx", "", ()),
        ("Relatório - Modo de Compatibilidade - Word", "winword.exe", "Relatório",
         "", (".docx", ".doc", ".rtf", ".odt", ".txt")),
        ("contas.xlsx - Excel", "excel.exe", "contas.xlsx", "", ()),
        ("manual.pdf - Adobe Acrobat Reader (64-bit)", "acrord32.exe", "manual.pdf",
         "", ()),
        ("boleto.pdf e mais 2 páginas - Pessoal - Microsoft Edge", "msedge.exe",
         None, "", ()),
        ("artigo.pdf - Pessoal - Microsoft Edge", "msedge.exe", "artigo.pdf", "", ()),
    ],
)  # fmt: skip
def test_arquivo_no_titulo(titulo, processo, nome, projeto, extensoes):
    achado = janela.arquivo_no_titulo(_info(titulo, processo))
    if nome is None:
        assert achado is None
        return
    assert achado is not None
    assert achado.nome == nome
    assert achado.pasta_projeto == projeto
    assert achado.extensoes == extensoes


def test_caminho_completo_no_titulo():
    info = _info(r"C:\Users\ana\Documents\lista.txt - Notepad++", "notepad++.exe")
    achado = janela.arquivo_no_titulo(info)
    assert achado.caminho == r"C:\Users\ana\Documents\lista.txt"
    assert achado.nome == "lista.txt"


def test_pagina_sem_arquivo():
    info = _info("Notícias de hoje - Google Chrome", "chrome.exe")
    assert janela.arquivo_no_titulo(info) is None
    assert janela.nome_app(info) == "Google Chrome"


def test_nome_app():
    assert janela.nome_app(_info("x - Visual Studio Code", "code.exe")) == (
        "Visual Studio Code"
    )
    assert janela.nome_app(_info("notas.txt - Bloco de Notas", "notepad.exe")) == (
        "Bloco de Notas"
    )
    assert janela.nome_app(_info("Downloads", "explorer.exe"), "Explorer") == "Explorer"
    assert janela.nome_app(_info("Algo", "meuapp.exe")) == "Meuapp"


def test_rastreador_guarda_so_janela_de_fora():
    infos = {
        1: _info("planilha.xlsx - Excel", "excel.exe"),
        2: _info("Nicx - Microsoft Edge", "msedge.exe"),
        3: _info("", "explorer.exe", classe="Shell_TrayWnd"),
    }
    infos = {
        h: InfoJanela(h, i.titulo, i.processo, i.pid, i.classe)
        for h, i in infos.items()
    }
    rastreador = janela.RastreadorJanela(consultar=infos.get)
    rastreador.registrar(1)
    rastreador.registrar(2)  # o usuário foi para o Nicx
    rastreador.registrar(3)  # e passou pela barra de tarefas
    assert rastreador.ultima() == 1
    rastreador.registrar(999)  # janela que já fechou
    assert rastreador.ultima() == 1


# ---------------------------------------------------------------------------
# Arquivo aberto: só nas pastas do usuário
# ---------------------------------------------------------------------------


def test_resolve_dentro_das_pastas(tmp_path):
    docs = tmp_path / "Documents" / "trabalho"
    docs.mkdir(parents=True)
    alvo = docs / "relatorio.txt"
    alvo.write_text("conteúdo", encoding="utf-8")
    achado = arquivo_aberto.resolver(
        ArquivoNoTitulo("relatorio.txt"), raizes=[tmp_path / "Documents"], projetos=[]
    )
    assert achado == alvo


def test_resolve_word_sem_extensao(tmp_path):
    (tmp_path / "Relatorio.docx").write_bytes(b"x")
    achado = arquivo_aberto.resolver(
        ArquivoNoTitulo("Relatorio", extensoes=(".docx", ".doc")),
        raizes=[tmp_path],
        projetos=[],
    )
    assert achado == tmp_path / "Relatorio.docx"


def test_resolve_projeto_do_vscode(tmp_path):
    projeto = tmp_path / "MeuProjeto"
    (projeto / "src").mkdir(parents=True)
    (projeto / "src" / "app.py").write_text("print(1)", encoding="utf-8")
    achado = arquivo_aberto.resolver(
        ArquivoNoTitulo("app.py", pasta_projeto="MeuProjeto"),
        raizes=[],
        projetos=[projeto],
    )
    assert achado == projeto / "src" / "app.py"


def test_caminho_fora_das_pastas_e_recusado(tmp_path):
    fora = tmp_path / "sistema"
    fora.mkdir()
    (fora / "segredo.txt").write_text("x", encoding="utf-8")
    permitida = tmp_path / "Documents"
    permitida.mkdir()
    achado = arquivo_aberto.resolver(
        ArquivoNoTitulo("segredo.txt", caminho=str(fora / "segredo.txt")),
        raizes=[permitida],
        projetos=[],
    )
    assert achado is None
    # Nem por busca: o nome existe, mas fora das pastas permitidas.
    assert (
        arquivo_aberto.resolver(
            ArquivoNoTitulo("segredo.txt"), raizes=[permitida], projetos=[]
        )
        is None
    )


def _lnk(alvo: str) -> bytes:
    """Atalho .lnk mínimo só com o LinkInfo (caminho local em ANSI)."""
    cabecalho = bytearray(0x4C)
    struct.pack_into("<I", cabecalho, 0, 0x4C)
    struct.pack_into("<I", cabecalho, 0x14, 0x2)  # HasLinkInfo
    caminho = alvo.encode("cp1252") + b"\x00"
    tam_cab = 0x1C
    base_off = tam_cab
    sufixo_off = base_off + len(caminho)
    corpo = caminho + b"\x00"
    info = struct.pack(
        "<IIIIIII", tam_cab + len(corpo), tam_cab, 0x1, 0, base_off, 0, sufixo_off
    )
    return bytes(cabecalho) + info + corpo


def test_alvo_do_atalho_lnk():
    assert arquivo_aberto.alvo_do_atalho(_lnk(r"C:\Users\ana\Desktop\nota.txt")) == (
        r"C:\Users\ana\Desktop\nota.txt"
    )
    assert arquivo_aberto.alvo_do_atalho(b"lixo") is None


def test_le_texto_e_docx(tmp_path):
    txt = tmp_path / "a.md"
    txt.write_text("# Título\n\ncorpo", encoding="utf-8")
    assert arquivo_aberto.ler_arquivo(txt, 1000).texto == "# Título\n\ncorpo"

    docx = tmp_path / "b.docx"
    with zipfile.ZipFile(docx, "w") as pacote:
        pacote.writestr(
            "word/document.xml",
            "<w:document><w:body><w:p><w:r><w:t>Olá &amp; tchau</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Segunda linha</w:t></w:r></w:p></w:body></w:document>",
        )
    assert arquivo_aberto.ler_arquivo(docx, 1000).texto == "Olá & tchau\nSegunda linha"


def test_arquivo_sensivel_nao_e_lido(tmp_path):
    for nome in ("credentials.json", "passwords.txt"):
        arquivo = tmp_path / nome
        arquivo.write_text("SENHA=123", encoding="utf-8")
        leitura = arquivo_aberto.ler_arquivo(arquivo, 1000)
        assert not leitura.ok
        assert leitura.motivo == "sensivel"


def test_formato_desconhecido_nao_e_lido(tmp_path):
    exe = tmp_path / "programa.exe"
    exe.write_bytes(b"MZ\x00\x00")
    assert arquivo_aberto.ler_arquivo(exe, 1000).motivo == "formato"
