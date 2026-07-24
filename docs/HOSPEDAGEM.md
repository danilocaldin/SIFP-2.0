# Hospedagem

## Onde o sistema está no ar

| | URL |
|---|---|
| **App pessoal do Danilo (uso diário)** | https://frontend-seven-virid-91.vercel.app |
| **SaaS multiusuário (clientes, com login)** | https://sifra-saas.vercel.app |
| API (compartilhada pelos dois acima) | https://sifp-20-production.up.railway.app |
| Repositório | https://github.com/danilocaldin/SIFP-2.0 |

Duas frentes, mesmo código-fonte e mesma API: o app pessoal do Danilo continua sem login (SQLite, rotas `/api/...`); o SaaS multiusuário exige login (Supabase Postgres + Row Level Security, rotas `/api/v2/...`). Uma única variável de ambiente no frontend (`NEXT_PUBLIC_SAAS_MODE`) decide qual modo cada deploy roda — nenhuma tela foi duplicada. Ver [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md) e a memória do projeto para o processo completo de migração.

## Como está montado

- **Frontend pessoal** (Next.js) → **Vercel**, projeto `danilocaldins-projects/frontend`, deploy a partir da pasta `frontend/` do repositório. `NEXT_PUBLIC_SAAS_MODE` não definida.
- **Frontend SaaS** (mesmo código) → **Vercel**, projeto `danilocaldins-projects/sifra-saas`. `NEXT_PUBLIC_SAAS_MODE=true`.
- **API** (FastAPI) → **Railway**, projeto `zooming-motivation`, serviço `SIFP-2.0`, buildado a partir do `Dockerfile` na raiz do repositório. Serve os dois frontends ao mesmo tempo.
- **Banco de dados do app pessoal** (SQLite) → arquivo num **volume persistente** do Railway, montado em `/data`. Sobrevive a redeploys porque fica fora da imagem Docker.
- **Banco de dados do SaaS** (Postgres + Auth) → **Supabase**, projeto `sifra-saas` (org `danilocaldin`, região `sa-east-1`). Row Level Security isola os dados de cada cliente no próprio banco — ver `sifp/repositories/pg/schema.sql`.
- **Worker de importação por e-mail** (SaaS only) → **Railway**, mesmo projeto `zooming-motivation`, serviço separado (mesma imagem/`Dockerfile`, `startCommand` e `cronSchedule` diferentes — roda `python -m sifp.workers.email_import_worker` a cada 15 minutos). Lê a caixa `extratos.sifra@gmail.com` via IMAP e importa extratos encaminhados automaticamente — ver `sifp/workers/email_import_worker.py`.

### Variáveis de ambiente

| Onde | Variável | Valor |
|---|---|---|
| Railway | `SIFP_DB_PATH` | `/data/financas.db` |
| Railway | `CORS_ORIGINS` | `https://frontend-seven-virid-91.vercel.app` |
| Railway | `ANTHROPIC_API_KEY` | chave da Anthropic (console.anthropic.com) — sem ela, o botão "Explicar este mês" fica indisponível, mas o resto do sistema funciona normalmente |
| Railway | `SUPABASE_URL` | `https://nkusahedzogplsjknijj.supabase.co` |
| Railway | `SUPABASE_PUBLISHABLE_KEY` | chave pública do Supabase (safe, não é segredo) |
| Railway | `SUPABASE_DB_URL` | connection string do Postgres (transaction pooler, porta 6543 — IPv4, Railway não tem IPv6) |
| Railway (API) | `EMAIL_IMPORT_BASE` | `extratos.sifra@gmail.com` — usado só pra montar o endereço "+token" exibido na tela Perfil |
| Railway (worker de e-mail) | `SUPABASE_DB_URL`, `IMAP_USER`, `IMAP_APP_PASSWORD` | mesma connection string do Postgres + credenciais IMAP da caixa dedicada (senha de app do Google, não a senha normal da conta) |
| Vercel (app pessoal) | `SIFP_API_URL` / `NEXT_PUBLIC_SIFP_API_URL` | `https://sifp-20-production.up.railway.app` |
| Vercel (SaaS) | mesmas duas acima, **mais** `NEXT_PUBLIC_SAAS_MODE=true`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | |

(`SIFP_API_URL` é usada no servidor do Next.js; `NEXT_PUBLIC_SIFP_API_URL` é a mesma URL, mas com o prefixo que o Next.js exige pra deixá-la acessível também no navegador — funcionalidades como Upload chamam a API direto do navegador do usuário.)

## Convidando um novo cliente pro SaaS

Cadastro é por convite, não é aberto ao público (decisão do Danilo, dado sensível financeiro). Painel do Supabase → **Authentication → Users → Add user**, com "Auto Confirm User" marcado (ou usar "Send magic link"/"Invite" se preferir que o próprio cliente defina a senha por e-mail). O cliente acessa https://sifra-saas.vercel.app e loga — os dados dele nascem vazios e isolados dos de qualquer outro cliente (RLS garante isso no banco, não só no código).

## Como publicar uma atualização

Depois de commitar as mudanças:

```bash
# 1. Envia o código
git push origin master

# 2. Pega o hash do commit mais recente
git log -1 --format=%H

# 3. Manda o Railway buildar esse commit específico
#    (troque <SHA> pelo hash do passo 2)
```

O passo 3 usa a API do Railway diretamente (GraphQL), porque a CLI da Railway não aceita o tipo de token de acesso deste projeto — ver detalhes técnicos em [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md). Na prática, isso é feito pelo Claude quando pedido.

```bash
# 4. Deploy do frontend (a partir da pasta frontend/)
cd frontend
vercel deploy --prod --yes
```

Depois de qualquer deploy, vale conferir:
- `curl https://sifp-20-production.up.railway.app/health` → deve responder `{"status":"ok"}`
- Abrir o app e olhar se os dados reais continuam aparecendo (o banco não deveria ter sido afetado por um deploy de código, mas confirmar é rápido e evita sustos)

## Como reimportar dados depois de qualquer reinstalação do banco

`financas.db` e `categorizer_model.joblib` nunca vão pro Git (são sensíveis, ficam de fora por design). Se o banco de produção precisar ser recriado do zero por qualquer motivo, o caminho é: acessar `/upload` no app publicado e reimportar os extratos bancários salvos localmente (CSV/XLS), depois `/patrimonio` para os PDFs de investimento. Não existe hoje um caminho de cópia direta do banco local pro volume do Railway — e não é necessário, já que o próprio sistema faz essa reconstrução.

## Autonomia de deploy via tokens

O Claude tem tokens de API do Railway e da Vercel (gerados por você, escopados ao projeto) que permitem fazer deploys, configurar variáveis e criar recursos sem precisar de cliques manuais no painel. Se algum dia quiser revogar esse acesso, é só apagar os tokens nas configurações de cada conta (`railway.app/account/tokens` e `vercel.com/account/tokens`) — o Claude avisa se precisar de um novo.
