"""Qual projeto o usuário está tocando agora, só com sinais do próprio PC.

- a janela em uso (``nicx.contexto.janela``): a pasta aberta no VS Code ou
  o caminho do arquivo no título;
- o git da pasta do projeto: branch, últimos commits e arquivos alterados
  (``git`` local por subprocess, nunca com rede);
- os arquivos mexidos por último nas pastas do projeto.

Nada disso é gravado o tempo todo: o observador olha a janela a cada
alguns minutos e só marca atividade no projeto (no máximo uma gravação a
cada ``INTERVALO_GRAVACAO`` segundos por projeto). O conteúdo dos arquivos
nunca é lido aqui, só nomes e datas.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from nicx.projetos import busca
from nicx.projetos.armazenamento import Projetos
from nicx.projetos.modelo import Projeto

logger = logging.getLogger(__name__)

INTERVALO_GRAVACAO = 300.0  # segundos entre duas marcas do mesmo projeto
INTERVALO_OBSERVADOR = 120.0
TEMPO_GIT = 3.0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_PULAR = frozenset(
    {
        ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
        "target", ".next", ".cache", ".idea", ".vscode", ".mypy_cache",
        ".pytest_cache", ".ruff_cache", "coverage", ".turbo", "out",
    }
)  # fmt: skip


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------


def _normcase(caminho: str) -> str:
    return os.path.normcase(os.path.normpath(caminho)).rstrip("\\/")


def projeto_do_caminho(caminho: str, projetos: Iterable[Projeto]) -> Optional[Projeto]:
    """O projeto que tem *caminho* dentro de uma de suas pastas."""
    if not caminho:
        return None
    alvo = _normcase(caminho)
    melhor: tuple[int, Optional[Projeto]] = (0, None)
    for projeto in projetos:
        for pasta in projeto.pastas:
            base = _normcase(pasta)
            if base and (alvo == base or alvo.startswith(base + os.sep)):
                if len(base) > melhor[0]:
                    melhor = (len(base), projeto)
    return melhor[1]


def projeto_da_pasta_aberta(
    nome_pasta: str, projetos: Iterable[Projeto]
) -> Optional[Projeto]:
    """VS Code mostra só o nome da pasta: compara com as pastas e os nomes."""
    if not nome_pasta:
        return None
    lista = list(projetos)
    alvo = os.path.normcase(nome_pasta.strip())
    for projeto in lista:
        for pasta in projeto.pastas:
            if os.path.normcase(Path(pasta).name) == alvo:
                return projeto
    chave = busca.normalizar(nome_pasta).replace(" ", "")
    for projeto in lista:
        if busca.normalizar(projeto.nome).replace(" ", "") == chave:
            return projeto
    return None


@dataclass(frozen=True)
class SinalJanela:
    caminho: str = ""  # caminho completo do arquivo, quando o título traz
    pasta_aberta: str = ""  # VS Code: nome da pasta aberta
    arquivo: str = ""  # nome do arquivo


def sinal_da_janela(info: object = None) -> Optional[SinalJanela]:
    """O arquivo/pasta da janela em uso; None fora do Windows ou sem janela."""
    if sys.platform != "win32" and info is None:
        return None
    try:
        from nicx.contexto import janela

        if info is None:
            info = janela.janela_de_fora()
        if info is None or janela.sensivel(info):
            return None
        arquivo = janela.arquivo_no_titulo(info)
    except Exception:  # noqa: BLE001 — sinal opcional
        logger.debug("Janela ativa indisponível", exc_info=True)
        return None
    if arquivo is None:
        return None
    return SinalJanela(arquivo.caminho, arquivo.pasta_projeto, arquivo.nome)


def projeto_da_janela(
    projetos: Iterable[Projeto], sinal: Optional[SinalJanela] = None
) -> Optional[Projeto]:
    lista = list(projetos)
    if not lista:
        return None
    sinal = sinal if sinal is not None else sinal_da_janela()
    if sinal is None:
        return None
    return projeto_do_caminho(sinal.caminho, lista) or projeto_da_pasta_aberta(
        sinal.pasta_aberta, lista
    )


def pasta_do_vscode(nome_pasta: str) -> Optional[str]:
    """Caminho completo de uma pasta aberta há pouco no VS Code, pelo nome."""
    if not nome_pasta:
        return None
    try:
        from nicx.contexto.arquivo_aberto import pastas_vscode

        for pasta in pastas_vscode():
            if os.path.normcase(pasta.name) == os.path.normcase(nome_pasta):
                return str(pasta)
    except Exception:  # noqa: BLE001
        logger.debug("Pastas do VS Code indisponíveis", exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Commit:
    hash: str
    data: str  # ISO
    assunto: str


@dataclass(frozen=True)
class InfoGit:
    pasta: str
    branch: str = ""
    commits: tuple[Commit, ...] = ()
    alterados: tuple[str, ...] = ()
    total_alterados: int = 0


Executor = Callable[[list[str], str], Optional[str]]


def _rodar_git(args: list[str], pasta: str) -> Optional[str]:
    """Roda ``git`` local na pasta; None se falhar. Nunca pede senha nem rede."""
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",  # o status não grava o índice
        "LC_ALL": "C",
    }
    try:
        resultado = subprocess.run(
            ["git", "-C", pasta, *args],
            capture_output=True,
            timeout=TEMPO_GIT,
            env=env,
            creationflags=_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if resultado.returncode != 0:
        return None
    return resultado.stdout.decode("utf-8", errors="replace")


def info_git(
    pasta: str,
    *,
    commits: int = 3,
    max_alterados: int = 8,
    rodar: Executor = _rodar_git,
) -> Optional[InfoGit]:
    """Branch, últimos commits e arquivos alterados; None se não for git."""
    if not pasta or not Path(pasta).is_dir():
        return None
    log = rodar(["log", f"-{max(1, commits)}", "--format=%h%x1f%cI%x1f%s"], pasta)
    if log is None:
        return None
    lista = []
    for linha in log.splitlines():
        partes = linha.split("\x1f")
        if len(partes) == 3:
            lista.append(Commit(partes[0], partes[1], partes[2].strip()[:120]))
    branch = (rodar(["branch", "--show-current"], pasta) or "").strip()
    status = rodar(["status", "--porcelain", "--untracked-files=normal"], pasta) or ""
    alterados = [linha[3:].strip().strip('"') for linha in status.splitlines() if linha]
    return InfoGit(
        pasta=pasta,
        branch=branch,
        commits=tuple(lista),
        alterados=tuple(alterados[:max_alterados]),
        total_alterados=len(alterados),
    )


# ---------------------------------------------------------------------------
# Arquivos recentes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArquivoRecente:
    caminho: str  # relativo à pasta do projeto
    modificado: float  # epoch


def arquivos_recentes(
    pastas: Iterable[str],
    *,
    limite: int = 5,
    max_vistos: int = 4000,
    prazo: float = 1.0,
) -> list[ArquivoRecente]:
    """Os arquivos mexidos por último, sem entrar em .git, node_modules etc."""
    fim = time.monotonic() + prazo
    achados: list[tuple[float, str]] = []
    vistos = 0
    for pasta in pastas:
        raiz = Path(pasta)
        if not raiz.is_dir():
            continue
        pilha = [raiz]
        while pilha and vistos < max_vistos and time.monotonic() < fim:
            atual = pilha.pop()
            try:
                entradas = list(os.scandir(atual))
            except OSError:
                continue
            for entrada in entradas:
                vistos += 1
                try:
                    if entrada.is_dir(follow_symlinks=False):
                        if entrada.name not in _PULAR and not entrada.name.startswith(
                            "."
                        ):
                            pilha.append(Path(entrada.path))
                    elif entrada.is_file(follow_symlinks=False):
                        mtime = entrada.stat(follow_symlinks=False).st_mtime
                        rel = os.path.relpath(entrada.path, raiz)
                        achados.append((mtime, rel))
                except OSError:
                    continue
    achados.sort(reverse=True)
    return [ArquivoRecente(rel, mtime) for mtime, rel in achados[:limite]]


# ---------------------------------------------------------------------------
# Atividade (com intervalo mínimo entre gravações)
# ---------------------------------------------------------------------------

_ULTIMAS: dict[str, float] = {}
_ULTIMAS_LOCK = threading.Lock()


def registrar_atividade(
    projeto: Projeto,
    *,
    loja: Optional[Projetos] = None,
    intervalo: float = INTERVALO_GRAVACAO,
    relogio: Callable[[], float] = time.monotonic,
) -> bool:
    """Marca atividade no projeto, no máximo uma vez por *intervalo*.

    Devolve True se gravou. A primeira olhada é na memória (sem disco).
    """
    agora_s = relogio()
    with _ULTIMAS_LOCK:
        ultima = _ULTIMAS.get(projeto.id)
        if ultima is not None and agora_s - ultima < intervalo:
            return False
        _ULTIMAS[projeto.id] = agora_s
    try:
        (loja or Projetos()).tocar(projeto.id)
    except Exception:  # noqa: BLE001 — marcar atividade nunca atrapalha nada
        logger.debug("Não deu para marcar atividade no projeto", exc_info=True)
        return False
    return True


def esquecer_intervalos() -> None:
    """Para os testes."""
    with _ULTIMAS_LOCK:
        _ULTIMAS.clear()


# ---------------------------------------------------------------------------
# Observador da janela (servidor, só Windows)
# ---------------------------------------------------------------------------


@dataclass
class Observador:
    intervalo: float = INTERVALO_OBSERVADOR
    _parar: threading.Event = field(default_factory=threading.Event)
    _thread: Optional[threading.Thread] = None

    def iniciar(self) -> bool:
        if sys.platform != "win32" or self._thread is not None:
            return False
        self._parar.clear()
        self._thread = threading.Thread(
            target=self._laco, name="nicx-projetos", daemon=True
        )
        self._thread.start()
        return True

    def parar(self) -> None:
        self._parar.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    def _laco(self) -> None:
        while not self._parar.wait(self.intervalo):
            try:
                olhar_janela()
            except Exception:  # noqa: BLE001
                logger.debug("Observador de projetos falhou", exc_info=True)


def olhar_janela(loja: Optional[Projetos] = None) -> Optional[Projeto]:
    """Se a janela em uso é de um projeto, marca atividade nele."""
    loja = loja or Projetos()
    if not loja.caminho.exists():
        return None  # sem projetos, nem olha a janela
    projetos = loja.listar()
    projeto = projeto_da_janela(projetos)
    if projeto is not None:
        registrar_atividade(projeto, loja=loja)
    return projeto


_OBSERVADOR = Observador()


def iniciar_observador() -> bool:
    return _OBSERVADOR.iniciar()


def parar_observador() -> None:
    _OBSERVADOR.parar()


__all__ = [
    "ArquivoRecente",
    "Commit",
    "InfoGit",
    "Observador",
    "SinalJanela",
    "arquivos_recentes",
    "info_git",
    "iniciar_observador",
    "olhar_janela",
    "parar_observador",
    "pasta_do_vscode",
    "projeto_da_janela",
    "projeto_da_pasta_aberta",
    "projeto_do_caminho",
    "registrar_atividade",
    "sinal_da_janela",
]
