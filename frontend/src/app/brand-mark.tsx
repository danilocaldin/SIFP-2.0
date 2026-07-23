// Geometria replicada de src/app/icon.svg (viewBox 100x100) em JSX
// compatível com Satori (next/og) — usado pelas rotas de ícone PWA
// (icon-192, icon-512, apple-icon), que precisam de PNGs reais em
// tamanhos fixos, não de um único SVG servido em vários contextos.
export function BrandMark({ size }: { size: number }) {
  const bars = [
    { left: 18, height: 22 },
    { left: 36, height: 34 },
    { left: 54, height: 46 },
    { left: 72, height: 56 },
  ];
  const s = (n: number) => (n / 100) * size;

  return (
    <div
      style={{
        width: size,
        height: size,
        display: "flex",
        position: "relative",
        background: "#16211f",
        borderRadius: s(24),
      }}
    >
      {bars.map((bar) => (
        <div
          key={bar.left}
          style={{
            position: "absolute",
            left: s(bar.left),
            bottom: s(24),
            width: s(10),
            height: s(bar.height),
            borderRadius: s(5),
            background: "#7fdcca",
            display: "flex",
          }}
        />
      ))}
    </div>
  );
}
