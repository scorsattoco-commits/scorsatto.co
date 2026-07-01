create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text,
  phone text,
  email text,
  city text,
  state text,
  newsletter boolean default true,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.addresses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  address text,
  number text,
  complement text,
  neighborhood text,
  city text,
  state text,
  zip text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create unique index if not exists addresses_user_id_unique on public.addresses(user_id);

create table if not exists public.favorites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  product_slug text not null,
  created_at timestamptz default now(),
  unique(user_id, product_slug)
);

create table if not exists public.cart_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  product_slug text not null,
  size text not null,
  quantity integer not null default 1 check (quantity > 0),
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(user_id, product_slug, size)
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  customer_name text,
  customer_phone text,
  customer_city text,
  items jsonb not null default '[]'::jsonb,
  status text default 'whatsapp',
  created_at timestamptz default now()
);

create table if not exists public.customer_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  product_slug text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz default now()
);

create table if not exists public.admin_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  name text,
  role text not null default 'admin',
  created_at timestamptz default now()
);

create table if not exists public.product_overrides (
  slug text primary key,
  data jsonb not null default '{}'::jsonb,
  updated_by uuid references auth.users(id) on delete set null,
  updated_at timestamptz default now()
);

create or replace view public.abandoned_carts as
select
  c.user_id,
  p.email,
  p.name,
  p.phone,
  count(*) as item_count,
  sum(c.quantity) as total_quantity,
  max(c.updated_at) as last_cart_update
from public.cart_items c
left join public.profiles p on p.id = c.user_id
group by c.user_id, p.email, p.name, p.phone
having max(c.updated_at) < now() - interval '2 hours';

alter table public.profiles enable row level security;
alter table public.addresses enable row level security;
alter table public.favorites enable row level security;
alter table public.cart_items enable row level security;
alter table public.orders enable row level security;
alter table public.customer_events enable row level security;
alter table public.admin_users enable row level security;
alter table public.product_overrides enable row level security;

create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_select_admin" on public.profiles for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id);

create policy "addresses_all_own" on public.addresses for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "addresses_select_admin" on public.addresses for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "favorites_all_own" on public.favorites for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "favorites_select_admin" on public.favorites for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "cart_items_all_own" on public.cart_items for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "cart_items_select_admin" on public.cart_items for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "orders_select_own" on public.orders for select using (auth.uid() = user_id);
create policy "orders_select_admin" on public.orders for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "orders_insert_own_or_guest" on public.orders for insert with check (auth.uid() = user_id or user_id is null);
create policy "customer_events_insert_own_or_guest" on public.customer_events for insert with check (auth.uid() = user_id or user_id is null);
create policy "customer_events_select_own" on public.customer_events for select using (auth.uid() = user_id);
create policy "customer_events_select_admin" on public.customer_events for select using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
create policy "admin_users_select_own" on public.admin_users for select using (auth.uid() = user_id);
create policy "product_overrides_public_select" on public.product_overrides for select using (true);
create policy "product_overrides_admin_write" on public.product_overrides
for all
using (exists (select 1 from public.admin_users a where a.user_id = auth.uid()))
with check (exists (select 1 from public.admin_users a where a.user_id = auth.uid()));
