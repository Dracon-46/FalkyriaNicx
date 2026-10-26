# Instalação

## Requisitos

- Windows 10/11, Linux ou macOS. Funciona só com CPU; 16 GB de RAM é o
  confortável para o modelo padrão (`qwen3.5:4b`, ~3,4 GB carregado).
- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.12 do projeto).
- [Ollama](https://ollama.com) e o modelo: `ollama pull qwen3.5:4b`.
- Rust (via rustup) e, no Windows, o Visual Studio C++ Build Tools, para
  compilar a extensão `nicx_rust`.
- Node 22+ para a interface.

## Passo a passo (a partir do código)

```bash
git clone https://github.com/Dracon-46/FalkyriaNicx.git
cd FalkyriaNicx

# Python, dependências e a extensão Rust (com ~/.cargo/bin no PATH)
uv sync --extra server --extra inference-cloud --extra memory-bm25 --extra pdf \
        --extra dev --extra speech --extra voice --extra desktop --group desktop-native

# Interface
cd frontend && npm ci && npm run build && cd ..

# Configuração inicial (cria ~/.nicx/config.toml e pergunta sobre estatísticas)
uv run nicx init
uv run nicx doctor
```

> `uv sync` sem todos os extras **desinstala** os que faltarem. Use sempre o
> comando completo acima.

### Só recompilar a extensão Rust

```bash
CARGO_BUILD_JOBS=2 uv run maturin develop --release -m rust/crates/nicx-ponte/Cargo.toml
```

Leva ~2,5 min numa CPU de notebook com 2 núcleos dedicados (o limite de
núcleos evita travar a máquina).

## Instalador do Windows

O instalador fica em `packaging/windows/` (Inno Setup). Ele instala o
Python, as dependências, a extensão e a interface, e pergunta sobre as
estatísticas de uso. Ainda não é publicado.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| `uv` não reconhecido | Feche e abra o terminal (o PATH muda na instalação). |
| Ambiente quebrado depois de mover o Python | `uv venv --allow-existing --python 3.12 --prompt nicx .venv` recria os lançadores sem perder pacotes. |
| Pasta do projeto foi movida | `uv sync --reinstall` com os mesmos extras. |
| Ollama sem memória | Diminua `[engine.ollama] num_ctx` (8192 → 4096). |
| Respostas lentas | Na bateria a CPU fica mais lenta; feche apps pesados. Veja [Arquitetura](arquitetura.md#por-que-o-prompt-e-tao-curto). |
