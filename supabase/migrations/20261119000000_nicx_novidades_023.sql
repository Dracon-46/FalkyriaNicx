-- Novidades da 0.2.3 (vão assinadas no arquivo de versões da release).
insert into public.nicx_novidades (versao, data, titulo, itens, publicado) values
(
  '0.2.3', '2026-11-19', 'Modo Trabalho: o Nicx trabalha numa pasta',
  array[
    'Modo Trabalho: escolha uma pasta e diga a tarefa ("junta as notas numa planilha", "faz um relatório em Word destes PDFs"). O Nicx monta um plano, você aprova e ele trabalha sozinho, lendo e criando planilhas, documentos e arquivos só dentro dessa pasta.',
    'No modo Trabalho, tudo o que muda tem cópia: "Desfazer tudo" volta a pasta como era. Para apagar, ele sempre pergunta antes. Dá para pausar, parar e retomar, e uma notificação avisa quando termina.',
    'Volume exato: "aumenta o volume em 20%" ou "volume para 80" faz exatamente isso, e o Nicx diz em quanto ficou.',
    'O Nicx só responde falando quando você pede (por exemplo, "responde em voz alta"); no resto, responde por texto.'
  ],
  true
)
on conflict (versao) do nothing;
