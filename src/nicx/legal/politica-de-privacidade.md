# Política de Privacidade do Nicx

**Versão 2026-10-23**

Esta política explica quais dados o **Nicx**, a inteligência artificial da
**Falkyria**, trata, por quê, e como você controla isso. Ela vale para o
programa de linha de comando, o app desktop e a interface no navegador.

## Resumo

- **Suas conversas, arquivos e memórias ficam no seu computador.** O Nicx roda
  com modelos de IA locais e não envia esse conteúdo para a Falkyria.
- **Estatísticas de uso só com a sua permissão.** Se você aceitar, o Nicx envia
  dados anônimos de uso (quais recursos você usa, tempos, erros), nunca o
  conteúdo do que você escreve.
- **Você manda.** Pode recusar, mudar de ideia ou apagar o que já foi enviado a
  qualquer momento.

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

## 3. O que enviamos se você permitir

Com o seu consentimento, o Nicx envia à Falkyria **estatísticas anônimas de
uso**:

| Dado | Exemplo |
|---|---|
| Eventos de uso | o app foi aberto; um recurso foi usado (voz, memória, ferramentas); uma sessão de conversa terminou |
| Contagens e tempos | número de mensagens, tokens, tempo de resposta, duração da sessão |
| Erros | apenas o tipo do erro (por exemplo, "modelo não encontrado") |
| Instalação | etapas concluídas ou que falharam |
| Ambiente | versão do Nicx, sistema operacional, arquitetura do processador |
| Modelo | identificador do modelo transformado em código irreversível (hash) |
| Identificador | um código aleatório criado na instalação, que não revela quem você é |
| Consentimento | quando você aceitou ou recusou, e a versão desta política |

**Nunca** enviamos: o conteúdo de conversas ou perguntas, arquivos, nomes de
arquivos ou pastas, seu nome, e-mail, telefone ou dados de contas conectadas.
O Nicx filtra os dados antes do envio e descarta qualquer informação que não
esteja na lista acima.

O provedor de infraestrutura pode registrar o endereço IP de cada envio em
registros técnicos de acesso, por tempo limitado e para fins de segurança. A
Falkyria não guarda o IP na base de estatísticas.

## 4. Para que usamos

Somente para melhorar o Nicx: entender se a instalação funciona, quais recursos
são usados, onde ocorrem erros e como está o desempenho. Não usamos esses dados
para publicidade, não traçamos perfis de pessoas e **não vendemos nem
compartilhamos** os dados com terceiros.

## 5. Base legal

O envio de estatísticas se baseia no seu **consentimento** (LGPD, art. 7º, I).
Ele é opcional: recusar não muda nenhuma função do Nicx. Você pode revogá-lo a
qualquer momento, e a revogação vale a partir daquele momento.

## 6. Onde os dados ficam e por quanto tempo

As estatísticas são armazenadas no **Supabase**, em servidores localizados em
**São Paulo, Brasil**. O Supabase atua como operador, tratando os dados apenas
conforme as instruções da Falkyria.

Os eventos são **apagados automaticamente após 24 meses**.

O acesso é restrito a pessoas autorizadas da Falkyria. A comunicação é
criptografada (HTTPS) e as regras do banco de dados só permitem que o Nicx
**adicione** eventos: nenhuma instalação consegue ler os dados de outra.

## 7. Seus direitos

Pela LGPD (art. 18), você pode pedir confirmação de tratamento, acesso,
correção, anonimização, portabilidade, eliminação dos dados, informação sobre
compartilhamento e revogação do consentimento.

No próprio Nicx:

- **Mudar a escolha**: Configurações → Privacidade, ou
  `nicx config set analytics.enabled false` no terminal.
- **Apagar o que já foi enviado**: Configurações → Privacidade → "Apagar meus
  dados". Isso exclui dos servidores da Falkyria todos os eventos desta
  instalação e cria um novo identificador.

Para os demais pedidos, ou se tiver dúvidas, escreva para o contato da seção 1.
Você também pode reclamar à Autoridade Nacional de Proteção de Dados (ANPD).

## 8. Crianças e adolescentes

O Nicx não se destina a menores de 18 anos sem a supervisão de um responsável.

## 9. Mudanças nesta política

Quando esta política mudar de forma relevante, a versão no topo será
atualizada e o Nicx pedirá o seu consentimento de novo antes de enviar
qualquer estatística.
