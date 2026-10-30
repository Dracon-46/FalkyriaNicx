"""Acha e lê o arquivo que a janela mostra, só dentro das pastas do usuário.

O título traz o nome ("relatorio.docx - Word"); o caminho vem, nesta ordem:
do próprio título (quando ele tem o caminho completo), dos atalhos de
"Recentes" do Windows, da pasta de projeto do VS Code e de uma busca curta
nas pastas do usuário. Qualquer caminho fora das pastas permitidas é
ignorado, assim como arquivos sensíveis (.env, chaves, credenciais).

Leitura: texto puro, PDF (pdfplumber, o mesmo da memória, quando instalado)
e .docx (XML do próprio arquivo, sem dependência). Tudo com limite.
"""

from __future__ import annotations

import json
import logging
import os
import re
import struct
import time
import zipfile
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urlparse

from nicx.contexto.janela import ArquivoNoTitulo
from nicx.contexto.montagem import Leitura, ler_limitado

logger = logging.getLogger(__name__)

MAX_BYTES_TEXTO = 4 * 1024 * 1024
MAX_BYTES_PDF = 50 * 1024 * 1024
MAX_BYTES_DOCX = 30 * 1024 * 1024
TEMPO_BUSCA_S = 1.5
PROFUNDIDADE_BUSCA = 5

EXTENSOES_TEXTO = frozenset(
    {
        ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json",
        ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
        ".html", ".htm", ".css", ".scss", ".js", ".jsx", ".ts", ".tsx", ".mjs",
        ".cjs", ".py", ".pyi", ".ipynb", ".java", ".kt", ".c", ".h", ".cpp",
        ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".swift", ".sql", ".sh",
        ".ps1", ".bat", ".cmd", ".lua", ".r", ".dart", ".vue", ".svelte",
        ".tex", ".srt", ".vtt",
    }
)  # fmt: skip
EXTENSOES_LIDAS = EXTENSOES_TEXTO | {".pdf", ".docx"}

_PULAR = frozenset(
    {
        "node_modules", ".git", ".venv", "venv", "__pycache__", "target", "dist",
        "build", ".next", ".cache", "AppData", "$RECYCLE.BIN",
    }
)  # fmt: skip


def _perfil() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def pastas_do_usuario(extras: Iterable[str] = ()) -> list[Path]:
    """Área de Trabalho, Documentos, Downloads, OneDrive e as extras."""
    perfil = _perfil()
    candidatas = [perfil / "Desktop", perfil / "Documents", perfil / "Downloads"]
    try:
        candidatas += [p for p in perfil.glob("OneDrive*") if p.is_dir()]
    except OSError:
        pass
    candidatas += [Path(os.path.expandvars(os.path.expanduser(e))) for e in extras if e]
    return _unicas(p for p in candidatas if p.is_dir())


def _unicas(pastas: Iterable[Path]) -> list[Path]:
    vistas: set[str] = set()
    saida: list[Path] = []
    for pasta in pastas:
        try:
            chave = os.path.normcase(str(pasta.resolve()))
        except OSError:
            continue
        if chave not in vistas:
            vistas.add(chave)
            saida.append(pasta)
    return saida


_URI_PASTA = re.compile(
    r'"(?:folderUri|folder|workspace|configURIPath)"\s*:\s*"(file:///[^"]+)"'
)


def pastas_vscode() -> list[Path]:
    """Pastas de projeto abertas recentemente no VS Code (storage.json)."""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    pastas: list[Path] = []
    for produto in ("Code", "Code - Insiders", "Cursor"):
        arquivo = Path(appdata) / produto / "User" / "globalStorage" / "storage.json"
        try:
            if not arquivo.is_file() or arquivo.stat().st_size > 5 * 1024 * 1024:
                continue
            conteudo = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for uri in _URI_PASTA.findall(conteudo):
            caminho = Path(unquote(urlparse(uri).path).lstrip("/"))
            if caminho.suffix == ".code-workspace":
                caminho = caminho.parent
            if caminho.is_dir():
                pastas.append(caminho)
    return _unicas(pastas)


def dentro_de(caminho: Path, raizes: Iterable[Path]) -> bool:
    try:
        alvo = os.path.normcase(str(caminho.resolve()))
    except OSError:
        return False
    for raiz in raizes:
        try:
            base = os.path.normcase(str(raiz.resolve()))
        except OSError:
            continue
        if alvo == base or alvo.startswith(base.rstrip("\\/") + os.sep):
            return True
    return False


# ---------------------------------------------------------------------------
# Atalhos .lnk ("Recentes" do Windows)
# ---------------------------------------------------------------------------


def alvo_do_atalho(dados: bytes) -> Optional[str]:
    """Caminho local de um .lnk (formato Shell Link), sem COM.

    Lê o LinkInfo: ``LocalBasePath`` (+ ``CommonPathSuffix``), em Unicode
    quando o cabeçalho traz os campos novos.
    """
    try:
        if len(dados) < 0x4C or struct.unpack_from("<I", dados, 0)[0] != 0x4C:
            return None
        flags = struct.unpack_from("<I", dados, 0x14)[0]
        pos = 0x4C
        if flags & 0x1:  # HasLinkTargetIDList
            pos += 2 + struct.unpack_from("<H", dados, pos)[0]
        if not flags & 0x2:  # HasLinkInfo
            return None
        inicio = pos
        tam_cab = struct.unpack_from("<I", dados, inicio + 4)[0]
        info_flags = struct.unpack_from("<I", dados, inicio + 8)[0]
        if not info_flags & 0x1:  # VolumeIDAndLocalBasePath
            return None
        base_off = struct.unpack_from("<I", dados, inicio + 16)[0]
        sufixo_off = struct.unpack_from("<I", dados, inicio + 24)[0]
        if tam_cab >= 0x24:
            base_u = struct.unpack_from("<I", dados, inicio + 28)[0]
            sufixo_u = struct.unpack_from("<I", dados, inicio + 32)[0]
            if base_u:
                base = _ler_utf16(dados, inicio + base_u)
                sufixo = _ler_utf16(dados, inicio + sufixo_u) if sufixo_u else ""
                return _juntar(base, sufixo)
        base = _ler_ansi(dados, inicio + base_off)
        sufixo = _ler_ansi(dados, inicio + sufixo_off) if sufixo_off else ""
        return _juntar(base, sufixo)
    except (struct.error, IndexError, UnicodeDecodeError):
        return None


def _juntar(base: str, sufixo: str) -> Optional[str]:
    if not base:
        return None
    if sufixo and not base.endswith("\\"):
        return base + "\\" + sufixo
    return base + sufixo


def _ler_ansi(dados: bytes, pos: int) -> str:
    fim = dados.index(b"\x00", pos)
    bruto = dados[pos:fim]
    try:
        return bruto.decode("mbcs")
    except LookupError:
        return bruto.decode("cp1252", errors="replace")


def _ler_utf16(dados: bytes, pos: int) -> str:
    fim = pos
    while fim + 1 < len(dados) and dados[fim : fim + 2] != b"\x00\x00":
        fim += 2
    return dados[pos:fim].decode("utf-16-le")


def _pasta_recentes() -> Optional[Path]:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    pasta = Path(appdata) / "Microsoft" / "Windows" / "Recent"
    return pasta if pasta.is_dir() else None


def _pelos_recentes(nomes: list[str]) -> Iterable[Path]:
    pasta = _pasta_recentes()
    if pasta is None:
        return
    for nome in nomes:
        atalho = pasta / f"{nome}.lnk"
        try:
            if not atalho.is_file() or atalho.stat().st_size > 64 * 1024:
                continue
            alvo = alvo_do_atalho(atalho.read_bytes())
        except OSError:
            continue
        if alvo:
            yield Path(alvo)


# ---------------------------------------------------------------------------
# Busca curta por nome
# ---------------------------------------------------------------------------


def _buscar(raiz: Path, nomes: set[str], prazo: float) -> list[Path]:
    achados: list[Path] = []
    base = len(raiz.parts)
    for atual, pastas, arquivos in os.walk(raiz):
        if time.monotonic() > prazo:
            break
        if len(Path(atual).parts) - base >= PROFUNDIDADE_BUSCA:
            pastas[:] = []
        pastas[:] = [p for p in pastas if p not in _PULAR and not p.startswith(".")]
        for arquivo in arquivos:
            if arquivo.lower() in nomes:
                achados.append(Path(atual) / arquivo)
    return achados


def _mais_recente(caminhos: Iterable[Path]) -> Optional[Path]:
    melhor: Optional[Path] = None
    melhor_data = -1.0
    for caminho in caminhos:
        try:
            data = caminho.stat().st_mtime
        except OSError:
            continue
        if data > melhor_data:
            melhor, melhor_data = caminho, data
    return melhor


def resolver(
    arquivo: ArquivoNoTitulo,
    *,
    extras: Iterable[str] = (),
    raizes: Optional[list[Path]] = None,
    projetos: Optional[list[Path]] = None,
    tempo_max: float = TEMPO_BUSCA_S,
) -> Optional[Path]:
    """O caminho do arquivo do título, se estiver nas pastas permitidas."""
    raizes = pastas_do_usuario(extras) if raizes is None else raizes
    projetos = pastas_vscode() if projetos is None else projetos
    permitidas = _unicas([*raizes, *projetos])
    if not permitidas:
        return None
    nomes = [arquivo.nome]
    if arquivo.extensoes:
        nomes = [arquivo.nome + ext for ext in arquivo.extensoes]

    def aceita(caminho: Path) -> bool:
        return (
            caminho.is_file()
            and caminho.name.lower() in {n.lower() for n in nomes}
            and dentro_de(caminho, permitidas)
        )

    if arquivo.caminho:
        caminho = Path(arquivo.caminho)
        return caminho if aceita(caminho) else None

    recentes = [c for c in _pelos_recentes(nomes) if aceita(c)]
    if recentes:
        return _mais_recente(recentes)

    prazo = time.monotonic() + tempo_max
    alvo = {n.lower() for n in nomes}
    if arquivo.pasta_projeto:
        for projeto in projetos:
            if projeto.name.lower() == arquivo.pasta_projeto.lower():
                achados = [c for c in _buscar(projeto, alvo, prazo) if aceita(c)]
                if achados:
                    return _mais_recente(achados)
    achados = []
    for raiz in permitidas:
        achados += [c for c in _buscar(raiz, alvo, prazo) if aceita(c)]
        if time.monotonic() > prazo:
            break
    return _mais_recente(achados)


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _sensivel(caminho: Path) -> bool:
    try:
        from nicx.seguranca.file_policy import is_sensitive_file

        return bool(is_sensitive_file(caminho))
    except Exception:  # noqa: BLE001 - na dúvida, não lê
        logger.debug("Política de arquivos sensíveis indisponível", exc_info=True)
        return True


def _texto_puro(caminho: Path) -> str:
    with caminho.open("rb") as arquivo:
        bruto = arquivo.read(MAX_BYTES_TEXTO)
    if bruto.startswith((b"\xff\xfe", b"\xfe\xff")):
        return bruto.decode("utf-16", errors="replace")
    if b"\x00" in bruto[:4096]:
        return ""  # binário
    try:
        return bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        return bruto.decode("latin-1")


def _pdf(caminho: Path, max_caracteres: int) -> str:
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except ImportError:
        return ""
    paginas: list[str] = []
    total = 0
    with pdfplumber.open(caminho) as pdf:
        for pagina in pdf.pages:
            texto = pagina.extract_text() or ""
            if texto:
                paginas.append(texto)
                total += len(texto)
            if total >= max_caracteres * 2:
                break
    return "\n\n".join(paginas)


_PARAGRAFO = re.compile(r"</w:p>")
_TAG = re.compile(r"<[^>]+>")


def _docx(caminho: Path) -> str:
    import html

    with zipfile.ZipFile(caminho) as pacote:
        info = pacote.getinfo("word/document.xml")
        if info.file_size > MAX_BYTES_DOCX:
            return ""
        xml = pacote.read(info).decode("utf-8", errors="replace")
    xml = xml.replace("<w:tab/>", "\t").replace("<w:br/>", "\n")
    texto = _TAG.sub("", _PARAGRAFO.sub("\n", xml))
    return html.unescape(texto)


def ler_arquivo(caminho: Path, max_caracteres: int) -> Leitura:
    """Texto do arquivo, limpo e cortado; motivo quando não dá para ler."""
    extensao = caminho.suffix.lower()
    if extensao not in EXTENSOES_LIDAS:
        return Leitura(motivo="formato")
    if _sensivel(caminho):
        return Leitura(motivo="sensivel")
    try:
        tamanho = caminho.stat().st_size
        if extensao == ".pdf":
            if tamanho > MAX_BYTES_PDF:
                return Leitura(motivo="grande")
            texto = _pdf(caminho, max_caracteres)
        elif extensao == ".docx":
            texto = _docx(caminho)
        else:
            texto = _texto_puro(caminho)
            if extensao == ".ipynb":
                texto = _celulas_notebook(texto) or texto
    except Exception:  # noqa: BLE001 - arquivo em uso, corrompido...
        logger.debug("Falha ao ler o arquivo aberto", exc_info=True)
        return Leitura(motivo="erro")
    return ler_limitado(texto, max_caracteres)


def _celulas_notebook(texto: str) -> str:
    try:
        dados = json.loads(texto)
    except ValueError:
        return ""
    partes = []
    for celula in dados.get("cells", []):
        fonte = celula.get("source", "")
        partes.append("".join(fonte) if isinstance(fonte, list) else str(fonte))
    return "\n\n".join(partes)


__all__ = [
    "EXTENSOES_LIDAS",
    "alvo_do_atalho",
    "dentro_de",
    "ler_arquivo",
    "pastas_do_usuario",
    "pastas_vscode",
    "resolver",
]
