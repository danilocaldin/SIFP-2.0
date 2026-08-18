"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createClient } from "@/lib/supabase/client";
import { validarForcaSenha } from "@/lib/senha";
import { cpfValido } from "@/lib/cpf";
import { completarCadastro } from "@/lib/api";

// Cadastro completo pra quem acabou de aceitar um convite (recurso de
// assessor ou convite direto do Danilo pelo painel do Supabase) -- ver
// plano em C:\Users\User\.claude\plans\velvet-prancing-bengio.md. A
// sessão já existe nesse ponto (o convite/código já provou que a pessoa
// é dona do e-mail), então não tem uma etapa separada de "verificar
// e-mail" -- só falta completar o cadastro.

const UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG",
  "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

type Dados = {
  nome: string;
  telefone: string;
  senha: string;
  confirmacaoSenha: string;
  cpf: string;
  dataNascimento: string;
  pais: string;
  estado: string;
  cidade: string;
  termosAceitos: boolean;
  marketingConsent: boolean;
};

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

const ETAPAS = ["Dados pessoais", "Dados adicionais", "Termos", "Concluído"];

export function CadastroWizard({ email }: { email: string }) {
  const router = useRouter();
  const [etapa, setEtapa] = useState(1);
  const [dados, setDados] = useState<Dados>(DADOS_INICIAIS);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  function atualizar(campo: Partial<Dados>) {
    setDados((prev) => ({ ...prev, ...campo }));
  }

  async function concluirCadastro() {
    setErro(null);
    setCarregando(true);
    try {
      const supabase = createClient();
      const { error: erroSenha } = await supabase.auth.updateUser({
        password: dados.senha,
        data: { full_name: dados.nome.trim(), phone: dados.telefone },
      });
      if (erroSenha) {
        setErro(`Não foi possível salvar seus dados: ${erroSenha.message}.`);
        setCarregando(false);
        return;
      }
      await completarCadastro({
        cpf: dados.cpf,
        data_nascimento: dados.dataNascimento,
        pais: dados.pais,
        estado: dados.estado,
        cidade: dados.cidade,
        termos_aceitos: dados.termosAceitos,
        marketing_consent: dados.marketingConsent,
      });
      setEtapa(4);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro desconhecido.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {etapa <= 3 && (
        <div className="flex items-center gap-1.5">
          {ETAPAS.slice(0, 3).map((nomeEtapa, i) => (
            <div key={nomeEtapa} className="flex flex-1 flex-col items-center gap-1">
              <div
                className={`h-1.5 w-full rounded-full ${
                  i + 1 <= etapa ? "bg-primary" : "bg-border"
                }`}
              />
              <span className="text-center text-[10px] text-muted-foreground">{nomeEtapa}</span>
            </div>
          ))}
        </div>
      )}

      {erro && <p className="text-sm text-destructive">{erro}</p>}

      {etapa === 1 && (
        <EtapaDadosBasicos
          email={email}
          dados={dados}
          onAtualizar={atualizar}
          onErro={setErro}
          onAvancar={() => setEtapa(2)}
        />
      )}
      {etapa === 2 && (
        <EtapaDadosAdicionais
          dados={dados}
          onAtualizar={atualizar}
          onErro={setErro}
          onVoltar={() => setEtapa(1)}
          onAvancar={() => setEtapa(3)}
        />
      )}
      {etapa === 3 && (
        <EtapaTermos
          dados={dados}
          onAtualizar={atualizar}
          onVoltar={() => setEtapa(2)}
          onConcluir={concluirCadastro}
          carregando={carregando}
        />
      )}
      {etapa === 4 && (
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <p className="text-lg font-semibold">Cadastro concluído!</p>
          <p className="text-sm text-muted-foreground">Seu acesso foi criado com sucesso.</p>
          <Button
            type="button"
            className="mt-2 w-full"
            onClick={() => {
              router.push("/");
              router.refresh();
            }}
          >
            Entrar no aplicativo
          </Button>
        </div>
      )}
    </div>
  );
}

function EtapaDadosBasicos({
  email,
  dados,
  onAtualizar,
  onErro,
  onAvancar,
}: {
  email: string;
  dados: Dados;
  onAtualizar: (campo: Partial<Dados>) => void;
  onErro: (erro: string | null) => void;
  onAvancar: () => void;
}) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onErro(null);
    if (!dados.nome.trim()) return onErro("Digite seu nome completo.");
    if (!/^\d{2}9?\d{8}$/.test(dados.telefone.replace(/\D/g, ""))) {
      return onErro("Telefone inválido. Use o formato (DDD) 9XXXX-XXXX.");
    }
    const erroSenha = validarForcaSenha(dados.senha);
    if (erroSenha) return onErro(erroSenha);
    if (dados.senha !== dados.confirmacaoSenha) return onErro("As senhas não coincidem.");
    onAvancar();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-email">E-mail</Label>
        <Input id="cad-email" type="email" value={email} disabled />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-nome">Nome completo</Label>
        <Input
          id="cad-nome"
          required
          value={dados.nome}
          onChange={(e) => onAtualizar({ nome: e.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-telefone">Celular</Label>
        <Input
          id="cad-telefone"
          required
          placeholder="(11) 98888-7777"
          value={dados.telefone}
          onChange={(e) => onAtualizar({ telefone: e.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-senha">Senha</Label>
        <Input
          id="cad-senha"
          type="password"
          required
          autoComplete="new-password"
          value={dados.senha}
          onChange={(e) => onAtualizar({ senha: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Mínimo 8 caracteres, com maiúscula, minúscula e número.
        </p>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-confirmacao">Confirme a senha</Label>
        <Input
          id="cad-confirmacao"
          type="password"
          required
          autoComplete="new-password"
          value={dados.confirmacaoSenha}
          onChange={(e) => onAtualizar({ confirmacaoSenha: e.target.value })}
        />
      </div>
      <Button type="submit" className="mt-1">
        Continuar
      </Button>
    </form>
  );
}

function EtapaDadosAdicionais({
  dados,
  onAtualizar,
  onErro,
  onVoltar,
  onAvancar,
}: {
  dados: Dados;
  onAtualizar: (campo: Partial<Dados>) => void;
  onErro: (erro: string | null) => void;
  onVoltar: () => void;
  onAvancar: () => void;
}) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onErro(null);
    if (!cpfValido(dados.cpf)) return onErro("CPF inválido.");
    if (!dados.dataNascimento) return onErro("Informe sua data de nascimento.");
    if (!dados.estado) return onErro("Selecione seu estado.");
    if (!dados.cidade.trim()) return onErro("Informe sua cidade.");
    onAvancar();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-cpf">CPF</Label>
        <Input
          id="cad-cpf"
          required
          placeholder="000.000.000-00"
          value={dados.cpf}
          onChange={(e) => onAtualizar({ cpf: e.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-nascimento">Data de nascimento</Label>
        <Input
          id="cad-nascimento"
          type="date"
          required
          value={dados.dataNascimento}
          onChange={(e) => onAtualizar({ dataNascimento: e.target.value })}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-pais">País</Label>
        <Select value={dados.pais} onValueChange={(v) => v && onAtualizar({ pais: v })}>
          <SelectTrigger id="cad-pais" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="Brasil">Brasil</SelectItem>
            <SelectItem value="Outro">Outro</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-estado">Estado</Label>
        <Select value={dados.estado} onValueChange={(v) => v && onAtualizar({ estado: v })}>
          <SelectTrigger id="cad-estado" className="w-full">
            <SelectValue placeholder="Selecione" />
          </SelectTrigger>
          <SelectContent>
            {UFS.map((uf) => (
              <SelectItem key={uf} value={uf}>
                {uf}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="cad-cidade">Cidade</Label>
        <Input
          id="cad-cidade"
          required
          value={dados.cidade}
          onChange={(e) => onAtualizar({ cidade: e.target.value })}
        />
      </div>
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" onClick={onVoltar}>
          Voltar
        </Button>
        <Button type="submit" className="flex-1">
          Continuar
        </Button>
      </div>
    </form>
  );
}

function EtapaTermos({
  dados,
  onAtualizar,
  onVoltar,
  onConcluir,
  carregando,
}: {
  dados: Dados;
  onAtualizar: (campo: Partial<Dados>) => void;
  onVoltar: () => void;
  onConcluir: () => void;
  carregando: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Antes de continuar, precisamos da sua autorização.</p>
      <label className="flex items-start gap-2.5 text-sm">
        <input
          type="checkbox"
          required
          checked={dados.termosAceitos}
          onChange={(e) => onAtualizar({ termosAceitos: e.target.checked })}
          className="mt-0.5 size-4 flex-shrink-0"
        />
        <span>
          Li e aceito os{" "}
          <a href="/termos" target="_blank" rel="noopener" className="underline underline-offset-2">
            Termos de Uso
          </a>{" "}
          e a{" "}
          <a href="/privacidade" target="_blank" rel="noopener" className="underline underline-offset-2">
            Política de Privacidade
          </a>
          .
        </span>
      </label>
      <label className="flex items-start gap-2.5 text-sm">
        <input
          type="checkbox"
          checked={dados.marketingConsent}
          onChange={(e) => onAtualizar({ marketingConsent: e.target.checked })}
          className="mt-0.5 size-4 flex-shrink-0"
        />
        <span>Aceito receber comunicações, novidades e conteúdos do Sifra.</span>
      </label>
      <div className="flex items-center gap-3">
        <Button type="button" variant="outline" onClick={onVoltar} disabled={carregando}>
          Voltar
        </Button>
        <Button
          type="button"
          className="flex-1"
          disabled={!dados.termosAceitos || carregando}
          onClick={onConcluir}
        >
          {carregando ? "Concluindo…" : "Concluir cadastro"}
        </Button>
      </div>
    </div>
  );
}
