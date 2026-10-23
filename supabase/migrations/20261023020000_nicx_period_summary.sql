-- Period-scoped numbers for the analytics dashboard.
--
-- Days follow America/Sao_Paulo like the daily views. The current period is
-- the last p_days calendar days including today; the previous period is the
-- same span right before it. security invoker: the caller's row level
-- security applies, so only administrators get anything back.

create function public.nicx_period_summary(p_days integer)
returns jsonb
language sql
stable
security invoker
set search_path = ''
as $$
  with bounds as (
    select
      (now() at time zone 'America/Sao_Paulo')::date as today,
      greatest(1, least(p_days, 366)) as days
  ),
  periods as (
    select
      today - (days - 1) as cur_start,
      today as cur_end,
      today - (2 * days - 1) as prev_start,
      today - days as prev_end
    from bounds
  ),
  events as (
    select e.*, (e.received_at at time zone 'America/Sao_Paulo')::date as day
    from public.nicx_events e, periods p
    where (e.received_at at time zone 'America/Sao_Paulo')::date between p.prev_start and p.cur_end
  ),
  current_events as (
    select e.* from events e, periods p where e.day between p.cur_start and p.cur_end
  )
  select jsonb_build_object(
    'installations', (select count(distinct anon_id) from current_events),
    'installations_prev', (
      select count(distinct e.anon_id) from events e, periods p
      where e.day between p.prev_start and p.prev_end
    ),
    'features', coalesce((
      select jsonb_agg(f order by f.uses desc)
      from (
        select
          properties ->> 'feature_name' as feature,
          count(*) as uses,
          count(distinct anon_id) as installations,
          max(received_at) as last_used_at
        from current_events
        where event = 'feature_used' and properties ? 'feature_name'
        group by 1
      ) f
    ), '[]'::jsonb),
    'error_classes', coalesce((
      select jsonb_agg(c order by c.occurrences desc)
      from (
        select
          properties ->> 'error_class' as error_class,
          count(*) as occurrences,
          count(distinct anon_id) as installations,
          max(received_at) as last_seen_at
        from current_events
        where event = 'error_shown_to_user'
        group by 1
      ) c
    ), '[]'::jsonb)
  );
$$;

revoke all on function public.nicx_period_summary(integer) from public, anon;
grant execute on function public.nicx_period_summary(integer) to authenticated;
