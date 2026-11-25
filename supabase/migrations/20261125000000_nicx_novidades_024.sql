-- Novidades da 0.2.4 (vão assinadas no arquivo de versões da release).
insert into public.nicx_novidades (versao, data, titulo, itens, publicado) values
(
  '0.2.4', '2026-11-25', 'Caixa de entrada, Pesquisar em tudo e o modo Trabalho analisando dados',
  array[
    'Caixa de entrada no sininho: aprovações, perguntas do modo Trabalho ("posso apagar?") e planos esperando você num lugar só, para responder ali mesmo, mais os avisos de tarefas concluídas ou com erro.',
    'O mascote mostra o que está acontecendo: fica trabalhando enquanto uma tarefa roda, esperando você quando há uma decisão, comemora quando termina.',
    'Modo Trabalho bem mais rápido (metade do tempo com o Ollama atualizado) e com ferramentas novas: analisar planilhas e somar por mês, gráficos do Excel, converter arquivos (inclusive tabelas de PDF para Excel) e comparar duas versões de um documento.',
    'Pesquisar em tudo: uma busca só em conversas, projetos, tarefas, notas, agenda, lembretes, memória e histórico.',
    'Captura rápida: selecione um texto em qualquer programa e aperte Ctrl+Alt+K para guardar nas notas (ligue em Configurações).',
    'Contas e datas na hora, sem esperar o modelo: "quanto é 15% de 230", "230 com 15% de desconto", "quantos dias faltam pro Natal", "que dia cai daqui a 45 dias".',
    'Exportar todos os meus dados (Configurações > Dados) e Diagnóstico (Configurações > Diagnóstico), que confere Ollama, modelo, memória, microfone, voz e atalhos e diz o que fazer.',
    'Pacotes prontos novos: Pesquisador, Escritor e Pequeno negócio.'
  ],
  true
)
on conflict (versao) do nothing;
