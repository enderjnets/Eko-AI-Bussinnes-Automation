import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { WorkspaceProvider } from "@/contexts/WorkspaceContext";
import QueryProvider from "@/components/QueryProvider";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const plusJakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  variable: "--font-display",
});

export const metadata: Metadata = {
  title: "Eko AI — Automatización de Negocios con IA",
  description: "Agentes de IA 24/7 para cualquier negocio. Atiende clientes, agenda citas, responde emails y escala sin contratar más personal. Demo gratis.",
  keywords: ["automatización", "IA", "inteligencia artificial", "agente IA", "chatbot", "automatización negocios", "recepcionista virtual"],
  openGraph: {
    title: "Eko AI — Automatización de Negocios con IA",
    description: "Tu negocio funciona mientras duermes. Agente IA 24/7 para cualquier industria.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className={`${inter.variable} ${plusJakarta.variable}`}>
      <body className="bg-eko-graphite text-eko-white font-sans antialiased">
        <QueryProvider>
          <AuthProvider>
            <WorkspaceProvider>
              {children}
            </WorkspaceProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
