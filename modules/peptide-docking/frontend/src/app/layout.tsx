import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Peptide Docking — Triagem de Candidatos contra Leishmania | ic-research-lab",
  description:
    "Módulo A: Descoberta computacional de peptídeos contra alvo sem ortólogo humano com orquestração de docking, ranking e inspeção de poses.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
