# Configuração

A configuração fica em `~/.nicx/config.toml`, criado pelo `nicx init`. Só é
preciso escrever o que muda em relação ao padrão. Para ver tudo o que está
valendo: `nicx config show`.

## Exemplo

```toml
[engine]
default = "ollama"

[engine.ollama]
num_ctx = 8192        # janela de contexto; 4096 se faltar memória
keep_alive = "20m"    # tempo que o modelo fica carregado sem uso

[intelligence]
default_model = "qwen3.5:4b"

[agent]
quick_actions = true    # comandos diretos sem o modelo
tools_on_demand = true  # ferramentas só quando a mensagem precisa

[tools]
enabled = ["controle_pc", "code_interpreter", "web_search", "file_read", "shell_exec"]

[speech]
model = "small"         # Whisper da conversa
language = "pt"
voice_id = "pf_dora"    # voz do Kokoro
wake_word = false       # "Nicx, ligar"

[analytics]
enabled = false         # estatísticas de uso, só com consentimento

[security]
profile = "personal"
```

## Opções principais

### Motor e modelo

| Chave | Padrão | Para que serve |
|---|---|---|
| `[engine] default` | `ollama` | Motor de inferência. |
| `[engine.ollama] host` | `http://localhost:11434` | Endereço do Ollama (também `OLLAMA_HOST`). |
| `[engine.ollama] num_ctx` | `8192` | Janela de contexto. Mais contexto = mais RAM (`NICX_NUM_CTX`). |
| `[engine.ollama] keep_alive` | `20m` | Tempo carregado sem uso; `0` descarrega após cada resposta (`NICX_KEEP_ALIVE`). |
| `[intelligence] default_model` | — | Modelo padrão. |

### Agente

| Chave | Padrão | Para que serve |
|---|---|---|
| `[agent] quick_actions` | `true` | Executa "aumenta o volume", "que horas são" etc. na hora. |
| `[agent] tools_on_demand` | `true` | Manda a lista de ferramentas só quando a mensagem precisa (economiza ~600 tokens). |
| `[agent] default_system_prompt` | identidade do Nicx | Prompt de identidade, curto de propósito. |
| `[server] agent` | `orchestrator` | Agente que atende o chat. |
| `[tools] enabled` | ver exemplo | Ferramentas disponíveis para o agente. |

A personalidade fica em `~/.nicx/SOUL.md`; o que o Nicx deve lembrar de você,
em `MEMORY.md` e `USER.md`. Os três vão no prompt, então mantenha-os curtos.

### Voz

Veja [Voz](voz.md).

### Privacidade

`[analytics] enabled` só deve ser ligado com o consentimento de quem usa; o
app, o `nicx init` e o instalador perguntam. Veja [Privacidade](privacidade.md).
