-- Conta Falkyria (opcional): perfil, registro do aceite e backup criptografado.
--
-- LGPD: só o necessário. O e-mail e a senha ficam no Supabase Auth; aqui vão o
-- nome (opcional), as versões dos termos e da política que a pessoa aceitou (e
-- quando) e os backups, cifrados no PC com uma senha que não sai de lá: o
-- conteúdo é ilegível para a Falkyria. Cada um só vê, cria e apaga o que é
-- seu; apagar a conta (nicx_apagar_conta) apaga tudo junto. A conta não tem
-- ligação com o identificador anônimo das estatísticas.

create table public.nicx_contas (
  id uuid primary key references auth.users (id) on delete cascade,
  nome text not null default '' check (char_length(nome) <= 60),
  termos_versao text not null default '' check (char_length(termos_versao) <= 20),
  politica_versao text not null default '' check (char_length(politica_versao) <= 20),
  aceitou_em timestamptz,
  criado_em timestamptz not null default now()
);

comment on table public.nicx_contas is
  'Perfil da Conta Falkyria e registro do aceite. Cada pessoa vê e muda só a sua linha.';

alter table public.nicx_contas enable row level security;

create policy "Conta: vê a sua"
  on public.nicx_contas for select
  to authenticated
  using (id = (select auth.uid()));

create policy "Conta: cria a sua"
  on public.nicx_contas for insert
  to authenticated
  with check (id = (select auth.uid()));

create policy "Conta: muda a sua"
  on public.nicx_contas for update
  to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));

revoke all on public.nicx_contas from anon, authenticated;
grant select on public.nicx_contas to authenticated;
grant insert (id, nome, termos_versao, politica_versao) on public.nicx_contas to authenticated;
grant update (nome, termos_versao, politica_versao) on public.nicx_contas to authenticated;

-- Quem marca o aceite é o banco (a hora), a pessoa só diz as versões.
create function public.nicx_conta_aceite()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    new.aceitou_em := case when new.termos_versao <> '' then now() end;
    new.criado_em := now();
  elsif new.termos_versao is distinct from old.termos_versao
     or new.politica_versao is distinct from old.politica_versao then
    new.aceitou_em := now();
  end if;
  return new;
end;
$$;

create trigger nicx_conta_aceite
  before insert or update on public.nicx_contas
  for each row execute function public.nicx_conta_aceite();

-- Cadastro pelo app: o aceite vem nos metadados do cadastro.
create function public.nicx_nova_conta()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.nicx_contas (id, nome, termos_versao, politica_versao)
  values (
    new.id,
    left(coalesce(new.raw_user_meta_data ->> 'nome', ''), 60),
    left(coalesce(new.raw_user_meta_data ->> 'termos_versao', ''), 20),
    left(coalesce(new.raw_user_meta_data ->> 'politica_versao', ''), 20)
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

revoke all on function public.nicx_nova_conta() from public, anon, authenticated;

create trigger nicx_nova_conta
  after insert on auth.users
  for each row execute function public.nicx_nova_conta();

-- ---------------------------------------------------------------------------
-- Backups cifrados
-- ---------------------------------------------------------------------------

create table public.nicx_backups (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  rotulo text not null default '' check (char_length(rotulo) <= 60),
  versao_nicx text not null default '' check (char_length(versao_nicx) <= 32),
  conteudo text not null check (octet_length(conteudo) <= 5242880),
  tamanho integer generated always as (octet_length(conteudo)) stored,
  criado_em timestamptz not null default now()
);

create index nicx_backups_user_idx on public.nicx_backups (user_id, criado_em desc);

comment on table public.nicx_backups is
  'Backups da Conta Falkyria, cifrados no PC (AES-256-GCM, chave da senha do backup). Ilegíveis no servidor.';

alter table public.nicx_backups enable row level security;

create policy "Backup: vê os seus"
  on public.nicx_backups for select
  to authenticated
  using (user_id = (select auth.uid()));

create policy "Backup: cria os seus"
  on public.nicx_backups for insert
  to authenticated
  with check (user_id = (select auth.uid()));

create policy "Backup: apaga os seus"
  on public.nicx_backups for delete
  to authenticated
  using (user_id = (select auth.uid()));

revoke all on public.nicx_backups from anon, authenticated;
grant select, delete on public.nicx_backups to authenticated;
grant insert (rotulo, versao_nicx, conteudo) on public.nicx_backups to authenticated;

-- Até 30 backups por dia e só os 5 mais novos ficam guardados.
create function public.nicx_backup_limites()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (
    select count(*) from public.nicx_backups
    where user_id = new.user_id and criado_em > now() - interval '1 day'
  ) >= 30 then
    raise exception 'limite de backups por dia atingido' using errcode = 'P0001';
  end if;
  new.criado_em := now();
  return new;
end;
$$;

create trigger nicx_backup_limites
  before insert on public.nicx_backups
  for each row execute function public.nicx_backup_limites();

create function public.nicx_backup_guardar_5()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  delete from public.nicx_backups
  where user_id = new.user_id
    and id not in (
      select id from public.nicx_backups
      where user_id = new.user_id
      order by criado_em desc
      limit 5
    );
  return null;
end;
$$;

create trigger nicx_backup_guardar_5
  after insert on public.nicx_backups
  for each row execute function public.nicx_backup_guardar_5();

revoke all on function public.nicx_backup_limites() from public, anon, authenticated;
revoke all on function public.nicx_backup_guardar_5() from public, anon, authenticated;

-- ---------------------------------------------------------------------------
-- Apagar a conta (direito de eliminação): some o login, o perfil e os backups
-- ---------------------------------------------------------------------------

create function public.nicx_apagar_conta()
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if auth.uid() is null then
    raise exception 'sem sessão' using errcode = '42501';
  end if;
  delete from auth.users where id = auth.uid();
end;
$$;

revoke all on function public.nicx_apagar_conta() from public, anon;
grant execute on function public.nicx_apagar_conta() to authenticated;

-- Arrumação da loja: o anon só lê (o Supabase dá tudo a ele por padrão; a
-- regra de linha já barrava, agora nem a permissão existe).
revoke insert, update, delete on public.nicx_loja_pacotes, public.nicx_loja_versoes from anon;
