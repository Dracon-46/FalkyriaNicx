# Arquitetura

O Nicx é um assistente que roda no computador de quem usa: o modelo de
linguagem, a voz e os dados ficam na máquina. Esta página mostra como o código
está organizado e o caminho que uma pergunta percorre.

## Visão geral

```
 Interface (React/Tauri)      CLI (nicx ...)        Voz ("Nicx, ligar")
          │                        │                        │
          └──────────────┬─────────┴────────────┬───────────┘
                         ▼                      ▼
                nicx.servidor (FastAPI)    nicx.comandos
                         │
        ┌────────────────┼─────────────────────────────┐
        ▼                ▼                             ▼
   nicx.acoes      nicx.cerebro                   nicx.voz
 (comandos na     agentes, prompt,             Whisper + Kokoro
  hora, sem       roteamento, habilidades           (locais)
  modelo)              │
                       ▼
          nicx.ferramentas ◄──► nicx.memoria
                       │
                       ▼
                 nicx.motores ──► Ollama (qwen3.5:4b, na CPU)
```

A extensão em Rust (`nicx_rust`) acelera as partes sensíveis de segurança e
desempenho: scanners de segredos e dados pessoais, política de permissões,
ferramentas de arquivo e shell, e as bases de memória SQLite e BM25.

## Pastas

```
src/nicx/
├── nucleo/          configuração, registros, tipos, eventos, caminhos
│   ├── sistema/     montagem do sistema completo (SystemBuilder)
│   └── rust.py      ponto único de acesso à extensão nicx_rust
├── motores/         motores de inferência (Ollama e outros)
├── cerebro/
│   ├── agentes/     base (_stubs), conversa/, pesquisa/, autonomos/, gestao/
│   ├── prompt/      montagem do prompt de sistema e do orquestrador
│   ├── roteamento/  complexidade da pergunta e escolha de modelo
│   ├── inteligencia/ catálogo de modelos
│   ├── habilidades/ skills (instalação, descoberta, catálogo)
│   ├── fluxos/      grafos de fluxo (workflows)
│   ├── receitas/    receitas prontas
│   └── operadores/  agentes persistentes agendados
├── ferramentas/     ferramentas do modelo, por função:
│   ├── web/  arquivos/  codigo/  conhecimento/
│   ├── pessoal/  agentes/  integracoes/
│   ├── mcp/         cliente e servidor MCP
│   └── sandbox/     execução isolada
├── acoes/           comandos instantâneos e controle do PC (controle_pc)
├── voz/             fala para texto e texto para fala
│   └── escuta/      "Nicx, ligar": detector, janela flutuante
├── memoria/         memória automática, fatos
│   ├── armazenamento/  bases de busca (SQLite, BM25, densa, híbrida)
│   └── sessoes/     sessões de conversa entre canais
├── conectores/      Gmail, Google Agenda, Obsidian, Notion e outros
├── canais/          WhatsApp, Telegram, Slack, e-mail e outros
├── servidor/        API compatível com OpenAI
│   ├── rotas/       chat, api, agentes, privacidade, conectores, escuta...
│   ├── pontes/      canais, streaming SSE, WebSocket
│   ├── custos/      comparação com o custo na nuvem
│   └── gateway/     gateway de canais
├── comandos/        a CLI: conversa/, sistema/, instalacao/, agentes/,
│                    recursos/, voz/
├── seguranca/       permissões, scanners, auditoria, perfis
├── agenda/          tarefas agendadas
├── registros/       telemetria/ (desempenho) e rastros/ (conversas)
└── privacidade/     estatísticas com consentimento e textos legais

rust/crates/
├── nicx-nucleo        tipos, configuração, catálogo de modelos
├── nicx-motores       cliente de inferência
├── nicx-seguranca     scanners, permissões, SSRF, arquivos sensíveis
├── nicx-ferramentas   ferramentas nativas e bases SQLite/BM25
├── nicx-agentes       LoopGuard (evita laços de ferramenta)
└── nicx-ponte         ponte PyO3 que gera o módulo nicx_rust
```

Os testes em `tests/` seguem a mesma árvore (`tests/cerebro/agentes`,
`tests/servidor`...).

## O caminho de uma pergunta

1. **Entrada.** A interface manda `POST /v1/chat/completions`
   (`servidor/rotas/chat.py`) com o histórico da conversa. Pela voz, o pedido
   vem marcado com `voice: true`.
2. **Comando direto?** `nicx.acoes` reconhece frases como "aumenta o volume",
   "abre o YouTube" ou "que horas são" e executa na hora, sem o modelo
   (`[agent] quick_actions`). A resposta sai em menos de 1 s.
3. **Precisa de ferramenta?** `acoes/roteamento.py` olha a mensagem (e a
   anterior). Conversa comum vai direto ao motor, com streaming e um prompt de
   ~270 tokens. Pedidos de busca, dados atuais, arquivos, PC ou contas vão ao
   agente orquestrador, que recebe a lista de ferramentas
   (`[agent] tools_on_demand`).
4. **Agente.** O orquestrador (`cerebro/agentes/conversa/orchestrator.py`)
   chama o modelo, executa as ferramentas pedidas
   (`ferramentas.ToolExecutor`) sob a política de permissões
   (`seguranca/capabilities.py`) e repete até ter a resposta.
5. **Motor.** `motores/ollama.py` fala com o Ollama. O modelo fica carregado
   20 min entre perguntas (`keep_alive`) e é descarregado quando o Nicx fecha.
6. **Registro.** Telemetria de desempenho e rastros vão para SQLite em
   `~/.nicx/`. Estatísticas de uso só saem da máquina com consentimento
   (`nicx.privacidade`).

### Por que o prompt é tão curto

Com o `qwen3.5` no Ollama, nada do prompt é reaproveitado entre perguntas:
cada token de entrada é relido, a ~15 tokens/s na bateria e ~25 na tomada.
Por isso o prompt de identidade e o `SOUL.md` são compactos, a lista de
ferramentas só vai quando necessária e, na voz, o modelo é instruído a
responder em até duas frases (limite de 200 tokens).

## Pontos de extensão

Componentes se registram em registros (`nucleo/registry.py`) e são achados
pelo nome que aparece na configuração:

| Registro | Exemplo de chave | Onde registrar |
|---|---|---|
| `ToolRegistry` | `controle_pc`, `web_search` | `@ToolRegistry.register("nome")` numa subclasse de `BaseTool` |
| `AgentRegistry` | `orchestrator`, `codeact` | `@AgentRegistry.register("nome")` |
| `EngineRegistry` | `ollama` | motores em `nicx.motores` |
| `ChannelRegistry` | `telegram` | canais em `nicx.canais` |
| `ConnectorRegistry` | `gmail` | conectores em `nicx.conectores` |

Uma ferramenta nova precisa também de uma entrada em
`DEFAULT_TOOL_CAPABILITIES` (`seguranca/capabilities.py`); sem ela, a
segurança trata a ferramenta como administrativa.

## Dados na máquina

Tudo fica em `~/.nicx/` (no Windows, `C:\Users\<você>\.nicx`):

| Arquivo | Conteúdo |
|---|---|
| `config.toml` | configuração |
| `SOUL.md`, `MEMORY.md`, `USER.md` | persona, memória e perfil, enviados no prompt |
| `telemetry.db` | desempenho de cada resposta (tokens, tempo) |
| `traces.db` | rastros das conversas com o agente |
| `memory.db`, `memory_facts.jsonl` | memória de longo prazo |
| `sessions.db`, `agents.db`, `approvals.db` | sessões, agentes gerenciados, aprovações |
| `wake.log`, `server.log` | logs da escuta e do servidor |
