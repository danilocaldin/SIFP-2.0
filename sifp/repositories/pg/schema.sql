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

-- Achado real de auditoria: diferente das outras tabelas, essas duas têm
-- chave primária só em "id" (sem user_id), então sem um índice explícito
-- qualquer leitura filtrada por RLS (toda leitura é) varre a tabela
-- inteira de TODOS os clientes em vez de ir direto nas linhas do usuário
-- -- e "goals" ainda faz ORDER BY prazo, que sem índice lê tudo antes de
-- ordenar e só então descartar o que não é do usuário.
create index if not exists goals_user_idx on goals (user_id);
create index if not exists despesas_fixas_user_idx on despesas_fixas (user_id);

-- Configurações do usuário de valor único (ex: limiar de alerta de
-- despesas fixas) — chave-valor genérica, mesmo motivo da versão SQLite.
create table if not exists preferencias (
    chave text not null,
    valor text not null,
    user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    primary key (user_id, chave)
);

-- Dados adicionais de cadastro (wizard de onboarding pós-convite, ver
-- frontend/src/components/cadastro-wizard.tsx) -- nome e telefone ficam
-- em user_metadata (Supabase Auth), mas CPF precisa de garantia de
-- unicidade de verdade, que um blob JSON não oferece, daí a tabela
-- própria. `on delete cascade` libera o CPF automaticamente se a conta
-- for excluída (recurso de autoatendimento já existente, LGPD art. 18).
create table if not exists perfis (
    user_id uuid primary key references auth.users(id) on delete cascade,
    cpf text not null,
    data_nascimento date not null,
    pais text not null default 'Brasil',
    estado text not null,
    cidade text not null,
    -- Data/hora do aceite dos Termos/Privacidade -- LGPD art. 8º §5º, o
    -- ônus da prova de que houve consentimento é do controlador (mesmo
    -- raciocínio já aplicado em advisor_links.aceito_em).
    termos_aceitos_em timestamptz not null default now(),
    marketing_consent boolean not null default false,
    created_at timestamptz not null default now()
);
create unique index if not exists perfis_cpf_uidx on perfis (cpf);
alter table perfis enable row level security;
drop policy if exists perfis_select on perfis;
drop policy if exists perfis_insert on perfis;
create policy perfis_select on perfis for select to authenticated using (user_id = auth.uid());
create policy perfis_insert on perfis for insert to authenticated with check (user_id = auth.uid());
grant select, insert on perfis to authenticated;

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
    criado_em timestamptz default now(),
    -- "Confiar no primeiro uso": o primeiro e-mail que chega nesse alias
    -- registra o remetente aqui; e-mails seguintes só são processados se
    -- vierem do MESMO remetente (ver email_import_worker.py). Sem isso,
    -- qualquer pessoa que descubra o alias de alguém (vazamento,
    -- encaminhamento) podia injetar um extrato falso na conta da vítima.
    remetente_confiavel text
);

-- Migração idempotente: garante a coluna em bancos que já tinham a
-- tabela antes dessa mudança (rodar este arquivo de novo é seguro).
alter table import_aliases add column if not exists remetente_confiavel text;

-- Recurso de assessor financeiro: vínculo assessor<->cliente, somente
-- leitura, mediante convite aceito explicitamente pelo cliente (nunca
-- automático — ver docs/análise LGPD). Uma linha por par, ciclo de vida
-- inteiro nela (nunca deletada -- histórico de consentimento é evidência,
-- LGPD art. 8º §5º: o ônus da prova de que houve consentimento é do
-- controlador). Reconvidar depois de revogado faz UPDATE na mesma linha
-- (volta pra 'pendente'), não duplica -- o unique(advisor_id, client_id)
-- já impede duas linhas pro mesmo par.
create table if not exists advisor_links (
    id bigint generated always as identity primary key,
    advisor_id uuid not null references auth.users(id) on delete cascade,
    -- Nullable de propósito: no convite, o assessor só tem o e-mail do
    -- cliente -- auth.users é uma tabela protegida do Supabase, a role
    -- authenticated não pode consultar "existe alguém com esse e-mail?"
    -- sem a Admin API (segredo que ainda não temos, ver client_email
    -- abaixo). client_id só é preenchido quando o próprio dono do e-mail
    -- loga e "reivindica" o vínculo (ver claim_pending no repository) --
    -- funciona tanto pra quem já tem conta quanto, depois, pra quem
    -- ganhar conta nova via convite por e-mail (fase futura).
    client_id uuid references auth.users(id) on delete cascade,
    client_email text not null,
    status text not null default 'pendente' check (status in ('pendente', 'aceito', 'revogado')),
    convidado_em timestamptz not null default now(),
    aceito_em timestamptz,
    revogado_em timestamptz,
    -- Quem revogou (assessor ou cliente) -- decide se o cliente precisa
    -- ser avisado (revogação pelo próprio assessor, sem o cliente pedir,
    -- é o caso que precisa de aviso).
    revogado_por uuid references auth.users(id)
);
-- Migração idempotente: primeira versão desta tabela tinha client_id
-- NOT NULL + unique(advisor_id, client_id) inline -- ajusta bancos que já
-- rodaram essa versão antes de client_id virar nullable.
alter table advisor_links alter column client_id drop not null;
alter table advisor_links drop constraint if exists advisor_links_advisor_id_client_id_key;

-- Migração idempotente (exclusão de conta em autoatendimento, LGPD art.
-- 18): `revogado_por` não tinha `on delete cascade`/`on delete set null`
-- -- por padrão o Postgres usa NO ACTION, que bloqueia com erro de FK
-- qualquer tentativa de excluir (via Admin API) um usuário que já
-- revogou algum vínculo. `set null` (não `cascade`) porque revogado_por
-- é só metadado informativo da linha -- a linha em si (e seu histórico
-- de consentimento) já é apagada corretamente pelo cascade em advisor_id
-- ou client_id quando um dos dois lados do vínculo exclui a conta.
alter table advisor_links drop constraint if exists advisor_links_revogado_por_fkey;
alter table advisor_links add constraint advisor_links_revogado_por_fkey
    foreign key (revogado_por) references auth.users(id) on delete set null;

-- Migração idempotente (Fase 6, tela do cliente): faltava um jeito do
-- cliente saber QUEM é o assessor que mandou o convite -- client_email já
-- existia (denormalizado, mesma razão), mas o e-mail do assessor nunca
-- tinha sido gravado. Preenchido pela aplicação em convidar() a partir do
-- e-mail do próprio JWT do assessor (get_current_user_email) -- não
-- precisa da Admin API, é o mesmo padrão de client_email.
alter table advisor_links add column if not exists advisor_email text;

-- unique só entre linhas já reivindicadas -- várias linhas com
-- client_id NULL (convites ainda não reivindicados) são permitidas, a
-- aplicação evita duplicar convite pendente pro mesmo e-mail antes disso
-- (ver advisor_link_repository.py::convidar).
create unique index if not exists advisor_links_advisor_client_uidx
    on advisor_links (advisor_id, client_id) where client_id is not null;

alter table advisor_links enable row level security;
drop policy if exists advisor_links_select on advisor_links;
drop policy if exists advisor_links_insert on advisor_links;
drop policy if exists advisor_links_update on advisor_links;
-- SELECT: os dois lados do vínculo enxergam a própria linha -- inclui
-- "cliente ainda não reivindicou" via client_email = e-mail do próprio
-- JWT (auth.jwt() ->> 'email' é claim padrão do Supabase Auth), senão o
-- convidado nunca conseguiria VER o próprio convite pendente pra aceitar.
-- lower() nos dois lados: e-mail não é case-sensitive na prática, e o
-- validador do DTO (shared.py::validar_email) já normaliza pra minúsculo
-- antes de gravar -- sem o lower() aqui, um JWT com e-mail em maiúscula
-- (comum se o usuário digitou assim no cadastro) nunca bateria.
create policy advisor_links_select on advisor_links for select to authenticated
    using (advisor_id = auth.uid() or client_id = auth.uid() or lower(client_email) = lower(auth.jwt() ->> 'email'));
-- INSERT: só o assessor cria o convite (o cliente nunca insere aqui, só aceita/revoga).
create policy advisor_links_insert on advisor_links for insert to authenticated
    with check (advisor_id = auth.uid());
-- UPDATE: mesmo alcance do SELECT pra permitir a "reivindicação" (setar
-- client_id pela primeira vez) -- o WITH CHECK não precisa da cláusula de
-- e-mail porque, após a atualização, client_id = auth.uid() já é
-- verdadeiro pra linha resultante.
create policy advisor_links_update on advisor_links for update to authenticated
    using (advisor_id = auth.uid() or client_id = auth.uid() or lower(client_email) = lower(auth.jwt() ->> 'email'))
    with check (advisor_id = auth.uid() or client_id = auth.uid());
grant select, insert, update on advisor_links to authenticated;
grant usage, select on sequence advisor_links_id_seq to authenticated;

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

-- Acesso somente-leitura do assessor aos dados financeiros de um cliente
-- vinculado (status 'aceito'). Política ADICIONAL, só de SELECT, ao lado
-- da tenant_isolation acima -- políticas permissivas do Postgres se
-- combinam com OR, então isso não precisa (nem pode, com segurança)
-- alterar a política existente. "preferencias" e "import_aliases" ficam
-- de fora de propósito: configuração de conta, não dado financeiro do
-- cliente. A separação de "qual identidade a conexão está usando agora"
-- (o próprio assessor vs. um cliente específico) é feita na camada de
-- aplicação (ver sifp/api/auth.py::get_db) -- essa política sozinha só
-- garante que a linha É legível quando a conexão já está "como" o cliente.
do $$
declare
    t text;
begin
    foreach t in array array['transactions', 'daily_balances', 'assets', 'budgets', 'goals', 'despesas_fixas']
    loop
        execute format('drop policy if exists advisor_read on %I', t);
        execute format(
            'create policy advisor_read on %I for select to authenticated '
            'using (user_id in (select client_id from advisor_links where advisor_id = auth.uid() and status = ''aceito''))',
            t
        );
    end loop;
end $$;

grant usage, select on sequence goals_id_seq to authenticated;
grant usage, select on sequence despesas_fixas_id_seq to authenticated;
