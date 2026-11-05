"""Procurar, baixar e instalar atualizações do Nicx.

- :func:`verificar`: baixa o arquivo de versões (até 1 MB), confere a
  assinatura (:mod:`manifesto`) e guarda em ``~/.nicx/atualizacao.json``.
- :func:`baixar`: baixa o instalador numa thread para
  ``~/.nicx/atualizacoes/``, conferindo tamanho e sha256 do arquivo de versões.
- :func:`instalar`: confere o arquivo de novo e abre o instalador em modo
  silencioso por cima da instalação atual (``/REABRIR=1``: o Nicx volta
  sozinho). O instalador para o servidor antes de trocar os arquivos; por isso
  ele sai por ``cmd /c start``, fora da árvore de processos do servidor (o
  ``nicx stop`` encerra a árvore inteira).
- :func:`ligar_verificacao_diaria`: uma vez por dia, se ``[atualizacao]
  automatica``; avisa com uma notificação quando acha versão nova.

Só a instalação pelo ``NicxSetup.exe`` se atualiza pelo app. Num clone do git
(Mac, Linux, desenvolvimento) a página mostra ``nicx self-update``.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import nicx
from nicx.atualizacao import manifesto

logger = logging.getLogger(__name__)

MAX_MANIFESTO = 1024 * 1024
INTERVALO_S = 24 * 3600
_ESPERA_INICIAL_S = 120.0

_LOCK = threading.RLock()
_DOWNLOAD: dict[str, Any] = {
    "baixando": False,
    "progresso": 0.0,
    "erro": None,
    "arquivo": None,
    "versao": None,
}
_THREAD: Optional[threading.Thread] = None
_PARAR = threading.Event()


class AtualizacaoErro(RuntimeError):
    """Algo que impede atualizar agora; a mensagem diz por quê (em português)."""


# --------------------------------------------------------------------- lugar


def _pasta() -> Path:
    from nicx.nucleo.paths import get_config_dir

    return get_config_dir()


def _arquivo_estado() -> Path:
    return _pasta() / "atualizacao.json"


def pasta_downloads() -> Path:
    return _pasta() / "atualizacoes"


def versao_atual() -> str:
    return str(nicx.__version__)


def instalacao() -> str:
    """Como o Nicx foi instalado.

    ``windows`` (NicxSetup.exe), ``git`` (clone: ``nicx self-update``) ou ``outro``.
    """
    if sys.platform == "win32":
        app = Path(sys.prefix).resolve().parent
        if (app / "unins000.exe").is_file() and (app / "setup").is_dir():
            return "windows"
    try:
        from nicx.comandos.instalacao._install_detect import detect_install

        if detect_install().kind == "editable-git":
            return "git"
    except Exception:  # noqa: BLE001 - só muda o texto da página
        logger.debug("Não deu para saber como o Nicx foi instalado", exc_info=True)
    return "outro"


def _config() -> Any:
    try:
        from nicx.nucleo.config import load_config

        return load_config().atualizacao
    except Exception:  # noqa: BLE001
        from nicx.nucleo.config import AtualizacaoConfig

        return AtualizacaoConfig()


def _url(config: Any = None) -> str:
    cfg = config if config is not None else _config()
    return (getattr(cfg, "url", "") or "").strip() or manifesto.URL_PADRAO


# ------------------------------------------------------------------- estado


def _ler_guardado() -> dict[str, Any]:
    try:
        return json.loads(_arquivo_estado().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar(dados: dict[str, Any]) -> None:
    arquivo = _arquivo_estado()
    try:
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        temporario.replace(arquivo)
    except OSError:
        logger.warning("Não consegui guardar o estado das atualizações", exc_info=True)


def _ultima() -> Optional[dict[str, Any]]:
    """O arquivo de versões guardado, conferido de novo (pode ter sido mexido)."""
    assinado = _ler_guardado().get("assinado")
    if not assinado:
        return None
    try:
        return manifesto.ler(assinado)
    except manifesto.ManifestoInvalido:
        return None


def estado(config: Any = None) -> dict[str, Any]:
    from nicx.atualizacao.novidades import NOVIDADES

    cfg = config if config is not None else _config()
    guardado = _ler_guardado()
    ultima = _ultima()
    atual = versao_atual()
    tipo = instalacao()
    ha_nova = bool(ultima and manifesto.mais_nova(ultima["versao"], atual))
    with _LOCK:
        download = dict(_DOWNLOAD)
    pronto = bool(
        ha_nova
        and download["arquivo"]
        and download["versao"] == (ultima or {}).get("versao")
        and not download["baixando"]
    )
    # Novidades: as do arquivo de versões (trazem as que ainda não chegaram)
    # ou, sem ele, as que vieram com este Nicx.
    novidades = (ultima or {}).get("novidades") or NOVIDADES
    return {
        "versao_atual": atual,
        "instalacao": tipo,
        "pode_instalar": tipo == "windows",
        "automatica": bool(getattr(cfg, "automatica", True)),
        "verificado_em": guardado.get("verificado_em"),
        "erro": guardado.get("erro"),
        "ultima": (
            {
                "versao": ultima["versao"],
                "publicado_em": ultima.get("publicado_em", ""),
                "tamanho": (ultima.get("windows") or {}).get("tamanho"),
                "comando_mac": (ultima.get("mac") or {}).get("comando", ""),
            }
            if ultima
            else None
        ),
        "ha_nova": ha_nova,
        "baixando": download["baixando"],
        "progresso": round(float(download["progresso"]), 3),
        "erro_download": download["erro"],
        "pronto_para_instalar": pronto,
        "novidades": novidades,
        "comando_git": "nicx self-update",
    }


# --------------------------------------------------------------- verificar


def verificar(config: Any = None, *, cliente: Any = None) -> dict[str, Any]:
    """Baixa e confere o arquivo de versões. Erro de rede fica no estado."""
    import httpx

    cfg = config if config is not None else _config()
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    guardado = _ler_guardado()
    try:
        dono = cliente or httpx.Client(timeout=20.0, follow_redirects=True)
        try:
            with dono.stream("GET", _url(cfg)) as resp:
                if resp.status_code == 404:
                    raise AtualizacaoErro("nenhuma versão publicada ainda")
                resp.raise_for_status()
                corpo = b""
                for parte in resp.iter_bytes():
                    corpo += parte
                    if len(corpo) > MAX_MANIFESTO:
                        raise AtualizacaoErro("o arquivo de versões veio grande demais")
        finally:
            if cliente is None:
                dono.close()
        assinado = json.loads(corpo.decode("utf-8"))
        manifesto.ler(assinado)
    except (httpx.HTTPError, OSError) as exc:
        logger.info("Não consegui procurar atualização: %s", type(exc).__name__)
        guardado.update(
            verificado_em=agora, erro="sem conexão com o servidor de versões"
        )
        _guardar(guardado)
        return estado(cfg)
    except (AtualizacaoErro, manifesto.ManifestoInvalido, ValueError) as exc:
        logger.warning("Arquivo de versões recusado: %s", exc)
        guardado.update(verificado_em=agora, erro=str(exc))
        _guardar(guardado)
        return estado(cfg)
    _guardar({"verificado_em": agora, "erro": None, "assinado": assinado})
    return estado(cfg)


# ------------------------------------------------------------------ baixar


def _destino(versao: str, nome: str) -> Path:
    base = Path(nome).stem
    return pasta_downloads() / f"{base}-{versao}.exe"


def _limpar_antigos(manter: Optional[Path]) -> None:
    pasta = pasta_downloads()
    if not pasta.is_dir():
        return
    for item in pasta.iterdir():
        if manter is not None and item.resolve() == manter.resolve():
            continue
        try:
            item.unlink()
        except OSError:
            logger.debug("Não apaguei %s", item.name, exc_info=True)


def _baixar_agora(win: dict[str, Any], versao: str, cliente: Any = None) -> None:
    import hashlib

    import httpx

    destino = _destino(versao, win["arquivo"])
    parcial = destino.with_suffix(".part")
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        _limpar_antigos(None)
        h = hashlib.sha256()
        recebido = 0
        dono = cliente or httpx.Client(timeout=60.0, follow_redirects=True)
        try:
            with dono.stream("GET", win["url"]) as resp, parcial.open("wb") as saida:
                resp.raise_for_status()
                for bloco in resp.iter_bytes(1024 * 256):
                    recebido += len(bloco)
                    if recebido > win["tamanho"]:
                        raise AtualizacaoErro("o instalador veio maior que o anunciado")
                    h.update(bloco)
                    saida.write(bloco)
                    with _LOCK:
                        _DOWNLOAD["progresso"] = recebido / win["tamanho"]
        finally:
            if cliente is None:
                dono.close()
        if recebido != win["tamanho"] or h.hexdigest() != win["sha256"]:
            raise AtualizacaoErro(
                "o instalador baixado não é o que a Falkyria publicou; tente de novo"
            )
        parcial.replace(destino)
        with _LOCK:
            _DOWNLOAD.update(
                arquivo=str(destino), versao=versao, progresso=1.0, erro=None
            )
    except (httpx.HTTPError, OSError) as exc:
        logger.info("Download da atualização falhou: %s", type(exc).__name__)
        with _LOCK:
            _DOWNLOAD.update(
                erro="o download falhou; confira a internet e tente de novo"
            )
    except AtualizacaoErro as exc:
        with _LOCK:
            _DOWNLOAD.update(erro=str(exc))
    finally:
        parcial.unlink(missing_ok=True)
        with _LOCK:
            _DOWNLOAD["baixando"] = False


def baixar(*, esperar: bool = False, cliente: Any = None) -> dict[str, Any]:
    if instalacao() != "windows":
        raise AtualizacaoErro("esta instalação não se atualiza pelo app")
    ultima = _ultima()
    if not ultima or not manifesto.mais_nova(ultima["versao"], versao_atual()):
        raise AtualizacaoErro("não há versão nova para baixar")
    win = ultima.get("windows")
    if not win:
        raise AtualizacaoErro("a versão nova não tem instalador para Windows")
    with _LOCK:
        if _DOWNLOAD["baixando"]:
            return estado()
        _DOWNLOAD.update(
            baixando=True, progresso=0.0, erro=None, arquivo=None, versao=None
        )
    trabalho = threading.Thread(
        target=_baixar_agora,
        args=(win, ultima["versao"], cliente),
        name="nicx-atualizacao-download",
        daemon=True,
    )
    trabalho.start()
    if esperar:
        trabalho.join()
    return estado()


# ----------------------------------------------------------------- instalar


def _abrir_instalador(exe: Path, log: Path) -> None:
    """Abre o instalador fora da árvore do servidor (``cmd /c start``)."""
    texto = str(exe)
    if '"' in texto or '"' in str(log):
        raise AtualizacaoErro("caminho do instalador inválido")
    argumentos = f'/SILENT /SUPPRESSMSGBOXES /NORESTART /REABRIR=1 /LOG="{log}"'
    linha = f'cmd.exe /d /c start "" "{texto}" {argumentos}'
    subprocess.Popen(  # noqa: S602 - linha montada aqui, sem nada do usuário
        linha,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
        cwd=str(exe.parent),
    )


def instalar(abrir: Optional[Callable[[Path, Path], None]] = None) -> dict[str, Any]:
    if instalacao() != "windows":
        raise AtualizacaoErro("esta instalação não se atualiza pelo app")
    ultima = _ultima()
    with _LOCK:
        arquivo = _DOWNLOAD["arquivo"]
        versao = _DOWNLOAD["versao"]
    if not ultima or not arquivo or versao != ultima["versao"]:
        raise AtualizacaoErro("baixe a atualização antes de instalar")
    exe = Path(arquivo)
    win = ultima["windows"]
    # De novo, logo antes de abrir: o arquivo não pode ter mudado na pasta.
    if not exe.is_file() or manifesto.sha256_do_arquivo(exe) != win["sha256"]:
        with _LOCK:
            _DOWNLOAD.update(arquivo=None, versao=None)
        raise AtualizacaoErro("o instalador baixado mudou; baixe de novo")
    log = pasta_downloads() / f"instalacao-{versao}.log"
    (abrir or _abrir_instalador)(exe, log)
    logger.info("Atualização para a %s iniciada", versao)
    return {"ok": True, "versao": versao}


# ---------------------------------------------------- verificação diária


def _precisa_verificar(agora: float) -> bool:
    quando = _ler_guardado().get("verificado_em")
    if not quando:
        return True
    try:
        ultima = datetime.fromisoformat(quando).timestamp()
    except ValueError:
        return True
    return agora - ultima >= INTERVALO_S


def _avisar_se_nova(antes: Optional[str]) -> None:
    ultima = _ultima()
    if not ultima or not manifesto.mais_nova(ultima["versao"], versao_atual()):
        return
    if ultima["versao"] == antes:
        return  # já avisou desta versão
    try:
        from nicx.acoes.lembretes import show_notification

        show_notification(
            f"Nicx {ultima['versao']} disponível. "
            "Abra Atualizações no app para instalar."
        )
    except Exception:  # noqa: BLE001 - o aviso é só um extra
        logger.debug("Aviso de atualização não mostrado", exc_info=True)


def _laco() -> None:
    if _PARAR.wait(_ESPERA_INICIAL_S):
        return
    while not _PARAR.is_set():
        try:
            cfg = _config()
            if getattr(cfg, "automatica", True) and _precisa_verificar(time.time()):
                antes = (_ultima() or {}).get("versao")
                verificar(cfg)
                _avisar_se_nova(antes)
        except Exception:  # noqa: BLE001 - o laço não pode morrer
            logger.debug("Verificação de atualização falhou", exc_info=True)
        if _PARAR.wait(3600):
            return


def ligar_verificacao_diaria() -> None:
    global _THREAD
    if os.environ.get("NICX_NO_UPDATE_CHECK") == "1":
        return
    with _LOCK:
        if _THREAD is not None and _THREAD.is_alive():
            return
        _PARAR.clear()
        _THREAD = threading.Thread(target=_laco, name="nicx-atualizacao", daemon=True)
        _THREAD.start()


def desligar_verificacao_diaria() -> None:
    _PARAR.set()


__all__ = [
    "AtualizacaoErro",
    "baixar",
    "desligar_verificacao_diaria",
    "estado",
    "instalacao",
    "instalar",
    "ligar_verificacao_diaria",
    "pasta_downloads",
    "verificar",
    "versao_atual",
]
