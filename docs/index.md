# Nicx

O **Nicx** é a inteligência artificial da **Falkyria**. Ele conversa em
português do Brasil, por texto ou voz, e roda inteiro no seu computador: o
modelo de linguagem (via Ollama), o reconhecimento de fala e a voz ficam na
máquina, sem API paga e sem mandar suas conversas para fora.

O que ele faz hoje:

- **Conversa** pelo app, pelo terminal (`nicx chat`) ou pela voz, com um
  mascote animado.
- **Age no computador** na hora: volume, mídia, abrir apps e sites, pesquisar,
  hora, data, bateria, bloquear a tela ("aumenta o volume", "abre o YouTube").
- **Pesquisa e usa ferramentas** quando precisa: busca na web, arquivos,
  Python, comandos, base de conhecimento.
- **Escuta "Nicx, ligar"** (desligado por padrão) e abre o mascote flutuante
  para uma conversa por voz.
- **Respeita a privacidade**: estatísticas de uso só com consentimento, para o
  Supabase da Falkyria, sem o conteúdo das conversas.

## Páginas

- [Instalação](instalacao.md): o que instalar e como rodar.
- [Uso](uso.md): comandos, app, voz e ações rápidas.
- [Configuração](configuracao.md): o `config.toml` e as opções principais.
- [Arquitetura](arquitetura.md): pastas e o caminho de uma pergunta.
- [Voz](voz.md): reconhecimento de fala, voz do Nicx e "Nicx, ligar".
- [Privacidade](privacidade.md): o que é coletado, quando e como apagar.
- [Desenvolvimento](desenvolvimento.md): testes, extensão Rust e CI.
