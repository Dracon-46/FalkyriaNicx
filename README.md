<div align="center">
  <img alt="Nicx" src="assets/Nicx_Horizontal_Logo.png" width="400">

  <p><i>A inteligência artificial da Falkyria.</i></p>
</div>

---

O **Nicx** é o assistente de IA da Falkyria. Ele roda **no seu próprio computador**,
com modelos locais via [Ollama](https://ollama.com): sem custo por uso e sem
mandar suas conversas para servidores de terceiros.

- **Conversa e perguntas** pelo terminal (`nicx chat`, `nicx ask`) ou pela
  interface gráfica (`nicx gui` e o app desktop).
- **Agentes com ferramentas**: busca na web, leitura de arquivos, execução de
  código e shell, sempre com confirmação e com as proteções de segurança ligadas.
- **Memória**: o Nicx guarda fatos e documentos indexados e os usa como contexto.
- **Briefing diário**, pesquisa em profundidade, monitoramento agendado e skills
  instaláveis.
- **Privacidade por padrão**: telemetria de uso desligada, sem destino externo
  configurado e com redação automática de segredos.

## Requisitos

- Windows 10/11, macOS ou Linux
- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.12 do projeto)
- [Ollama](https://ollama.com) com um modelo baixado, por exemplo `ollama pull qwen3.5:4b`
- Node.js 22+ para a interface gráfica
- Rust (via [rustup](https://rustup.rs)) para compilar a extensão nativa; no
  Windows, também o Visual Studio C++ Build Tools

Em máquinas sem GPU dedicada, prefira modelos de até 4B parâmetros.

## Instalação

```bash
git clone https://github.com/Dracon-46/FalkyriaNicx.git
cd FalkyriaNicx
uv sync --extra server --extra memory-bm25 --extra pdf --extra dev --group desktop-native
uv run nicx init
uv run nicx doctor
```

`--group desktop-native` compila a extensão em Rust (`nicx_rust`), necessária
para ferramentas, memória e segurança. Ela precisa do `cargo` no `PATH`.

> **Atenção:** `uv sync` remove os extras que você não listar. Rode sempre com a
> lista completa dos extras que usa.

## Uso

```bash
uv run nicx                     # abre o chat
uv run nicx ask "Quem é você?"  # pergunta única
uv run nicx gui                 # interface gráfica no navegador
uv run nicx doctor              # diagnóstico do ambiente
```

Modelos de começo:

```bash
uv run nicx init --preset <nome> --force
```

| Preset | O que faz |
|---|---|
| `chat-simple` | Conversa leve, sem ferramentas |
| `code-assistant` | Agente com execução de código, arquivos e shell |
| `deep-research` | Pesquisa em várias etapas sobre documentos indexados, com citações |
| `scheduled-monitor` | Agente agendado com memória |
| `morning-digest-minimal` / `-linux` / `-mac` | Briefing diário falado (e-mail, agenda, notícias) |

A configuração do usuário fica em `~/.nicx/config.toml`, junto com a persona
(`SOUL.md`), a memória (`MEMORY.md`) e o perfil do usuário (`USER.md`).

## Desenvolvimento

```bash
uv run pytest tests -n auto -q -m "not live and not cloud and not hub"
uv run ruff check src tests
uv run ruff format --check src tests
```

Frontend (React + Vite + Tauri) em `frontend/`:

```bash
cd frontend
npm install
npm run dev          # interface web em desenvolvimento
npm run tauri dev    # app desktop
```

Documentação técnica em [`docs/`](docs/).

## Licença

Software proprietário. Copyright © 2026 Falkyria. Todos os direitos reservados.
Veja [LICENSE](LICENSE).
