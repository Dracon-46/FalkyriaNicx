"""Arquivos, fotos e YouTube: achar, abrir, listar, organizar e desfazer."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from nicx.acoes import arquivos, executores, handle, parse, youtube


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Perfil de usuário falso; nada é aberto de verdade."""
    profile = tmp_path / "perfil"
    for sub in ("Desktop", "Documents", "Downloads", "Pictures/Screenshots", "Videos"):
        (profile / sub).mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: profile)
    monkeypatch.setenv("NICX_HOME", str(tmp_path / "nicx"))
    opened: list[str] = []
    monkeypatch.setattr(executores, "_start", opened.append)
    return profile, opened


def _file(path: Path, age_minutes: float = 60) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    t = time.time() - age_minutes * 60
    os.utime(path, (t, t))
    return path


# ---------------------------------------------------------------------------
# Frases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "target", "op"),
    [
        ("toca Legião Urbana no YouTube", "youtube", "Legião Urbana", ""),
        ("toca Tempo Perdido", "youtube", "Tempo Perdido", ""),
        ("abre o vídeo do gato no youtube", "youtube", "gato", ""),
        ("abre a última foto", "file_latest", "imagem", ""),
        ("mostra o último print", "file_latest", "print", ""),
        ("abre o último download", "file_latest", "download", ""),
        ("abre a foto da praia", "file_open", "praia", "imagem"),
        ("abre o PDF do contrato", "file_open", "contrato", "pdf"),
        ("procura o arquivo do Contrato", "file_find", "Contrato", ""),
        ("onde está a planilha de gastos", "file_find", "gastos", "planilha"),
        ("o que tem na pasta downloads", "folder_list", "downloads", ""),
        (
            "lista os arquivos da área de trabalho",
            "folder_list",
            "area de trabalho",
            "",
        ),
        ("organiza a pasta downloads", "organize", "downloads", ""),
        ("arruma minha área de trabalho", "organize", "area de trabalho", ""),
        ("desfaz a organização", "organize_undo", "", ""),
    ],
)
def test_parse(text, kind, target, op):
    action = parse(text)
    assert action is not None and action.kind == kind
    assert (action.target, action.op) == (target, op)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("toca a música", "media"),  # continuar a mídia, não buscar
        ("abre o YouTube", "open"),
        ("abre a pasta downloads", "folder"),
    ],
)
def test_existing_commands_unchanged(text, kind):
    assert parse(text).kind == kind


# ---------------------------------------------------------------------------
# Achar e abrir
# ---------------------------------------------------------------------------


def test_open_latest_photo_and_print(home):
    profile, opened = home
    _file(profile / "Pictures" / "ferias" / "praia.jpg", age_minutes=120)
    newest = _file(profile / "Downloads" / "meme.png", age_minutes=5)
    shot = _file(profile / "Pictures" / "Screenshots" / "tela.png", age_minutes=300)
    assert handle("abre a última foto").message == "Abrindo meme.png (Downloads)."
    assert opened == [str(newest)]
    handle("mostra o último print")
    assert opened[-1] == str(shot)


def test_open_photo_by_name_ignores_accents_and_case(home):
    profile, opened = home
    target = _file(profile / "Pictures" / "Viagem à Praia.JPG")
    _file(profile / "Documents" / "praia.pdf")  # não é foto
    assert handle("abre a foto da praia").message.startswith(
        "Abrindo Viagem à Praia.JPG"
    )
    assert opened == [str(target)]


def test_find_lists_matches_newest_first(home):
    profile, _opened = home
    _file(profile / "Documents" / "contrato antigo.pdf", age_minutes=600)
    _file(profile / "Downloads" / "contrato novo.docx", age_minutes=10)
    message = handle("procura o arquivo do contrato").message
    assert message.startswith("Achei 2 arquivos: contrato novo.docx (Downloads);")


def test_find_skips_system_folders(home):
    profile, _opened = home
    _file(profile / "Documents" / "node_modules" / "relatorio.pdf")
    assert handle("procura o pdf do relatorio").message.startswith("Não achei PDF")


def test_list_folder(home):
    profile, _opened = home
    _file(profile / "Downloads" / "a.txt", age_minutes=10)
    _file(profile / "Downloads" / "b.txt", age_minutes=5)
    assert handle("o que tem na pasta downloads").message == (
        "Em Downloads (mais recentes): b.txt; a.txt."
    )


# ---------------------------------------------------------------------------
# Organizar e desfazer
# ---------------------------------------------------------------------------


def test_organize_asks_then_moves_and_undo_restores(home):
    profile, _opened = home
    downloads = profile / "Downloads"
    _file(downloads / "foto.jpg")
    _file(downloads / "nota.pdf")
    _file(downloads / "setup.exe")
    _file(downloads / "estranho.xyz")
    _file(downloads / "baixando.crdownload")  # ainda baixando
    _file(downloads / "agora.png", age_minutes=0)  # mexido agora
    ask = handle("organiza a pasta downloads").message
    assert ask.startswith("Vou separar 4 arquivos de Downloads em pastas")
    assert (downloads / "foto.jpg").exists()  # nada antes de confirmar
    done = handle("confirmo").message
    assert done.startswith("Pronto: 4 arquivos organizados em Downloads")
    assert (downloads / "Imagens" / "foto.jpg").exists()
    assert (downloads / "PDFs" / "nota.pdf").exists()
    assert (downloads / "Instaladores" / "setup.exe").exists()
    assert (downloads / "Outros" / "estranho.xyz").exists()
    assert (downloads / "baixando.crdownload").exists()
    assert (downloads / "agora.png").exists()
    undo = handle("desfaz a organização").message
    assert undo == "Desfeito: 4 arquivos voltaram para Downloads."
    assert (downloads / "foto.jpg").exists() and not (downloads / "Imagens").exists()


def test_organize_keeps_both_on_name_clash(home):
    profile, _opened = home
    downloads = profile / "Downloads"
    _file(downloads / "Imagens" / "foto.jpg")
    _file(downloads / "foto.jpg")
    handle("organiza a pasta downloads")
    handle("confirmo")
    assert (downloads / "Imagens" / "foto.jpg").exists()
    assert (downloads / "Imagens" / "foto (2).jpg").exists()


def test_nothing_to_organize(home):
    assert handle("organiza a pasta downloads").message == (
        "Downloads já está organizada: nada solto para mover."
    )


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------


def test_youtube_opens_the_first_video(home, monkeypatch):
    _profile, opened = home

    class Page:
        text = 'xx"videoId":"abcDEF12345"yy"videoId":"zzzzzzzzzzz"'

        def raise_for_status(self):
            return None

    monkeypatch.setattr(youtube.httpx, "get", lambda *a, **k: Page())
    assert (
        handle("toca Tempo Perdido no YouTube").message
        == "Tocando Tempo Perdido no YouTube."
    )
    assert opened == ["https://www.youtube.com/watch?v=abcDEF12345"]


def test_youtube_falls_back_to_search(home, monkeypatch):
    _profile, opened = home

    def offline(*_a, **_k):
        raise youtube.httpx.ConnectError("sem internet")

    monkeypatch.setattr(youtube.httpx, "get", offline)
    message = handle("toca Tempo Perdido").message
    assert message == "Abri a busca por Tempo Perdido no YouTube."
    assert opened == ["https://www.youtube.com/results?search_query=Tempo+Perdido"]


# ---------------------------------------------------------------------------
# Ferramenta do modelo
# ---------------------------------------------------------------------------


def test_files_tool(home):
    from nicx.acoes.ferramenta import FilesTool

    profile, opened = home
    _file(profile / "Documents" / "gastos 2026.xlsx")
    tool = FilesTool()
    found = tool.execute(acao="procurar", busca="gastos", tipo="planilha")
    assert found.success and "gastos 2026.xlsx (Documents)" in found.content
    assert tool.execute(acao="abrir", busca="gastos").success
    assert opened[-1].endswith("gastos 2026.xlsx")
    assert not tool.execute(acao="listar_pasta", pasta="segredos").success
    assert tool.execute(acao="listar_pasta", pasta="documentos").success


def test_kind_of_extensions():
    assert arquivos.kind_of(Path("a.HEIC")) == "imagem"
    assert arquivos.kind_of(Path("a.xlsx")) == "planilha"
    assert arquivos.kind_of(Path("a.unknown")) is None
