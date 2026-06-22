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

create table if not exists public.favorites (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  product_slug text not null,
  created_at timestamptz default now(),
  unique(user_id, product_slug)
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

alter table public.profiles enable row level security;
alter table public.addresses enable row level security;
alter table public.favorites enable row level security;
alter table public.orders enable row level security;

create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id);

create policy "addresses_all_own" on public.addresses for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "favorites_all_own" on public.favorites for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "orders_select_own" on public.orders for select using (auth.uid() = user_id);
create policy "orders_insert_own_or_guest" on public.orders for insert with check (auth.uid() = user_id or user_id is null);
