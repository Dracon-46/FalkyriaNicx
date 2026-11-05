# Nicx para VS Code

A IA da **Falkyria** no seu editor. Ela usa o Nicx que roda no seu computador
(modelo local, pelo Ollama): o seu código não sai do PC.

## O que faz

- **Chat ao lado do código** (ícone do Nicx na barra lateral). Os blocos de
  código da resposta têm **Copiar** e **Inserir no editor**.
- **Botão direito → Nicx**, com um trecho selecionado:
  - **Explicar o trecho**;
  - **Corrigir o trecho** e **Melhorar o trecho**: a mudança abre como diff
    (original × proposta) e só entra no arquivo quando você clica em
    **Aplicar** (Ctrl+Z desfaz);
  - **Escrever testes**;
  - **Perguntar sobre o código** (também em `Ctrl+Alt+N`).
- Vão junto o arquivo, a linguagem, algumas linhas em volta e os erros que o VS
  Code mostra no trecho. Sem seleção, vai o arquivo inteiro, se for pequeno.

## Precisa

O Nicx instalado e aberto neste PC (menu Iniciar → Nicx). A extensão conversa
com `http://127.0.0.1:8000` e só aceita endereços locais.

## Configurações

| Opção | Padrão | O que é |
|-------|--------|---------|
| `nicx.servidor` | `http://127.0.0.1:8000` | Endereço do Nicx neste PC |
| `nicx.modelo` | vazio | Modelo; vazio = o padrão do Nicx |
| `nicx.chaveApi` | vazio | Só se você ligou `NICX_API_KEY` |
| `nicx.linhasDeContexto` | `40` | Linhas em volta da seleção, só como contexto |

Os pedidos da extensão vão direto ao modelo: sem ferramentas do PC, sem ler a
tela, e o código não entra na memória automática do Nicx.

Um produto Falkyria, feito no Brasil.
