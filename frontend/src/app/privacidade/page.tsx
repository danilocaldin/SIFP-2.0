import Link from "next/link";

export const metadata = {
  title: "Política de Privacidade — Sifra",
};

export default function PrivacidadePage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12 sm:py-16">
      <Link href="/" className="mb-6 inline-flex items-center gap-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icon.svg" alt="Sifra" width={28} height={28} className="rounded-[7px]" />
        <span className="font-display text-base font-semibold">Sifra</span>
      </Link>

      <div className="mb-6 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-300">
        <strong>Versão provisória, em revisão jurídica.</strong> Este texto descreve honestamente o que
        o Sifra faz hoje com seus dados, mas ainda não foi validado por um advogado como texto legal
        final — pode mudar.
      </div>

      <h1 className="text-xl font-semibold">Política de Privacidade</h1>
      <p className="mt-1 text-sm text-muted-foreground">Última atualização: agosto de 2026.</p>

      <div className="mt-6 flex flex-col gap-5 text-sm leading-relaxed text-foreground">
        <section>
          <h2 className="mb-1.5 font-medium">1. Quais dados coletamos</h2>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            <li>Cadastro: nome, e-mail, celular, CPF, data de nascimento, país, estado e cidade.</li>
            <li>
              Dados financeiros que você importa: transações bancárias, saldos, investimentos, orçamento,
              metas e despesas fixas — incluindo, quando presentes nos seus extratos, nomes de terceiros
              em descrições de transação (ex: nome de quem recebeu um Pix).
            </li>
            <li>Se você cadastrar biometria (Face ID/Touch ID) pra entrar sem senha, um dado biométrico.</li>
            <li>Histórico de conversas com o assistente de IA, se você usar o chat.</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">2. Por que coletamos</h2>
          <p className="text-muted-foreground">
            Pra entregar o serviço em si (organizar e mostrar seus dados financeiros, gerar diagnósticos
            e projeções) e, quando você autoriza, pra biometria de login e pra funcionar o assistente de
            chat. Não vendemos nem compartilhamos seus dados com terceiros pra fins de publicidade.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">3. Com quem seus dados podem ser compartilhados</h2>
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            <li>
              <strong>Anthropic</strong> (Estados Unidos): quando você usa o chat ou a explicação
              automática de diagnósticos, o texto da sua pergunta e os dados financeiros necessários pra
              responder são enviados pra API da Anthropic — isso envolve transferência internacional de
              dados.
            </li>
            <li>
              <strong>Supabase</strong>: hospeda o banco de dados e a autenticação da sua conta.
            </li>
            <li>
              <strong>SendGrid</strong>: envia e-mails de convite e recuperação de senha em seu nome.
            </li>
            <li>
              Um <strong>assessor financeiro</strong>, só se e quando você aceitar explicitamente um
              convite dele — acesso somente leitura, revogável a qualquer momento (ver Termos de Uso).
            </li>
          </ul>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">4. Seus direitos</h2>
          <p className="text-muted-foreground">
            Você pode acessar, corrigir e excluir seus dados a qualquer momento pela tela de Perfil. A
            exclusão de conta apaga permanentemente todos os seus dados financeiros. Ainda estamos
            construindo um recurso de exportação completa dos seus dados (portabilidade).
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">5. Retenção</h2>
          <p className="text-muted-foreground">
            Mantemos seus dados enquanto sua conta existir. Registros de consentimento (ex: aceite de
            convite de um assessor) são preservados mesmo depois de revogados, como prova de que o
            consentimento existiu — exigência legal, não usados pra nenhum outro fim.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">6. Segurança</h2>
          <p className="text-muted-foreground">
            Seus dados financeiros são isolados dos de qualquer outro usuário do Sifra por controle de
            acesso no próprio banco de dados (não só na aplicação). Senhas nunca são armazenadas em texto
            puro.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">7. Encarregado de Proteção de Dados (DPO)</h2>
          <p className="text-muted-foreground">
            Estamos formalizando o canal oficial de contato do Encarregado. Enquanto isso, qualquer
            dúvida ou pedido sobre seus dados pode ser feito diretamente a quem te convidou pro Sifra.
          </p>
        </section>

        <p className="text-xs text-muted-foreground">
          Veja também nossos{" "}
          <Link href="/termos" className="underline underline-offset-2">
            Termos de Uso
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
