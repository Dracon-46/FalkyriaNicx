-- Novidades de cada versão do Nicx (página Atualizações do app).
--
-- A fonte é esta tabela: a Falkyria cadastra pelo Painel (seção Novidades) ou
-- com um INSERT. Ao lançar uma versão, `nicx atualizacao assinar` lê daqui as
-- novidades publicadas e as põe no arquivo de versões assinado que vai na
-- release; o app mostra o que veio assinado e não consulta esta tabela.
--
-- Lançar pelo SQL:
--   insert into public.nicx_novidades (versao, data, titulo, itens, publicado)
--   values ('0.2.2', '2026-11-10', 'Título curto',
--           array['O que mudou, em uma frase.', 'Outra mudança.'], true);
--
-- Leitura pública só do publicado; escrita só de administradores
-- (nicx_is_admin: lista + e-mail confirmado + segundo fator).

create table public.nicx_novidades (
  versao text primary key check (versao ~ '^[0-9]+\.[0-9]+\.[0-9]+$'),
  data date not null default current_date,
  titulo text not null check (char_length(titulo) between 1 and 120),
  itens text[] not null default '{}'
    check (
      cardinality(itens) between 1 and 30
      and array_position(itens, '') is null
      and char_length(array_to_string(itens, '')) <= 6000
    ),
  publicado boolean not null default false,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table public.nicx_novidades is
  'Novidades de cada versão do Nicx. Leitura pública do publicado; escrita só de administradores. Vão assinadas no arquivo de versões da release.';

create function public.nicx_novidades_tocar()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.atualizado_em := now();
  return new;
end;
$$;

create trigger nicx_novidades_tocar
  before update on public.nicx_novidades
  for each row execute function public.nicx_novidades_tocar();

alter table public.nicx_novidades enable row level security;

-- O visitante (anon) não executa nicx_is_admin(): regras separadas.
create policy "Novidades: visitantes leem o publicado"
  on public.nicx_novidades for select
  to anon
  using (publicado);

create policy "Novidades: logados leem o publicado (admins, tudo)"
  on public.nicx_novidades for select
  to authenticated
  using (publicado or public.nicx_is_admin());

create policy "Novidades: administradores escrevem"
  on public.nicx_novidades for all
  to authenticated
  using (public.nicx_is_admin())
  with check (public.nicx_is_admin());

revoke all on public.nicx_novidades from anon, authenticated;
grant select on public.nicx_novidades to anon, authenticated;
grant insert, update, delete on public.nicx_novidades to authenticated;

-- As versões já lançadas.
insert into public.nicx_novidades (versao, data, titulo, itens, publicado) values
(
  '0.2.1', '2026-11-05', 'Respostas que chegam e atualização pelo app',
  array[
    'Atualizações pelo próprio app: a página Atualizações mostra as novidades e instala a versão nova por cima, sem perder conversas nem configurações.',
    'Imagens e vídeos no chat: anexe pelo clipe, cole um print ou arraste. O Nicx enxerga as imagens e, nos vídeos, olha alguns quadros e ouve o áudio, tudo no seu PC.',
    'Quando o Ollama falha (por exemplo, a placa de vídeo cai), o erro aparece na tela e o Nicx tenta de novo só no processador, em vez de ficar sem responder.',
    'O botão Parar agora para o modelo de verdade: a próxima pergunta não espera mais atrás de uma resposta abandonada.',
    'O agente tem prazo e sempre termina com uma resposta; histórico longo e limite de resposta exagerado não deixam mais tudo lento.',
    'Instalação mais rápida, com o Ollama testado e as ferramentas padrão ligadas; downloads interrompidos continuam de onde pararam.',
    'Privacidade: se a política mudar, o app pergunta de novo; pacotes não escolhem mais a confiança dos servidores MCP nem levam chaves ao serem exportados.',
    'Erros com o motivo, Enter no login da Conta Falkyria, confirmação ao apagar conversa e opções da memória que valem de verdade.'
  ],
  true
),
(
  '0.2.0', '2026-11-04', 'Extensões, loja e Conta Falkyria',
  array[
    'Extensões: servidores MCP, habilidades e pacotes por profissão.',
    'Loja da Falkyria com pacotes assinados.',
    'Conta Falkyria opcional, com backup criptografado no seu PC.',
    'Construtor de assistentes, rotinas, planejador e histórico com desfazer.'
  ],
  true
),
(
  '0.1.0', '2026-10-29', 'Primeira versão',
  array[
    'O Nicx rodando no seu computador, com modelo local, voz em português e ações rápidas no Windows.'
  ],
  true
);
