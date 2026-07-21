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

      <div className="mt-8">
        <UploadFlow />
      </div>
    </main>
  );
}
