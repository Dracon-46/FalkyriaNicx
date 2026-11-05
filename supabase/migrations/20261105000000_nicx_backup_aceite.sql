-- Backup só de quem registrou o aceite dos Termos e da Política.
--
-- O app já recusava (servico._exigir_aceite), mas a regra de linha deixava
-- qualquer sessão válida gravar direto pela API. Agora o banco também exige o
-- aceite registrado em nicx_contas. A versão atual dos textos é conferida no
-- app (o banco não sabe qual é a vigente).

drop policy "Backup: cria os seus" on public.nicx_backups;

create policy "Backup: cria os seus, com aceite"
  on public.nicx_backups for insert
  to authenticated
  with check (
    user_id = (select auth.uid())
    and exists (
      select 1
      from public.nicx_contas c
      where c.id = (select auth.uid())
        and c.aceitou_em is not null
        and c.termos_versao <> ''
        and c.politica_versao <> ''
    )
  );
