import { NetWorthChart } from "@/components/charts/net-worth-chart";
import { PatrimonioAssetsTable } from "@/components/patrimonio-assets-table";
import { PatrimonioUpload } from "@/components/patrimonio-upload";
import { Card, CardContent } from "@/components/ui/card";
import { getPatrimonio } from "@/lib/api-server";
import { formatBRL } from "@/lib/format";

export default async function PatrimonioPage() {
  const patrimonio = await getPatrimonio();

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Patrimônio</p>
      <h1 className="mt-1 text-xl font-semibold">Ativos</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Ainda não há dívidas/passivos cadastrados, então por enquanto o patrimônio líquido é a
        soma dos seus ativos.
      </p>

      <div className="mt-6">
        <PatrimonioUpload />
      </div>

      {!patrimonio.has_data ? (
        <p className="mt-8 text-sm text-muted-foreground">
          Nenhum ativo importado ainda. Envie um extrato de conta investimento em PDF acima.
        </p>
      ) : (
        <>
          <Card className="mt-8">
            <CardContent className="space-y-1">
              <p className="text-sm text-muted-foreground">Patrimônio total (Ativos)</p>
              <p className="text-2xl font-semibold tracking-tight">
                {formatBRL(patrimonio.patrimonio_total)}
              </p>
            </CardContent>
          </Card>

          <div className="mt-8">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Ativos atuais</h2>
            <PatrimonioAssetsTable assets={patrimonio.assets} />
          </div>

          <div className="mt-10">
            <h2 className="mb-3 text-sm font-medium text-muted-foreground">Evolução do patrimônio</h2>
            {patrimonio.net_worth_history.length >= 2 ? (
              <NetWorthChart data={patrimonio.net_worth_history} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Só há um snapshot importado até agora — envie extratos de meses diferentes pra ver
                a evolução ao longo do tempo.
              </p>
            )}
          </div>
        </>
      )}
    </main>
  );
}
