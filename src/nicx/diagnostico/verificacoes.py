"""As verificações do diagnóstico.

Todas são rápidas e não mudam nada: não abrem o microfone, não carregam a
voz nem o modelo, não mandam nada para fora do PC (o Ollama é local). Cada
uma devolve ``Verificacao`` com o estado (ok, aviso, falha), o que achou e,
quando há problema, o que fazer.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

OK = "ok"
AVISO = "aviso"
FALHA = "falha"

#: Versão do Ollama a partir da qual ele reaproveita a conversa (medido).
OLLAMA_RECOMENDADO = (0, 40, 14)
RAM_MINIMA_GB = 2.0
DISCO_MINIMO_GB = 5.0


@dataclass
class Verificacao:
    id: str
    estado: str
    mensagem: str
    dica: str = ""


def _versao(texto: str) -> tuple[int, ...]:
    partes = []
    for p in texto.strip().lstrip("v").split("."):
        num = "".join(c for c in p if c.isdigit())
        if not num:
            break
        partes.append(int(num))
    return tuple(partes)


# ------------------------------------------------------------------ Ollama


def _host(config: Any) -> str:
    from nicx.motores.ollama import _normalize_host

    host = ""
    try:
        host = config.engine.ollama.host
    except AttributeError:
        pass
    return _normalize_host(host or os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434")


def ollama(config: Any, http: Any = None) -> list[Verificacao]:
    """Ollama no ar, versão e modelo padrão baixado."""
    import httpx

    cliente = http or httpx.Client(base_url=_host(config), timeout=3.0)
    modelo = ""
    try:
        modelo = config.intelligence.default_model or ""
    except AttributeError:
        pass
    try:
        versao = cliente.get("/api/version").json().get("version", "")
        tags = cliente.get("/api/tags").json().get("models", [])
    except Exception:  # noqa: BLE001
        return [
            Verificacao(
                "ollama",
                AVISO,
                "O Ollama não está respondendo agora.",
                "Normal se o Nicx estiver fechado: ele liga o Ollama sozinho ao "
                "conversar. Se o chat não responder, reinstale o Ollama.",
            )
        ]
    finally:
        if http is None:
            cliente.close()
    resultado = []
    if _versao(versao) and _versao(versao) < OLLAMA_RECOMENDADO:
        resultado.append(
            Verificacao(
                "ollama",
                AVISO,
                f"Ollama {versao} funcionando, mas antigo.",
                "Atualize o Ollama (ollama.com/download ou 'winget upgrade "
                "Ollama.Ollama'): a partir da 0.40.14 ele reaproveita a conversa "
                "e o Nicx fica bem mais rápido.",
            )
        )
    else:
        resultado.append(
            Verificacao("ollama", OK, f"Ollama {versao or '?'} funcionando.")
        )
    nomes = {m.get("name", "") for m in tags} | {m.get("model", "") for m in tags}
    if not modelo:
        resultado.append(
            Verificacao(
                "modelo",
                AVISO,
                "Nenhum modelo padrão escolhido.",
                "Escolha um modelo no topo da conversa.",
            )
        )
    elif modelo in nomes or f"{modelo}:latest" in nomes:
        resultado.append(Verificacao("modelo", OK, f"Modelo {modelo} baixado."))
    else:
        resultado.append(
            Verificacao(
                "modelo",
                FALHA,
                f"O modelo {modelo} não está baixado.",
                f"Baixe com 'ollama pull {modelo}' ou escolha outro modelo no "
                "topo da conversa.",
            )
        )
    return resultado


# ---------------------------------------------------------------- sistema


def extensao_rust() -> Verificacao:
    if importlib.util.find_spec("nicx_rust") is not None:
        return Verificacao(
            "rust", OK, "Componente de segurança e ferramentas instalado."
        )
    return Verificacao(
        "rust",
        FALHA,
        "Falta o componente nicx_rust: os agentes com ferramentas não funcionam.",
        "Reinstale o Nicx (o instalador traz o componente pronto).",
    )


def memoria_ram(psutil_mod: Any = None) -> Verificacao:
    try:
        ps = psutil_mod or __import__("psutil")
        livre = ps.virtual_memory().available / 1024**3
        total = ps.virtual_memory().total / 1024**3
    except Exception:  # noqa: BLE001
        return Verificacao("ram", AVISO, "Não deu para ler a memória do PC.")
    texto = f"{livre:.1f} GB livres de {total:.0f} GB."
    if livre < RAM_MINIMA_GB:
        return Verificacao(
            "ram",
            AVISO,
            texto,
            "Pouca memória livre: feche abas e programas pesados antes de usar o "
            "modo Trabalho ou a voz, senão o PC pode travar.",
        )
    return Verificacao("ram", OK, texto)


def disco(pasta: Path) -> Verificacao:
    try:
        livre = (
            shutil.disk_usage(pasta if pasta.exists() else pasta.anchor).free / 1024**3
        )
    except OSError:
        return Verificacao("disco", AVISO, "Não deu para ler o espaço em disco.")
    texto = f"{livre:.0f} GB livres no disco do Nicx."
    if livre < DISCO_MINIMO_GB:
        return Verificacao(
            "disco",
            AVISO,
            texto,
            "Libere espaço: atualizações e modelos precisam de alguns GB.",
        )
    return Verificacao("disco", OK, texto)


def pasta_gravavel(pasta: Path) -> Verificacao:
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=pasta, prefix=".teste-", delete=True) as f:
            f.write(b"ok")
    except OSError as exc:
        return Verificacao(
            "pasta",
            FALHA,
            f"O Nicx não consegue gravar em {pasta}: {exc.strerror or exc}.",
            "Confira se a pasta não está só leitura ou bloqueada pelo antivírus.",
        )
    return Verificacao("pasta", OK, f"Dados em {pasta} (gravando normalmente).")


# -------------------------------------------------------------------- voz


def microfone(sd_mod: Any = None) -> Verificacao:
    """Só lista os dispositivos; não abre o microfone."""
    try:
        sd = sd_mod or __import__("sounddevice")
        entradas = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
    except Exception:  # noqa: BLE001
        return Verificacao(
            "microfone",
            AVISO,
            "Não deu para listar os microfones (o suporte de voz não está instalado).",
            "A voz é opcional: instale com o componente de voz do instalador.",
        )
    if not entradas:
        return Verificacao(
            "microfone",
            AVISO,
            "Nenhum microfone encontrado.",
            "Conecte um microfone ou confira em Configurações do Windows > "
            "Privacidade > Microfone.",
        )
    try:
        padrao = sd.query_devices(kind="input").get("name", "")
    except Exception:  # noqa: BLE001
        padrao = entradas[0].get("name", "")
    return Verificacao(
        "microfone",
        OK,
        f"{len({d.get('name', '') for d in entradas})} microfone(s); padrão: {padrao}.",
    )


def voz(achar: Callable[[str], Any] = importlib.util.find_spec) -> Verificacao:
    ouvir = achar("faster_whisper") is not None
    falar = achar("kokoro") is not None
    if ouvir and falar:
        return Verificacao("voz", OK, "Ouvir (Whisper) e falar (Kokoro) instalados.")
    faltam = [n for n, ok in (("ouvir", ouvir), ("falar", falar)) if not ok]
    return Verificacao(
        "voz",
        AVISO,
        f"Voz incompleta: falta {' e '.join(faltam)}.",
        "A voz é opcional: reinstale o Nicx marcando o componente de voz.",
    )


# ---------------------------------------------------------------- atalhos


_NOMES_ATALHO = {
    "atalho": "atalho do Nicx",
    "ditado": "ditado",
    "captura": "captura rápida",
}


def atalhos(estado: Any) -> list[Verificacao]:
    """Estado dos atalhos globais ligados (app.state do servidor)."""
    resultado = []
    for chave, nome in _NOMES_ATALHO.items():
        gerenciador = getattr(estado, chave, None) if estado is not None else None
        if gerenciador is None or not hasattr(gerenciador, "status"):
            continue
        try:
            st = gerenciador.status()
        except Exception:  # noqa: BLE001
            continue
        situacao = st.get("estado", "")
        if situacao in ("", "desligado", "sem_suporte"):
            continue
        if situacao in ("em_uso", "erro", "invalido"):
            resultado.append(
                Verificacao(
                    f"atalho_{chave}",
                    AVISO,
                    f"O {nome} não funciona: {st.get('mensagem') or situacao}.",
                    "Escolha outra combinação de teclas nas Configurações.",
                )
            )
        else:
            resultado.append(
                Verificacao(f"atalho_{chave}", OK, f"O {nome} está pronto.")
            )
    return resultado


# --------------------------------------------------------------- histórico


def historico() -> Verificacao:
    try:
        from nicx.historico.registro import registro

        r = registro().verificar()
    except Exception as exc:  # noqa: BLE001
        return Verificacao(
            "historico", AVISO, f"Não deu para conferir o histórico: {exc}."
        )
    if r.get("ok"):
        return Verificacao(
            "historico", OK, f"Histórico íntegro ({r.get('linhas', 0)} registros)."
        )
    return Verificacao(
        "historico",
        AVISO,
        "O histórico foi alterado fora do Nicx "
        f"(a partir do registro {r.get('quebra_em')}).",
        "Se não foi você, confira quem mexe na pasta do Nicx.",
    )


# ------------------------------------------------------------------- todas


def rodar(config: Any = None, estado: Any = None, pasta: Optional[Path] = None) -> dict:
    """Roda tudo (em paralelo, com teto de tempo) e resume."""
    if config is None:
        from nicx.nucleo.config import load_config

        config = load_config()
    if pasta is None:
        from nicx.nucleo.paths import get_config_dir

        pasta = get_config_dir()
    inicio = time.monotonic()
    tarefas: list[Callable[[], Any]] = [
        lambda: ollama(config),
        extensao_rust,
        memoria_ram,
        lambda: disco(pasta),
        lambda: pasta_gravavel(pasta),
        microfone,
        voz,
        lambda: atalhos(estado),
        historico,
    ]
    verificacoes: list[Verificacao] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for futuro in [pool.submit(t) for t in tarefas]:
            try:
                r = futuro.result(timeout=10)
            except Exception as exc:  # noqa: BLE001 - uma verificação quebrada não derruba as outras
                logger.debug("Diagnóstico: verificação falhou", exc_info=True)
                r = Verificacao("erro", AVISO, f"Uma verificação falhou: {exc}")
            verificacoes.extend(r if isinstance(r, list) else [r])
    contagem = {
        e: sum(1 for v in verificacoes if v.estado == e) for e in (OK, AVISO, FALHA)
    }
    return {
        "verificacoes": [asdict(v) for v in verificacoes],
        "resumo": contagem,
        "segundos": round(time.monotonic() - inicio, 2),
    }


__all__ = ["AVISO", "FALHA", "OK", "Verificacao", "rodar"]
