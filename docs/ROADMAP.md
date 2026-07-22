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

## Pendente

### Fase 6 — Camada de Inteligência Artificial
Deliberadamente deixada para depois de tudo o resto estar sólido. Escopo pretendido: explicar oscilações do patrimônio em linguagem natural, permitir perguntas livres sobre as finanças ("quanto gastei com Uber esse ano?"), detecção de anomalias, previsões mais sofisticadas que a projeção linear/composta atual.

### Integração automática via Open Finance
Importar extratos automaticamente em vez de precisar baixar e subir o arquivo manualmente. Deixado por último porque depende de fatores externos (aprovação/parceria com provedores de Open Finance) fora do controle direto do desenvolvimento.

### Identidade visual própria
Marca, nome de exibição, ícone, paleta de cores de identidade (hoje o frontend usa um tema neutro cinza, já parecido com Linear/Notion, mas sem identidade própria). Decisão tomada em 22/07/2026: fazer depois, não agora — a arquitetura (variáveis de tema centralizadas) já deixa essa mudança barata de aplicar mais tarde, e o retorno é maior quando (e se) o sistema for aberto pra outras pessoas usarem, não só o Danilo.

### Visão de longo prazo: SaaS multiusuário
Hoje o SIFP é uso pessoal, sem login. A visão de longo prazo, já validada com o Danilo, é abrir como produto aberto — qualquer pessoa pode se cadastrar. Isso exige, quando chegar a hora: autenticação real (cadastro/login com senha), migração do banco de SQLite pra Postgres com isolamento de dados por usuário, e uma superfície de API mais ampla. O Streamlit **não** vai ganhar login — ele continua sendo só a ferramenta pessoal do Danilo; a versão multiusuário nasce inteiramente no frontend novo.
