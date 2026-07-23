# Entregar o Sifra para clientes

Duas estratégias em paralelo, decididas com o Danilo em 22/07/2026: uma **rápida** (instância isolada por cliente, pronta em minutos, sem depender de nenhum trabalho novo de código) pra começar a entregar já, e uma **definitiva** (SaaS multiusuário de verdade) sendo construída por trás, sem pressa. Ver a estratégia definitiva em [`ROADMAP.md`](ROADMAP.md).

## Por que não dá pra simplesmente mandar o link de hoje pra um cliente

O sistema hoje não tem login nem isolamento de dados — é um banco só, compartilhado. Mandar a URL atual (`https://frontend-seven-virid-91.vercel.app`) pra um cliente faria ele ver os dados financeiros reais do Danilo, não os dele. Não é uma questão de gosto, é uma questão de privacidade.

## Estratégia rápida: uma instância isolada por cliente

Cada cliente ganha sua própria cópia do sistema — próprio serviço na Railway (com volume/banco vazio, só dele) e próprio projeto na Vercel — sem precisar de login, porque cada cliente tem sua própria URL isolada que ninguém mais conhece. É essencialmente repetir o processo de hospedagem já feito pro Danilo (ver [`HOSPEDAGEM.md`](HOSPEDAGEM.md)), mais uma vez por cliente.

**Quando faz sentido:** poucos clientes, cada onboarding é feito manualmente. Não escala operacionalmente (10 clientes = 10 sistemas pra manter atualizados), mas tem custo de implementação praticamente zero — usa exatamente a mesma infraestrutura e workflow já validados.

**Quando parar de usar esse caminho:** se o número de clientes crescer a ponto de manter N cópias manualmente virar trabalho de verdade, é o sinal de que vale a pena automatizar esse processo num script (ainda não construído de propósito — não faz sentido automatizar um processo que só foi executado uma vez pro próprio Danilo; ver o porquê de não construir à frente da necessidade em [`DECISOES_E_LICOES.md`](DECISOES_E_LICOES.md)).

### Passo a passo (executado pelo Claude quando houver um cliente real)

1. **Railway — novo ambiente no mesmo projeto** (`environmentCreate`, projeto `zooming-motivation`, mesmo serviço `SIFP-2.0` já conectado ao GitHub): cria um ambiente novo (ex: `cliente-nomedocliente`) que builda o mesmo código, mas roda isolado.
2. **Volume novo** nesse ambiente, pra um banco SQLite vazio, exclusivo do cliente.
3. **Variáveis de ambiente do novo ambiente:** `SIFP_DB_PATH` apontando pro volume novo, `CORS_ORIGINS` apontando pra URL do frontend do cliente (passo 5), `ANTHROPIC_API_KEY` só se o cliente for usar as features de IA (Explicação/Chat) — decisão caso a caso, é custo variável por cliente.
4. **Domínio novo** pro serviço nesse ambiente (`serviceDomainCreate`), gerando uma URL própria de API pro cliente.
5. **Vercel — novo projeto**, deploy a partir da mesma pasta `frontend/`, com `SIFP_API_URL`/`NEXT_PUBLIC_SIFP_API_URL` apontando pra URL de API do passo 4. Gera uma URL própria de frontend.
6. **Cliente reimporta os próprios extratos** através do próprio Upload/Patrimônio — banco nasce vazio, sem nenhum dado do Danilo ou de outro cliente.
7. Registrar a URL do cliente e o nome do ambiente/projeto numa lista de controle (a decidir onde — hoje não existe esse registro ainda, criar quando o primeiro cliente for onboardado).

**Custo por cliente:** cada ambiente novo na Railway consome parte do plano Hobby (já ativo); cada projeto novo na Vercel é gratuito no plano atual até um certo volume de uso. Vale acompanhar se isso virar custo relevante conforme o número de clientes cresce.

## Estratégia definitiva: SaaS multiusuário

Ver a seção "SaaS multiusuário" em [`ROADMAP.md`](ROADMAP.md) para o escopo técnico completo e o status atual da decisão de arquitetura (autenticação + banco).
