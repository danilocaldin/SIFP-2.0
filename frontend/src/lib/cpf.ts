// Validação de CPF no navegador (feedback imediato) -- espelha o mesmo
// algoritmo (módulo 11) usado no backend, sifp/api/shared.py::validar_cpf.
// O backend continua sendo a fonte de verdade (nunca confia só no
// navegador), mas duplicar aqui evita uma viagem ao servidor só pra
// avisar "CPF inválido" enquanto a pessoa ainda está digitando.

function digitoVerificador(base: string, pesoInicial: number): number {
  let soma = 0;
  for (let i = 0; i < base.length; i++) {
    soma += parseInt(base[i], 10) * (pesoInicial - i);
  }
  const resto = soma % 11;
  return resto < 2 ? 0 : 11 - resto;
}

export function cpfValido(cpfBruto: string): boolean {
  const cpf = cpfBruto.replace(/\D/g, "");
  if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) return false;
  const d1 = digitoVerificador(cpf.slice(0, 9), 10);
  const d2 = digitoVerificador(cpf.slice(0, 9) + d1, 11);
  return cpf[9] === String(d1) && cpf[10] === String(d2);
}
