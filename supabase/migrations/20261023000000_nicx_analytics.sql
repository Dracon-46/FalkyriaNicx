-- Nicx usage analytics.
--
-- Nicx installations send anonymous, aggregated usage events here, and only
-- after the user consents (see docs/legal/politica-de-privacidade.md). The
-- publishable key ships inside the app, so the anon role may only INSERT
-- well-formed events: it can never read, change or delete anything. Reads are
-- reserved for Falkyria administrators signed in through Supabase Auth.

-- ---------------------------------------------------------------------------
-- Events
-- ---------------------------------------------------------------------------

create table public.nicx_events (
  id bigint generated always as identity primary key,
  received_at timestamptz not null default now(),
  sent_at timestamptz,
  anon_id uuid not null,
  event text not null check (
    event in (
      'install_started', 'install_stage_completed', 'install_completed',
      'install_failed', 'uninstall_started', 'app_opened', 'setup_completed',
      'first_chat_sent', 'chat_session_ended', 'tool_first_used',
      'model_changed', 'connector_auth_completed', 'feature_used',
      'feedback_submitted', 'error_shown_to_user', 'settings_changed',
      'usage_daily_summary', 'analytics_consent'
    )
  ),
  properties jsonb not null default '{}'::jsonb check (
    jsonb_typeof(properties) = 'object' and pg_column_size(properties) <= 4096
  ),
  app_version text check (char_length(app_version) <= 64),
  platform text check (char_length(platform) <= 32),
  os text check (char_length(os) <= 16),
  arch text check (char_length(arch) <= 16)
);

comment on table public.nicx_events is
  'Anonymous Nicx usage events, sent only with user consent. No message content.';

create index nicx_events_received_at_idx on public.nicx_events (received_at desc);
create index nicx_events_event_received_at_idx on public.nicx_events (event, received_at desc);
create index nicx_events_anon_id_idx on public.nicx_events (anon_id);

alter table public.nicx_events enable row level security;

-- Installations may only add events. A client clock far in the future is
-- rejected so it cannot pollute time-based charts.
create policy "Nicx installations insert events"
  on public.nicx_events for insert
  to anon, authenticated
  with check (sent_at is null or sent_at <= now() + interval '1 day');

-- ---------------------------------------------------------------------------
-- Administrators (who may read the analytics)
-- ---------------------------------------------------------------------------

create table public.nicx_admins (
  email text primary key check (email = lower(email)),
  added_at timestamptz not null default now()
);

comment on table public.nicx_admins is
  'Emails allowed to read Nicx analytics. Managed with SQL only (no API access).';

alter table public.nicx_admins enable row level security;
-- No policies: neither anon nor authenticated users can touch this table.

create function public.nicx_is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.nicx_admins a
    where a.email = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

revoke all on function public.nicx_is_admin() from public, anon;
grant execute on function public.nicx_is_admin() to authenticated;

create policy "Falkyria admins read events"
  on public.nicx_events for select
  to authenticated
  using ((select public.nicx_is_admin()));

-- ---------------------------------------------------------------------------
-- Right to deletion (LGPD art. 18): an installation can erase its own events.
-- The anon_id is a random UUID known only to that installation.
-- ---------------------------------------------------------------------------

create function public.nicx_forget(p_anon_id uuid)
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  removed bigint;
begin
  delete from public.nicx_events where anon_id = p_anon_id;
  get diagnostics removed = row_count;
  return removed;
end;
$$;

revoke all on function public.nicx_forget(uuid) from public;
grant execute on function public.nicx_forget(uuid) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Dashboard views (security_invoker: the reader's RLS applies, so only admins
-- see rows).
-- ---------------------------------------------------------------------------

create view public.nicx_daily_activity
with (security_invoker = true) as
select
  date_trunc('day', received_at at time zone 'America/Sao_Paulo')::date as day,
  count(distinct anon_id) as installations,
  count(*) filter (where event = 'app_opened') as app_opens,
  count(*) filter (where event = 'chat_session_ended') as chat_sessions,
  count(*) filter (where event = 'error_shown_to_user') as errors,
  count(*) as events
from public.nicx_events
group by 1;

create view public.nicx_daily_usage
with (security_invoker = true) as
select
  date_trunc('day', received_at at time zone 'America/Sao_Paulo')::date as day,
  sum(coalesce((properties ->> 'turn_count')::bigint, 0)) as turns,
  sum(coalesce((properties ->> 'tokens_in')::bigint, 0)) as tokens_in,
  sum(coalesce((properties ->> 'tokens_out')::bigint, 0)) as tokens_out,
  sum(coalesce((properties ->> 'tool_count')::bigint, 0)) as tool_calls,
  round(avg((properties ->> 'latency_ms_p50')::numeric)) as latency_ms_p50,
  round(avg((properties ->> 'latency_ms_p95')::numeric)) as latency_ms_p95,
  sum(coalesce((properties ->> 'duration_ms')::bigint, 0)) as duration_ms
from public.nicx_events
where event = 'chat_session_ended'
group by 1;

create view public.nicx_feature_usage
with (security_invoker = true) as
select
  properties ->> 'feature_name' as feature,
  count(*) as uses,
  count(distinct anon_id) as installations,
  max(received_at) as last_used_at
from public.nicx_events
where event = 'feature_used' and properties ? 'feature_name'
group by 1;

create view public.nicx_error_classes
with (security_invoker = true) as
select
  properties ->> 'error_class' as error_class,
  count(*) as occurrences,
  count(distinct anon_id) as installations,
  max(received_at) as last_seen_at
from public.nicx_events
where event = 'error_shown_to_user'
group by 1;

create view public.nicx_platforms
with (security_invoker = true) as
select
  coalesce(platform, 'desconhecida') as platform,
  coalesce(os, 'desconhecido') as os,
  coalesce(app_version, 'desconhecida') as app_version,
  count(distinct anon_id) as installations,
  max(received_at) as last_seen_at
from public.nicx_events
where received_at > now() - interval '30 days'
group by 1, 2, 3;

create view public.nicx_install_funnel
with (security_invoker = true) as
select
  count(distinct anon_id) filter (where event = 'install_started') as install_started,
  count(distinct anon_id) filter (where event = 'install_completed') as install_completed,
  count(distinct anon_id) filter (where event = 'setup_completed') as setup_completed,
  count(distinct anon_id) filter (where event = 'first_chat_sent') as first_chat_sent,
  count(distinct anon_id) filter (where event = 'chat_session_ended') as active_chatters
from public.nicx_events;

create view public.nicx_consent_summary
with (security_invoker = true) as
select
  (properties ->> 'granted')::boolean as granted,
  properties ->> 'policy_version' as policy_version,
  count(*) as records,
  max(received_at) as last_at
from public.nicx_events
where event = 'analytics_consent'
group by 1, 2;

revoke all on public.nicx_daily_activity, public.nicx_daily_usage,
  public.nicx_feature_usage, public.nicx_error_classes, public.nicx_platforms,
  public.nicx_install_funnel, public.nicx_consent_summary from anon;
grant select on public.nicx_daily_activity, public.nicx_daily_usage,
  public.nicx_feature_usage, public.nicx_error_classes, public.nicx_platforms,
  public.nicx_install_funnel, public.nicx_consent_summary to authenticated;

-- ---------------------------------------------------------------------------
-- Retention: events older than 24 months are deleted every night.
-- ---------------------------------------------------------------------------

create extension if not exists pg_cron with schema pg_catalog;

select cron.schedule(
  'nicx-events-retention',
  '0 6 * * *',
  $$delete from public.nicx_events where received_at < now() - interval '24 months'$$
);
