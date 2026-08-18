import Link from "next/link";

export const metadata = {
  title: "Termos de Uso — Sifra",
};

export default function TermosPage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-12 sm:py-16">
      <Link href="/" className="mb-6 inline-flex items-center gap-2">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/icon.svg" alt="Sifra" width={28} height={28} className="rounded-[7px]" />
        <span className="font-display text-base font-semibold">Sifra</span>
      </Link>

      <div className="mb-6 rounded-md border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-300">
        <strong>Versão provisória, em revisão jurídica.</strong> Este texto descreve honestamente o que
        o Sifra faz hoje, mas ainda não foi validado por um advogado como texto legal final — pode mudar.
      </div>

      <h1 className="text-xl font-semibold">Termos de Uso</h1>
      <p className="mt-1 text-sm text-muted-foreground">Última atualização: agosto de 2026.</p>

      <div className="mt-6 flex flex-col gap-5 text-sm leading-relaxed text-foreground">
        <section>
          <h2 className="mb-1.5 font-medium">1. O que é o Sifra</h2>
          <p className="text-muted-foreground">
            O Sifra é uma plataforma de inteligência financeira pessoal: você importa seus extratos
            bancários e de investimentos, e o Sifra organiza, categoriza e apresenta diagnósticos sobre
            sua vida financeira — orçamento, metas, patrimônio, projeções e um assistente de chat com IA
            pra tirar dúvidas sobre seus próprios dados.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">2. Acesso por convite</h2>
          <p className="text-muted-foreground">
            O acesso ao Sifra é feito por convite — seu ou de um assessor financeiro que você autorizou.
            Você é responsável por manter sua senha em sigilo e por tudo que acontecer na sua conta.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">3. Assessores financeiros</h2>
          <p className="text-muted-foreground">
            Se você vincular um assessor financeiro à sua conta, ele passa a ver os mesmos dados
            financeiros que você vê (exceto seu histórico de conversas no chat e a tela de Perfil/segurança),
            em modo somente leitura — ele nunca pode alterar seus dados. Esse acesso só existe depois que
            você aceita explicitamente o convite, e você pode revogar a qualquer momento, na tela de Perfil.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">4. O que você pode esperar do Sifra</h2>
          <p className="text-muted-foreground">
            Fazemos o possível pra manter o serviço no ar e os dados corretos, mas o Sifra é uma
            ferramenta de organização e apoio à decisão — não somos consultores financeiros licenciados, e
            nada no app deve ser lido como recomendação de investimento. Diagnósticos e projeções são
            estimativas baseadas nos dados que você importou, não garantias.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">5. Exclusão de conta</h2>
          <p className="text-muted-foreground">
            Você pode excluir sua conta a qualquer momento, na tela de Perfil — isso apaga
            permanentemente todos os seus dados financeiros do Sifra. Essa ação não pode ser desfeita.
          </p>
        </section>

        <section>
          <h2 className="mb-1.5 font-medium">6. Alterações</h2>
          <p className="text-muted-foreground">
            Podemos atualizar estes Termos conforme o Sifra evolui. Mudanças relevantes serão comunicadas
            antes de entrarem em vigor.
          </p>
        </section>

        <p className="text-xs text-muted-foreground">
          Veja também nossa{" "}
          <Link href="/privacidade" className="underline underline-offset-2">
            Política de Privacidade
          </Link>
          .
        </p>
      </div>
    </main>
  );
}
