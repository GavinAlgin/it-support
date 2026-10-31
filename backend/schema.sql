
-- CLOUDMONITOR DATABASE SCHEMA

create extension if not exists pgcrypto;

-- User profiles linked to Supabase Authentication
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    username text unique,
    role text not null default 'employee'
        check (role in ('admin', 'employee')),
    created_at timestamptz default now()
);

-- Authorized computers
create table if not exists public.devices (
    id uuid primary key default gen_random_uuid(),
    hostname text not null,
    os_name text,
    agent_version text,
    device_token_hash text not null,
    monitoring_enabled boolean not null default false,
    permissions jsonb not null default '{}'::jsonb,
    last_seen timestamptz,
    created_at timestamptz default now()
);

-- Administrator-generated enrollment codes
create table if not exists public.enrollment_codes (
    id uuid primary key default gen_random_uuid(),
    code_hash text not null unique,
    created_by uuid references public.profiles(id),
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz default now()
);

-- Permission requests
create table if not exists public.permission_requests (
    id uuid primary key default gen_random_uuid(),
    device_id uuid not null references public.devices(id) on delete cascade,
    scope text not null,
    description text,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'denied')),
    created_at timestamptz default now(),
    responded_at timestamptz
);

-- Incoming system metrics
create table if not exists public.metrics (
    id bigint generated always as identity primary key,
    device_id uuid not null references public.devices(id) on delete cascade,
    metrics jsonb not null,
    recorded_at timestamptz not null default now()
);

create index if not exists metrics_device_time_idx
on public.metrics(device_id, recorded_at desc);

-- System alerts
create table if not exists public.alerts (
    id uuid primary key default gen_random_uuid(),
    device_id uuid not null references public.devices(id) on delete cascade,
    alert_type text not null,
    message text not null,
    severity text not null default 'warning',
    acknowledged boolean not null default false,
    created_at timestamptz default now()
);

-- Enable row-level security
alter table public.profiles enable row level security;
alter table public.devices enable row level security;
alter table public.enrollment_codes enable row level security;
alter table public.permission_requests enable row level security;
alter table public.metrics enable row level security;
alter table public.alerts enable row level security;

-- No direct access from ordinary client roles.
-- Backend accesses these tables using the service role key.
