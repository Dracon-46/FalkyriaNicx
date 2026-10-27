-- Keeps the project awake.
--
-- On the free plan Supabase pauses a project after a stretch without
-- activity, and every event sent while it is paused is lost. A scheduled
-- GitHub workflow calls this function every few days. It reads nothing:
-- it only answers with the database clock.

create function public.nicx_keepalive()
returns timestamptz
language sql
stable
security invoker
set search_path = ''
as $$
  select now();
$$;

revoke all on function public.nicx_keepalive() from public;
grant execute on function public.nicx_keepalive() to anon, authenticated;
