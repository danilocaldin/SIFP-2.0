"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";

const SAAS_MODE = process.env.NEXT_PUBLIC_SAAS_MODE === "true";

export default function PerfilPage() {
  if (!SAAS_MODE) {
    return (
      <main className="mx-auto flex min-h-[60vh] w-full max-w-lg flex-1 items-center justify-center px-6 text-center">
        <p className="text-sm text-muted-foreground">Essa página existe só no Sifra multiusuário.</p>
      </main>
    );
  }

  return <PerfilForm />;
}

function PerfilForm() {
  const [nome, setNome] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [salvo, setSalvo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setNome((data.user?.user_metadata?.full_name as string | undefined) ?? "");
      setCarregando(false);
    });
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSalvando(true);
    setErro(null);
    setSalvo(false);

    const supabase = createClient();
    const { error } = await supabase.auth.updateUser({ data: { full_name: nome.trim() } });

    setSalvando(false);
    if (error) {
      setErro("Não foi possível salvar. Tente novamente.");
      return;
    }
    setSalvo(true);
  }

  return (
    <main className="mx-auto w-full max-w-lg flex-1 px-6 py-12 sm:py-16">
      <p className="text-sm font-medium text-muted-foreground">Perfil</p>
      <h1 className="mt-1 text-xl font-semibold">Seus dados</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Usado para identificar seus relatórios — por exemplo, na capa do relatório em PDF.
      </p>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">Nome completo</CardTitle>
          <CardDescription>Como você quer ser identificado nos seus documentos.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="nome">Nome completo</Label>
              <Input
                id="nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                disabled={carregando}
                placeholder="Seu nome completo"
              />
            </div>
            {erro && <p className="text-sm text-destructive">{erro}</p>}
            <div className="flex items-center gap-3">
              <Button type="submit" disabled={carregando || salvando || !nome.trim()}>
                {salvando ? "Salvando…" : "Salvar"}
              </Button>
              {salvo && <span className="text-sm text-muted-foreground">Salvo.</span>}
            </div>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
