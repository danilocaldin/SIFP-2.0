# Hospedagem

## Onde o sistema está no ar

| | URL |
|---|---|
| **App (uso diário)** | https://frontend-seven-virid-91.vercel.app |
| API (uso interno) | https://sifp-20-production.up.railway.app |
| Repositório | https://github.com/danilocaldin/SIFP-2.0 |

Ainda não existe login — é hospedagem de uso pessoal (só o Danilo), sem autenticação. Virar produto multiusuário é uma etapa futura deliberadamente separada (ver [`ROADMAP.md`](ROADMAP.md)).

## Como está montado

- **Frontend** (Next.js) → **Vercel**, projeto `danilocaldins-projects/frontend`, deploy a partir da pasta `frontend/` do repositório.
- **API** (FastAPI) → **Railway**, projeto `zooming-motivation`, serviço `SIFP-2.0`, buildado a partir do `Dockerfile` na raiz do repositório.
- **Banco de dados** (SQLite) → arquivo num **volume persistente** do Railway, montado em `/data`. Sobrevive a redeploys porque fica fora da imagem Docker.

### Variáveis de ambiente

| Onde | Variável | Valor |
|---|---|---|
| Railway | `SIFP_DB_PATH` | `/data/financas.db` |
| Railway | `CORS_ORIGINS` | `https://frontend-seven-virid-91.vercel.app` |
| Railway | `ANTHROPIC_API_KEY` | chave da Anthropic (console.anthropic.com) — sem ela, o botão "Explicar este mês" fica indisponível, mas o resto do sistema funciona normalmente |
| Vercel | `SIFP_API_URL` | `https://sifp-20-production.up.railway.app` |
| Vercel | `NEXT_PUBLIC_SIFP_API_URL` | `https://sifp-20-production.up.railway.app` |

(`SIFP_API_URL` é usada no servidor do Next.js; `NEXT_PUBLIC_SIFP_API_URL` é a mesma URL, mas com o prefixo que o Next.js exige pra deixá-la acessível também no navegador — funcionalidades como Upload chamam a API direto do navegador do usuário.)

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
