# Uso

## O app

```bash
uv run nicx gui
```

Sobe o servidor (porta 8000) e a interface, e abre o navegador. No app:
conversa por texto, **Conversa por voz** (mãos livres), modelos, memória,
agentes, conectores e **Configurações** (inclusive Privacidade). Fechar com
`nicx stop` também descarrega o modelo da memória.

## Terminal

| Comando | O que faz |
|---|---|
| `nicx ask "pergunta"` | Uma pergunta, uma resposta. |
| `nicx chat` | Conversa contínua; `nicx chat --voice` para falar. |
| `nicx serve` | Só o servidor da API (compatível com OpenAI). |
| `nicx start` / `stop` / `status` | Servidor em segundo plano. |
| `nicx escuta` | Liga a escuta do "Nicx, ligar". |
| `nicx mascote` | Abre o mascote flutuante já ouvindo. |
| `nicx model list` / `pull` | Modelos do Ollama. |
| `nicx memory` | Memória de longo prazo. |
| `nicx doctor` | Diagnóstico da instalação. |
| `nicx legal privacidade` | Política de privacidade (também `termos`, `consentimento`). |
| `nicx config show` | Configuração carregada. |

Todos aceitam `--help`.

## Ações rápidas

Frases que o Nicx executa na hora, sem passar pelo modelo (texto ou voz):

| Pedido | Exemplos |
|---|---|
| Volume | "aumenta o volume", "abaixa o som um pouco", "volume em 30%", "volume no máximo", "muta" |
| Mídia | "pausa a música", "próxima música", "música anterior" |
| Abrir | "abre o YouTube", "abre o bloco de notas", "abre o VS Code", "abre as configurações" |
| Pesquisar | "pesquisa receita de bolo no YouTube", "pesquisa X no Google" |
| Informações | "que horas são", "que dia é hoje", "quanto de bateria tem" |
| Sistema | "bloqueia o computador" |

Gentilezas em volta ("Nicx, por favor…", "…pra mim") não atrapalham.
Perguntas sobre o assunto ("como eu aumento o volume do Windows?") vão para o
modelo. Pedidos mais livres ("tá muito alto esse som") também vão ao modelo,
que usa a ferramenta `controle_pc`.

Volume e mídia usam as teclas multimídia do Windows; em outros sistemas
funcionam abrir sites, hora, data e bateria.
