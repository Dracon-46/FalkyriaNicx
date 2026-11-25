"""Ferramentas do modo Trabalho, presas à pasta escolhida.

Cada mudança entra no diário da tarefa antes de acontecer:

- arquivo que já existia e vai mudar: cópia em ``copias/`` (só a primeira vez);
- arquivo novo: anotado como criado;
- mover: de onde para onde;
- apagar: pede confirmação e vai para ``lixeira/`` (nada é apagado de vez).

:func:`desfazer` percorre o diário de trás para frente e deixa a pasta como
estava.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from nicx.trabalho.modelo import Tarefa, pasta_da_tarefa
from nicx.trabalho.pasta import ForaDaPasta, Pasta

MAX_LER = 8000
MAX_ARQUIVO_LIDO = 25 * 1024 * 1024
MAX_ESCRITA = 5 * 1024 * 1024
MAX_LISTA = 300
TEXTO = {
    ".txt",
    ".md",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".cfg",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".htm",
    ".css",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".srt",
    ".vtt",
    ".rtf",
}
IGNORADAS = {"node_modules", ".git", "__pycache__", ".venv", "venv"}

Confirmar = Callable[[str], bool]


class ErroFerramenta(RuntimeError):
    """Falha explicada ao modelo (ele tenta de outro jeito)."""


# --------------------------------------------------------------- definições


def _f(
    nome: str, descricao: str, props: dict[str, Any], obrigatorios: list[str]
) -> dict:
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": obrigatorios,
            },
        },
    }


_CAMINHO = {"type": "string", "description": "caminho relativo à pasta de trabalho"}

DEFINICOES = [
    _f(
        "listar_arquivos",
        "Lista arquivos e subpastas (com tamanho). Use antes de mexer em qualquer "
        "coisa.",
        {
            "caminho": {**_CAMINHO, "default": "."},
            "recursivo": {"type": "boolean", "default": False},
        },
        [],
    ),
    _f(
        "ler_arquivo",
        "Lê o conteúdo de um arquivo: texto, Word (.docx), PDF ou Excel (.xlsx).",
        {"caminho": _CAMINHO},
        ["caminho"],
    ),
    _f(
        "escrever_arquivo",
        "Cria ou substitui um arquivo de texto (.txt, .md, .csv, .json...). Para Word "
        "e Excel use as outras.",
        {"caminho": _CAMINHO, "conteudo": {"type": "string"}},
        ["caminho", "conteudo"],
    ),
    _f(
        "criar_planilha",
        "Cria ou substitui uma planilha Excel (.xlsx). A primeira linha de cada aba é "
        "o cabeçalho.",
        {
            "caminho": _CAMINHO,
            "abas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "linhas": {
                            "type": "array",
                            "items": {"type": "array", "items": {}},
                        },
                    },
                },
            },
        },
        ["caminho", "abas"],
    ),
    _f(
        "criar_documento",
        "Cria ou substitui um documento Word (.docx). No texto: '# ' título, '## ' "
        "subtítulo, '- ' item.",
        {
            "caminho": _CAMINHO,
            "titulo": {"type": "string"},
            "texto": {"type": "string"},
        },
        ["caminho", "texto"],
    ),
    _f(
        "criar_pasta",
        "Cria uma pasta (e as pastas do caminho, se faltarem).",
        {"caminho": _CAMINHO},
        ["caminho"],
    ),
    _f(
        "mover",
        "Move ou renomeia um arquivo ou pasta. Se o destino for uma pasta que existe, "
        "vai para dentro dela.",
        {"origem": _CAMINHO, "destino": _CAMINHO},
        ["origem", "destino"],
    ),
    _f(
        "apagar",
        "Apaga um arquivo ou pasta (a pessoa confirma antes; vai para a lixeira da "
        "tarefa).",
        {"caminho": _CAMINHO, "motivo": {"type": "string"}},
        ["caminho", "motivo"],
    ),
    _f(
        "pesquisar_web",
        "Pesquisa na internet e devolve os resultados (título, endereço e trecho).",
        {"consulta": {"type": "string"}},
        ["consulta"],
    ),
    _f(
        "analisar_dados",
        "Resume uma tabela .csv/.xlsx (colunas, somas, médias, datas). Com "
        "agrupar_por, faz a conta por grupo; por_mes agrupa uma coluna de datas "
        "por mês. Use isto para contas: não some de cabeça.",
        {
            "caminho": _CAMINHO,
            "aba": {"type": "string"},
            "agrupar_por": {"type": "string", "description": "nome da coluna"},
            "valor": {"type": "string", "description": "coluna com os números"},
            "operacao": {
                "type": "string",
                "enum": ["soma", "media", "contagem", "maximo", "minimo"],
            },
            "por_mes": {"type": "boolean", "default": False},
        },
        ["caminho"],
    ),
    _f(
        "criar_grafico",
        "Cria um gráfico do Excel (.xlsx): numa planilha nova ou numa aba nova de uma "
        "que existe. linhas: a 1ª é o cabeçalho; a 1ª coluna são os rótulos e as "
        "outras, os valores.",
        {
            "caminho": _CAMINHO,
            "titulo": {"type": "string"},
            "tipo": {
                "type": "string",
                "enum": ["colunas", "barras", "linhas", "pizza"],
            },
            "linhas": {"type": "array", "items": {"type": "array", "items": {}}},
        },
        ["caminho", "linhas"],
    ),
    _f(
        "converter",
        "Converte um arquivo: csv/json→xlsx, xlsx/json→csv, docx/pdf→txt/md, "
        "tabelas de PDF→xlsx, txt/md→docx.",
        {"origem": _CAMINHO, "destino": _CAMINHO},
        ["origem", "destino"],
    ),
    _f(
        "comparar",
        "Compara dois arquivos (texto, Word, PDF ou Excel) e mostra o que entrou e o "
        "que saiu de um para o outro.",
        {"a": _CAMINHO, "b": _CAMINHO},
        ["a", "b"],
    ),
]
NOMES = {d["function"]["name"] for d in DEFINICOES}


# ------------------------------------------------------------------ leitura


def _tamanho(n: int) -> str:
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024
    return f"{n} B"


def _cortar(texto: str) -> str:
    if len(texto) <= MAX_LER:
        return texto
    return texto[:MAX_LER] + f"\n… (cortado: o arquivo tem {len(texto)} caracteres)"


def ler_conteudo(p: Path) -> str:
    """Texto de um arquivo (Word, PDF e Excel viram texto)."""
    if p.stat().st_size > MAX_ARQUIVO_LIDO:
        raise ErroFerramenta(
            f"arquivo grande demais para ler ({_tamanho(p.stat().st_size)})"
        )
    ext = p.suffix.lower()
    if ext == ".docx":
        import docx

        d = docx.Document(str(p))
        partes = [par.text for par in d.paragraphs if par.text.strip()]
        for tabela in d.tables:
            for linha in tabela.rows:
                partes.append(" | ".join(c.text.strip() for c in linha.cells))
        return "\n".join(partes)
    if ext == ".pdf":
        import pdfplumber

        with pdfplumber.open(str(p)) as pdf:
            paginas = [(pg.extract_text() or "") for pg in pdf.pages[:30]]
        texto = "\n\n".join(
            f"[página {i + 1}]\n{t}" for i, t in enumerate(paginas) if t.strip()
        )
        return texto or "(PDF sem texto: provavelmente é imagem escaneada)"
    if ext in (".xlsx", ".xlsm"):
        import openpyxl

        livro = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
        partes = []
        try:
            for aba in livro.worksheets:
                partes.append(f"[aba {aba.title}]")
                for i, linha in enumerate(aba.iter_rows(values_only=True)):
                    if i >= 300:
                        partes.append("… (mais linhas)")
                        break
                    if any(v is not None for v in linha):
                        partes.append(
                            "\t".join("" if v is None else str(v) for v in linha)
                        )
        finally:
            livro.close()
        return "\n".join(partes)
    if ext in TEXTO or ext == "":
        dados = p.read_bytes()
        if b"\x00" in dados[:4000]:
            raise ErroFerramenta("arquivo binário: não dá para ler como texto")
        for codificacao in ("utf-8", "cp1252"):
            try:
                return dados.decode(codificacao)
            except UnicodeDecodeError:
                continue
        return dados.decode("utf-8", errors="replace")
    raise ErroFerramenta(f"não sei ler arquivos {ext} (só texto, Word, PDF e Excel)")


# -------------------------------------------------------------- execução


class Ferramentas:
    """As ferramentas de uma tarefa: pasta, diário e confirmação."""

    def __init__(
        self, tarefa: Tarefa, confirmar: Confirmar, salvar: Callable[[], None]
    ) -> None:
        self.tarefa = tarefa
        self.pasta = Pasta(Path(tarefa.pasta))
        self._confirmar = confirmar
        self._salvar = salvar
        self._dados = pasta_da_tarefa(tarefa.id)

    # diário --------------------------------------------------------------
    def _ja_no_diario(self, rel: str) -> bool:
        return any(
            d.get("caminho") == rel and d["op"] in ("criou", "alterou")
            for d in self.tarefa.diario
        )

    def _antes_de_escrever(self, p: Path) -> None:
        rel = self.pasta.relativo(p)
        if self._ja_no_diario(rel):
            return
        if p.exists():
            copias = self._dados / "copias"
            copias.mkdir(parents=True, exist_ok=True)
            copia = copias / f"{len(self.tarefa.diario):04d}_{p.name}"
            shutil.copy2(p, copia)
            self.tarefa.diario.append(
                {"op": "alterou", "caminho": rel, "copia": str(copia)}
            )
        else:
            self.tarefa.diario.append({"op": "criou", "caminho": rel})
        self._salvar()

    # ferramentas ---------------------------------------------------------
    def listar_arquivos(self, caminho: str = ".", recursivo: bool = False) -> str:
        p = self.pasta.caminho(caminho)
        if not p.is_dir():
            raise ErroFerramenta(f"'{caminho}' não é uma pasta")
        itens = p.rglob("*") if recursivo else p.iterdir()
        linhas = []
        for item in sorted(itens, key=lambda x: (x.is_file(), str(x).lower())):
            if any(parte in IGNORADAS for parte in item.relative_to(p).parts):
                continue
            rel = self.pasta.relativo(item)
            try:
                if item.is_dir():
                    linhas.append(f"[pasta] {rel}/")
                else:
                    linhas.append(f"{rel}  ({_tamanho(item.stat().st_size)})")
            except OSError:
                continue
            if len(linhas) >= MAX_LISTA:
                linhas.append("… (mais itens; liste uma subpasta)")
                break
        return "\n".join(linhas) or "(pasta vazia)"

    def ler_arquivo(self, caminho: str) -> str:
        p = self.pasta.caminho(caminho)
        if not p.is_file():
            raise ErroFerramenta(f"'{caminho}' não existe ou não é um arquivo")
        return _cortar(ler_conteudo(p))

    def _alvo_de_escrita(
        self, caminho: str, extensoes: Optional[set[str]] = None
    ) -> Path:
        p = self.pasta.caminho(caminho)
        if p == self.pasta.raiz or p.is_dir():
            raise ErroFerramenta(f"'{caminho}' é uma pasta")
        if extensoes and p.suffix.lower() not in extensoes:
            raise ErroFerramenta(
                f"o nome precisa terminar em {' ou '.join(sorted(extensoes))}"
            )
        return p

    def escrever_arquivo(self, caminho: str, conteudo: str) -> str:
        p = self._alvo_de_escrita(caminho)
        if p.suffix.lower() in (".docx", ".xlsx", ".pdf"):
            raise ErroFerramenta(
                "para Word use criar_documento; para Excel, criar_planilha"
            )
        dados = str(conteudo).encode("utf-8")
        if len(dados) > MAX_ESCRITA:
            raise ErroFerramenta("conteúdo grande demais")
        self._antes_de_escrever(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
        return f"gravei {self.pasta.relativo(p)} ({_tamanho(len(dados))})"

    def criar_planilha(self, caminho: str, abas: list) -> str:
        import openpyxl
        from openpyxl.styles import Font

        p = self._alvo_de_escrita(caminho, {".xlsx"})
        if not isinstance(abas, list) or not abas:
            raise ErroFerramenta("mande pelo menos uma aba com linhas")
        livro = openpyxl.Workbook()
        livro.remove(livro.active)
        total = 0
        for i, aba in enumerate(abas):
            aba = aba if isinstance(aba, dict) else {"linhas": aba}
            folha = livro.create_sheet(str(aba.get("nome") or f"Aba {i + 1}")[:31])
            for n, linha in enumerate(aba.get("linhas") or []):
                valores = linha if isinstance(linha, list) else [linha]
                folha.append([_numero(v) for v in valores])
                if n == 0:
                    for celula in folha[1]:
                        celula.font = Font(bold=True)
                total += 1
            for coluna in folha.columns:
                largura = max(
                    (len(str(c.value)) for c in coluna if c.value is not None),
                    default=8,
                )
                folha.column_dimensions[coluna[0].column_letter].width = min(
                    60, largura + 2
                )
        self._antes_de_escrever(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        livro.save(str(p))
        return (
            f"criei a planilha {self.pasta.relativo(p)} "
            f"({len(abas)} aba(s), {total} linhas)"
        )

    def criar_documento(self, caminho: str, texto: str, titulo: str = "") -> str:
        import docx

        p = self._alvo_de_escrita(caminho, {".docx"})
        d = docx.Document()
        if titulo:
            d.add_heading(titulo, level=0)
        for linha in str(texto).splitlines():
            limpa = linha.rstrip()
            if limpa.startswith("## "):
                d.add_heading(limpa[3:], level=2)
            elif limpa.startswith("# "):
                d.add_heading(limpa[2:], level=1)
            elif limpa.lstrip().startswith(("- ", "* ", "• ")):
                d.add_paragraph(limpa.lstrip()[2:], style="List Bullet")
            elif limpa.strip():
                d.add_paragraph(limpa)
        self._antes_de_escrever(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        d.save(str(p))
        return f"criei o documento {self.pasta.relativo(p)}"

    def criar_pasta(self, caminho: str) -> str:
        p = self.pasta.caminho(caminho)
        if p.exists():
            return f"a pasta {self.pasta.relativo(p)} já existe"
        p.mkdir(parents=True)
        self.tarefa.diario.append(
            {"op": "criou_pasta", "caminho": self.pasta.relativo(p)}
        )
        self._salvar()
        return f"criei a pasta {self.pasta.relativo(p)}"

    def mover(self, origem: str, destino: str) -> str:
        de = self.pasta.caminho(origem)
        if de == self.pasta.raiz or not de.exists():
            raise ErroFerramenta(f"'{origem}' não existe")
        para = self.pasta.caminho(destino)
        if para.is_dir():
            para = para / de.name
            self.pasta.caminho(self.pasta.relativo(para))  # confere de novo
        if para.exists():
            raise ErroFerramenta(
                f"já existe '{self.pasta.relativo(para)}'; escolha outro nome"
            )
        if para.is_relative_to(de):
            raise ErroFerramenta("não dá para mover uma pasta para dentro dela mesma")
        para.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(de), str(para))
        self.tarefa.diario.append(
            {
                "op": "moveu",
                "de": self.pasta.relativo(de),
                "para": self.pasta.relativo(para),
            }
        )
        self._salvar()
        return f"movi {self.pasta.relativo(de)} para {self.pasta.relativo(para)}"

    def apagar(self, caminho: str, motivo: str = "") -> str:
        p = self.pasta.caminho(caminho)
        if p == self.pasta.raiz:
            raise ErroFerramenta("não dá para apagar a pasta de trabalho inteira")
        if not p.exists():
            raise ErroFerramenta(f"'{caminho}' não existe")
        rel = self.pasta.relativo(p)
        texto = f"Apagar {rel}{'/' if p.is_dir() else ''}?" + (
            f" Motivo: {motivo}" if motivo else ""
        )
        if not self._confirmar(texto):
            return f"a pessoa não deixou apagar {rel}: siga sem apagar"
        lixeira = self._dados / "lixeira"
        lixeira.mkdir(parents=True, exist_ok=True)
        lixo = lixeira / f"{len(self.tarefa.diario):04d}_{p.name}"
        shutil.move(str(p), str(lixo))
        self.tarefa.diario.append({"op": "apagou", "caminho": rel, "lixo": str(lixo)})
        self._salvar()
        return f"apaguei {rel} (dá para desfazer)"

    def pesquisar_web(self, consulta: str) -> str:
        from nicx.ferramentas.web.web_search import WebSearchTool

        resultado = WebSearchTool().execute(query=str(consulta), max_results=5)
        if not resultado.success:
            raise ErroFerramenta(resultado.content or "a pesquisa falhou")
        return _cortar(resultado.content)

    # dados ----------------------------------------------------------------
    def _arquivo(self, caminho: str) -> Path:
        p = self.pasta.caminho(caminho)
        if not p.is_file():
            raise ErroFerramenta(f"'{caminho}' não existe ou não é um arquivo")
        if p.stat().st_size > MAX_ARQUIVO_LIDO:
            raise ErroFerramenta(
                f"arquivo grande demais ({_tamanho(p.stat().st_size)})"
            )
        return p

    def analisar_dados(
        self,
        caminho: str,
        aba: str = "",
        agrupar_por: str = "",
        valor: str = "",
        operacao: str = "soma",
        por_mes: bool = False,
    ) -> str:
        from nicx.trabalho import dados

        try:
            cab, linhas = dados.ler_tabela(self._arquivo(caminho), aba or "")
            return _cortar(
                dados.analisar(
                    cab,
                    linhas,
                    agrupar_por=agrupar_por or "",
                    valor=valor or "",
                    operacao=operacao or "soma",
                    por_mes=bool(por_mes),
                )
            )
        except dados.ErroDados as exc:
            raise ErroFerramenta(str(exc)) from exc

    def criar_grafico(
        self, caminho: str, linhas: list, titulo: str = "", tipo: str = "colunas"
    ) -> str:
        from nicx.trabalho import dados

        p = self._alvo_de_escrita(caminho, {".xlsx"})
        self._antes_de_escrever(p)
        try:
            n = dados.grafico_xlsx(
                p, linhas, tipo=tipo or "colunas", titulo=titulo or ""
            )
        except dados.ErroDados as exc:
            raise ErroFerramenta(str(exc)) from exc
        return (
            f"criei o gráfico ({tipo or 'colunas'}, {n} itens) "
            f"em {self.pasta.relativo(p)}"
        )

    def converter(self, origem: str, destino: str) -> str:
        from nicx.trabalho import dados

        de = self._arquivo(origem)
        para = self._alvo_de_escrita(destino)
        if para == de:
            raise ErroFerramenta("o destino precisa ser outro arquivo")
        self._antes_de_escrever(para)
        try:
            detalhe = dados.converter(de, para, ler_conteudo)
        except dados.ErroDados as exc:
            raise ErroFerramenta(str(exc)) from exc
        return (
            f"converti {self.pasta.relativo(de)} em {self.pasta.relativo(para)} "
            f"({detalhe})"
        )

    def comparar(self, a: str, b: str) -> str:
        from nicx.trabalho import dados

        pa, pb = self._arquivo(a), self._arquivo(b)
        return dados.comparar(
            ler_conteudo(pa),
            ler_conteudo(pb),
            self.pasta.relativo(pa),
            self.pasta.relativo(pb),
            limite=MAX_LER,
        )

    # despacho ------------------------------------------------------------
    def executar(self, nome: str, argumentos: str | dict) -> tuple[bool, str]:
        """Roda a ferramenta *nome*; devolve (deu certo, texto para o modelo)."""
        if nome not in NOMES:
            return False, f"ferramenta desconhecida: {nome}"
        try:
            params = (
                json.loads(argumentos)
                if isinstance(argumentos, str)
                else dict(argumentos or {})
            )
            if not isinstance(params, dict):
                raise ValueError
        except (ValueError, TypeError):
            return False, "argumentos inválidos (mande um objeto JSON)"
        try:
            return True, getattr(self, nome)(**params)
        except TypeError as exc:
            return False, f"argumentos errados para {nome}: {exc}"
        except (ForaDaPasta, ErroFerramenta) as exc:
            return False, str(exc)
        except OSError as exc:
            return False, f"o Windows recusou: {exc.strerror or exc}"


def _numero(valor: Any) -> Any:
    """'42', '3.5' e '1.234,56' viram número na planilha; o resto fica como veio.

    Códigos com zero à esquerda (CEP, matrícula) continuam texto.
    """
    if not isinstance(valor, str):
        return valor
    t = valor.strip()
    if len(t) > 1 and t.startswith("0") and t[1] not in ",.":
        return valor
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d+", t):
        return float(t)
    if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*,\d+|-?\d+,\d+", t):
        return float(t.replace(".", "").replace(",", "."))
    return valor


# ----------------------------------------------------------------- desfazer


def desfazer(tarefa: Tarefa) -> list[str]:
    """Volta a pasta para como estava antes da tarefa; devolve o que não deu."""
    pasta = Pasta(Path(tarefa.pasta))
    problemas = []
    for d in reversed(tarefa.diario):
        try:
            if d["op"] == "criou":
                p = pasta.caminho(d["caminho"])
                if p.is_file():
                    p.unlink()
            elif d["op"] == "alterou":
                shutil.copy2(d["copia"], pasta.caminho(d["caminho"]))
            elif d["op"] == "criou_pasta":
                p = pasta.caminho(d["caminho"])
                if p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
            elif d["op"] == "moveu":
                de, para = pasta.caminho(d["de"]), pasta.caminho(d["para"])
                if para.exists() and not de.exists():
                    de.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(para), str(de))
            elif d["op"] == "apagou":
                p = pasta.caminho(d["caminho"])
                if not p.exists():
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(d["lixo"], str(p))
        except (OSError, ForaDaPasta, KeyError) as exc:
            problemas.append(f"{d.get('caminho') or d.get('para')}: {exc}")
    return problemas


__all__ = ["DEFINICOES", "ErroFerramenta", "Ferramentas", "desfazer", "ler_conteudo"]
