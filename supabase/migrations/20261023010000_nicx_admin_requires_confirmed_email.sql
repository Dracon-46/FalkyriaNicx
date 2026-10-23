-- Only a signed-in user whose email is confirmed counts as an administrator.
-- The JWT email claim alone is not enough: an unconfirmed sign-up could carry
-- an administrator's address if email confirmation were ever turned off.

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
  );
$$;

revoke all on function public.nicx_is_admin() from public, anon;
grant execute on function public.nicx_is_admin() to authenticated;
