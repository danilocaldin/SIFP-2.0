# Arquitetura

## Princípio central

Todo o código de regra de negócio (ler extratos, categorizar, calcular indicadores, gerar diagnósticos, projetar, gravar no banco) vive em `sifp/`, organizado em camadas. Tanto o app Streamlit (`app.py`) quanto a API (`sifp/api/main.py`, que alimenta o frontend novo) são **camadas de apresentação finas** — elas só chamam `sifp/`, nunca reimplementam nada. Isso garante que os dois nunca mostrem números diferentes para a mesma pergunta.

```
extrato bancário (CSV/XLS/PDF)
        │
        ▼
  sifp/importers      -- lê o arquivo, normaliza pra um formato comum
        │
        ▼
  sifp/intelligence    -- categoriza (regras + ML), detecta transferências
        │
        ▼
  sifp/repositories     -- grava/lê do SQLite (financas.db)
        │
        ▼
  sifp/services          -- calcula indicadores, diagnósticos, projeções,
        │                    monta o "payload" de cada tela
        ▼
  app.py  (Streamlit)  OU  sifp/api/main.py (FastAPI) → frontend/ (Next.js)
```

## As camadas, em detalhe

### `sifp/domain/`
Modelos de dados puros (dataclasses, enums), sem nenhuma dependência de banco ou UI.
- `models.py` — `Transaction`, `AssetPosition`, `Diagnostic`/`DiagnosticSeverity`, `Budget`, `Goal`
- `categories.py` — a lista fixa de categorias (`CATEGORIAS_PADRAO`) e a categoria especial `"Não categorizado"`

### `sifp/importers/`
Lê arquivos de extrato e devolve dados já normalizados (nunca no formato bruto do banco).
- `base.py` — interface comum (`StatementImporter`) que todo importador de banco implementa
- `btg_importer.py` — extrato de conta corrente do BTG Pactual (CSV, XLS, XLSX)
- `btg_investment_importer.py` — extrato de investimentos do BTG (PDF)
- Pensado pra crescer: outros bancos (Inter, Nubank, Santander, XP) entrariam aqui, implementando a mesma interface, sem tocar em mais nada do sistema.

### `sifp/intelligence/`
- `categorization.py` — decide a categoria de cada transação, em ordem de prioridade: memória aprendida (o que você já confirmou antes pra essa descrição exata) → transferência entre contas próprias (detecção automática) → regras de palavra-chave → categoria que o próprio banco sugeriu → Machine Learning (TF-IDF + Regressão Logística, treinado com as transações que você já confirmou)
- `diagnostics.py` — motor de regras que gera os alertas automáticos (saldo negativo recorrente, taxa de poupança baixa, reserva de emergência insuficiente, etc.)
- `merchant_normalizer.py` — limpa nomes de estabelecimento pra exibição

### `sifp/repositories/`
Único lugar do sistema que sabe que o banco de dados é SQLite — se um dia trocar pra Postgres (necessário pra virar SaaS multiusuário), a mudança fica contida aqui.
- `connection.py` — conexão e schema; caminho do banco configurável via variável de ambiente `SIFP_DB_PATH` (usado em produção pra apontar pro volume persistente do Railway)
- `transaction_repository.py`, `balance_repository.py`, `asset_repository.py`, `budget_repository.py`, `goal_repository.py`

### `sifp/services/`
Onde a lógica de cada tela é montada — cada `*_service.py` tem um método `build_X()` que agrega indicadores/diagnósticos num único payload, compartilhado entre Streamlit e a API.
- `indicator_service.py` — funções puras de cálculo (resumo do período, evolução mensal, concentração por estabelecimento, etc.)
- `import_service.py` — orquestra ler → categorizar → gravar um extrato
- `projection_service.py` — projeção de patrimônio futuro
- `report_service.py` — monta o relatório em texto
- `summary_service.py`, `dashboard_service.py`, `patrimonio_service.py`, `projecoes_service.py`, `orcamento_service.py`, `relatorio_service.py`, `revisao_service.py` — um por tela
- `formatting.py` — formatação de moeda em padrão brasileiro (R$ 1.234,56), compartilhada por tudo

### `sifp/api/main.py`
API REST (FastAPI) que expõe os `services` pela web, pro frontend novo consumir. Zero regra de negócio nova aqui — só tradução HTTP/JSON. Lista completa de endpoints em [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md).

### `frontend/`
Next.js 16 (App Router) + TypeScript + Tailwind + shadcn/ui. Cada tela é uma página que busca dados da API (Server Component) e delega interatividade (formulários, uploads, seletores) a Componentes Cliente (`"use client"`). Gráficos usam a paleta de cores validada (contraste e daltonismo) pela `dataviz` skill.

## Por que duas interfaces em paralelo

Streamlit foi o jeito mais rápido de validar as Fases 1–5 (importação, categorização, diagnósticos, projeções) sem esforço de frontend. Uma vez que essas fases provaram valor, começou a construção do frontend dedicado — mais rápido, mais bonito, hospedável — reaproveitando 100% da lógica já validada. O Streamlit não foi descontinuado: continua funcionando como app pessoal enquanto o frontend novo é a versão que vai virar produto.
