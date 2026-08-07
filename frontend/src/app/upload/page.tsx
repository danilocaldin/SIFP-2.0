import { UploadFlow } from "@/components/upload-flow";

export default function UploadPage() {
  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Upload</p>
      <h1 className="mt-1 text-xl font-semibold">Importar extrato do BTG Pactual</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Selecione o arquivo (CSV, XLS ou XLSX) exportado do internet banking do BTG. O sistema
        identifica automaticamente as colunas de data, descrição e valor, detecta transferências
        para você mesmo, e categoriza cada transação (regras + Machine Learning) ao confirmar.
      </p>

      <details className="mt-4 rounded-lg border border-border p-4 text-sm">
        <summary className="cursor-pointer font-medium text-foreground">
          ℹ️ Formatos suportados
        </summary>
        <div className="mt-3 space-y-3 text-muted-foreground">
          <p>
            <span className="font-medium text-foreground">CSV</span> — o parser identifica
            automaticamente as colunas de:
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <span className="font-medium text-foreground">Data</span> (<code>Data</code>,{" "}
              <code>Data Lançamento</code>, ...)
            </li>
            <li>
              <span className="font-medium text-foreground">Descrição</span> (<code>Descrição</code>,{" "}
              <code>Histórico</code>, <code>Lançamento</code>, ...)
            </li>
            <li>
              <span className="font-medium text-foreground">Valor</span> (<code>Valor</code>, formatos
              como <code>1.234,56</code> ou <code>-45,00</code>)
            </li>
          </ul>
          <p>
            <span className="font-medium text-foreground">XLS / XLSX</span> — o extrato de conta
            corrente baixado pelo internet banking do BTG (com bloco de Cliente/CPF/Agência/Conta
            no topo, que se repete a cada página). O parser localiza a tabela de lançamentos
            automaticamente, ignora linhas de &quot;Saldo Diário&quot;, detecta transferências para
            você mesmo (ex: para uma conta investimento) e aproveita a coluna{" "}
            <span className="font-medium text-foreground">Categoria</span> que o próprio BTG já
            preenche como uma pista extra para a categorização automática.
          </p>
          <p>
            Em ambos os formatos, datas no padrão brasileiro (<code>dd/mm/aaaa</code>) e valores com
            vírgula decimal são convertidos automaticamente. Despesas devem vir como valores
            negativos e receitas como positivos (padrão dos extratos bancários brasileiros).
          </p>
        </div>
      </details>

      <div className="mt-8">
        <UploadFlow />
      </div>
    </main>
  );
}
