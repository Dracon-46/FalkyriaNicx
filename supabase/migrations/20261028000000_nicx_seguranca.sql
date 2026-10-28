-- Segurança do Painel Falkyria.
--
-- 1. Segundo fator obrigatório: os dados só saem para um administrador com
--    e-mail confirmado E sessão verificada com código do app autenticador
--    (aal2). Senha vazada sozinha não abre nada.
-- 2. Auditoria: cada entrada, verificação e saída do painel fica registrada
--    (quem, quando, IP e navegador), visível só para administradores.
-- 3. Limite de envio: a chave pública do app permite inserir eventos; um
--    limite por instalação e um geral impedem que alguém entupa o banco.

-- ---------------------------------------------------------------------------
-- 1. Administrador = lista + e-mail confirmado + segundo fator
-- ---------------------------------------------------------------------------

create or replace function public.nicx_is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from auth.users u
    join public.nicx_admins a on a.email = lower(u.email)
    where u.id = auth.uid()
      and u.email_confirmed_at is not null
  )
  and coalesce(auth.jwt() ->> 'aal', '') = 'aal2';
$$;

revoke all on function public.nicx_is_admin() from public, anon;
grant execute on function public.nicx_is_admin() to authenticated;

-- O painel precisa saber se pede o segundo fator antes de mostrar dados.
create function public.nicx_admin_status()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'admin', exists (
      select 1
      from auth.users u
      join public.nicx_admins a on a.email = lower(u.email)
      where u.id = auth.uid()
        and u.email_confirmed_at is not null
    ),
    'aal', coalesce(auth.jwt() ->> 'aal', 'aal1')
  );
$$;

revoke all on function public.nicx_admin_status() from public, anon;
grant execute on function public.nicx_admin_status() to authenticated;

-- ---------------------------------------------------------------------------
-- 2. Auditoria de acesso ao painel
-- ---------------------------------------------------------------------------

create table public.nicx_admin_audit (
  id bigint generated always as identity primary key,
  at timestamptz not null default now(),
  user_id uuid not null,
  email text not null,
  action text not null check (
    action in ('login', 'mfa_enrolled', 'mfa_verified', 'view', 'logout', 'idle_logout')
  ),
  aal text check (char_length(aal) <= 8),
  ip text check (char_length(ip) <= 64),
  user_agent text check (char_length(user_agent) <= 300)
);

create index nicx_admin_audit_at_idx on public.nicx_admin_audit (at desc);

comment on table public.nicx_admin_audit is
  'Acessos ao Painel Falkyria. Gravado só por nicx_audit(); lido só por administradores.';

alter table public.nicx_admin_audit enable row level security;

create policy "Falkyria admins read audit"
  on public.nicx_admin_audit
  for select
  to authenticated
  using ((select public.nicx_is_admin()));

revoke all on public.nicx_admin_audit from public, anon, authenticated;
grant select on public.nicx_admin_audit to authenticated;

create function public.nicx_audit(p_action text, p_user_agent text default null)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  headers json := nullif(current_setting('request.headers', true), '')::json;
  forwarded text := split_part(coalesce(headers ->> 'x-forwarded-for', ''), ',', 1);
begin
  if auth.uid() is null then
    raise exception 'não autenticado' using errcode = '42501';
  end if;
  insert into public.nicx_admin_audit (user_id, email, action, aal, ip, user_agent)
  select u.id,
         lower(u.email),
         p_action,
         coalesce(auth.jwt() ->> 'aal', 'aal1'),
         nullif(trim(forwarded), ''),
         left(p_user_agent, 300)
  from auth.users u
  where u.id = auth.uid();
end;
$$;

revoke all on function public.nicx_audit(text, text) from public, anon;
grant execute on function public.nicx_audit(text, text) to authenticated;

-- ---------------------------------------------------------------------------
-- 3. Limite de envio de eventos
-- ---------------------------------------------------------------------------

create index nicx_events_anon_id_received_at_idx
  on public.nicx_events (anon_id, received_at desc);

create function public.nicx_events_rate_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Uma instalação normal manda dezenas de eventos por hora, não centenas.
  if (
    select count(*) from public.nicx_events
    where anon_id = new.anon_id and received_at > now() - interval '1 hour'
  ) >= 600 then
    raise exception 'limite de eventos por instalação atingido' using errcode = '54000';
  end if;
  -- Teto geral contra quem troca de anon_id a cada envio.
  if (
    select count(*) from public.nicx_events
    where received_at > now() - interval '1 minute'
  ) >= 3000 then
    raise exception 'limite geral de eventos atingido' using errcode = '54000';
  end if;
  return new;
end;
$$;

revoke all on function public.nicx_events_rate_limit() from public, anon, authenticated;

create trigger nicx_events_rate_limit
  before insert on public.nicx_events
  for each row execute function public.nicx_events_rate_limit();
