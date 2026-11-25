"""Exportar todos os meus dados (LGPD, art. 18): um .zip com o que o Nicx guarda.

Vai tudo o que está em ``~/.nicx`` e é da pessoa: memória, histórico, notas,
lembretes, agenda, projetos, assistentes, rotinas, habilidades, tarefas do modo
Trabalho, configuração e os bancos SQLite (copiados de forma consistente, sem
parar o Nicx). As conversas ficam no navegador: o app as manda junto.

Não vai o que é segredo (cofre da conta, chaves, tokens de conectores, sessão
do WhatsApp) nem o que é só cache ou arquivo temporário. O ``mcp.json`` e o
``config.toml`` vão com os valores secretos trocados por ``••••••``.
"""

from __future__ import annotations

import io
import json
import logging
import re
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MASCARA = "••••••"
MAX_ARQUIVO = 50 * 1024 * 1024

#: Segredos: nunca saem, nem mascarados.
SEGREDOS_ARQUIVOS = {
    "conta.bin",
    ".vault_key",
    "cloud-keys.env",
    "credentials.toml",
    "server.identity.json",
}
SEGREDOS_PASTAS = {"connectors", "whatsapp_baileys_bridge"}
#: Cache, temporários e cópias internas: não são dados da pessoa.
IGNORADAS_PASTAS = {
    "cache",
    "skill-cache",
    "skill-index",
    "webview-mascote",
    ".scripts",
    "desfazer",
    "copias",
    "lixeira",
    "__pycache__",
}
IGNORADOS_SUFIXOS = (".lock", ".pid", ".log", "-wal", "-shm", ".tmp")
IGNORADOS_ARQUIVOS = {"server.json", "first_chat_sent"}

_CHAVE_SECRETA = re.compile(
    r"(?i)^(\s*[\w.\-]*(?:key|token|secret|password|senha|apikey)[\w.\-]*\s*=\s*)(.+)$"
)

LEIA_ME = """Seus dados do Nicx ({quando})
==============================

Este arquivo tem tudo o que o Nicx guarda sobre você neste computador:

- conversas.json: suas conversas (estavam guardadas no app).
- dados/: a pasta do Nicx (~/.nicx), com memória (memory.db, MEMORY.md, USER.md),
  histórico (historico.db), notas (notas.md), lembretes, agenda, projetos,
  assistentes, rotinas, habilidades (skills/), tarefas do modo Trabalho
  (trabalho/) e a configuração (config.toml).
- Os arquivos .db são bancos SQLite: abrem em qualquer leitor de SQLite.

Não vão, por segurança: o cofre da Conta Falkyria, chaves e tokens de
conectores e a sessão do WhatsApp. Chaves dentro de config.toml e mcp.json
aparecem como ••••••.
{fora}
O Nicx roda no seu PC: nada disso foi enviado a ninguém para gerar este arquivo.
Um produto Falkyria.
"""


def _ignorar(rel: Path) -> Optional[str]:
    """Motivo para deixar de fora (None = vai)."""
    partes = rel.parts
    if partes and partes[0] in SEGREDOS_PASTAS:
        return "segredo"
    if rel.name in SEGREDOS_ARQUIVOS:
        return "segredo"
    if any(p in IGNORADAS_PASTAS for p in partes[:-1]):
        return "cache"
    if rel.name in IGNORADOS_ARQUIVOS or rel.name.endswith(IGNORADOS_SUFIXOS):
        return "cache"
    return None


def _config_mascarada(p: Path) -> bytes:
    linhas = []
    for linha in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _CHAVE_SECRETA.match(linha)
        if m and m.group(2).strip() not in ('""', "''"):
            linha = f'{m.group(1)}"{MASCARA}"'
        linhas.append(linha)
    return ("\n".join(linhas) + "\n").encode("utf-8")


def _mcp_mascarado() -> bytes:
    from nicx.extensoes import mcp

    try:
        servidores = [mcp.publico(s) for s in mcp.listar()]
    except Exception:  # noqa: BLE001
        servidores = []
    return json.dumps({"servidores": servidores}, ensure_ascii=False, indent=2).encode(
        "utf-8"
    )


def _sqlite(p: Path) -> bytes:
    """Cópia consistente (inclui o que ainda está no WAL) sem travar o Nicx."""
    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / p.name
        origem = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            copia = sqlite3.connect(destino)
            try:
                origem.backup(copia)
            finally:
                copia.close()
        finally:
            origem.close()
        return destino.read_bytes()


def montar(conversas: Any = None, raiz: Optional[Path] = None) -> tuple[bytes, dict]:
    """O .zip (em memória) e um resumo do que entrou e do que ficou de fora."""
    if raiz is None:
        from nicx.nucleo.paths import get_config_dir

        raiz = get_config_dir()
    raiz = Path(raiz)
    agora = datetime.now()
    resumo: dict[str, Any] = {"arquivos": 0, "bytes": 0, "fora": []}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        if conversas is not None:
            texto = (
                conversas
                if isinstance(conversas, str)
                else json.dumps(conversas, ensure_ascii=False, indent=2)
            )
            z.writestr("conversas.json", texto.encode("utf-8"))
            resumo["arquivos"] += 1
        if raiz.is_dir():
            for p in sorted(raiz.rglob("*")):
                if not p.is_file() or p.is_symlink():
                    continue
                rel = p.relative_to(raiz)
                motivo = _ignorar(rel)
                if motivo:
                    if motivo == "segredo":
                        resumo["fora"].append(rel.as_posix())
                    continue
                try:
                    if p.stat().st_size > MAX_ARQUIVO:
                        resumo["fora"].append(f"{rel.as_posix()} (grande demais)")
                        continue
                    if rel.as_posix() == "mcp.json":
                        dados = _mcp_mascarado()
                    elif rel.as_posix() == "config.toml":
                        dados = _config_mascarada(p)
                    elif p.suffix == ".db":
                        dados = _sqlite(p)
                    else:
                        dados = p.read_bytes()
                except (OSError, sqlite3.Error) as exc:
                    logger.debug("Exportação: %s ficou de fora (%s)", rel, exc)
                    resumo["fora"].append(f"{rel.as_posix()} (não deu para ler)")
                    continue
                z.writestr(f"dados/{rel.as_posix()}", dados)
                resumo["arquivos"] += 1
                resumo["bytes"] += len(dados)
        fora = ""
        if resumo["fora"]:
            fora = "\nFicaram de fora:\n" + "".join(f"- {f}\n" for f in resumo["fora"])
        z.writestr(
            "LEIA-ME.txt",
            LEIA_ME.format(quando=agora.strftime("%d/%m/%Y %H:%M"), fora=fora).encode(
                "utf-8"
            ),
        )
    return buffer.getvalue(), resumo


__all__ = ["montar"]
