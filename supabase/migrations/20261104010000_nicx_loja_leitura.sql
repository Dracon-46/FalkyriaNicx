-- Correção da loja: o visitante (anon) não pode executar nicx_is_admin(), então
-- a regra de leitura não pode chamá-la para ele. Visitantes leem só o
-- publicado; usuários logados leem o publicado e, se forem administradores,
-- tudo.

drop policy "Loja: todos leem o publicado" on public.nicx_loja_pacotes;
drop policy "Loja: todos leem versões publicadas" on public.nicx_loja_versoes;

create policy "Loja: visitantes leem o publicado"
  on public.nicx_loja_pacotes for select
  to anon
  using (publicado);

create policy "Loja: logados leem o publicado (admins, tudo)"
  on public.nicx_loja_pacotes for select
  to authenticated
  using (publicado or public.nicx_is_admin());

create policy "Loja: visitantes leem versões publicadas"
  on public.nicx_loja_versoes for select
  to anon
  using (
    exists (
      select 1 from public.nicx_loja_pacotes p
      where p.id = pacote_id and p.publicado
    )
  );

create policy "Loja: logados leem versões publicadas (admins, todas)"
  on public.nicx_loja_versoes for select
  to authenticated
  using (
    exists (
      select 1 from public.nicx_loja_pacotes p
      where p.id = pacote_id and (p.publicado or public.nicx_is_admin())
    )
  );
