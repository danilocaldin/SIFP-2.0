# Roadmap

Cronograma em ordem cronológica de construção. Ver [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) para o inventário completo de telas e [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md) para o porquê de cada decisão.

## Concluído (11 de 11 entregas planejadas até aqui)

### Fase 1 — Arquitetura em camadas
Migração dos scripts soltos originais para uma estrutura em camadas (`domain`, `importers`, `intelligence`, `repositories`, `services`) — a base que permitiu todo o resto crescer sem reescrever o que já funcionava.

### Fase 2 — Patrimônio
Importação de extratos de investimento (PDF do BTG) e evolução do patrimônio ao longo do tempo, a partir das posições reais em cada snapshot mensal.

### Fase 4 — Diagnósticos automáticos
Motor de regras extensível (construído antes da Fase 3, por ter o maior retorno com o menor esforço) — a base sobre a qual toda detecção automática do sistema roda até hoje, incluindo as peças de IA mais recentes.

### Fase 3 — Orçamento e Metas
Limite de gasto mensal por categoria (com sugestão automática baseada na média histórica) e acompanhamento de metas financeiras — ambos plugados no mesmo motor de diagnósticos da Fase 4, sem sistema de alerta paralelo.

### Fase 5 — Projeções
Projeção de patrimônio futuro com rendimento composto, usando a rentabilidade real dos investimentos (não a variação bruta do saldo) e a economia mensal recente.

### Frontend dedicado (21–22/07/2026)
Next.js hospedável, com paridade completa de funcionalidades em relação ao app Streamlit — todas as telas listadas em [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md), nenhum dos dois com funcionalidade exclusiva.

### Hospedagem (22/07/2026)
Sistema no ar em produção — API na Railway com volume persistente, frontend na Vercel — acessível de qualquer lugar, não só localmente. Ver [`HOSPEDAGEM.md`](HOSPEDAGEM.md).

### Revisão proativa no upload (22/07/2026)
Transferências e estabelecimentos novos passaram a ser perguntados logo após o upload, um de cada vez, em vez de esperar uma visita manual à tela de Revisão.

### Consolidação (22/07/2026)
Primeira revisão de segurança dedicada do sistema (sem achados), telas de erro amigáveis no frontend (antes inexistentes), e um bug real corrigido: o site inteiro renderizava na fonte errada desde o primeiro commit (ver [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md)).

### Fase 6 — Camada de Inteligência Artificial (22/07/2026) — completa, 5 de 5 peças
Da primeira regra estatística até o chat com acesso livre aos dados reais. As três primeiras peças não dependem de nenhum provedor de IA externo; as duas últimas usam a API da Anthropic (Claude Haiku), sempre sob demanda, nunca automaticamente.

1. ✅ **Detecção de anomalias** — transação individual fora do padrão histórico da categoria (método de Tukey/IQR), sem LLM.
2. ✅ **Faixa de confiança nas Projeções** — três cenários (pior/média/melhor), baseados em meses reais observados, não estatística instável, sem LLM.
3. ✅ **Reajuste em cobrança recorrente** — assinatura, mensalidade ou conta fixa que subiu de valor em relação ao próprio histórico estável, sem LLM.
4. ✅ **Explicação em linguagem natural** — botão sob demanda na tela Resumo que explica o porquê das oscilações do mês, em português simples (Claude Haiku).
5. ✅ **Chat com perguntas livres** — tela dedicada onde o Claude consulta os dados reais por conta própria (tool use — 4 ferramentas) para responder perguntas abertas como "quanto gastei com Uber esse ano?" (Claude Haiku).

### Identidade visual própria — Sifra (22/07/2026)
Nome de marca (**Sifra** — evolução de "SIFP" pra uma palavra real: cifra = quantia em dinheiro, e também código a decifrar), paleta azul-petróleo profundo (light e dark, tokens centralizados em `globals.css`), ícone/favicon (barras ascendentes, geometria simples que funciona em qualquer tamanho), wordmark em serifada. **SIFP continua sendo o nome técnico** — pacote Python, repositório, variáveis de ambiente, projetos na Railway/Vercel não mudaram, evitando um custo de retrabalho/risco de deploy sem ganho visível pra quem usa. Ver [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md) para o processo completo de escolha do nome.

**Segunda passada, depois do feedback "muito simples, não profissional" (22/07/2026):** menu lateral fixo sempre na cor de tinta da marca (independente do tema claro/escuro do conteúdo), agrupado por propósito com ícones; Resumo ganhou um gráfico de evolução mensal de verdade e um número de patrimônio grande em serifada; e alternador de modo claro/escuro (`next-themes`, detecta a preferência do sistema operacional e lembra a escolha entre visitas).

### Relatório em PDF (23/07/2026)
Botão "Baixar PDF" na tela Relatório (frontend) e na aba Relatório (Streamlit), ao lado do já existente ".txt". Capa com a marca, número de patrimônio em destaque, resumo do mês, gráfico de gastos por categoria e de evolução mensal (nativos, `reportlab.graphics.charts` — sem depender de matplotlib), e os 3 diagnósticos mais relevantes — deliberadamente curto (1–2 páginas), não um documento institucional denso. `pdf_report_service.py` reaproveita exatamente os mesmos dados que `RelatorioService` já compõe pro relatório em texto (nenhum número recalculado). Escolhido reportlab (puro Python) em vez de WeasyPrint pra evitar dependência nativa de SO (Pango/Cairo) — mesmo raciocínio da fonte Geist self-hosted.

## Em andamento

### SaaS multiusuário (decisão de escalar tomada em 22/07/2026)
Danilo decidiu começar a entregar o Sifra pra clientes reais. Duas frentes em paralelo:

1. **Estratégia rápida, disponível já:** uma instância isolada por cliente (próprio deploy, próprio banco vazio, sem necessidade de login porque cada um tem sua própria URL). Zero trabalho novo de código — reaproveita o processo de hospedagem já validado. Ver o passo a passo completo em [`CLIENTES.md`](CLIENTES.md).
2. **Estratégia definitiva, em construção por trás:** SaaS multiusuário de verdade — um único sistema, cadastro aberto, dados isolados por usuário no banco. Exige: autenticação real, migração de SQLite pra Postgres, isolamento de dados por usuário em toda tabela/rota, e telas de cadastro/login no frontend novo (o Streamlit **não** vai ganhar login — continua sendo só a ferramenta pessoal do Danilo).

**Decisão de arquitetura proposta (aguardando confirmação do Danilo):** usar **Supabase** como base — hospeda o Postgres *e* a autenticação no mesmo provedor, e oferece Row Level Security (RLS): o isolamento entre clientes fica garantido no próprio banco de dados, não só em cada linha de código que filtra por usuário. Isso importa especialmente aqui porque um filtro esquecido numa única query seria um vazamento real de dado financeiro entre clientes, não um bug cosmético — RLS fecha essa classe inteira de erro numa camada só, em vez de depender de disciplina manual espalhada em cada repository.

**Nasce em:** só no frontend novo.
