# Changelog

Mudanças relevantes do Nicx. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Adicionado

- Identidade da Falkyria: nome, logotipo, paleta de cores, banner do terminal e
  persona padrão em português do Brasil.
- **Mascote animado**: um slime ciano com núcleo azul flutuante, que reage ao que o
  Nicx está fazendo (ouvindo, pensando, falando, feliz, erro). Aparece no chat, nas
  respostas, nas Configurações e no overlay do desktop.
- **Voz em português, toda local**: reconhecimento com Whisper e voz brasileira com
  Kokoro (`pf_dora`); ditado, leitura em voz alta e o modo "Conversa por voz" no app;
  `nicx chat --voice` no terminal.
- **Estatísticas de uso para a Falkyria**, só com consentimento: eventos anônimos no
  Supabase da Falkyria (São Paulo), filtrados por um catálogo fechado, apagados após
  24 meses. Pedido de consentimento no app, no `nicx init` e no instalador; seção
  Privacidade nas Configurações, com "Apagar meus dados".
- **Painel Falkyria**: painel analítico no app, com login e acesso só para
  administradores.
- Política de privacidade, termos de uso e termo de consentimento embutidos
  (`nicx legal`), e código de conduta.
- Opção `[engine.ollama] num_ctx` para limitar a memória usada pelo modelo.
- Escalada opcional de perguntas complexas para um modelo na nuvem
  (`[intelligence] escalation_model`). Desligada por padrão.
- Auditoria de fronteiras de dados (`nicx scan --data-boundaries`) passa a
  apontar a escalada para a nuvem quando configurada.

### Alterado

- Licença proprietária da Falkyria.
- Erros do Ollama (como falta de memória) aparecem como mensagens claras em
  português, sem traceback.
- O briefing diário usa voz local (Kokoro) e o fuso de São Paulo.
- `nicx self-update` atualiza somente a partir do repositório git; instalações
  via PyPI são recusadas.
- Dicas de instalação usam `uv sync --extra ...` em vez de `pip install`.
- O app desktop respeita `NICX_HOME` e, no Windows, usa a mesma pasta de dados
  da linha de comando.
- Listas em markdown voltam a mostrar marcadores no chat.

### Removido

- Placar de economia e campanha de compartilhamento; o SDK do PostHog.
- Agentes híbridos local + nuvem (dependiam de APIs pagas).
- Atualizador automático do app desktop e checagem de novas versões.
