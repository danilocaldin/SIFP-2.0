// Regra de senha compartilhada entre DefinirSenhaForm (recuperação) e
// CadastroWizard (primeiro acesso via convite) -- um só lugar pra não
// desalinhar as duas telas com o tempo.

export function validarForcaSenha(senha: string): string | null {
  if (senha.length < 8) return "A senha precisa ter pelo menos 8 caracteres.";
  if (!/[A-Z]/.test(senha)) return "A senha precisa ter pelo menos 1 letra maiúscula.";
  if (!/[a-z]/.test(senha)) return "A senha precisa ter pelo menos 1 letra minúscula.";
  if (!/[0-9]/.test(senha)) return "A senha precisa ter pelo menos 1 número.";
  return null;
}
