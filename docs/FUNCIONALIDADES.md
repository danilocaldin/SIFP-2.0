# Funcionalidades

Inventário de cada tela: o que faz, onde a lógica mora, e o endpoint da API correspondente (quando existe).

## Resumo (`/`)
Tela inicial. Responde de cara as três perguntas centrais: quanto você tem (patrimônio + rentabilidade do mês), como está seu saldo (com comparação ao mês anterior), e o que mais precisa de atenção agora (o diagnóstico de maior prioridade). Projeção de 12 meses condensada numa frase.
**Serviço:** `summary_service.py` · **Endpoint:** `GET /api/resumo`

## Upload (`/upload`)
Importa um extrato bancário (CSV, XLS ou XLSX do BTG). Fluxo em duas etapas: primeiro mostra uma pré-visualização das transações lidas (sem gravar nada), depois — só quando você confirma — categoriza e grava de fato. Reimportar o mesmo arquivo nunca duplica dados (detecção por hash da transação).

Desde 22/07/2026, se o upload trouxer uma **transferência para outra pessoa** (Pix, TED) ou um **estabelecimento novo que o sistema não teve confiança pra categorizar sozinho**, uma caixinha pergunta a categoria de cada um, uma por vez, antes de fechar o processo — porque o BTG nem sempre categoriza certo, e transferências podem significar coisas diferentes a cada vez. Transferências entre suas próprias contas não entram nessa pergunta (já são detectadas com certeza).

**Serviço:** `import_service.py` · **Endpoints:** `POST /api/upload/preview`, `POST /api/upload/persist`

## Revisão de Categorias (`/revisao`)
Onde você corrige categorias em massa. Duas partes: (1) estabelecimentos pendentes agrupados por descrição, pra aplicar uma categoria de uma vez em todas as ocorrências; (2) uma tabela completa de todas as transações, com filtros (só pendentes / só baixa confiança), onde você edita a categoria linha a linha e confirma. Toda correção vira "memória" — a próxima transação com a mesma descrição exata já vem categorizada sozinha. Uma descrição que já variou de categoria (ex: Pix pra uma pessoa que às vezes é uma coisa, às vezes outra) fica sempre marcada como pendente, porque o sistema sabe que precisa da sua decisão a cada vez.
**Serviço:** `revisao_service.py` · **Endpoints:** `GET /api/revisao`, `POST /api/revisao/lote`, `POST /api/revisao/confirmar`, `POST /api/revisao/retreinar`

## Dashboard (`/dashboard`)
Visão geral de um mês (ou de todo o período): receitas, despesas, saldo, taxa de poupança, comparação com o mês anterior, gastos por categoria, evolução mensal, maiores gastos individuais, maiores estabelecimentos.
**Serviço:** `dashboard_service.py` · **Endpoint:** `GET /api/dashboard?month=`

## Patrimônio (`/patrimonio`)
Importa extratos de investimento (PDF do BTG) e mostra o patrimônio total, a posição de cada ativo, e a evolução do patrimônio ao longo do tempo.
**Serviço:** `patrimonio_service.py` · **Endpoints:** `GET /api/patrimonio`, `POST /api/patrimonio/import`

## Orçamento e Metas (`/orcamento`)
Duas coisas independentes na mesma tela: (1) limites de gasto mensal por categoria, com sugestão automática de valor inicial baseada na sua média histórica; (2) metas financeiras (nome, valor necessário, prazo, progresso). Ambos alimentam o motor de diagnósticos automaticamente (orçamento estourado, meta atrasada).
**Serviço:** `orcamento_service.py` (limites) + acesso direto ao `goal_repo` (metas, CRUD simples o suficiente pra não precisar de service próprio) · **Endpoints:** `GET /api/orcamento`, `POST/DELETE /api/orcamento/limites`, `GET/POST/PATCH/DELETE /api/metas`

## Projeções (`/projecoes`)
Projeta o patrimônio nos próximos 6/12/24 meses, com base na sua economia mensal recente e na rentabilidade real dos seus investimentos (não a bruta — isola o efeito de aportes/resgates). Mostra uma **faixa** entre o pior e o melhor cenário (baseada nos meses reais mais fraco e mais forte dos últimos 3, não uma estimativa estatística), em vez de um número único que passaria uma precisão falsa. O gráfico aparece sempre que houver algum cenário positivo — mesmo que a média recente seja negativa, desde que um mês bom recente sustente um cenário de crescimento. Mostra também, por meta cadastrada, a data prevista de conclusão no ritmo médio atual.
**Serviço:** `projecoes_service.py` (usa `projection_service.py` por baixo) · **Endpoint:** `GET /api/projecoes?horizonte=`

## Diagnósticos (`/diagnosticos`)
Lista completa de alertas automáticos, ordenados por prioridade. Regras hoje: saldo negativo recorrente, taxa de poupança baixa, concentração excessiva numa categoria, transações pendentes de categorização, reserva de emergência insuficiente, orçamento estourado, meta atrasada/em risco, investimento rendendo abaixo do CDI, categoria com gasto crescendo, gasto de fim de semana muito acima do normal, dinheiro parado na conta corrente perdendo rentabilidade, **gasto individual fora do padrão** (compara cada transação do mês contra o histórico da mesma categoria por método estatístico) e **reajuste em cobrança recorrente** (assinatura, mensalidade ou conta fixa que subiu de valor em relação ao seu próprio histórico estável) — as duas últimas são peças da Fase 6/IA que não usam nenhum modelo de linguagem.
**Motor:** `sifp/intelligence/diagnostics.py` · **Endpoint:** reaproveita `GET /api/resumo` (mesma lista completa de diagnósticos, não tem endpoint próprio)

## Relatório (`/relatorio`)
Consolida tudo (resumo, categorias, estabelecimentos, diagnósticos, patrimônio, dívidas) num texto único pra um mês, pronto pra copiar ou baixar. Nunca diverge das outras telas porque usa exatamente os mesmos cálculos.
**Serviço:** `relatorio_service.py` (usa `report_service.py` por baixo) · **Endpoint:** `GET /api/relatorio?month=`

---

## Paridade entre as duas interfaces

Toda aba que existe no Streamlit (`app.py`) tem uma tela equivalente no frontend novo, e vice-versa — nenhum dos dois tem funcionalidade exclusiva.
