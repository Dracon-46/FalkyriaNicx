-- Novidades da 0.2.2 (vão assinadas no arquivo de versões da release).
insert into public.nicx_novidades (versao, data, titulo, itens, publicado) values
(
  '0.2.2', '2026-11-06', 'Nicx no VS Code e editor de código',
  array[
    'Nicx para VS Code: em Configurações > VS Code, "Conectar ao VS Code" instala a extensão. Chat na barra lateral e, no botão direito, Explicar, Corrigir, Melhorar e Escrever testes; a correção abre num diff e só entra se você aplicar.',
    'Editor de código no app: abra uma pasta ou um arquivo, edite com cores por linguagem e peça ao Nicx para explicar, corrigir ou melhorar o trecho selecionado. A proposta aparece lado a lado e só entra com Aplicar.',
    'Pedidos do editor e do VS Code vão direto ao modelo do seu PC, sem ferramentas e sem entrar na memória automática.',
    'O Painel Falkyria só aparece para administradores.'
  ],
  true
)
on conflict (versao) do nothing;
