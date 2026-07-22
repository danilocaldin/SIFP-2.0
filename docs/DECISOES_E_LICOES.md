# Decisões e lições aprendidas

Registro do "porquê" por trás de escolhas importantes, e de bugs reais que já apareceram e foram corrigidos — pra não serem reintroduzidos por engano no futuro.

## Decisões de produto

**Não é um app de anotar gastos, é inteligência financeira.** Cada tela responde uma pergunta ("como estou indo?", "o que precisa de atenção?"), não só lista números. Guia toda decisão de funcionalidade nova: automatizar interpretação em vez de só exibir dados.

**Streamlit primeiro, frontend dedicado depois — de propósito.** Validar a lógica de negócio (importação, categorização, diagnósticos, projeções) rápido, sem esforço de UI, antes de investir em uma interface polida. O Streamlit nunca foi descartado — continua rodando em paralelo.

**Sem módulo formal de Passivos.** Só categorias informais de dívida ("Dívida", "Ajuda Familiar") — não há rastreamento de financiamento/cartão de crédito estruturado, porque não foi pedido.

**Orçamento sugere um valor inicial em vez de pedir pra você adivinhar.** O formulário de limite de categoria já vem preenchido com sua média histórica de gasto naquela categoria (3 meses) — você só ajusta se quiser.

**Rentabilidade real, não a variação bruta do saldo.** Como o CDB do Danilo é usado como reserva de liquidez (aportes e resgates frequentes), calcular "quanto cresceu" a partir da diferença entre dois extratos é enganoso — um mês mostrou "+160%" quando o rendimento real era 1,13%. A correção foi usar sempre a rentabilidade que o próprio banco calcula (baseada em cota), que já isola contribuições de rendimento de verdade. **Regra geral: nunca calcular "crescimento" a partir de dois saldos brutos quando a conta pode receber aportes/resgates — sempre preferir o índice de rentabilidade que a instituição já calcula.**

**Revisão rápida no upload: só categoria, sem campo de texto livre.** Ao perguntar sobre transferências e estabelecimentos novos logo após o upload, a decisão foi manter simples — sem digitação, só escolher a categoria da lista já existente.

## Decisões de arquitetura

**Toda regra de negócio vive em `sifp/`, nunca no Streamlit ou na API.** Isso é o que garante que as duas interfaces nunca mostrem números diferentes.

**SQLite isolado numa única camada (`sifp/repositories/connection.py`).** Se um dia for necessário migrar pra Postgres (necessário pra virar SaaS multiusuário — múltiplos usuários, cada um com seus dados isolados), a mudança fica contida ali.

**Formato de moeda brasileiro em todo lugar.** Foi encontrada uma inconsistência real: texto pré-formatado de diagnósticos usava separador americano (R$ 3,006.49) enquanto o resto do sistema usava separador brasileiro (R$ 3.006,49) — mesma tela, dois formatos. Corrigido na origem (`formatting.py`), nunca formatar moeda "na unha" de novo (`f"R$ {x:,.2f}"` é o padrão errado).

## Bugs reais encontrados e corrigidos

### Datas em formatos diferentes viravam `NaT` silenciosamente
O importador de CSV gravava a data como `"2026-06-01"` (sem hora) enquanto o importador de Excel gravava `"2026-06-01 07:35"` (com hora) — dois formatos de texto diferentes na mesma coluna do banco. Como o pandas infere automaticamente o formato de data ao ler de volta (baseado na maioria das linhas), qualquer linha no formato minoritário virava uma data inválida (`NaT`) sem erro nenhum — e isso corrompia silenciosamente qualquer indicador calculado a partir dela. **Corrigido centralizando a normalização de data no único ponto de gravação** (`TransactionRepository.insert_new()`), não em cada importador — protege qualquer importador de banco que for adicionado no futuro.

### Sugestão da IA sempre "opina" — nunca diz "não sei"
O modelo de Machine Learning treinado prevê alguma categoria pra qualquer texto, mesmo um nunca visto antes — não existe uma opção "não tenho certeza" embutida nele. Isso é esperado (é assim que classificadores desse tipo funcionam), mas importa saber: a fila de "revisão pendente" não é "tudo que é novo", é especificamente "o que ficou com categoria Não categorizada" — que pode não incluir todo estabelecimento genuinamente novo, se o modelo "chutar" com confiança.

### Coluna de texto de moeda escapada aparecendo errada
Streamlit renderiza `$` pareado como fórmula matemática (LaTeX) dentro de texto markdown — então todo texto de diagnóstico que passa por `st.markdown` precisa escapar o `R$` como `R\$`. Só que a API (que serve o frontend novo, sem renderização de markdown) precisa do texto *sem* esse escape, senão a barra invertida aparece visível na tela. Solução: uma função de "desescape" (`unescape_currency`) aplicada só na camada da API.

### O site inteiro renderizava na fonte errada desde o primeiro commit
No arquivo de tema (`globals.css`), a variável `--font-sans` estava definida como `var(--font-sans)` — apontando pra si mesma. CSS não acusa erro nisso, só resolve silenciosamente pra "nada", caindo no fallback padrão do navegador (uma fonte serifada, tipo Times New Roman). A variável de fonte monoespaçada, logo abaixo, estava correta (`var(--font-geist-mono)`) — só a `sans` tinha o typo. Passou despercebido porque uma fonte serifada genérica ainda "parece uma página normal" numa olhada rápida; só apareceu inspecionando o estilo computado (`getComputedStyle`) durante uma revisão de consolidação, meses depois de o frontend ter ido ao ar. **Lição: uma variável CSS que aponta pra si mesma nunca dá erro — se uma fonte/cor parecer "quase certa mas não exatamente", vale a pena checar o estilo computado de verdade, não só olhar a tela.**

## Revisão de segurança (22/07/2026)

Passada dedicada de segurança em todo o código que fala com a internet (`sifp/api/`, `sifp/repositories/`, `sifp/importers/`) — a primeira desde que o sistema foi ao ar. Checado e confirmado limpo: toda query SQL é parametrizada (sem injeção), upload de arquivo é tratado inteiramente em memória (nunca grava em disco, sem risco de path traversal), sem `eval`/`exec`/execução de comando dinâmica em lugar nenhum, CORS restrito à origem exata do frontend, sem modo debug em produção, e nenhum token usado durante o desenvolvimento (Railway, Vercel) jamais foi parar no histórico do Git — conferido diretamente. Zero problemas encontrados. Vale repetir essa revisão periodicamente conforme o sistema crescer, especialmente antes de qualquer autenticação/multiusuário entrar em cena.

## Aprendizados sobre ferramentas (técnico)

- A CLI da Railway não aceita tokens de acesso escopados a um workspace (só tokens de conta) — o deploy é feito direto pela API GraphQL da Railway nesse caso. A CLI da Vercel, por outro lado, funciona normalmente com qualquer token.
- `pandas`, ao aplicar uma função que devolve booleano numa coluna vazia, às vezes infere o tipo errado (`str` em vez de `bool`) — o que quebra operações lógicas (`|`, `&`) depois. Sempre forçar `.astype(bool)` explicitamente nesses casos.
