# Política de Privacidade do Nicx

**Versão 2026-11-05**

Esta política explica quais dados o **Nicx**, a inteligência artificial da
**Falkyria**, trata, por quê, e como você controla isso. Ela vale para o
programa de linha de comando, o app desktop e a interface no navegador.

## Resumo

- **Suas conversas, arquivos e memórias ficam no seu computador.** O Nicx roda
  com modelos de IA locais e não envia esse conteúdo para a Falkyria.
- **Estatísticas e relatórios de erro só com a sua permissão.** Se você
  aceitar, o Nicx envia dados anônimos de uso (quais recursos você usa, tempos,
  erros e avisos técnicos, saúde do programa), nunca o conteúdo do que você
  escreve.
- **Conta Falkyria é opcional.** Se você criar uma, guardamos o seu e-mail, o
  nome (se informar), quando você aceitou estes termos e os seus backups, que
  vão **cifrados** do seu computador: a Falkyria não consegue lê-los.
- **Você manda.** Pode recusar, mudar de ideia, baixar ou apagar o que já foi
  enviado a qualquer momento.

## 1. Quem é responsável pelos dados

A **Falkyria** é a controladora dos dados descritos nesta política, nos termos
da Lei Geral de Proteção de Dados (Lei nº 13.709/2018, "LGPD").

Contato para assuntos de privacidade: **arthurgaspare@gmail.com**.

## 2. O que fica apenas no seu computador

Tudo o que você faz no Nicx é processado e guardado localmente, na pasta de
dados do Nicx (por padrão `~/.nicx`):

- conversas, perguntas e respostas;
- arquivos, documentos e memórias que você indexa;
- áudio do microfone e voz sintetizada (o reconhecimento e a síntese de voz
  rodam no seu computador);
- histórico de uso, métricas de desempenho e de energia (telemetria local);
- configurações e chaves de serviços que você conectar.

A Falkyria não tem acesso a nada disso.

Algumas ferramentas, quando você as usa, acessam a internet por conta própria:
por exemplo, a busca na web consulta um mecanismo de busca e os conectores
(e-mail, agenda etc.) falam com os serviços que você autorizar. Esses acessos
seguem as políticas desses serviços e não passam pela Falkyria.

A **Loja da Falkyria** (página Extensões) busca o catálogo e os pacotes nos
servidores da Falkyria quando você abre a página ou instala um pacote dela.
Esse pedido não leva nada sobre você nem sobre o que você faz no Nicx; o
contador de downloads de cada pacote só soma um, sem saber quem baixou. Como
em qualquer acesso à internet, o provedor de infraestrutura pode registrar o
endereço IP (veja a seção 3). A loja não depende da permissão de estatísticas
e só é acessada quando você a abre.

Para saber se há **versão nova do Nicx**, o app baixa uma vez por dia o
arquivo público de versões das releases do Nicx no GitHub (onde fica o
instalador) e confere a assinatura da Falkyria. Esse pedido não leva nada
sobre você; o GitHub, como provedor, pode registrar o endereço IP. Você
desliga isso na página Atualizações (opção "Procurar sozinho") e ainda pode
procurar quando quiser. Instalar a versão nova é sempre escolha sua.

## 3. O que enviamos se você permitir

Com o seu consentimento, o Nicx envia à Falkyria **estatísticas anônimas de
uso**:

| Dado | Exemplo |
|---|---|
| Eventos de uso | o app foi aberto; um recurso foi usado (voz, memória, ferramentas); uma sessão de conversa terminou |
| Contagens e tempos | número de mensagens, tokens, tempo de resposta, duração da sessão |
| Erros mostrados | apenas o tipo do erro (por exemplo, "modelo não encontrado") |
| Avisos e erros técnicos | a mensagem técnica do programa, limpa no seu computador antes do envio (sem textos entre aspas, caminhos, e-mails, links, IPs ou números longos), o tipo do erro, o ponto do código do Nicx onde ocorreu e quantas vezes aconteceu |
| Saúde do Nicx | motor e família do modelo em uso (por exemplo, "qwen3.5"), se o Nicx precisou ligar o motor, recursos de voz ligados, tempo de abertura, memória usada pelo Nicx, uso de memória e processador do computador, total de memória e de núcleos |
| Instalação | etapas concluídas ou que falharam |
| Ambiente | versão do Nicx, sistema operacional, arquitetura do processador |
| Modelo | família pública do modelo (por exemplo, "qwen3.5") ou o identificador transformado em código irreversível (hash) |
| Identificador | um código aleatório criado na instalação, que não revela quem você é |
| Consentimento | quando você aceitou ou recusou, e a versão desta política |

**Nunca** enviamos: o conteúdo de conversas ou perguntas, arquivos, nomes de
arquivos ou pastas, seu nome, e-mail, telefone ou dados de contas conectadas.
O Nicx filtra os dados antes do envio e descarta qualquer informação que não
esteja na lista acima.

O provedor de infraestrutura pode registrar o endereço IP de cada envio em
registros técnicos de acesso, por tempo limitado e para fins de segurança. A
Falkyria não guarda o IP na base de estatísticas.

## 4. Conta Falkyria (opcional)

O Nicx funciona inteiro sem conta. Se você criar uma, tratamos:

| Dado | Para quê |
|---|---|
| E-mail e senha | entrar na conta; mandar o código de confirmação e o de nova senha. A senha é guardada pelo serviço de login só como código irreversível (hash) e nunca fica no Nicx |
| Nome (opcional) | mostrar na conta |
| Aceite | qual versão dos Termos de Uso e desta política você aceitou, e quando |
| Backups | guardar e devolver, quando você pedir, seus assistentes, rotinas, habilidades, servidores MCP (sem chaves nem senhas) e a lista de pacotes |
| Registros de acesso | data do cadastro e do último login; o serviço de login registra o endereço IP e o navegador por segurança, por tempo limitado |

**Os backups são cifrados no seu computador** (AES-256, com uma chave tirada da
senha do backup) antes de sair dele. A senha do backup não é enviada nem
guardada: a Falkyria não consegue abrir os backups, e se você a esquecer não há
como recuperá-los. Ficam guardados os 5 backups mais novos de cada conta. No
computador, a sessão fica protegida pelo Windows.

Conversas, memória, notas e arquivos **não** vão para a conta. A conta não tem
ligação com o identificador anônimo das estatísticas: uma coisa não leva à
outra.

**Base legal:** a execução do contrato que você aceita ao criar a conta (LGPD,
art. 7º, V). **Por quanto tempo:** enquanto a conta existir. Ao apagá-la, o
login, o perfil e todos os backups são excluídos na hora.

**No próprio Nicx** (Configurações → Conta Falkyria): ver os seus dados,
corrigir o nome, **baixar tudo** o que a Falkyria guarda da conta (arquivo
JSON) e **apagar a conta**.

## 5. Para que usamos as estatísticas

Somente para melhorar o Nicx: entender se a instalação funciona, quais recursos
são usados, onde ocorrem erros e como está o desempenho. Não usamos esses dados
para publicidade, não traçamos perfis de pessoas e **não vendemos nem
compartilhamos** os dados com terceiros.

## 6. Base legal

O envio de estatísticas se baseia no seu **consentimento** (LGPD, art. 7º, I);
a Conta Falkyria, na execução do contrato (seção 4).
Ele é opcional: recusar não muda nenhuma função do Nicx. Você pode revogá-lo a
qualquer momento, e a revogação vale a partir daquele momento.

## 7. Onde os dados ficam e por quanto tempo

As estatísticas, a Conta Falkyria e a Loja ficam no **Supabase**, em servidores
localizados em **São Paulo, Brasil**. O Supabase atua como operador, tratando os dados apenas
conforme as instruções da Falkyria.

Os eventos são **apagados automaticamente após 24 meses**; os avisos e erros
técnicos, **após 90 dias**.

O acesso é restrito a administradores da Falkyria, que entram com senha **e**
um código de verificação de um aplicativo autenticador; cada acesso fica
registrado. A comunicação é criptografada (HTTPS) e as regras do banco de dados
só permitem que o Nicx **adicione** estatísticas: nenhuma instalação consegue
ler os dados de outra, e cada conta só vê o que é dela.

## 8. Seus direitos

Pela LGPD (art. 18), você pode pedir confirmação de tratamento, acesso,
correção, anonimização, portabilidade, eliminação dos dados, informação sobre
compartilhamento e revogação do consentimento.

No próprio Nicx:

- **Mudar a escolha**: Configurações → Privacidade, ou
  `nicx config set analytics.enabled false` no terminal.
- **Apagar o que já foi enviado**: Configurações → Privacidade → "Apagar meus
  dados". Isso exclui dos servidores da Falkyria todos os eventos desta
  instalação e cria um novo identificador.
- **Conta Falkyria**: Configurações → Conta Falkyria → "Baixar meus dados" ou
  "Apagar minha conta".

Para os demais pedidos, ou se tiver dúvidas, escreva para o contato da seção 1.
Você também pode reclamar à Autoridade Nacional de Proteção de Dados (ANPD).

## 9. Crianças e adolescentes

O Nicx não se destina a menores de 18 anos sem a supervisão de um responsável.

## 10. Mudanças nesta política

Quando esta política mudar de forma relevante, a versão no topo será
atualizada e o Nicx pedirá o seu consentimento de novo antes de enviar
qualquer estatística; quem tem Conta Falkyria aceita a versão nova antes de
continuar a usá-la.
