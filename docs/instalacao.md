# Instalação

## Requisitos

- Windows 10/11, Linux ou macOS (no macOS, use o [comando único](#macos-um-comando)).
  Funciona só com CPU; 16 GB de RAM é o confortável para o modelo padrão
  (`qwen3.5:4b`, ~3,4 GB carregado).
- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.12 do projeto).
- [Ollama](https://ollama.com) e o modelo: `ollama pull qwen3.5:4b`.
- Rust (via rustup) e, no Windows, o Visual Studio C++ Build Tools, para
  compilar a extensão `nicx_rust`.
- Node 22+ para a interface.

## macOS (um comando)

**Requisitos:** macOS 14 (Sonoma) ou mais novo (exigência do Ollama), Mac
com Apple Silicon (M1 ou mais novo) recomendado, 8 GB de RAM ou mais
(16 GB é o confortável) e ~8 GB livres em disco. Não precisa de senha de
administrador nem de Homebrew.

Abra o Terminal e cole:

```bash
curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash
```

O instalador só instala o que falta: o git (Ferramentas de Linha de
Comando do Xcode, abre uma janela do sistema), o uv e o Python 3.12, o
Nicx em `~/.nicx`, a interface web, o Ollama (pelo Homebrew, se você tiver,
ou o app oficial, conferido pelo SHA-256 e pela assinatura) e o modelo
`qwen3.5:4b` (~3,4 GB; Macs com menos RAM recebem um menor). O
`~/.nicx/config.toml` só é criado se ainda não existir. Ele pergunta sobre as
estatísticas de uso: sem resposta, ficam **desligadas** e nada é enviado.

**Abrir:** procure **Nicx** no Launchpad ou no Spotlight, ou rode
`nicx-abrir` no Terminal (liga o Nicx e abre `http://127.0.0.1:8000`). No
terminal também há `nicx chat`, `nicx ask "..."` e `nicx doctor`. Abra um
Terminal novo depois da instalação para os comandos aparecerem.

**Opções** (depois de `| bash -s --`): `--voz` instala a voz local
(~1,5 GB); `--servico` liga o Nicx sozinho ao entrar no macOS; `--minimal`
não baixa o modelo. Exemplo:
`curl -fsSL .../install.sh | bash -s -- --voz`. Rodar o comando de novo
conserta o que faltar; com `--force` ele também atualiza o código.

**Desinstalar:** `nicx-uninstall` (pede "sim"). Apaga `~/.nicx`, os
comandos, o app do Launchpad, o serviço e a linha do PATH. O Ollama e os
modelos (`~/.ollama`) ficam; o desinstalador mostra como removê-los.

O mesmo comando funciona no Linux (aí o Ollama usa o instalador oficial
dele, que pede `sudo`).

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
