# Changelog

Mudanças relevantes do Nicx. Formato inspirado em
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Adicionado

- Identidade da Falkyria: nome, logotipo, paleta de cores, banner do terminal e
  persona padrão em português do Brasil.
- Escalada opcional de perguntas complexas para um modelo na nuvem
  (`[intelligence] escalation_model`). Desligada por padrão.
- Auditoria de fronteiras de dados (`nicx scan --data-boundaries`) passa a
  apontar a escalada para a nuvem quando configurada.

### Alterado

- Licença proprietária da Falkyria.
- `nicx self-update` atualiza somente a partir do repositório git; instalações
  via PyPI são recusadas.
- Dicas de instalação usam `uv sync --extra ...` em vez de `pip install`.
- O app desktop respeita `NICX_HOME` e, no Windows, usa a mesma pasta de dados
  da linha de comando.

### Removido

- Envio de estatísticas de uso, placar de economia e campanha de compartilhamento.
- Agentes híbridos local + nuvem (dependiam de APIs pagas).
- Atualizador automático do app desktop e checagem de novas versões.
