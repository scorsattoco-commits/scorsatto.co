create table if not exists public.instagram_leads (
  id uuid primary key default gen_random_uuid(),
  external_id text unique,
  handle text,
  name text,
  city text,
  source text not null default 'instagram',
  origin text,
  follows_profile boolean,
  context text,
  note text,
  status text not null default 'Novo',
  score integer not null default 0,
  raw jsonb not null default '{}'::jsonb,
  last_interaction_at timestamptz default now(),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists instagram_leads_status_idx on public.instagram_leads(status);
create index if not exists instagram_leads_score_idx on public.instagram_leads(score desc);
create index if not exists instagram_leads_updated_at_idx on public.instagram_leads(updated_at desc);
create index if not exists instagram_leads_handle_idx on public.instagram_leads(handle);

alter table public.instagram_leads enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'instagram_leads'
      and policyname = 'instagram_leads_select_admin'
  ) then
    create policy "instagram_leads_select_admin" on public.instagram_leads
    for select
    using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'instagram_leads'
      and policyname = 'instagram_leads_write_admin'
  ) then
    create policy "instagram_leads_write_admin" on public.instagram_leads
    for all
    using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()))
    with check (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
  end if;
end $$;

create or replace view public.instagram_daily_queue as
select
  id,
  handle,
  name,
  city,
  source,
  origin,
  context,
  note,
  status,
  score,
  last_interaction_at,
  updated_at
from public.instagram_leads
where coalesce(status, 'Novo') not in ('Arquivado', 'Sem interesse')
order by score desc, last_interaction_at desc nulls last, updated_at desc
limit 10;
