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
| Lembretes | "me lembra de tirar o bolo em 20 minutos", "me lembra amanhã às 8 de pagar a conta", "timer de 5 minutos", "alarme para as 7 da manhã", "quais meus lembretes", "cancela os lembretes" |
| Anotações | "anota: comprar pão", "lê minhas anotações", "apaga minhas anotações" |
| Estado do PC | "como tá o computador?" (processador, memória, disco, bateria e o que mais pesa) |
| Pastas | "abre a pasta downloads", "abre meus documentos", "abre a área de trabalho" |
| Print | "tira um print" (salva em Imagens\Nicx) |
| Fechar apps | "fecha o Chrome" (como clicar no X: o app pode pedir para salvar) |
| Energia | "desliga o PC", "reinicia o PC", "suspende o PC" (sempre pede "confirmo"); "cancela o desligamento" |
| Sistema | "bloqueia o computador" |

Os lembretes ficam em `~/.nicx/lembretes.json` e as anotações em
`~/.nicx/notas.md`. Na hora marcada, o Nicx mostra uma notificação do Windows
e fala o lembrete (se a voz local estiver instalada). O aviso depende do
servidor do Nicx estar ligado; lembretes que venceram com ele desligado são
avisados assim que ele voltar, dizendo que passaram da hora.

Desligar, reiniciar e suspender só acontecem por comando direto e com
confirmação: o modelo de linguagem não tem acesso a eles.

Gentilezas em volta ("Nicx, por favor…", "…pra mim") não atrapalham.
Perguntas sobre o assunto ("como eu aumento o volume do Windows?") vão para o
modelo. Pedidos mais livres ("tá muito alto esse som") também vão ao modelo,
que usa a ferramenta `controle_pc`.

Volume e mídia usam as teclas multimídia do Windows; em outros sistemas
funcionam abrir sites, hora, data e bateria.
