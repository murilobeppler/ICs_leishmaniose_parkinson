import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FOG-GNN — Predição de Freezing of Gait com GNN Espaço-Temporal | ic-research-lab",
  description:
    "Módulo B: Modelagem do corpo como grafo espaço-temporal sobre sensores inerciais corporais (IMU) com validação estrita Leave-One-Subject-Out (LOSO).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
