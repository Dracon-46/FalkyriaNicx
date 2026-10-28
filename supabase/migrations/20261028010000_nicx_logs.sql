-- Logs de aviso e erro do Nicx, para o Painel Falkyria.
--
-- Só com consentimento, como os eventos. O app manda cada tipo de aviso ou
-- erro agrupado (quantas vezes aconteceu num intervalo), com a mensagem
-- limpa no próprio PC: sem conteúdo de conversa, caminhos, e-mails, IPs,
-- links ou textos entre aspas. A instalação só insere; só administradores
-- com segundo fator leem; tudo some depois de 90 dias.

-- Eventos novos de saúde do servidor (catálogo em src/nicx/privacidade/events.py).
alter table public.nicx_events drop constraint nicx_events_event_check;
alter table public.nicx_events add constraint nicx_events_event_check check (
  event in (
    'install_started', 'install_stage_completed', 'install_completed',
    'install_failed', 'uninstall_started', 'app_opened', 'setup_completed',
    'first_chat_sent', 'chat_session_ended', 'tool_first_used',
    'model_changed', 'connector_auth_completed', 'feature_used',
    'feedback_submitted', 'error_shown_to_user', 'settings_changed',
    'usage_daily_summary', 'analytics_consent',
    'server_started', 'server_health'
  )
);

create table public.nicx_logs (
  id bigint generated always as identity primary key,
  received_at timestamptz not null default now(),
  anon_id uuid not null,
  level text not null check (level in ('warning', 'error', 'critical')),
  logger text not null check (char_length(logger) <= 120),
  message text not null check (char_length(message) <= 300),
  exc_type text check (char_length(exc_type) <= 120),
  location text check (char_length(location) <= 200),
  fingerprint text not null check (fingerprint ~ '^[0-9a-f]{16}$'),
  occurrences integer not null default 1 check (occurrences between 1 and 100000),
  first_at timestamptz,
  last_at timestamptz,
  app_version text check (char_length(app_version) <= 64),
  platform text check (char_length(platform) <= 32),
  os text check (char_length(os) <= 16),
  arch text check (char_length(arch) <= 16)
);

create index nicx_logs_received_at_idx on public.nicx_logs (received_at desc);
create index nicx_logs_fingerprint_idx on public.nicx_logs (fingerprint, received_at desc);
create index nicx_logs_anon_id_received_at_idx on public.nicx_logs (anon_id, received_at desc);

comment on table public.nicx_logs is
  'Avisos e erros do Nicx, agrupados e sem dados pessoais. Só com consentimento.';

alter table public.nicx_logs enable row level security;

create policy "Nicx installations insert logs"
  on public.nicx_logs for insert
  to anon, authenticated
  with check (
    (first_at is null or first_at <= now() + interval '1 day')
    and (last_at is null or last_at <= now() + interval '1 day')
  );

create policy "Falkyria admins read logs"
  on public.nicx_logs for select
  to authenticated
  using ((select public.nicx_is_admin()));

revoke all on public.nicx_logs from public, anon, authenticated;
grant insert on public.nicx_logs to anon, authenticated;
grant select on public.nicx_logs to authenticated;

-- Limite de envio, como nos eventos.
create function public.nicx_logs_rate_limit()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (
    select count(*) from public.nicx_logs
    where anon_id = new.anon_id and received_at > now() - interval '1 hour'
  ) >= 300 then
    raise exception 'limite de logs por instalação atingido' using errcode = '54000';
  end if;
  if (
    select count(*) from public.nicx_logs
    where received_at > now() - interval '1 minute'
  ) >= 2000 then
    raise exception 'limite geral de logs atingido' using errcode = '54000';
  end if;
  return new;
end;
$$;

revoke all on function public.nicx_logs_rate_limit() from public, anon, authenticated;

create trigger nicx_logs_rate_limit
  before insert on public.nicx_logs
  for each row execute function public.nicx_logs_rate_limit();

-- Painel: cada tipo de aviso/erro dos últimos 30 dias, com o total de vezes,
-- quantas instalações viram e em quais versões.
create view public.nicx_log_groups
with (security_invoker = true) as
select
  fingerprint,
  (array_agg(level order by case level when 'critical' then 3 when 'error' then 2 else 1 end desc))[1] as level,
  (array_agg(logger order by received_at desc))[1] as logger,
  (array_agg(message order by received_at desc))[1] as message,
  (array_agg(exc_type order by received_at desc))[1] as exc_type,
  (array_agg(location order by received_at desc))[1] as location,
  sum(occurrences)::bigint as occurrences,
  count(distinct anon_id)::bigint as installations,
  array_agg(distinct app_version) filter (where app_version is not null) as versions,
  min(coalesce(first_at, received_at)) as first_seen_at,
  max(coalesce(last_at, received_at)) as last_seen_at
from public.nicx_logs
where received_at > now() - interval '30 days'
group by fingerprint;

revoke all on public.nicx_log_groups from public, anon;
grant select on public.nicx_log_groups to authenticated;

-- "Apagar meus dados" passa a apagar também os logs da instalação.
create or replace function public.nicx_forget(p_anon_id uuid)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed_events bigint;
  removed_logs bigint;
begin
  delete from public.nicx_events where anon_id = p_anon_id;
  get diagnostics removed_events = row_count;
  delete from public.nicx_logs where anon_id = p_anon_id;
  get diagnostics removed_logs = row_count;
  return removed_events + removed_logs;
end;
$$;

revoke all on function public.nicx_forget(uuid) from public;
grant execute on function public.nicx_forget(uuid) to anon, authenticated;

-- Logs ficam 90 dias.
select cron.schedule(
  'nicx-logs-retention',
  '17 4 * * *',
  $$delete from public.nicx_logs where received_at < now() - interval '90 days'$$
);
