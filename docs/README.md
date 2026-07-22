# SIFP — Sistema de Inteligência Financeira Pessoal

Documentação de referência do projeto. Se surgir uma dúvida sobre como o sistema funciona, por que uma decisão foi tomada, ou como mexer em alguma parte dele, comece por aqui.

## O que é o SIFP

O SIFP não é um app de "anotar gastos" — é uma plataforma de **inteligência financeira pessoal**: importa extratos bancários reais, categoriza transações automaticamente (regras + Machine Learning), calcula indicadores, gera diagnósticos automáticos sobre a saúde financeira, projeta patrimônio futuro, e consolida tudo isso em relatórios. A ideia central é que o sistema *interprete* os dados pra você, não só os organize.

Hoje é uso pessoal do Danilo. O objetivo de longo prazo é abrir como um produto que qualquer pessoa possa usar (SaaS multiusuário) — ver [`ROADMAP.md`](ROADMAP.md).

## Onde encontrar cada coisa

| Dúvida | Documento |
|---|---|
| Como o código está organizado, o que cada camada faz | [`ARQUITETURA.md`](ARQUITETURA.md) |
| O que cada tela do sistema faz, onde a lógica dela mora | [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) |
| Onde o sistema está hospedado, como fazer um novo deploy | [`HOSPEDAGEM.md`](HOSPEDAGEM.md) |
| Por que uma decisão foi tomada, bugs reais já encontrados e corrigidos | [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md) |
| O que já foi feito, o que falta | [`ROADMAP.md`](ROADMAP.md) |

## Duas interfaces, um só motor

O sistema tem **duas interfaces** rodando sobre o mesmo código de negócio (`sifp/`), nunca duplicado:

1. **App Streamlit** (`app.py`) — a versão original, roda só localmente (`streamlit run app.py`), uso pessoal do Danilo no dia a dia enquanto o frontend novo amadurece. Continua funcionando em paralelo — nada foi desativado.
2. **Frontend dedicado** (`frontend/`, Next.js) + **API** (`sifp/api/`, FastAPI) — a versão hospedada, acessível de qualquer lugar, é a que está evoluindo e vai ser o produto final. Ver [`HOSPEDAGEM.md`](HOSPEDAGEM.md) para os links de acesso.

Ambas chamam exatamente os mesmos `services`/`repositories` em `sifp/` — nunca há duas implementações da mesma regra de negócio.

## Como rodar localmente

```bash
# App Streamlit
streamlit run app.py

# API (necessária pro frontend novo)
uvicorn sifp.api.main:app --port 8000

# Frontend novo (numa pasta separada)
cd frontend
npm run dev
```

Testes: `pytest` (roda a partir da raiz do projeto).

## Dados reais e segurança

`financas.db` (banco de dados com as transações reais) e `categorizer_model.joblib` (modelo de IA treinado) **nunca vão pro Git** — estão no `.gitignore` de propósito, porque contêm dados financeiros sensíveis. Isso vale tanto para o ambiente local quanto para produção: o banco em produção (Railway) é um arquivo completamente separado, num volume persistente, alimentado só pelos uploads feitos através do próprio sistema.
