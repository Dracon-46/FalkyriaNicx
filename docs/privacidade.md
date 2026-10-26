# Privacidade

O Nicx foi feito para funcionar sem mandar nada para fora: o modelo, a voz e
os dados ficam no computador. A única coisa que pode sair, e só se você
concordar, são **estatísticas de uso anônimas**.

## Estatísticas de uso

- **Desligadas por padrão.** O `nicx init`, o instalador e o app perguntam;
  sem resposta, ficam desligadas.
- **Sem conteúdo.** Nunca vão mensagens, respostas, arquivos, nomes ou
  caminhos. Só eventos de um catálogo fechado (`privacidade/events.py`): por
  exemplo, que uma ferramenta foi usada, a versão do Nicx, o sistema
  operacional, quanto tempo uma resposta levou.
- **Identificação anônima.** Cada instalação tem um identificador aleatório
  (`~/.nicx/anon_id`), sem relação com você.
- **Destino:** o banco da Falkyria no Supabase (região São Paulo). Quem
  instala só pode **gravar** eventos; ler é restrito aos administradores do
  Painel Falkyria.
- **Retenção:** eventos com mais de 24 meses são apagados automaticamente.

## Como mudar ou apagar

- Ligar ou desligar: **Configurações → Privacidade** no app, ou
  `[analytics] enabled` no `config.toml`.
- **Apagar meus dados**: o botão em Configurações → Privacidade apaga tudo o
  que a sua instalação enviou e gera um identificador novo.

## Textos legais

```bash
nicx legal privacidade    # política de privacidade
nicx legal termos         # termos de uso
nicx legal consentimento  # o termo de consentimento das estatísticas
```

Os textos ficam em `src/nicx/privacidade/textos/`. Ao mudar a política,
atualize `POLICY_VERSION` (`nicx.privacidade`) e a data no topo do texto: o
consentimento registrado traz a versão aceita.

Contato: arthurgaspare@gmail.com.

## O que fica só na máquina

Conversas, memória, rastros e telemetria de desempenho ficam em `~/.nicx/`
(veja [Arquitetura](arquitetura.md#dados-na-maquina)). Pesquisas na web e
conectores (Gmail, Notion etc.) acessam a internet, naturalmente, mas só
quando você pede ou conecta a conta.
