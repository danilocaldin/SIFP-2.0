# Roadmap

Cronograma em ordem cronológica de construção. Ver [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md) para o inventário completo de telas e [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md) para o porquê de cada decisão.

## Concluído (10 de 10 entregas planejadas até aqui)

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

## Pendente — três iniciativas em espera, não esquecidas

Nenhuma foi descartada por falta de valor. Cada uma tem um critério claro de quando fazer sentido, e o código de hoje já foi desenhado pra não exigir retrabalho quando chegar a hora.

### Integração automática via Open Finance — custo não compensa ainda (pesquisado 22/07/2026)
Pesquisa confirmou custo real: Pluggy a partir de R$2.500/mês, Belvo ~R$6.000/mês, a opção mais barata regulada (Tecnospeed) R$1.500 de entrada + R$540/mês. Inviável para o uso atual (só o Danilo) — só faz sentido financeiro quando houver assinantes pagantes suficientes pra diluir esse custo.

**Integração direta com o BTG especificamente também foi descartada:** a API oficial do BTG (`developers.empresas.btgpactual.com`) é exclusiva pra contas Pessoa Jurídica, com plano pago — não existe versão pra pessoa física. O único caminho pra automação numa conta pessoal continua sendo o Open Finance (BTG participa como provedor de dados), o que não muda a conclusão acima.

**Retomar quando:** houver receita de assinatura real. Até lá, se for necessário suportar outro banco, o caminho mais barato é adicionar mais importadores manuais (mesmo padrão do `BTGImporter`, sem custo de API).

### Identidade visual própria — adiado de propósito (decisão 22/07/2026)
Marca, nome de exibição, ícone, paleta de cores de identidade. Hoje o frontend usa um tema neutro cinza (já parecido com Linear/Notion) sobre variáveis de tema centralizadas — essa arquitetura já deixa a troca barata de aplicar mais tarde.

**Retomar quando:** o sistema for aberto pra outras pessoas além do Danilo — é aí que o retorno do investimento em marca própria fica maior.

### Visão de longo prazo: SaaS multiusuário
Hoje o SIFP é uso pessoal, sem login. A visão de longo prazo, já validada com o Danilo, é abrir como produto aberto — qualquer pessoa pode se cadastrar. Isso exige, quando chegar a hora: autenticação real (cadastro/login com senha), migração do banco de SQLite pra Postgres com isolamento de dados por usuário, e uma superfície de API mais ampla.

**Nasce em:** só no frontend novo — o Streamlit **não** vai ganhar login, continua sendo só a ferramenta pessoal do Danilo.
