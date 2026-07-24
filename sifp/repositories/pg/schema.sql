-- sifp/repositories/pg/schema.sql
-- --------------------------------
-- Schema do Postgres/Supabase para o SaaS multiusuário do Sifra. Espelha
-- as mesmas 5 tabelas de sifp/repositories/connection.py (SQLite, usado
-- pelo Streamlit pessoal do Danilo — não mexemos lá), com duas diferenças
-- deliberadas em toda tabela:
--   1) coluna user_id, default auth.uid() (preenchida sozinha a partir da
--      sessão da transação — nenhum INSERT dos repositories precisa
--      declará-la; ver connection.py) referenciando auth.users
--   2) Row Level Security (RLS): cada tabela só é legível/gravável pela
--      própria linha do dono. Isso é reforçado no banco, não só no código
--      do FastAPI — ver sifp/repositories/pg/connection.py para como cada
--      request seta o "usuário atual" da transação antes de qualquer query.
--
-- Idempotente: pode rodar de novo sem duplicar nada (DROP POLICY IF EXISTS
-- + CREATE TABLE IF NOT EXISTS).

create table if not exists transactions (
    tx_hash text not null,
    date text not null,
    description text not null,
    value double precision not null,
    category text default 'Não categorizado',
    confidence double precision default 0.0,
    source_file text,
    imported_at timestamptz default now(),
    bank_category text default '',
    human_confirmed boolean not null default false,
    self_transfer boolean not null default false,
    merchant text default '',
    category_source text default '',
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, tx_hash)
);

create table if not exists daily_balances (
    date text not null,
    balance double precision not null,
    source_file text,
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, date)
);

create table if not exists assets (
    position_key text not null,
    nome text not null,
    identificador text not null,
    tipo text,
    instituicao text,
    data_referencia text not null,
    quantidade double precision,
    cotacao double precision,
    saldo_bruto double precision default 0.0,
    saldo_liquido double precision default 0.0,
    rentabilidade_mes_pct double precision,
    rentabilidade_ano_pct double precision,
    rentabilidade_12m_pct double precision,
    benchmark text,
    benchmark_mes_pct double precision,
    benchmark_ano_pct double precision,
    benchmark_12m_pct double precision,
    source_file text,
    imported_at timestamptz default now(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, position_key)
);

create table if not exists budgets (
    category text not null,
    limite_mensal double precision not null,
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, category)
);

create table if not exists goals (
    id bigint generated always as identity primary key,
    nome text not null,
    valor_necessario double precision not null,
    valor_acumulado double precision not null default 0.0,
    prazo text not null,
    criado_em timestamptz default now(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade
);

create table if not exists despesas_fixas (
    id bigint generated always as identity primary key,
    nome text not null,
    categoria text not null,
    valor_mensal double precision not null,
    tipo text not null,
    data_inicio text not null,
    parcela_atual integer,
    parcelas_totais integer,
    ativa boolean not null default true,
    criado_em timestamptz default now(),
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade
);

-- Configurações do usuário de valor único (ex: limiar de alerta de
-- despesas fixas) — chave-valor genérica, mesmo motivo da versão SQLite.
create table if not exists preferencias (
    chave text not null,
    valor text not null,
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, chave)
);

-- Endereço de encaminhamento de e-mail (Módulo 18 — importação
-- automática via e-mail): token opaco, um por usuário, usado como sufixo
-- "+token" no endereço de recebimento. O worker (sifp/workers/
-- email_import_worker.py) consulta essa tabela com uma conexão SEM
-- escopo de usuário (bypassa RLS de propósito — é a única peça do
-- sistema que precisa mapear "token" -> "de quem é" antes de saber quem
-- é o usuário) — nunca exposta como endpoint público, só o processo
-- agendado interno lê assim.
create table if not exists import_aliases (
    token text primary key,
    user_id uuid not null unique default auth.uid() references auth.users(id) on delete cascade,
    criado_em timestamptz default now()
);

-- RLS: habilita e cria uma política única por tabela (cobre SELECT/INSERT/
-- UPDATE/DELETE — USING filtra leitura, WITH CHECK filtra escrita, ambos
-- exigindo user_id = auth.uid()). auth.uid() já existe em todo projeto
-- Supabase (lê o claim "sub" do JWT setado na transação — mesmo mecanismo
-- que o PostgREST usa por baixo dos panos).
do $$
declare
    t text;
begin
    foreach t in array array['transactions', 'daily_balances', 'assets', 'budgets', 'goals', 'despesas_fixas', 'preferencias', 'import_aliases']
    loop
        execute format('alter table %I enable row level security', t);
        execute format('drop policy if exists tenant_isolation on %I', t);
        execute format(
            'create policy tenant_isolation on %I to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())',
            t
        );
        execute format('grant select, insert, update, delete on %I to authenticated', t);
    end loop;
end $$;

grant usage, select on sequence goals_id_seq to authenticated;
grant usage, select on sequence despesas_fixas_id_seq to authenticated;
