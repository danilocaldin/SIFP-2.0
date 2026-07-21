export function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function formatPct(value: number, decimals = 0): string {
  return `${value.toFixed(decimals)}%`;
}

export function formatPctSigned(value: number, decimals = 0): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}
