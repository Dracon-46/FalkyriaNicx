"""O que vai no backup da Conta Falkyria e como volta.

Vai: assistentes, rotinas, habilidades e servidores MCP (sem token nem valores
de variáveis) e a lista de pacotes instalados. Não vai: conversas, memória,
notas, arquivos, histórico. O formato é o de um pacote (``nicx.extensoes.pacotes``),
então restaurar passa pela mesma validação de qualquer pacote.
"""

from __future__ import annotations

from typing import Any

from nicx.extensoes import pacotes

ID = "backup-da-conta"


class BackupVazio(ValueError):
    """Nada para guardar."""


def montar() -> dict[str, Any]:
    from nicx.assistentes import armazenamento as assistentes
    from nicx.extensoes import habilidades, mcp
    from nicx.rotinas import armazenamento as rotinas

    try:
        pacote = pacotes.exportar(
            ID,
            "Backup da Conta Falkyria",
            assistentes_ids=[a.id for a in assistentes.listar()],
            rotinas_ids=[r.id for r in rotinas.listar()],
            habilidades_nomes=[h.nome for h in habilidades.listar()],
            mcp_ids=[s.id for s in mcp.listar()],
        )
    except pacotes.PacoteInvalido as exc:
        raise BackupVazio(
            "ainda não há assistentes, rotinas, habilidades ou servidores para guardar"
        ) from exc
    pacote["pacotes_instalados"] = [
        {k: p.get(k) for k in ("id", "nome", "versao", "pronto", "loja")}
        for p in pacotes.instalados()
    ]
    return pacote


def resumo(pacote: dict[str, Any]) -> dict[str, int]:
    return {
        k: len(pacote.get(k) or [])
        for k in ("assistentes", "rotinas", "habilidades", "mcp", "pacotes_instalados")
    }


def aplicar(conteudo: str) -> dict[str, Any]:
    """Põe de volta o que não existe neste PC (o que já existe fica como está)."""
    pacote = pacotes.ler(conteudo)
    resultado = pacotes.instalar(pacote, com_mcp=True, pular_existentes=True)
    # Restaurado vira do usuário, não de um pacote: sai do registro de pacotes.
    pacotes.esquecer(ID)
    return resultado


__all__ = ["ID", "BackupVazio", "aplicar", "montar", "resumo"]
