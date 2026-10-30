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

## Atalho de teclado

Uma combinação de teclas chama o Nicx de qualquer janela. Fica **desligado**
até você ligar em **Configurações → Atalho de teclado** (ou no `config.toml`):

```toml
[atalho]
ativo = true
teclas = "ctrl+alt+n"   # modificadores + uma tecla
acao = "flutuante"      # "flutuante": mascote já ouvindo; "app": abre o app
```

- No app, clique no campo da combinação e aperte as teclas juntas; Esc cancela.
- Precisa de Ctrl, Alt ou Win. Combinações do sistema ou de uso geral
  (Ctrl+Alt+Del, Win+L, Alt+Tab, Ctrl+C...) são recusadas.
- Se a janela já estiver aberta, o atalho só a traz para a frente.
- Se outro programa já usa a combinação, as Configurações mostram "Em uso por
  outro programa" e o log do servidor avisa: grave outra.
- O atalho vive no servidor do Nicx (`nicx serve`/`nicx start`): só funciona
  com ele ligado. Só no Windows; nos outros sistemas o servidor registra no log
  que não há suporte.

## Ditado

Em qualquer programa (Word, navegador, e-mail, chat...): aperte o atalho do
ditado, fale, e o texto é digitado onde está o cursor. Fica **desligado** até
você ligar em **Configurações → Ditado** (ou no `config.toml`):

```toml
[ditado]
ativo = true
teclas = "ctrl+alt+d"   # mesmas regras do [atalho]; diferente dele
modo = "alternar"       # ou "segurar" (grava enquanto a tecla está apertada)
idioma = ""             # "pt-BR", "en"...; vazio = o de [speech] language
som = true              # bipe curto ao começar e ao terminar
```

- **alternar**: aperte para começar e de novo para parar. Para sozinho após
  ~1,5 s de silêncio; no máximo 60 s. Se ninguém falar nos primeiros segundos,
  nada é digitado.
- O texto vai para a janela que estava em foco quando você apertou o atalho
  (o Nicx devolve o foco a ela). Se ela fechou ou não aceitar o foco, nada é
  digitado. Programas abertos como administrador não aceitam o ditado.
- A digitação é tecla a tecla (não usa a área de transferência: o que você
  copiou continua lá). A quebra de linha vai como Shift+Enter, para não enviar
  mensagens em programas de chat.
- Pontuação e maiúsculas são as do Whisper. Comandos de voz, em português e
  no idioma escolhido: "nova linha", "novo parágrafo", "ponto final" e
  "vírgula" (em inglês: "new line", "new paragraph", "full stop", "comma").
- Com a janela flutuante aberta, o mascote mostra "Ditado: ouvindo…" e a
  conversa por voz dela pausa até o ditado acabar.
- Privacidade: tudo local (microfone, VAD e Whisper do `[speech]`). O áudio só
  existe na memória; o texto não vai para a memória do Nicx nem para os logs
  (o log mostra só o tamanho).
- Como o atalho, vive no servidor do Nicx e só funciona no Windows.

## Contexto: o que eu copiei e a janela aberta

O Nicx enxerga o que você está vendo, sem precisar colar nada:

| Pedido | De onde vem o texto |
|---|---|
| "resume o que eu copiei", "traduz o texto copiado pra inglês", "corrige o que eu copiei", "responde o que eu copiei" | Área de transferência (o que você copiou com Ctrl+C) |
| "explica isso aqui", "o que é esse erro?", "resume essa página", "resume esse documento", "traduz isso pra inglês" | A janela que você estava usando antes do Nicx |
| "onde eu tô?" | Responde na hora: o app e o arquivo aberto |

Também em inglês ("summarize what I copied", "explain this page", "where am
I?"), espanhol ("resume lo que copié", "¿qué es este error?") e francês
("résume ce que j'ai copié", "explique cette page", "où suis-je ?").

Da janela, nesta ordem: o **texto selecionado**; o **arquivo aberto** (o nome
vem do título no VS Code, Bloco de Notas, Word, Excel, leitores de PDF... e o
arquivo só é lido se estiver na Área de Trabalho, Documentos, Downloads,
OneDrive, num projeto recente do VS Code ou em `[contexto] pastas_extras`);
o **texto da página ou do documento** (navegador, Word); os textos de uma
caixa de erro. Seleção e página são lidas pela acessibilidade do Windows
(UI Automation, a mesma dos leitores de tela). Se nada disso der texto,
copie (Ctrl+C) e peça "explica o que eu copiei".

"Traduz isso" sozinho só vale na primeira mensagem da conversa (ou por voz):
no meio da conversa, "isso" é a resposta anterior do Nicx.

O texto vai para o **modelo local** junto com o pedido, no fim da mensagem,
marcado como dado (o modelo é instruído a não seguir ordens escritas nele) e
cortado para caber no contexto do modelo. Nunca sai do PC (com um modelo da
nuvem escolhido, o Nicx se recusa), não vai para a memória automática nem
para os logs e rastros. Janelas de gerenciadores de senha (KeePass,
1Password, Bitwarden...), de banco e com "senha"/"password" no título não são
lidas, nem o que um gerenciador de senhas copiou.

Configurações → Contexto da tela, ou no `config.toml`:

```toml
[contexto]
ativo = true            # ler a área de transferência e a janela
copiar_selecao = false  # sem texto acessível, apertar Ctrl+C e devolver o que estava copiado
max_caracteres = 20000
```

`copiar_selecao` só age quando a janela ainda está na frente (pedido por voz
ou atalho) e só se a área de transferência tinha texto (imagens e arquivos
copiados nunca são trocados). O modelo também tem a ferramenta `contexto`,
que entra no prompt só quando a mensagem fala da tela. Só no Windows.

## Projetos e continuar de onde parei

O Nicx guarda os seus projetos: objetivo, estado (onde você parou, em uma
frase), pastas e arquivos, decisões, pendências e próximos passos. Página
**Projetos** no menu, ou pelo chat e pela voz:

| Pedido | O que faz |
|---|---|
| "cria o projeto Site Novo na pasta C:\dev\site" | Cria (a pasta pode ser o caminho ou o nome de uma pasta aberta no VS Code) |
| "quais meus projetos?", "como está o projeto Lumen?", "o que falta no projeto Lumen?" | Responde na hora |
| "anota no projeto Lumen que decidimos usar Postgres", "decisão no projeto Lumen: …" | Registra a decisão |
| "adiciona pendência no projeto Lumen: comprar o domínio", "conclui a pendência comprar o domínio do projeto Lumen" | Pendências |
| "atualiza o estado do projeto Lumen: API pronta", "arquiva o projeto Lumen", "renomeia o projeto Lumen para …" | Estado, arquivar, renomear |
| "continue de onde parei", "o que eu estava fazendo?", "vamos continuar" | Resumo + sugestão do próximo passo (pelo modelo) |

Também em inglês ("pick up where I left off", "what's left in project X?"),
espanhol ("continúa donde lo dejé", "¿cómo va el proyecto X?") e francês
("reprends où j'en étais", "où en est le projet X ?"). As respostas diretas
saem na hora, sem modelo, nos 7 idiomas. "Vamos continuar" sozinho só vale
na primeira mensagem da conversa.

"Continue de onde parei" escolhe o projeto aberto na janela em uso (pasta do
VS Code ou arquivo dentro de uma pasta do projeto) ou o de atividade mais
recente, e manda ao modelo local um resumo curto (até ~3.000 caracteres):
estado, pendências abertas, últimas decisões, últimos commits e arquivos
alterados (`git` local, sem rede), arquivos mexidos por último e lembretes ou
compromissos que citam o projeto. O modelo diz onde você parou, o que falta,
sugere o próximo passo e pergunta se quer seguir por ali. Com um modelo da
nuvem escolhido, o Nicx se recusa.

A atividade é marcada quando você fala do projeto ou trabalha numa pasta dele
(o Nicx olha a janela a cada 2 minutos e grava no máximo a cada 5, só com a
leitura da tela ligada). Quando a conversa cita "o projeto X" (um que já
existe) com "decidimos…" ou "falta…/preciso…", a memória automática anota a
decisão ou a pendência como **sugerida**; nunca cria projeto sozinha.

Tudo fica em `~/.nicx/projetos.json` (gravação atômica; a versão anterior em
`projetos.json.bak`; um arquivo estragado é guardado como
`projetos.json.corrompido` e os projetos voltam do `.bak`). Nada vai para
logs nem analytics. O modelo também tem a ferramenta `projetos`, que entra no
prompt só quando a mensagem fala de projeto.

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
| Agenda | "marca reunião com o João sexta às 15h", "agenda dentista dia 30", "o que eu tenho amanhã?", "minha agenda da semana", "desmarca a reunião de sexta", "manda pro calendário do Windows" |
| Google Agenda e Outlook | "manda pro Google Agenda", "manda a reunião de sexta pro Outlook", "coloca isso no Outlook do trabalho", "manda meus compromissos pro Google Agenda", "marca dentista sexta às 10h no Google Agenda", "manda pro calendário" (vai para o calendário padrão) |
| Arquivos | "procura o arquivo do contrato", "onde está a planilha de gastos", "abre o PDF do contrato", "abre o último download", "o que tem na pasta downloads" |
| Fotos | "abre a última foto", "mostra o último print", "abre a foto da praia" |
| Organizar | "organiza a pasta downloads", "arruma minha área de trabalho" (pede "confirmo"); "desfaz a organização" |
| YouTube | "toca Tempo Perdido", "toca Legião Urbana no YouTube", "abre o vídeo do gato no YouTube" |
| Estado do PC | "como tá o computador?" (processador, memória, disco, bateria e o que mais pesa) |
| Pastas | "abre a pasta downloads", "abre meus documentos", "abre a área de trabalho" |
| Print | "tira um print" (salva em Imagens\Nicx) |
| Fechar apps | "fecha o Chrome" (como clicar no X: o app pode pedir para salvar) |
| Energia | "desliga o PC", "reinicia o PC", "suspende o PC" (sempre pede "confirmo"); "cancela o desligamento" |
| Sistema | "bloqueia o computador" |
| Resumo do dia | "resumo do dia", "como foi meu dia?", "o que eu fiz hoje?", "o que ficou pendente hoje?", "resumo de ontem" |

Os lembretes ficam em `~/.nicx/lembretes.json` e as anotações em
`~/.nicx/notas.md`. Na hora marcada, o Nicx mostra uma notificação do Windows
e fala o lembrete (se a voz local estiver instalada). O aviso depende do
servidor do Nicx estar ligado; lembretes que venceram com ele desligado são
avisados assim que ele voltar, dizendo que passaram da hora.

Desligar, reiniciar e suspender só acontecem por comando direto e com
confirmação: o modelo de linguagem não tem acesso a eles.

A agenda fica em `~/.nicx/agenda.json` e avisa 15 minutos antes de cada
compromisso (os de dia todo, às 8h). Lembretes e avisos saem no idioma em
que foram pedidos ("Reminder: …" para um pedido em inglês), mesmo que a
interface mude depois.

### Google Agenda e Outlook

"Manda pro calendário" usa o **calendário padrão**, escolhido em
Configurações → Calendário (ou `[agenda] calendario_padrao` no
`config.toml`):

| Valor | O que acontece |
|---|---|
| `windows` (padrão) | Gera um `.ics` e abre no calendário do Windows. |
| `google` | Google Agenda. |
| `outlook` | Outlook pessoal (outlook.live.com). |
| `outlook_trabalho` | Outlook de trabalho ou escola (outlook.office.com). |

Dizer o nome ("manda pro Google Agenda", "manda pro Outlook do trabalho")
vale para aquele pedido. Sem dizer qual, vai o **último compromisso marcado**;
"manda a reunião de sexta…" manda aquele; "manda meus compromissos…" manda
todos (no navegador, até 5 abas de cada vez).

Dois caminhos, nesta ordem:

1. **Direto na conta**: com o Google Agenda conectado (Fontes de dados) e
   permissão de escrita, o evento é criado na agenda principal. No Outlook,
   só se algum conector tiver guardado um token do Microsoft Graph com
   `Calendars.ReadWrite` (o conector de e-mail do Outlook usa senha de app e
   não serve para isso). O id do evento criado fica guardado no compromisso,
   então pedir de novo não duplica.
2. **Link pré-preenchido**: sem conta, sem permissão ou sem internet, o
   navegador abre o evento já preenchido (título, data, hora e fuso
   `America/Sao_Paulo`); é só clicar em Salvar. Sem fim definido, o evento
   dura 1 hora.

Quem conectou o Google antes desta versão com permissão só de leitura ouve
o pedido para reconectar o Google Agenda: a conexão nova já pede
`calendar.events`. Nada muda para quem não reconectar; o link continua
funcionando.

"O que eu tenho amanhã?" também mostra os eventos do Google Agenda que o
conector já sincronizou, marcados com "(Google Agenda)" (só leitura, sem ir à
internet na hora).

Os arquivos são procurados nas pastas do usuário (Área de Trabalho,
Documentos, Downloads, Imagens, Vídeos, Músicas e OneDrive), sem entrar em
pastas de sistema. Organizar separa os arquivos soltos da pasta em
subpastas por tipo (Imagens, PDFs, Documentos, Planilhas, Instaladores...),
nunca apaga nada, pula o que ainda está baixando e guarda um registro em
`~/.nicx/organizacao/` para desfazer.

"Toca X" abre direto o primeiro vídeo da busca no YouTube; sem internet ou
se a página mudar, abre a busca.

Gentilezas em volta ("Nicx, por favor…", "…pra mim") não atrapalham.
Perguntas sobre o assunto ("como eu aumento o volume do Windows?") vão para o
modelo. Pedidos mais livres ("tá muito alto esse som") também vão ao modelo,
que usa a ferramenta `controle_pc`.

Volume e mídia usam as teclas multimídia do Windows; em outros sistemas
funcionam abrir sites, hora, data e bateria.

## Resumo do dia

"Resumo do dia", "como foi meu dia?", "o que eu fiz hoje?", "o que ficou
pendente hoje?" e "resumo de ontem" (também em inglês, espanhol e francês)
respondem na hora, sem o modelo. O resumo junta, só do dia:

- compromissos que já passaram e os que ainda vêm (agenda do Nicx e eventos
  que o conector do Google Agenda/Outlook já trouxe);
- lembretes que tocaram e os que ainda vêm (timers, alarmes e avisos de
  compromisso ficam de fora);
- quantas anotações foram feitas e as 3 últimas;
- pastas organizadas (organizações desfeitas não contam);
- projetos mexidos, pendências concluídas e as que ficaram abertas.

Seções vazias somem, e a última frase diz o que tem amanhã. "O que ficou
pendente" mostra só o que falta. Os lembretes que já tocaram ficam
registrados por 14 dias em `~/.nicx/lembretes_disparados.json`.

**Resumo automático** (desligado por padrão): em Configurações → Resumo do
dia, ou no `config.toml`:

```toml
[resumo]
ativo = true
hora = "18:00"
falar = true       # com a voz local, se instalada
notificar = true   # notificação do Windows
dias = ["seg", "ter", "qua", "qui", "sex"]
```

Com o `nicx serve` ligado, no horário (e nos dias marcados) o Nicx mostra a
notificação e fala o resumo, uma vez por dia. Se o servidor só ligar depois
do horário, o resumo sai assim que ele subir, no mesmo dia. A data do último
envio fica em `~/.nicx/resumo_estado.json`. O idioma é o da voz
(`[speech] language`).

Na tela, "Ver resumo de hoje" mostra o texto; "Deixar mais natural" pede ao
modelo local para reescrevê-lo (leva uns segundos a mais; modelo da nuvem
nunca é usado). API: `GET /v1/resumo?dia=AAAA-MM-DD&idioma=pt-BR`
(`&refinar=true` para o modelo) e `GET/PUT /v1/resumo/config`. Nada do
resumo vai para analytics nem para os logs.
