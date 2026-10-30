"""Registro único de atividades do Nicx (histórico universal e auditoria).

Uma linha por coisa que aconteceu: conversa, nota, lembrete, compromisso,
projeto, arquivo, organização de pasta, ação no PC ou ferramenta do modelo.
Fica só no PC, em ``~/.nicx/historico.db`` (SQLite + busca FTS5). Cada linha
leva o hash da anterior, então uma edição por fora do Nicx aparece na
verificação de integridade.

Anotar nunca levanta: se o banco falhar, o Nicx segue funcionando e só o
histórico fica sem aquela linha.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

TIPOS = (
    "conversa",
    "nota",
    "lembrete",
    "agenda",
    "projeto",
    "arquivo",
    "organizacao",
    "acao",
    "ferramenta",
    "desfazer",
)
# Resultados possíveis de uma linha
OK, FALHOU, BLOQUEADO, PENDENTE = "ok", "falhou", "bloqueado", "pendente"

# Quem pediu: definido por quem atende o pedido (chat, voz, agente...).
_origem: contextvars.ContextVar[str] = contextvars.ContextVar(
    "nicx_origem", default="app"
)


@contextmanager
def origem(nome: str) -> Iterator[None]:
    """Marca a origem das atividades anotadas dentro do bloco."""
    token = _origem.set(nome)
    try:
        yield
    finally:
        _origem.reset(token)


def origem_atual() -> str:
    return _origem.get()


def definir_origem(nome: str) -> None:
    """Marca a origem até o fim do contexto atual (um pedido HTTP, uma thread)."""
    _origem.set(nome)


@dataclass
class Atividade:
    id: int
    quando: str
    tipo: str
    titulo: str
    origem: str = "app"
    resultado: str = OK
    nivel: str = ""
    detalhe: dict[str, Any] = field(default_factory=dict)
    desfazer: Optional[dict[str, Any]] = None
    desfeito_em: Optional[str] = None

    @property
    def desfazivel(self) -> bool:
        return (
            self.desfazer is not None
            and self.desfeito_em is None
            and self.resultado == OK
        )

    def para_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "quando": self.quando,
            "tipo": self.tipo,
            "titulo": self.titulo,
            "origem": self.origem,
            "resultado": self.resultado,
            "nivel": self.nivel,
            "detalhe": self.detalhe,
            "desfazivel": self.desfazivel,
            "desfeito_em": self.desfeito_em,
        }


_SCHEMA = """
CREATE TABLE IF NOT EXISTS atividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    origem TEXT NOT NULL DEFAULT 'app',
    resultado TEXT NOT NULL DEFAULT 'ok',
    nivel TEXT NOT NULL DEFAULT '',
    detalhe TEXT NOT NULL DEFAULT '{}',
    desfazer TEXT,
    desfeito_em TEXT,
    hash_anterior TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS atividades_quando ON atividades(quando);
CREATE INDEX IF NOT EXISTS atividades_tipo ON atividades(tipo);
CREATE VIRTUAL TABLE IF NOT EXISTS atividades_busca USING fts5(
    titulo, detalhe, content='atividades', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS atividades_ai AFTER INSERT ON atividades BEGIN
    INSERT INTO atividades_busca(rowid, titulo, detalhe)
    VALUES (new.id, new.titulo, new.detalhe);
END;
CREATE TRIGGER IF NOT EXISTS atividades_ad AFTER DELETE ON atividades BEGIN
    INSERT INTO atividades_busca(atividades_busca, rowid, titulo, detalhe)
    VALUES ('delete', old.id, old.titulo, old.detalhe);
END;
"""


def _hash(
    anterior: str,
    quando: str,
    tipo: str,
    titulo: str,
    origem: str,
    resultado: str,
    detalhe: str,
) -> str:
    base = "\x1f".join((anterior, quando, tipo, titulo, origem, resultado, detalhe))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class Registro:
    """O banco do histórico. Seguro para várias threads."""

    def __init__(self, caminho: str | Path) -> None:
        self.caminho = Path(caminho)
        self._lock = threading.Lock()
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(
            str(self.caminho), check_same_thread=False, timeout=10
        )
        self._con.row_factory = sqlite3.Row
        with self._lock:
            self._con.execute("PRAGMA journal_mode=WAL")
            self._con.executescript(_SCHEMA)
            self._con.commit()

    # ------------------------------------------------------------------ escrita
    def anotar(
        self,
        tipo: str,
        titulo: str,
        *,
        detalhe: Optional[dict[str, Any]] = None,
        resultado: str = OK,
        nivel: str = "",
        desfazer: Optional[dict[str, Any]] = None,
        origem: Optional[str] = None,
        quando: Optional[datetime] = None,
    ) -> int:
        """Grava uma atividade e devolve o id."""
        quando_txt = (quando or datetime.now()).isoformat(timespec="seconds")
        origem = origem or origem_atual()
        detalhe_txt = json.dumps(detalhe or {}, ensure_ascii=False, default=str)
        titulo = titulo.strip()[:300] or tipo
        with self._lock:
            ultima = self._con.execute(
                "SELECT hash FROM atividades ORDER BY id DESC LIMIT 1"
            ).fetchone()
            anterior = ultima["hash"] if ultima else ""
            h = _hash(
                anterior, quando_txt, tipo, titulo, origem, resultado, detalhe_txt
            )
            cur = self._con.execute(
                "INSERT INTO atividades (quando, tipo, titulo, origem, resultado,"
                " nivel, detalhe, desfazer, hash_anterior, hash)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    quando_txt,
                    tipo,
                    titulo,
                    origem,
                    resultado,
                    nivel,
                    detalhe_txt,
                    json.dumps(desfazer, ensure_ascii=False, default=str)
                    if desfazer
                    else None,
                    anterior,
                    h,
                ),
            )
            self._con.commit()
            return int(cur.lastrowid or 0)

    def marcar_desfeito(
        self, atividade_id: int, quando: Optional[datetime] = None
    ) -> None:
        with self._lock:
            self._con.execute(
                "UPDATE atividades SET desfeito_em = ? WHERE id = ?",
                (
                    (quando or datetime.now()).isoformat(timespec="seconds"),
                    atividade_id,
                ),
            )
            self._con.commit()

    def limpar_antigas(self, dias: int) -> int:
        """Apaga atividades mais velhas que ``dias`` (0 = guarda tudo)."""
        if dias <= 0:
            return 0
        limite = (datetime.now() - timedelta(days=dias)).isoformat(timespec="seconds")
        with self._lock:
            cur = self._con.execute(
                "DELETE FROM atividades WHERE quando < ?", (limite,)
            )
            self._con.commit()
            return cur.rowcount

    # ------------------------------------------------------------------ leitura
    @staticmethod
    def _linha(row: sqlite3.Row) -> Atividade:
        def _json(texto: Optional[str]) -> Any:
            if not texto:
                return None
            try:
                return json.loads(texto)
            except ValueError:
                return None

        return Atividade(
            id=row["id"],
            quando=row["quando"],
            tipo=row["tipo"],
            titulo=row["titulo"],
            origem=row["origem"],
            resultado=row["resultado"],
            nivel=row["nivel"],
            detalhe=_json(row["detalhe"]) or {},
            desfazer=_json(row["desfazer"]),
            desfeito_em=row["desfeito_em"],
        )

    def obter(self, atividade_id: int) -> Optional[Atividade]:
        with self._lock:
            row = self._con.execute(
                "SELECT * FROM atividades WHERE id = ?", (atividade_id,)
            ).fetchone()
        return self._linha(row) if row else None

    def listar(
        self,
        *,
        busca: str = "",
        tipos: Optional[list[str]] = None,
        desde: Optional[datetime] = None,
        ate: Optional[datetime] = None,
        so_desfaziveis: bool = False,
        limite: int = 100,
        antes_de: Optional[int] = None,
    ) -> list[Atividade]:
        """Atividades mais recentes primeiro, com filtros opcionais."""
        sql = "SELECT a.* FROM atividades a"
        where: list[str] = []
        args: list[Any] = []
        termo = _termo_fts(busca)
        if termo:
            sql += " JOIN atividades_busca b ON b.rowid = a.id"
            where.append("atividades_busca MATCH ?")
            args.append(termo)
        if tipos:
            where.append(f"a.tipo IN ({','.join('?' * len(tipos))})")
            args.extend(tipos)
        if desde:
            where.append("a.quando >= ?")
            args.append(desde.isoformat(timespec="seconds"))
        if ate:
            where.append("a.quando <= ?")
            args.append(ate.isoformat(timespec="seconds"))
        if so_desfaziveis:
            where.append(
                "a.desfazer IS NOT NULL AND a.desfeito_em IS NULL"
                " AND a.resultado = 'ok'"
            )
        if antes_de:
            where.append("a.id < ?")
            args.append(antes_de)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY a.id DESC LIMIT ?"
        args.append(max(1, min(limite, 1000)))
        with self._lock:
            try:
                rows = self._con.execute(sql, args).fetchall()
            except sqlite3.OperationalError:
                logger.debug("Busca do histórico inválida: %r", busca, exc_info=True)
                return []
        return [self._linha(r) for r in rows]

    def ultima_desfazivel(
        self, tipos: Optional[list[str]] = None
    ) -> Optional[Atividade]:
        itens = self.listar(tipos=tipos, so_desfaziveis=True, limite=1)
        return itens[0] if itens else None

    def verificar(self) -> dict[str, Any]:
        """Confere a cadeia de hashes.

        ``quebra_em`` é o id da primeira linha alterada.
        """
        with self._lock:
            rows = self._con.execute(
                "SELECT id, quando, tipo, titulo, origem, resultado, detalhe,"
                " hash_anterior, hash"
                " FROM atividades ORDER BY id"
            ).fetchall()
        anterior: Optional[str] = None
        for r in rows:
            # a primeira linha que sobrou de uma limpeza aponta para uma linha apagada
            if anterior is not None and r["hash_anterior"] != anterior:
                return {"ok": False, "linhas": len(rows), "quebra_em": r["id"]}
            esperado = _hash(
                r["hash_anterior"],
                r["quando"],
                r["tipo"],
                r["titulo"],
                r["origem"],
                r["resultado"],
                r["detalhe"],
            )
            if esperado != r["hash"]:
                return {"ok": False, "linhas": len(rows), "quebra_em": r["id"]}
            anterior = r["hash"]
        return {"ok": True, "linhas": len(rows), "quebra_em": None}

    def fechar(self) -> None:
        with self._lock:
            self._con.close()


def _termo_fts(busca: str) -> str:
    """Texto digitado -> consulta FTS5 segura (prefixo em cada palavra)."""
    palavras = [
        p for p in "".join(c if c.isalnum() else " " for c in busca).split() if p
    ]
    return " ".join(f'"{p}"*' for p in palavras[:12])


_instancia: Optional[Registro] = None
_instancia_lock = threading.Lock()


def registro() -> Registro:
    """O registro do usuário atual (``~/.nicx/historico.db``)."""
    global _instancia
    from nicx.nucleo.paths import get_config_dir

    caminho = get_config_dir() / "historico.db"
    with _instancia_lock:
        if _instancia is None or _instancia.caminho != caminho:
            _instancia = Registro(caminho)
        return _instancia


def anotar(tipo: str, titulo: str, **kw: Any) -> Optional[int]:
    """Atalho que nunca levanta (o histórico não pode derrubar uma ação)."""
    try:
        from nicx.historico import config as cfg

        if not cfg.ligado():
            return None
        if tipo == "conversa" and not cfg.guardar_conversas():
            return None
        return registro().anotar(tipo, titulo, **kw)
    except Exception:  # noqa: BLE001
        logger.debug("Não deu para anotar no histórico", exc_info=True)
        return None
