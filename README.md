<div align="center">
  <img alt="Nicx, o slime ciano com um núcleo azul" src="assets/nicx-mascot.svg" width="180">
  <br>
  <img alt="Nicx" src="assets/Nicx_Horizontal_Logo.png" width="400">

  <p><i>A inteligência artificial da Falkyria.</i></p>
</div>

---

O **Nicx** é o assistente de IA da Falkyria. Ele roda **no seu próprio
computador**: o modelo de linguagem (via [Ollama](https://ollama.com)), o
reconhecimento de fala e a voz ficam na máquina, sem custo por uso e sem
mandar suas conversas para servidores de terceiros.

- **Conversa** por texto ou voz, no app (com um mascote animado), no terminal
  (`nicx chat`, `nicx ask`) ou dizendo **"Nicx, ligar"**.
- **Age no computador na hora**: "aumenta o volume", "pausa a música", "abre o
  YouTube", "que horas são", sem nem chamar o modelo.
- **Usa ferramentas** quando precisa: busca na web, arquivos, Python, comandos,
  base de conhecimento, sempre sob uma política de permissões.
- **Memória, agentes agendados, briefing diário, pesquisa profunda e skills.**
- **Privacidade por padrão**: estatísticas de uso só com consentimento, sem o
  conteúdo das conversas.

## Requisitos

- Windows 10/11, macOS ou Linux; 16 GB de RAM para o modelo padrão na CPU
- [uv](https://docs.astral.sh/uv/) (gerencia o Python 3.12 do projeto)
- [Ollama](https://ollama.com) com o modelo: `ollama pull qwen3.5:4b`
- Node.js 22+ para a interface
- Rust (via [rustup](https://rustup.rs)) para a extensão nativa; no Windows,
  também o Visual Studio C++ Build Tools

## Instalação

```bash
git clone https://github.com/Dracon-46/FalkyriaNicx.git
cd FalkyriaNicx
uv sync --extra server --extra inference-cloud --extra memory-bm25 --extra pdf \
        --extra dev --extra speech --extra voice --extra desktop --group desktop-native
cd frontend && npm ci && npm run build && cd ..
uv run nicx init
uv run nicx doctor
```

> `uv sync` remove os extras que você não listar: rode sempre com a lista
> completa.

## Uso

```bash
uv run nicx gui                 # o app, no navegador
uv run nicx chat                # conversa no terminal (--voice para falar)
uv run nicx ask "Quem é você?"  # uma pergunta
uv run nicx escuta              # liga o "Nicx, ligar"
```

A configuração fica em `~/.nicx/config.toml`, junto com a persona (`SOUL.md`),
a memória (`MEMORY.md`) e o perfil (`USER.md`).

## Documentação

- [Instalação](docs/instalacao.md) · [Uso](docs/uso.md) ·
  [Configuração](docs/configuracao.md)
- [Arquitetura](docs/arquitetura.md): pastas e o caminho de uma pergunta
- [Voz](docs/voz.md) · [Privacidade](docs/privacidade.md) ·
  [Desenvolvimento](docs/desenvolvimento.md)

## Licença

Software proprietário. Copyright © 2026 Falkyria. Todos os direitos reservados.
Veja [LICENSE](LICENSE).
