"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { completarCadastro, statusCadastro } from "@/lib/api";
import { EtapaDadosAdicionais, EtapaTermos, type Dados } from "@/components/cadastro-wizard";

// Card pra quem já tem conta de antes do wizard de cadastro existir (ex:
// convidada direto pelo painel do Supabase) e por isso nunca preencheu
// CPF/nascimento/endereço/termos -- essas contas não podem receber um
// novo convite (Supabase recusa com "email_exists"), então esse é o único
// jeito de coletar esses dados depois, já logada. Reaproveita as mesmas
// duas etapas do wizard original (cadastro-wizard.tsx), sem a etapa de
// senha/nome/telefone, que essas contas já têm.

const DADOS_INICIAIS: Dados = {
  nome: "",
  telefone: "",
  senha: "",
  confirmacaoSenha: "",
  cpf: "",
  dataNascimento: "",
  pais: "Brasil",
  estado: "",
  cidade: "",
  termosAceitos: false,
  marketingConsent: false,
};

export function CompletarCadastroCard() {
  const [precisa, setPrecisa] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [etapa, setEtapa] = useState<1 | 2>(1);
  const [dados, setDados] = useState<Dados>(DADOS_INICIAIS);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    statusCadastro()
      .then((r) => setPrecisa(!r.completo))
      .catch(() => setPrecisa(false))
      .finally(() => setCarregando(false));
  }, []);

  function atualizar(campo: Partial<Dados>) {
    setDados((prev) => ({ ...prev, ...campo }));
  }

  async function handleConcluir() {
    setErro(null);
    setEnviando(true);
    try {
      await completarCadastro({
        cpf: dados.cpf,
        data_nascimento: dados.dataNascimento,
        pais: dados.pais,
        estado: dados.estado,
        cidade: dados.cidade,
        termos_aceitos: dados.termosAceitos,
        marketing_consent: dados.marketingConsent,
      });
      setConcluido(true);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setEnviando(false);
    }
  }

  if (carregando || !precisa) return null;

  return (
    <Card className="mt-6 border-amber-500/30">
      <CardHeader>
        <CardTitle className="text-base">Complete seu cadastro</CardTitle>
        <CardDescription>
          Sua conta foi criada antes de pedirmos alguns dados a mais. Leva menos de um minuto.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {concluido ? (
          <p className="text-sm text-muted-foreground">Cadastro completo. Obrigado!</p>
        ) : (
          <>
            {erro && <p className="mb-3 text-sm text-destructive">{erro}</p>}
            {etapa === 1 && (
              <EtapaDadosAdicionais
                dados={dados}
                onAtualizar={atualizar}
                onErro={setErro}
                onAvancar={() => setEtapa(2)}
              />
            )}
            {etapa === 2 && (
              <EtapaTermos
                dados={dados}
                onAtualizar={atualizar}
                onVoltar={() => setEtapa(1)}
                onConcluir={handleConcluir}
                carregando={enviando}
              />
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
