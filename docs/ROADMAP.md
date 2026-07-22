# Roadmap

## Concluído

- ✅ **Fase 1** — Migração de scripts soltos pra arquitetura em camadas
- ✅ **Fase 2** — Patrimônio: importação de extratos de investimento, evolução do patrimônio ao longo do tempo
- ✅ **Fase 3** — Orçamento (limite por categoria) e Metas financeiras
- ✅ **Fase 4** — Diagnósticos automáticos (motor de regras extensível)
- ✅ **Fase 5** — Projeções de patrimônio futuro
- ✅ **Frontend dedicado** — Next.js hospedável, com paridade completa de funcionalidades em relação ao app Streamlit (todas as telas listadas em [`FUNCIONALIDADES.md`](FUNCIONALIDADES.md))
- ✅ **Hospedagem** — sistema no ar, acessível de qualquer lugar (ver [`HOSPEDAGEM.md`](HOSPEDAGEM.md))
- ✅ **Revisão proativa no upload** — pergunta categoria de transferências e estabelecimentos novos assim que um extrato é importado
- ✅ **Fase 6 (em andamento) — Detecção de anomalias** — o motor de diagnósticos agora sinaliza transações individuais fora do padrão histórico da categoria (ex: um Pix bem maior que o normal, uma compra atípica) usando estatística (método de Tukey/IQR), sem depender de nenhuma IA externa
- ✅ **Fase 6 (em andamento) — Faixa de confiança nas Projeções** — em vez de um número único, a tela agora mostra três cenários (pior/média/melhor mês recente), baseados em meses reais observados, não estatística instável. Efeito prático: a tela agora mostra a projeção mesmo quando a média dos últimos meses é negativa, desde que o melhor mês recente tenha sido positivo — antes disso ela simplesmente escondia tudo
- ✅ **Fase 6 (em andamento) — Reajuste em cobrança recorrente** — o motor de diagnósticos detecta quando um estabelecimento com cobrança historicamente estável (assinatura, mensalidade, conta fixa) subiu de valor no mês, sem depender de IA externa
- ✅ **Consolidação (22/07/2026)** — primeira revisão de segurança dedicada do sistema (sem achados), telas de erro amigáveis no frontend (antes inexistentes), e um bug real corrigido: o site inteiro renderizava na fonte errada desde o primeiro commit (ver [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md))
- ✅ **Fase 6 — Explicação em linguagem natural (22/07/2026)** — primeira peça de Fase 6 que usa um LLM de verdade: botão sob demanda na tela Resumo que manda os números já agregados do mês pro Claude Haiku (Anthropic) e recebe de volta 3-4 frases explicando o porquê das oscilações, em português simples. Presente tanto no Streamlit quanto no frontend novo.
- ✅ **Fase 6 — Chat com perguntas livres (22/07/2026)** — última peça planejada de Fase 6: nova tela de Chat onde o Claude consulta os dados reais por conta própria (tool use — 4 ferramentas: buscar transações, resumo de período, patrimônio, categorias válidas) em vez de receber tudo pronto de antemão, permitindo responder perguntas abertas tipo "quanto gastei com Uber esse ano?". Presente tanto no Streamlit quanto no frontend novo. Fase 6 está completa.

## Pendente

Nenhum item de Fase 6 pendente no momento — as cinco peças planejadas (detecção de anomalias, faixa de confiança nas Projeções, reajuste em cobrança recorrente, explicação em linguagem natural, chat com perguntas livres) estão todas no ar.

### Integração automática via Open Finance — pesquisado e descartado por ora (22/07/2026)
Pesquisa confirmou custo real: Pluggy a partir de R$2.500/mês, Belvo ~R$6.000/mês, a opção mais barata regulada (Tecnospeed) R$1.500 de entrada + R$540/mês. Inviável para o uso atual (só o Danilo) — só faz sentido financeiro quando houver assinantes pagantes suficientes pra diluir esse custo. Se um dia for necessário suportar outros bancos antes disso, o caminho mais barato é adicionar mais importadores manuais (mesmo padrão do `BTGImporter`, sem custo de API), não pagar por agregação automática.

**Integração direta com o BTG especificamente também foi descartada (22/07/2026):** a API oficial do BTG (`developers.empresas.btgpactual.com`) é exclusiva pra contas Pessoa Jurídica, com plano pago — não existe versão pra pessoa física. O único caminho pra automação numa conta pessoal continua sendo o Open Finance (BTG participa como provedor de dados), o que não muda a conclusão acima — ainda exige um agregador pago.

### Identidade visual própria
Marca, nome de exibição, ícone, paleta de cores de identidade (hoje o frontend usa um tema neutro cinza, já parecido com Linear/Notion, mas sem identidade própria). Decisão tomada em 22/07/2026: fazer depois, não agora — a arquitetura (variáveis de tema centralizadas) já deixa essa mudança barata de aplicar mais tarde, e o retorno é maior quando (e se) o sistema for aberto pra outras pessoas usarem, não só o Danilo.

### Visão de longo prazo: SaaS multiusuário
Hoje o SIFP é uso pessoal, sem login. A visão de longo prazo, já validada com o Danilo, é abrir como produto aberto — qualquer pessoa pode se cadastrar. Isso exige, quando chegar a hora: autenticação real (cadastro/login com senha), migração do banco de SQLite pra Postgres com isolamento de dados por usuário, e uma superfície de API mais ampla. O Streamlit **não** vai ganhar login — ele continua sendo só a ferramenta pessoal do Danilo; a versão multiusuário nasce inteiramente no frontend novo.
