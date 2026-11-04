-- Loja de pacotes da Falkyria.
--
-- Só a Falkyria publica: administradores (nicx_is_admin: lista + e-mail
-- confirmado + segundo fator) enviam pelo Painel um pacote já assinado no PC
-- da Falkyria. O app lê só o que está publicado e confere a impressão digital
-- (sha256) e a assinatura Ed25519 antes de instalar: nem quem invadir o banco
-- consegue pôr um pacote que o Nicx aceite.
--
-- O conteúdo fica em texto (o exato que foi assinado); jsonb reordenaria as
-- chaves e quebraria a assinatura. Nada aqui identifica quem baixa: o contador
-- de downloads só soma.

create table public.nicx_loja_pacotes (
  id text primary key check (id ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$'),
  nome text not null check (char_length(nome) between 1 and 60),
  descricao text not null default '' check (char_length(descricao) <= 300),
  autor text not null default 'Falkyria' check (char_length(autor) between 1 and 60),
  categoria text not null default 'geral' check (categoria ~ '^[a-z0-9-]{1,30}$'),
  versao text not null check (char_length(versao) between 1 and 20),
  publicado boolean not null default false,
  downloads bigint not null default 0 check (downloads >= 0),
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

comment on table public.nicx_loja_pacotes is
  'Catálogo da loja do Nicx. Leitura pública só do publicado; escrita só de administradores.';

create table public.nicx_loja_versoes (
  pacote_id text not null references public.nicx_loja_pacotes (id) on delete cascade,
  versao text not null check (char_length(versao) between 1 and 20),
  conteudo text not null check (octet_length(conteudo) <= 1048576),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  assinatura text not null check (char_length(assinatura) between 80 and 100),
  chave text not null check (chave ~ '^[0-9a-f]{16}$'),
  permissoes jsonb not null default '{}'::jsonb,
  notas text not null default '' check (char_length(notas) <= 500),
  publicado_em timestamptz not null default now(),
  primary key (pacote_id, versao)
);

comment on table public.nicx_loja_versoes is
  'Versões assinadas dos pacotes. O app confere sha256 e assinatura antes de instalar.';

create function public.nicx_loja_tocar()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  -- Baixar não conta como mudança do pacote.
  if (to_jsonb(new) - 'downloads' - 'atualizado_em')
     is distinct from (to_jsonb(old) - 'downloads' - 'atualizado_em') then
    new.atualizado_em := now();
  end if;
  return new;
end;
$$;

create trigger nicx_loja_pacotes_tocar
  before update on public.nicx_loja_pacotes
  for each row execute function public.nicx_loja_tocar();

alter table public.nicx_loja_pacotes enable row level security;
alter table public.nicx_loja_versoes enable row level security;

create policy "Loja: todos leem o publicado"
  on public.nicx_loja_pacotes for select
  to anon, authenticated
  using (publicado or public.nicx_is_admin());

create policy "Loja: administradores escrevem"
  on public.nicx_loja_pacotes for all
  to authenticated
  using (public.nicx_is_admin())
  with check (public.nicx_is_admin());

create policy "Loja: todos leem versões publicadas"
  on public.nicx_loja_versoes for select
  to anon, authenticated
  using (
    exists (
      select 1 from public.nicx_loja_pacotes p
      where p.id = pacote_id and (p.publicado or public.nicx_is_admin())
    )
  );

create policy "Loja: administradores escrevem versões"
  on public.nicx_loja_versoes for all
  to authenticated
  using (public.nicx_is_admin())
  with check (public.nicx_is_admin());

grant select on public.nicx_loja_pacotes, public.nicx_loja_versoes to anon, authenticated;
grant insert, update, delete on public.nicx_loja_pacotes, public.nicx_loja_versoes to authenticated;

-- Contador de downloads: só soma, sem guardar quem baixou.
create function public.nicx_loja_baixou(p_id text)
returns void
language sql
security definer
set search_path = ''
as $$
  update public.nicx_loja_pacotes
  set downloads = downloads + 1
  where id = p_id and publicado;
$$;

revoke all on function public.nicx_loja_baixou(text) from public;
grant execute on function public.nicx_loja_baixou(text) to anon, authenticated;
