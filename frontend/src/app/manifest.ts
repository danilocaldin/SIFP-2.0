import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Sifra — Inteligência Financeira Pessoal",
    short_name: "Sifra",
    description: "Como você está financeiramente, agora.",
    start_url: "/",
    display: "standalone",
    background_color: "#f6f8f7",
    theme_color: "#16211f",
    icons: [
      { src: "/icons/icon-192", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512", sizes: "512x512", type: "image/png" },
      { src: "/icons/icon-512", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
