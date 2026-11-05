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

## Imagens e vídeos no chat

Anexe pelo clipe ao lado do campo, cole um print (Win+Shift+S e Ctrl+V) ou
arraste o arquivo para o campo. Escreva a pergunta ou mande só o anexo ("O que
tem nesta imagem?").

- **Imagens:** até 4 por mensagem, reduzidas para 640 px antes de irem ao
  modelo (o `qwen3.5:4b` enxerga). Um modelo sem visão avisa em vez de inventar.
- **Vídeos:** viram 4 quadros espalhados pela duração e, se você instalou a voz,
  a transcrição dos primeiros 3 minutos de áudio (Whisper local). Até 300 MB.
  Um vídeo usa as 4 vagas de imagem da mensagem.
- Tudo fica no PC. As imagens não são guardadas na conversa: depois de fechar o
  app, a mensagem mostra só o nome do arquivo.
- Pela API: `images` (base64) na última mensagem de `/v1/chat/completions`, e
  `POST /v1/anexos/video` (multipart, campo `arquivo`) para os quadros e a fala.

## Contexto: o que eu copiei e a janela aberta

O Nicx enxerga o que você está vendo, sem precisar colar nada:

| Pedido | De onde vem o texto |
|---|---|
| "resume o que eu copiei", "traduz o texto copiado pra inglês", "corrige o que eu copiei", "responde o que eu copiei" | Área de transferência (o que você copiou com Ctrl+C) |
| "explica isso aqui", "o que é esse erro?", "resume essa página", "resume esse documento", "traduz isso pra inglês" | A janela que você estava usando antes do Nicx |
| "lê a tela", "o que tem na minha tela?" | A janela que você estava usando (pelo OCR se ela não tiver texto acessível) |
| "lê o texto da imagem que eu copiei" | Uma imagem copiada (print, "copiar imagem"), pelo OCR |
| "descreve essa imagem", "o que você vê na tela?", "explica esse gráfico", "descreve a imagem que eu copiei" | A imagem da janela (ou a copiada) vai ao modelo, que a descreve |
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
(UI Automation, a mesma dos leitores de tela).

Quando a janela não tem texto acessível (foto, PDF escaneado, vídeo, acesso
remoto, jogo), o Nicx lê o que aparece nela com o **OCR do próprio Windows**:
sem baixar modelo, sem internet, em menos de 1 s. Funciona mesmo com outra
janela na frente (não com ela minimizada). O mesmo vale para uma imagem
copiada: sem texto na área de transferência, ele lê o texto da imagem. A
imagem fica só na memória e nunca é gravada; janelas sensíveis (abaixo) nunca
passam pelo OCR. O idioma do OCR segue o da interface; se ele não estiver
instalado no Windows, usa o do seu perfil.

Para **descrever** uma imagem (uma foto, um gráfico, um desenho), e não só ler
o texto dela, o Nicx manda uma cópia pequena da janela ou da imagem copiada
(até 640 px de lado) ao modelo local, junto com o texto lido por OCR. O
`qwen3.5:4b` já enxerga: não precisa de outro modelo nem de mais memória.
Leva cerca de 50 s num PC sem placa de vídeo (perto de 1 min e 15 s se o
modelo ainda não estava carregado). Se o modelo escolhido não enxergar, vai só
o texto do OCR. Pedidos só de texto ("lê o texto da imagem", "o que está
escrito aqui?") usam só o OCR, que é bem mais rápido. A imagem não é gravada
em lugar nenhum e só vai para modelos locais.

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
ocr = true              # sem texto acessível, ler a janela ou a imagem copiada pelo OCR do Windows
ver_imagens = true      # "descreve essa imagem": mandar a imagem ao modelo (se ele enxergar)
lado_imagem = 640       # maior lado da imagem enviada (menor = mais rápido, menos detalhe)
max_caracteres = 20000
```

`copiar_selecao` só age quando a janela ainda está na frente (pedido por voz
ou atalho) e só se a área de transferência tinha texto (imagens e arquivos
copiados nunca são trocados). O modelo também tem a ferramenta `contexto`,
que entra no prompt só quando a mensagem fala da tela. Só no Windows.

## Mexer nos apps: "clica em Salvar"

O Nicx aciona botões, menus, abas, caixas e campos da janela que você estava
usando, pelo nome que aparece neles:

| Pedido | O que faz |
|---|---|
| "clica em Salvar", "clique no botão Enviar", "aperta o botão OK" | Clica no botão, link ou item |
| "abre o menu Arquivo" | Abre o menu |
| "vai na aba Revisão" | Troca de aba |
| "marca a caixa Lembrar de mim", "desmarca a opção notificações" | Marca ou desmarca |
| "escreve Falkyria no campo Pesquisar" | Escreve no campo |
| "o que dá pra clicar aqui?" | Lista o que dá para usar na janela |

Também em inglês ("click Save", "open the File menu", "type hello into the
search field"), espanhol ("haz clic en Guardar") e francês ("clique sur
Enregistrer"). Não acha o nome? Ele diz o que tem na janela.

Funciona pela acessibilidade do Windows (UI Automation, a mesma dos leitores
de tela): sem mover o mouse e sem foto da tela, em 1 a 3 s. A maioria dos apps
do Windows, Office e navegadores responde; jogos e alguns apps desenhados à mão
não. Por segurança:

- janelas de senha e de banco não são tocadas, e campo de senha nunca é preenchido;
- botões que apagam, enviam, publicam ou pagam ("Excluir", "Enviar", "Comprar"...)
  pedem "confirmo" antes, conferindo pelo nome do botão que ele achou;
- o modelo também pode ver e clicar botões (ferramenta `controle_pc`), mas
  isso passa pelo nível de autonomia: no nível assistido ele pede "confirmo";
- o histórico guarda em qual botão ou campo ele mexeu, nunca o que foi digitado.

## Assistentes: "fala com o Tutor de estudos"

Um assistente é o Nicx com um nome, instruções e as ferramentas que você
escolher: um tutor de estudos, um revisor de textos, um pesquisador. Monte na
página **Assistentes** (sem programar) de três jeitos:

- a partir de um modelo pronto (Tutor de estudos, Revisor de textos, Parceiro de
  código, Organizador do dia, Gerador de ideias, Pesquisador), ajustando o que quiser;
- descrevendo o que quer ("um assistente que me ajuda a estudar para o ENEM"):
  o modelo local monta um rascunho em 30 a 90 s e você revisa antes de salvar;
- do zero.

No chat ou por voz:

| Pedido | O que faz |
|---|---|
| "fala com o assistente Tutor de estudos", "usa o assistente revisor" | Passa a responder como ele (diz a saudação dele) |
| "fala com o Tutor de estudos" | O mesmo, sem a palavra "assistente", se o nome existir |
| "volta pro Nicx", "sai do assistente" | Volta para o Nicx de sempre |
| "quais assistentes eu tenho?", "qual assistente está ativo?" | Lista ou diz qual está em uso |
| "cria um assistente que revisa contratos de aluguel" | O modelo local monta e salva um novo |

Também em inglês ("talk to the study tutor assistant", "back to Nicx"),
espanhol ("habla con el asistente revisor") e francês ("parle à l'assistant
tuteur"). No topo do chat, o seletor mostra quem está respondendo e troca na hora.

O assistente ativo vale para o chat, a voz e a janela flutuante até você voltar
para o Nicx. As instruções dele entram no fim do prompt, sem tirar as regras do
Nicx (segurança, autonomia, confirmações). Cada assistente define:

- **ferramentas**: nenhuma (responde mais rápido, sem a lista de ~600 tokens),
  algumas ou todas. Ferramenta que ele não tem nem aparece para o modelo e, se
  for pedida, é recusada. Ações rápidas ditas por você (volume, lembretes, "clica
  em Salvar") funcionam sempre;
- **memória**: desligada, ele não lê o que o Nicx sabe de você e as conversas com
  ele não vão para a memória (bom para revisar textos e contratos).

Instruções longas deixam cada resposta mais lenta neste PC: cada token é relido
em todo pedido. Criar, mudar e apagar assistentes vai para o Histórico, com
desfazer. Tudo fica em `~/.nicx/assistentes.json`; o ativo, em
`~/.nicx/assistente_ativo.txt`.

## Extensões: pacotes, servidores MCP e habilidades

A página **Extensões** acrescenta capacidades ao Nicx. Tudo fica no PC.

**Pacotes** juntam assistentes, rotinas, habilidades e servidores MCP. Os prontos
(Professor, Estudante, Programador, Criador de conteúdo, Escritório) instalam com
um clique; remover o pacote tira tudo o que ele pôs (o que já era seu fica).
Também dá para importar um pacote recebido (`.nicx.json`): antes de instalar, a
tela mostra o que ele faz (programas que roda, endereços, chaves que pede,
ferramentas dos assistentes, rotinas com horário). Servidores MCP de um pacote só
entram se você marcar, e entram desligados enquanto faltar chave. **Exportar**
monta um pacote com os seus itens; chaves, tokens e senhas nunca vão no arquivo.

**Servidores MCP** dão ao Nicx ferramentas de outros programas: arquivos de uma
pasta, GitHub, Slack, PostgreSQL, busca do Brave... O catálogo adiciona os mais
comuns (precisam do Node.js, por causa do `npx`); "Adicionar outro" aceita
qualquer servidor stdio (programa no PC) ou HTTP. **Testar** liga, lista as
ferramentas e desliga; ao salvar, as ferramentas entram no chat sem reiniciar.
No terminal: `nicx add github --key TOKEN`, `nicx add filesystem --args C:/pasta`.

- token e variáveis de ambiente ficam em `~/.nicx/mcp.json` e nunca voltam pela
  tela (aparecem como `••••••`);
- cada servidor tem uma **confiança**: "pedir confirmação no modo assistido"
  (padrão), "livre" (só leitura, nunca pergunta) ou "sempre pedir confirmação";
- um servidor stdio roda um programa com as suas permissões: adicione só o que
  você conhece.

**Habilidades** são instruções que o Nicx segue quando o pedido combina ("como
fazer uma ata", "como revisar código"), no formato `SKILL.md` em `~/.nicx/skills`.
Crie na tela (título, quando usar, instruções), ligue e desligue sem apagar, ou
importe de um `.zip` ou de um repositório do GitHub. A pasta `scripts/` nunca é
copiada, e habilidade que pede permissão perigosa (rodar comandos, escrever
arquivos, abrir porta) só entra se você confirmar. No chat, cada habilidade ativa
vira a ferramenta `skill_<nome>`.

**Loja da Falkyria** (primeira aba): pacotes revisados e assinados pela Falkyria,
com busca, categorias, número de downloads e aviso de atualização. Antes de
mostrar ou instalar, o Nicx confere a impressão digital (sha256) e a assinatura
Ed25519 do pacote com a chave da Falkyria que vem no app; pacote mexido ou de
outra chave é recusado. Navegar e baixar não envia nada seu (o contador só soma).

Para a Falkyria publicar:

1. monte o pacote (pela tela, em Exportar, ou à mão) com `id` e `versao`;
2. `nicx loja assinar pacote.nicx.json` gera `<id>-<versao>.assinado.json` com a
   chave de `~/.falkyria-loja/` (que nunca sai do PC; guarde uma cópia segura);
3. no Painel Falkyria, seção Loja, envie o arquivo: o Painel confere a assinatura,
   mostra o conteúdo e publica. Ali também dá para esconder ou remover.

Versão nova: suba a `versao` no pacote, assine de novo e envie. `nicx loja
verificar arquivo` confere um arquivo assinado.

Uma mensagem que cita o nome de um servidor, de uma ferramenta dele ou de uma
habilidade manda a lista de ferramentas ao modelo (`[agent] tools_on_demand`).
Adicionar, mudar e remover extensões vai para o Histórico.

## Conta Falkyria (opcional)

O Nicx funciona inteiro sem conta. Com uma (Configurações → Conta Falkyria),
você guarda um **backup criptografado** dos seus assistentes, rotinas,
habilidades, servidores MCP (sem chaves nem senhas) e da lista de pacotes, e
restaura em outro PC. Conversas, memória, notas e arquivos não vão.

- **Criar:** nome (opcional), e-mail e senha (10 caracteres ou mais, com letras e
  números), aceitando os Termos de Uso e a Política de Privacidade. Chega um
  e-mail de confirmação: abra o link (ou digite o código, se vier um) e toque em
  "Já confirmei, entrar".
- **Esqueci a senha:** chega um link que abre a página do site para criar a
  senha nova.
- **Backup:** escolha uma senha de backup (8 caracteres ou mais; não é a da
  conta). O backup é cifrado no PC (scrypt + AES-256-GCM) antes de sair, e a
  Falkyria não consegue abrir. **Senha do backup esquecida = backup perdido.**
  Ficam os 5 mais novos. Restaurar põe de volta o que não existe neste PC e não
  mexe no que já existe; servidores MCP voltam desligados, esperando as chaves.
- **Seus dados (LGPD):** "Baixar meus dados" gera um JSON com tudo o que a
  Falkyria guarda da conta; "Apagar minha conta" (pede a senha) apaga login,
  perfil e backups na hora.
- A sessão fica em `~/.nicx/conta.bin`, protegida pelo Windows (DPAPI); a senha
  nunca é guardada. A conta não tem ligação com as estatísticas anônimas.
- Quando os Termos ou a Política mudam, a conta pede o aceite da versão nova
  antes de continuar.

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

## Histórico, desfazer e autonomia

**Histórico.** O Nicx anota no PC, em `~/.nicx/historico.db`, tudo o que faz:
o começo de cada pedido no chat (ou por voz), anotações, lembretes,
compromissos, projetos, pastas organizadas, arquivos escritos pelo modelo,
ações no PC e cada ferramenta que o modelo usou (com os argumentos). A página
**Histórico** mostra a linha do tempo, com busca (acentos não importam), filtro
por tipo e datas. A aba **Auditoria** mostra só ações e ferramentas, com o
resultado (feito, falhou, bloqueado, esperando "confirmo"), o nível de
autonomia e a origem. Cada linha leva o hash da anterior: se o arquivo for
mexido por fora, a auditoria avisa a partir de qual linha.

```toml
[historico]
ligado = true
guardar_conversas = true  # false: não guarda o começo dos pedidos
dias = 180                # 0 = guarda para sempre
```

Nada do histórico vai para analytics nem para os logs.

**Desfazer.** "Desfaz" (ou "desfaz isso", "undo", "deshaz eso", "défais ça",
"撤销", "पूर्ववत करो", "تراجع") volta a última mudança. Na página Histórico,
o botão **Desfazer** volta uma mudança escolhida, sem perder o que veio depois.
Dá para desfazer:

- lembrete criado ou cancelado; compromisso marcado ou desmarcado (o aviso de
  15 minutos volta junto);
- anotação feita e "apaga minhas anotações";
- pasta organizada ("desfaz a organização" continua valendo);
- projeto criado, mudado ou apagado;
- arquivo escrito pelo modelo (`file_write`, `apply_patch`): volta a cópia de
  antes; um arquivo novo vai para `~/.nicx/desfazer/` em vez de ser apagado.

As cópias ficam em `~/.nicx/desfazer/` por 30 dias (arquivos acima de 5 MB não
ganham cópia). "O que você fez?" lista as últimas mudanças.

**Autonomia.** Diz o que o Nicx faz sozinho quando é **o modelo** que decide
agir (um comando que você mesmo fala ou digita já é a autorização). Em
Configurações → Autonomia, ou:

```toml
[autonomia]
nivel = "assistido"   # observador | assistido | autonomo
```

| Nível | Faz sozinho | Pede "confirmo" |
|---|---|---|
| observador | só consultas (hora, ler arquivo, pesquisar) | qualquer mudança |
| assistido (padrão) | consultas e mudanças leves (lembrete, anotação, abrir app, volume) | escrever arquivo, organizar pasta, fechar app, apagar em lote |
| autônomo | também arquivos e projetos (sempre com desfazer) | só o que é de risco alto |

Desligar, reiniciar, rodar comandos no terminal e `git commit` pedem
"confirmo" em qualquer nível. Quando o modelo precisa de confirmação, ele
avisa e a ação espera até 2 minutos pelo seu "confirmo" (ou "cancela"). A
regra fica no código das ferramentas: um texto escondido numa página não faz
o Nicx pular a confirmação.

API: `GET /v1/historico?busca=&tipos=&desde=&ate=&limite=&antes_de=`,
`POST /v1/historico/desfazer` (`{"id": 12}` ou vazio para a última),
`GET /v1/historico/integridade`, `GET/PUT /v1/autonomia`.

## Rotinas e modo foco

Uma rotina junta várias ações rápidas com um nome. Crie na página **Rotinas**
ou falando:

> "Cria a rotina preparar faculdade: abre o chrome, abre o vs code, volume em
> 30, timer de 50 minutos, toda segunda às 9h"

Cada trecho entre vírgulas é um comando que o Nicx já entende sozinho; o
horário é opcional ("todo dia às 7h30", "de segunda a sexta às 8", "fim de
semana às 10", "every weekday at 8 am"). Para rodar, diga o nome
("preparar faculdade") ou "roda a rotina preparar faculdade". "Minhas
rotinas" lista; "apaga a rotina X" apaga (e "desfaz" traz de volta).

Podem entrar: volume, mídia, abrir apps, sites (`https://`) e pastas,
pesquisar, tocar no YouTube, fechar apps, anotar, lembretes e timers (contados
a partir da hora em que a rotina roda), bloquear a tela, print, hora, data,
bateria, estado do PC, agenda e resumo do dia. Desligar o PC, organizar pastas
e apagar em lote não entram numa rotina.

Com horário, a rotina roda sozinha com o `nicx serve` ligado, uma vez por dia,
nos dias marcados. Se o servidor só ligar depois, ela ainda roda até 2 horas
depois da hora; mais tarde que isso, fica para o próximo dia marcado. Ao rodar
pelo horário aparece uma notificação com o que foi feito.

**Modo foco** (pronto, editável na página Rotinas): "modo foco" ou "ativa o
modo foco" fecha o WhatsApp, deixa o volume em 25% e marca 50 minutos. O "não
perturbe" do Windows não é ligado: o Windows não oferece um jeito estável de
fazer isso por programa.

As rotinas ficam em `~/.nicx/rotinas.json`. API: `GET/POST /v1/rotinas`,
`PUT/DELETE /v1/rotinas/{id}`, `POST /v1/rotinas/{id}/executar`,
`POST /v1/rotinas/interpretar`, `GET /v1/rotinas/opcoes`.

## Planejador de objetivos

> "Monta um plano para aprender inglês até dezembro"

O modelo local divide o objetivo em etapas, com o tempo de cada uma e o que
depende do quê (leva de 30 s a 1 min e meio neste PC). O plano vira um projeto
com prazo: cada etapa ganha uma data, proporcional ao tempo estimado, e um
lembrete às 9h desse dia. Concluir a etapa (na página Projetos ou "conclui a
pendência X do projeto Y") cancela o lembrete. Prazos aceitos: "até dezembro", "até
15/12", "em 3 meses", "daqui a duas semanas", "até o fim do ano", "by
December 15", "in 6 weeks", "hasta diciembre", "dans 6 semaines".

Na página **Planejador** dá para revisar as etapas antes de criar, ver o
progresso de cada plano (feito, atrasado, se está no ritmo) e **reajustar**: as
etapas abertas são redistribuídas até o prazo (ou um prazo novo) e os
lembretes trocados. Planos só são montados com modelos locais.

API: `POST /v1/planejador/propor`, `POST /v1/planejador`,
`GET /v1/planejador/{projeto_id}`, `POST /v1/planejador/{projeto_id}/reajustar`,
`POST /v1/planejador/prazo`.
